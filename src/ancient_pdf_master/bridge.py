"""Python backend bridge for Electron.

Communicates via newline-delimited JSON over stdin/stdout.

Protocol:
  Request:  {"id": 1, "method": "start_ocr", "params": {...}}
  Response: {"id": 1, "result": {...}}  or  {"id": 1, "error": "..."}
  Event:    {"id": null, "event": "progress", "data": {...}}
"""

from __future__ import annotations

import json
import sys
import threading
import traceback


def send_response(request_id: int, result: dict):
    """Send a successful response."""
    msg = json.dumps({"id": request_id, "result": result})
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


def send_error(request_id: int, error: str):
    """Send an error response."""
    msg = json.dumps({"id": request_id, "error": error})
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


def send_event(event_name: str, data: dict):
    """Send a progress event (no request id)."""
    msg = json.dumps({"id": None, "event": event_name, "data": data})
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


# ── State ──

_cancel_flag = threading.Event()


# ── Handlers ──

def handle_check_tesseract(params: dict) -> dict:
    from .language import check_tesseract_available
    available, message = check_tesseract_available()
    return {"available": available, "message": message}


def handle_get_languages(params: dict) -> dict:
    from .language import SUPPORTED_LANGUAGES, get_installed_languages
    try:
        installed = get_installed_languages()
    except RuntimeError as e:
        return {"installed": [], "supported": SUPPORTED_LANGUAGES, "error": str(e)}

    return {
        "installed": installed,
        "supported": SUPPORTED_LANGUAGES,
    }


def _parse_page_range(range_str: str, total_pages: int) -> list[int]:
    """Parse a page range string like '1-5, 8, 10-12' into 0-based indices.

    Returns sorted, deduplicated list of valid 0-based page indices.
    """
    indices = set()
    for part in range_str.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            bounds = part.split("-", 1)
            try:
                start = int(bounds[0].strip())
                end = int(bounds[1].strip())
            except ValueError:
                continue
            for p in range(start, end + 1):
                if 1 <= p <= total_pages:
                    indices.add(p - 1)
        else:
            try:
                p = int(part)
                if 1 <= p <= total_pages:
                    indices.add(p - 1)
            except ValueError:
                continue
    return sorted(indices)


def handle_start_ocr(params: dict) -> dict:
    from .image_handler import load_images
    from .language import validate_languages
    from .ocr_engine import ocr_page, retry_low_confidence_words
    from .pdf_builder import build_searchable_pdf
    from .zone_ocr import ZONE_PRESETS, ZoneConfig, ZoneType, ocr_page_with_zones

    input_path = params["input"]
    output_path = params["output"]
    lang = params.get("lang", "grc+lat+eng")
    dpi = params.get("dpi", 300)
    min_confidence = params.get("min_confidence", 0)  # 0 = disabled
    page_range_str = params.get("page_range", "")

    # Validate language packs before starting
    validate_languages(lang)

    # Configure zone-based OCR
    zone_preset = params.get("zone_preset", "full_page")
    zone_params = params.get("zone_params", {})

    if zone_preset in ZONE_PRESETS:
        zones = ZONE_PRESETS[zone_preset](**zone_params)
    elif zone_preset == "custom" and params.get("zones"):
        zones = [
            ZoneConfig(
                zone_type=ZoneType(z.get("type", "body")),
                x_start=z.get("x_start", 0.0),
                y_start=z.get("y_start", 0.0),
                x_end=z.get("x_end", 1.0),
                y_end=z.get("y_end", 1.0),
                psm=z.get("psm", 3),
                lang=z.get("lang", ""),
            )
            for z in params["zones"]
        ]
    else:
        zones = None  # Use default single-pass OCR

    _cancel_flag.clear()

    # Load images
    send_event("progress", {"current": 0, "total": 0, "message": "Loading file..."})
    images = load_images(input_path, dpi=dpi)

    # Filter by page range if specified
    selected_indices = None
    if page_range_str:
        selected_indices = _parse_page_range(page_range_str, len(images))
        if not selected_indices:
            raise ValueError(f"No valid pages in range: {page_range_str}")
        images = [images[i] for i in selected_indices]
        send_event("progress", {
            "current": 0, "total": len(images),
            "message": f"Selected {len(images)} pages from range: {page_range_str}",
        })

    total = len(images)

    # Apply preprocessing if configured
    preprocess_cfg = params.get("preprocess")
    if preprocess_cfg:
        from .preprocess import PreprocessConfig, preprocess_image
        config = PreprocessConfig(
            deskew=preprocess_cfg.get("deskew", False),
            grayscale=preprocess_cfg.get("grayscale", False),
            bw=preprocess_cfg.get("bw", False),
            bw_threshold=preprocess_cfg.get("bw_threshold", 128),
            denoise=preprocess_cfg.get("denoise", False),
            autocontrast=preprocess_cfg.get("autocontrast", False),
        )
        send_event("progress", {"current": 0, "total": total, "message": "Preprocessing images..."})
        images = [preprocess_image(img, config) for img in images]

    if total == 0:
        raise ValueError("No pages found in the input file.")

    # OCR each page
    ocr_results = []
    for i, image in enumerate(images):
        if _cancel_flag.is_set():
            raise ValueError("Processing cancelled.")

        zone_label = f" ({zone_preset})" if zones else ""
        send_event("progress", {
            "current": i + 1,
            "total": total,
            "message": f"OCR page {i + 1}/{total}{zone_label}...",
        })

        if zones:
            result = ocr_page_with_zones(image, zones, lang=lang)
        else:
            result = ocr_page(image, lang=lang)
        ocr_results.append(result)

        send_event("progress", {
            "current": i + 1,
            "total": total,
            "message": f"OCR page {i + 1}/{total} complete",
            "page_result": {
                "page": i + 1,
                "words": result.word_count,
                "confidence": result.page_confidence,
            },
        })

    if _cancel_flag.is_set():
        raise ValueError("Processing cancelled.")

    # Confidence retry pass
    if min_confidence > 0:
        send_event("progress", {
            "current": 0,
            "total": total,
            "message": f"Retrying low-confidence words (< {min_confidence}%)...",
        })
        for i, (image, result) in enumerate(zip(images, ocr_results)):
            if _cancel_flag.is_set():
                raise ValueError("Processing cancelled.")

            old_conf = result.page_confidence
            improved = retry_low_confidence_words(
                image, result, lang=lang, min_confidence=min_confidence,
            )
            ocr_results[i] = improved
            new_conf = improved.page_confidence
            improved_count = sum(
                1 for old_w, new_w in zip(result.words, improved.words)
                if new_w.confidence > old_w.confidence
            )

            send_event("progress", {
                "current": i + 1,
                "total": total,
                "message": f"Retry page {i + 1}/{total}: {improved_count} words improved, "
                           f"confidence {old_conf:.1f}% → {new_conf:.1f}%",
            })

    # Parse optional page labels
    page_label_ranges = None
    if params.get("page_labels"):
        from .page_labels import PageLabelRange
        page_label_ranges = [
            PageLabelRange(
                start_page=r["start_page"],
                style=r.get("style", "arabic"),
                prefix=r.get("prefix", ""),
                start_number=r.get("start_number", 1),
            )
            for r in params["page_labels"]
        ]

    # Parse optional TOC entries
    toc_entries = None
    if params.get("toc"):
        from .toc_builder import TocEntry
        toc_entries = [
            TocEntry(
                title=e["title"],
                page=e["page"],
                level=e.get("level", 0),
            )
            for e in params["toc"]
        ]

    # Build searchable PDF
    send_event("progress", {
        "current": total,
        "total": total,
        "message": "Building searchable PDF...",
    })

    output = build_searchable_pdf(
        images, ocr_results, output_path, dpi=dpi,
        page_label_ranges=page_label_ranges,
        toc_entries=toc_entries,
    )

    return {"output_path": str(output), "pages": total}


def handle_cancel_ocr(params: dict) -> dict:
    _cancel_flag.set()
    return {"cancelled": True}


def handle_split_bilingual(params: dict) -> dict:
    from .image_handler import load_images
    from .language import validate_languages
    from .ocr_engine import ocr_page
    from .pdf_splitter import parse_page_ranges, split_bilingual_pdf

    input_path = params["input"]
    output_a = params["output_a"]
    output_b = params["output_b"]
    lang = params.get("lang", "grc+lat+eng")
    dpi = params.get("dpi", 300)

    validate_languages(lang)
    _cancel_flag.clear()

    # Load and OCR
    send_event("progress", {"current": 0, "total": 0, "message": "Loading file..."})
    images = load_images(input_path, dpi=dpi)
    total = len(images)

    ocr_results = []
    for i, image in enumerate(images):
        if _cancel_flag.is_set():
            raise ValueError("Processing cancelled.")
        send_event("progress", {
            "current": i + 1, "total": total,
            "message": f"OCR page {i + 1}/{total}...",
        })
        result = ocr_page(image, lang=lang)
        ocr_results.append(result)
        send_event("progress", {
            "current": i + 1, "total": total,
            "message": f"OCR page {i + 1}/{total} complete",
            "page_result": {
                "page": i + 1,
                "words": result.word_count,
                "confidence": result.page_confidence,
            },
        })

    # Parse page assignments
    lang_a_pages = parse_page_ranges(params.get("lang_a_pages", "odd"), total)
    lang_b_pages = parse_page_ranges(params.get("lang_b_pages", "even"), total)
    common_pages = parse_page_ranges(params.get("common_pages", ""), total)

    send_event("progress", {
        "current": total, "total": total,
        "message": "Splitting into bilingual PDFs...",
    })

    def on_split_progress(step, total_steps, msg):
        send_event("progress", {
            "current": step, "total": total_steps, "message": msg,
        })

    path_a, path_b = split_bilingual_pdf(
        images, ocr_results,
        lang_a_pages, lang_b_pages, common_pages,
        output_a, output_b, dpi=dpi,
        progress_callback=on_split_progress,
    )

    return {
        "output_a": str(path_a),
        "output_b": str(path_b),
        "pages_a": len(set(lang_a_pages) | set(common_pages)),
        "pages_b": len(set(lang_b_pages) | set(common_pages)),
    }

def handle_load_preview(params: dict) -> dict:
    """Load file and return page thumbnails as base64."""
    import base64
    import io

    from .image_handler import load_images

    input_path = params["input"]
    dpi = params.get("dpi", 72)  # low DPI for thumbnails
    max_width = params.get("max_width", 600)

    images = load_images(input_path, dpi=dpi)
    pages = []

    for i, img in enumerate(images):
        # Resize for preview
        ratio = max_width / img.width
        if ratio < 1:
            new_h = int(img.height * ratio)
            thumb = img.resize((max_width, new_h))
        else:
            thumb = img

        buf = io.BytesIO()
        thumb.save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        pages.append({
            "index": i,
            "width": thumb.width,
            "height": thumb.height,
            "data": f"data:image/png;base64,{b64}",
        })

    return {"pages": pages, "total": len(pages)}


def handle_preview_preprocess(params: dict) -> dict:
    """Apply preprocessing to a single page and return the result."""
    import base64
    import io

    from .image_handler import load_images
    from .preprocess import PreprocessConfig, preprocess_image

    input_path = params["input"]
    page_index = params.get("page", 0)
    dpi = params.get("dpi", 150)
    max_width = params.get("max_width", 600)

    images = load_images(input_path, dpi=dpi)
    if page_index >= len(images):
        raise ValueError(f"Page {page_index} out of range (total {len(images)})")

    img = images[page_index]

    # Apply preprocessing
    config = PreprocessConfig(
        deskew=params.get("deskew", False),
        grayscale=params.get("grayscale", False),
        bw=params.get("bw", False),
        bw_threshold=params.get("bw_threshold", 128),
        denoise=params.get("denoise", False),
        autocontrast=params.get("autocontrast", False),
    )
    img = preprocess_image(img, config)

    # Convert 1-bit images back for PNG encoding
    if img.mode == "1":
        img = img.convert("L")

    # Resize for preview
    ratio = max_width / img.width
    if ratio < 1:
        new_h = int(img.height * ratio)
        img = img.resize((max_width, new_h))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    return {
        "page": page_index,
        "width": img.width,
        "height": img.height,
        "data": f"data:image/png;base64,{b64}",
    }


# ── Dispatcher ──

HANDLERS = {
    "check_tesseract": handle_check_tesseract,
    "get_languages": handle_get_languages,
    "start_ocr": handle_start_ocr,
    "cancel_ocr": handle_cancel_ocr,
    "split_bilingual": handle_split_bilingual,
    "load_preview": handle_load_preview,
    "preview_preprocess": handle_preview_preprocess,
}


def dispatch(request: dict):
    """Dispatch a request to the appropriate handler."""
    request_id = request.get("id")
    method = request.get("method", "")
    params = request.get("params", {})

    handler = HANDLERS.get(method)
    if not handler:
        send_error(request_id, f"Unknown method: {method}")
        return

    try:
        result = handler(params)
        send_response(request_id, result)
    except Exception as e:
        send_error(request_id, str(e))


def main():
    """Main loop: read JSON requests from stdin, dispatch, respond on stdout."""
    # Check required packages before accepting requests
    missing = []
    for pkg, import_name in [
        ("pytesseract", "pytesseract"),
        ("Pillow", "PIL"),
        ("pdf2image", "pdf2image"),
        ("pikepdf", "pikepdf"),
        ("reportlab", "reportlab"),
    ]:
        try:
            __import__(import_name)
        except ImportError:
            missing.append(pkg)

    if missing:
        msg = json.dumps({
            "ready": False,
            "error": f"Missing Python packages: {', '.join(missing)}. "
                     f"Run: pip install {' '.join(missing)}",
        })
        sys.stdout.write(msg + "\n")
        sys.stdout.flush()
        sys.exit(1)

    # Signal ready
    sys.stdout.write(json.dumps({"ready": True}) + "\n")
    sys.stdout.flush()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        # Handle long-running OCR in a thread so cancel can work
        if request.get("method") == "start_ocr":
            thread = threading.Thread(target=dispatch, args=(request,))
            thread.start()
        else:
            dispatch(request)


if __name__ == "__main__":
    main()
