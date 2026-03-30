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
