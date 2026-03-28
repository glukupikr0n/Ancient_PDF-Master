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


def handle_start_ocr(params: dict) -> dict:
    from .image_handler import load_images
    from .language import validate_languages
    from .ocr_engine import ocr_page
    from .pdf_builder import build_searchable_pdf

    input_path = params["input"]
    output_path = params["output"]
    lang = params.get("lang", "grc+lat+eng")
    dpi = params.get("dpi", 300)

    # Validate language packs before starting
    validate_languages(lang)

    _cancel_flag.clear()

    # Load images
    send_event("progress", {"current": 0, "total": 0, "message": "Loading file..."})
    images = load_images(input_path, dpi=dpi)
    total = len(images)

    if total == 0:
        raise ValueError("No pages found in the input file.")

    # OCR each page
    ocr_results = []
    for i, image in enumerate(images):
        if _cancel_flag.is_set():
            raise ValueError("Processing cancelled.")

        send_event("progress", {
            "current": i + 1,
            "total": total,
            "message": f"OCR page {i + 1}/{total}...",
        })

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


# ── Dispatcher ──

HANDLERS = {
    "check_tesseract": handle_check_tesseract,
    "get_languages": handle_get_languages,
    "start_ocr": handle_start_ocr,
    "cancel_ocr": handle_cancel_ocr,
    "split_bilingual": handle_split_bilingual,
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
