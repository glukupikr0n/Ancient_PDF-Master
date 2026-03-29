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
    from .ocr_engine import detect_columns, ocr_page, ocr_page_two_column, retry_low_confidence_words
    from .pdf_builder import build_searchable_pdf
    from .zone_ocr import ZONE_PRESETS, ZoneConfig, ZoneType, ocr_page_with_zones

    input_path = params["input"]
    output_path = params["output"]
    lang = params.get("lang", "grc+lat+eng")
    dpi = params.get("dpi", 300)
    min_confidence = params.get("min_confidence", 0)  # 0 = disabled
    page_range_str = params.get("page_range", "")
    auto_deskew = params.get("auto_deskew", False)

    # Validate language packs before starting
    validate_languages(lang)

    # Configure zone-based OCR
    zone_preset = params.get("zone_preset", "full_page")
    zone_params = params.get("zone_params", {})
    auto_column = (zone_preset == "auto_column")

    if auto_column:
        zones = None  # handled per-page below
    elif zone_preset in ZONE_PRESETS:
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

    # Crop pages if configured
    crop_config = params.get("crop")
    if crop_config:
        send_event("progress", {"current": 0, "total": total, "message": "Cropping pages..."})
        for i in range(len(images)):
            # crop_config keys are string page indices from JS
            page_key = str(i)
            if selected_indices is not None:
                # Map back to original page index
                page_key = str(selected_indices[i]) if i < len(selected_indices) else str(i)
            crop = crop_config.get(page_key) or crop_config.get(str(i))
            if crop:
                img = images[i]
                x1 = int(crop["x_start"] * img.width)
                y1 = int(crop["y_start"] * img.height)
                x2 = int(crop["x_end"] * img.width)
                y2 = int(crop["y_end"] * img.height)
                images[i] = img.crop((x1, y1, x2, y2))
        send_event("progress", {"current": total, "total": total, "message": "Crop done"})

    # Auto deskew (independent of preprocessing toggle)
    if auto_deskew:
        from .preprocess import _deskew
        send_event("progress", {"current": 0, "total": total, "message": "Auto-deskewing pages..."})
        for i in range(len(images)):
            images[i] = _deskew(images[i])
            send_event("progress", {
                "current": i + 1, "total": total,
                "message": f"Deskewed page {i + 1}/{total}",
            })

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

    # OCR each page (parallel when possible)
    import concurrent.futures
    import os

    max_workers = min(os.cpu_count() or 2, total, 4)

    def _ocr_one(i_image):
        idx, img = i_image
        if _cancel_flag.is_set():
            return idx, None
        if auto_column:
            ncols = detect_columns(img)
            if ncols == 2:
                return idx, ocr_page_two_column(img, lang=lang)
            return idx, ocr_page(img, lang=lang)
        if zones:
            return idx, ocr_page_with_zones(img, zones, lang=lang)
        return idx, ocr_page(img, lang=lang)

    ocr_results = [None] * total

    if total >= 2 and max_workers >= 2:
        # Parallel OCR
        send_event("progress", {
            "current": 0, "total": total,
            "message": f"OCR {total} pages ({max_workers} threads)...",
        })
        done_count = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_ocr_one, (i, img)): i for i, img in enumerate(images)}
            for future in concurrent.futures.as_completed(futures):
                idx, result = future.result()
                if result is None:
                    raise ValueError("Processing cancelled.")
                ocr_results[idx] = result
                done_count += 1
                send_event("progress", {
                    "current": done_count,
                    "total": total,
                    "message": f"OCR page {idx + 1}/{total} complete",
                    "page_result": {
                        "page": idx + 1,
                        "words": result.word_count,
                        "confidence": result.page_confidence,
                    },
                })
    else:
        # Sequential OCR (single page)
        for i, image in enumerate(images):
            if _cancel_flag.is_set():
                raise ValueError("Processing cancelled.")
            zone_label = f" ({zone_preset})" if zones else ""
            send_event("progress", {
                "current": i + 1, "total": total,
                "message": f"OCR page {i + 1}/{total}{zone_label}...",
            })
            _, result = _ocr_one((i, image))
            if result is None:
                raise ValueError("Processing cancelled.")
            ocr_results[i] = result
            send_event("progress", {
                "current": i + 1, "total": total,
                "message": f"OCR page {i + 1}/{total} complete",
                "page_result": {
                    "page": i + 1,
                    "words": result.word_count,
                    "confidence": result.page_confidence,
                },
            })

    if _cancel_flag.is_set():
        raise ValueError("Processing cancelled.")

    # Confidence retry pass (smart: skips pages already above threshold)
    if min_confidence > 0:
        pages_needing_retry = [
            i for i, r in enumerate(ocr_results)
            if r.page_confidence < min_confidence
        ]
        if pages_needing_retry:
            send_event("progress", {
                "current": 0,
                "total": len(pages_needing_retry),
                "message": f"Retrying {len(pages_needing_retry)}/{total} pages "
                           f"(< {min_confidence}% confidence)...",
            })
            for done, i in enumerate(pages_needing_retry):
                if _cancel_flag.is_set():
                    raise ValueError("Processing cancelled.")

                result = ocr_results[i]
                old_conf = result.page_confidence
                improved = retry_low_confidence_words(
                    images[i], result, lang=lang, min_confidence=min_confidence,
                )
                ocr_results[i] = improved
                new_conf = improved.page_confidence
                improved_count = sum(
                    1 for old_w, new_w in zip(result.words, improved.words)
                    if new_w.confidence > old_w.confidence
                )

                send_event("progress", {
                    "current": done + 1,
                    "total": len(pages_needing_retry),
                    "message": f"Retry page {i + 1}: {improved_count} words improved, "
                               f"{old_conf:.1f}% → {new_conf:.1f}%",
                })
        else:
            send_event("progress", {
                "current": total, "total": total,
                "message": f"All pages above {min_confidence}% — skipping retry",
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


def handle_detect_toc(params: dict) -> dict:
    """Detect TOC entries from OCR results by analyzing text patterns.

    Looks for:
    1. Lines matching "Title ... PageNum" pattern (dots/spaces + number)
    2. Large/prominent text blocks at page starts (headings)
    3. Roman/Arabic numeral section headers (I., II., 1., 2., Chapter X, etc.)
    """
    import re

    import pytesseract
    from pytesseract import Output

    from .image_handler import load_images

    input_path = params["input"]
    dpi = params.get("dpi", 200)
    lang = params.get("lang", "grc+lat+eng")
    max_pages = params.get("max_pages", 0)  # 0 = scan all pages

    images = load_images(input_path, dpi=dpi)
    total = len(images)
    if max_pages > 0:
        total = min(total, max_pages)

    toc_entries = []

    # Pattern: "Title text ... 123" or "Title text    123"
    toc_line_re = re.compile(
        r'^(.+?)[\s.…·\-_]{3,}(\d{1,4})\s*$'
    )
    # Heading patterns: "Chapter 1", "BOOK II", "I.", "§1", etc.
    heading_re = re.compile(
        r'^(?:'
        r'(?:CHAPTER|Chapter|BOOK|Book|PART|Part|SECTION|Section|LIBER|Liber)\s+[\dIVXLCDMivxlcdm]+\.?'
        r'|[IVXLCDM]+\.\s'
        r'|\d+\.\s+[A-Z\u0370-\u03FF]'
        r'|§\s*\d+'
        r')',
    )

    for page_idx in range(total):
        img = images[page_idx]
        text = pytesseract.image_to_string(img, lang=lang)

        lines = text.strip().split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check TOC-style line: "Title ... page_number"
            m = toc_line_re.match(line)
            if m:
                title = m.group(1).strip()
                page_num = int(m.group(2))
                if title and len(title) > 1 and page_num > 0:
                    toc_entries.append({
                        "title": title,
                        "page": page_num,
                        "level": 0,
                        "source": "toc_page",
                        "found_on_page": page_idx + 1,
                    })
                continue

            # Check heading pattern (only first few lines of each page)
            line_idx = lines.index(line) if line in lines else 999
            if line_idx < 5 and heading_re.match(line):
                toc_entries.append({
                    "title": line.strip(),
                    "page": page_idx + 1,
                    "level": 0,
                    "source": "heading",
                    "found_on_page": page_idx + 1,
                })

    # Deduplicate by title
    seen = set()
    unique = []
    for e in toc_entries:
        key = (e["title"], e["page"])
        if key not in seen:
            seen.add(key)
            unique.append(e)

    # Sort by page number
    unique.sort(key=lambda e: e["page"])

    return {"entries": unique, "total": len(unique)}


def handle_detect_regions(params: dict) -> dict:
    """Detect text regions on a page using Tesseract block-level analysis."""
    import pytesseract
    from pytesseract import Output

    from .image_handler import load_images

    input_path = params["input"]
    page_index = params.get("page", 0)
    dpi = params.get("dpi", 150)
    lang = params.get("lang", "grc+lat+eng")
    min_area_pct = params.get("min_area_pct", 0.5)  # minimum block area as % of page

    images = load_images(input_path, dpi=dpi)
    if page_index >= len(images):
        raise ValueError(f"Page {page_index} out of range (total {len(images)})")

    img = images[page_index]
    w, h = img.size

    # Run Tesseract to get block-level bounding boxes
    data = pytesseract.image_to_data(img, lang=lang, output_type=Output.DICT)

    # Group by block_num to get block-level regions
    blocks: dict[int, dict] = {}
    for i in range(len(data["text"])):
        block_num = data["block_num"][i]
        if block_num == 0:
            continue

        text = data["text"][i].strip()
        conf = float(data["conf"][i])

        # Only count entries with actual text
        if not text or conf < 0:
            continue

        if block_num not in blocks:
            blocks[block_num] = {
                "x1": data["left"][i],
                "y1": data["top"][i],
                "x2": data["left"][i] + data["width"][i],
                "y2": data["top"][i] + data["height"][i],
                "word_count": 0,
                "total_conf": 0.0,
            }

        b = blocks[block_num]
        b["x1"] = min(b["x1"], data["left"][i])
        b["y1"] = min(b["y1"], data["top"][i])
        b["x2"] = max(b["x2"], data["left"][i] + data["width"][i])
        b["y2"] = max(b["y2"], data["top"][i] + data["height"][i])
        b["word_count"] += 1
        b["total_conf"] += conf

    # Convert to proportional coordinates and filter small noise blocks
    min_area_px = (w * h) * (min_area_pct / 100.0)
    regions = []
    for block_num, b in sorted(blocks.items()):
        bw = b["x2"] - b["x1"]
        bh = b["y2"] - b["y1"]
        if bw * bh < min_area_px:
            continue
        if b["word_count"] < 2:
            continue

        # Add padding (2% of page)
        pad_x = int(w * 0.02)
        pad_y = int(h * 0.02)
        x1 = max(0, b["x1"] - pad_x)
        y1 = max(0, b["y1"] - pad_y)
        x2 = min(w, b["x2"] + pad_x)
        y2 = min(h, b["y2"] + pad_y)

        avg_conf = b["total_conf"] / b["word_count"] if b["word_count"] > 0 else 0

        regions.append({
            "x_start": round(x1 / w, 4),
            "y_start": round(y1 / h, 4),
            "x_end": round(x2 / w, 4),
            "y_end": round(y2 / h, 4),
            "word_count": b["word_count"],
            "confidence": round(avg_conf, 1),
        })

    # Merge overlapping regions
    regions = _merge_overlapping_regions(regions)

    return {"page": page_index, "regions": regions, "total": len(regions)}


def _merge_overlapping_regions(regions: list[dict]) -> list[dict]:
    """Merge regions that overlap significantly."""
    if len(regions) <= 1:
        return regions

    merged = True
    while merged:
        merged = False
        new_regions = []
        used = set()
        for i in range(len(regions)):
            if i in used:
                continue
            r = dict(regions[i])
            for j in range(i + 1, len(regions)):
                if j in used:
                    continue
                s = regions[j]
                # Check overlap
                ox1 = max(r["x_start"], s["x_start"])
                oy1 = max(r["y_start"], s["y_start"])
                ox2 = min(r["x_end"], s["x_end"])
                oy2 = min(r["y_end"], s["y_end"])
                if ox1 < ox2 and oy1 < oy2:
                    # Merge
                    r["x_start"] = min(r["x_start"], s["x_start"])
                    r["y_start"] = min(r["y_start"], s["y_start"])
                    r["x_end"] = max(r["x_end"], s["x_end"])
                    r["y_end"] = max(r["y_end"], s["y_end"])
                    r["word_count"] = r["word_count"] + s["word_count"]
                    r["confidence"] = round(
                        (r["confidence"] + s["confidence"]) / 2, 1
                    )
                    used.add(j)
                    merged = True
            new_regions.append(r)
        regions = new_regions

    return regions


# ── Dispatcher ──

HANDLERS = {
    "check_tesseract": handle_check_tesseract,
    "get_languages": handle_get_languages,
    "start_ocr": handle_start_ocr,
    "cancel_ocr": handle_cancel_ocr,
    "split_bilingual": handle_split_bilingual,
    "load_preview": handle_load_preview,
    "preview_preprocess": handle_preview_preprocess,
    "detect_regions": handle_detect_regions,
    "detect_toc": handle_detect_toc,
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
