"""Zone-based OCR for margin annotations (verse numbers, line numbers, scholia).

Classical texts often have marginal annotations that Tesseract's default
page segmentation misses or merges with body text. This module splits a page
into configurable zones (left margin, body, right margin, top/bottom) and
OCRs each zone independently with appropriate PSM modes.

Tesseract Page Segmentation Modes (PSM) reference:
  3  = Fully automatic (default)
  4  = Single column of variable-size text
  6  = Single uniform block of text
  7  = Single text line
  11 = Sparse text — find as much text as possible, no particular order
  13 = Raw line — treat as single text line, no OSD
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

import pytesseract
from PIL import Image
from pytesseract import Output

from .ocr_engine import OcrPageResult, OcrWord


class ZoneType(Enum):
    LEFT_MARGIN = "left_margin"
    RIGHT_MARGIN = "right_margin"
    TOP_MARGIN = "top_margin"
    BOTTOM_MARGIN = "bottom_margin"
    BODY = "body"


@dataclass
class ZoneConfig:
    """Configuration for a single OCR zone.

    Coordinates are proportional (0.0 to 1.0) relative to page dimensions.
    This allows the same config to work across different page sizes/DPIs.
    """
    zone_type: ZoneType
    x_start: float  # 0.0 = left edge
    y_start: float  # 0.0 = top edge
    x_end: float    # 1.0 = right edge
    y_end: float    # 1.0 = bottom edge
    psm: int = 3    # Tesseract page segmentation mode
    lang: str = ""  # Override language for this zone (empty = use default)


# ── Presets ──

def preset_classical_left_margin(
    margin_width: float = 0.12,
    body_margin_top: float = 0.08,
    body_margin_bottom: float = 0.08,
) -> list[ZoneConfig]:
    """Preset for classical texts with verse/section numbers in the left margin.

    Common in Loeb Classical Library, Oxford Classical Texts, Teubner editions.
    """
    t = body_margin_top
    b = body_margin_bottom
    return [
        ZoneConfig(
            zone_type=ZoneType.LEFT_MARGIN,
            x_start=0.0,
            y_start=t,
            x_end=margin_width,
            y_end=1.0 - b,
            psm=11,  # Sparse text — best for scattered margin numbers
        ),
        ZoneConfig(
            zone_type=ZoneType.BODY,
            x_start=margin_width,
            y_start=t,
            x_end=1.0,
            y_end=1.0 - b,
            psm=3,  # Fully automatic for body
        ),
    ]


def preset_classical_both_margins(
    left_margin: float = 0.10,
    right_margin: float = 0.10,
    top_margin: float = 0.08,
    bottom_margin: float = 0.08,
    body_margin_top: float | None = None,
    body_margin_bottom: float | None = None,
) -> list[ZoneConfig]:
    """Preset for texts with annotations in both margins.

    Common in critical editions with line numbers on left and
    apparatus references on right.
    """
    # Allow frontend overrides for top/bottom margins
    t = body_margin_top if body_margin_top is not None else top_margin
    b = body_margin_bottom if body_margin_bottom is not None else bottom_margin
    return [
        ZoneConfig(
            zone_type=ZoneType.LEFT_MARGIN,
            x_start=0.0,
            y_start=t,
            x_end=left_margin,
            y_end=1.0 - b,
            psm=11,
        ),
        ZoneConfig(
            zone_type=ZoneType.BODY,
            x_start=left_margin,
            y_start=t,
            x_end=1.0 - right_margin,
            y_end=1.0 - b,
            psm=3,
        ),
        ZoneConfig(
            zone_type=ZoneType.RIGHT_MARGIN,
            x_start=1.0 - right_margin,
            y_start=t,
            x_end=1.0,
            y_end=1.0 - b,
            psm=11,
        ),
    ]


def preset_full_page() -> list[ZoneConfig]:
    """Default: treat the entire page as one zone (current behavior)."""
    return [
        ZoneConfig(
            zone_type=ZoneType.BODY,
            x_start=0.0,
            y_start=0.0,
            x_end=1.0,
            y_end=1.0,
            psm=3,
        ),
    ]


ZONE_PRESETS = {
    "full_page": preset_full_page,
    "left_margin": preset_classical_left_margin,
    "both_margins": preset_classical_both_margins,
}


# ── Zone OCR Engine ──

def _crop_zone(image: Image.Image, zone: ZoneConfig) -> Image.Image:
    """Crop an image region based on proportional zone coordinates."""
    w, h = image.size
    left = int(zone.x_start * w)
    top = int(zone.y_start * h)
    right = int(zone.x_end * w)
    bottom = int(zone.y_end * h)

    # Ensure minimum size
    right = max(right, left + 10)
    bottom = max(bottom, top + 10)

    return image.crop((left, top, right, bottom))


def ocr_zone(
    image: Image.Image,
    zone: ZoneConfig,
    lang: str = "grc+lat+eng",
) -> list[OcrWord]:
    """OCR a single zone and return words with coordinates adjusted to full page."""
    zone_lang = zone.lang or lang
    zone_img = _crop_zone(image, zone)

    config = f"--psm {zone.psm}"
    data = pytesseract.image_to_data(
        zone_img, lang=zone_lang, config=config, output_type=Output.DICT,
    )

    # Zone pixel offset within full page
    w, h = image.size
    x_offset = int(zone.x_start * w)
    y_offset = int(zone.y_start * h)

    words = []
    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        conf = float(data["conf"][i])

        if not text or conf < 0:
            continue

        words.append(OcrWord(
            text=text,
            x=data["left"][i] + x_offset,
            y=data["top"][i] + y_offset,
            width=data["width"][i],
            height=data["height"][i],
            confidence=conf,
        ))

    return words


def ocr_page_with_zones(
    image: Image.Image,
    zones: list[ZoneConfig],
    lang: str = "grc+lat+eng",
) -> OcrPageResult:
    """OCR a page using multiple zones and merge results.

    Each zone is OCR'd independently with its own PSM mode, then all
    words are combined into a single OcrPageResult with coordinates
    relative to the full page.
    """
    all_words: list[OcrWord] = []

    for zone in zones:
        zone_words = ocr_zone(image, zone, lang)
        all_words.extend(zone_words)

    # Build full text by sorting words top-to-bottom, left-to-right
    sorted_words = sorted(all_words, key=lambda w: (w.y, w.x))
    full_text = " ".join(w.text for w in sorted_words)

    return OcrPageResult(
        words=all_words,
        page_width=image.width,
        page_height=image.height,
        full_text=full_text,
    )
