"""Tesseract OCR wrapper with word-level bounding box extraction."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytesseract
from PIL import Image
from pytesseract import Output


@dataclass
class OcrWord:
    """A single recognized word with position and confidence."""
    text: str
    x: int
    y: int
    width: int
    height: int
    confidence: float


@dataclass
class OcrPageResult:
    """OCR results for a single page."""
    words: list[OcrWord] = field(default_factory=list)
    page_width: int = 0
    page_height: int = 0
    full_text: str = ""

    @property
    def page_confidence(self) -> float:
        """Mean confidence across all words."""
        if not self.words:
            return 0.0
        return sum(w.confidence for w in self.words) / len(self.words)

    @property
    def word_count(self) -> int:
        return len(self.words)


def ocr_page(image: Image.Image, lang: str = "grc+lat+eng") -> OcrPageResult:
    """Run OCR on a single page image and return structured results.

    Args:
        image: PIL Image of the page.
        lang: Tesseract language string (e.g. 'grc+lat+eng').

    Returns:
        OcrPageResult with word-level bounding boxes and confidence.
    """
    data = pytesseract.image_to_data(image, lang=lang, output_type=Output.DICT)
    full_text = pytesseract.image_to_string(image, lang=lang)

    words = []
    n_items = len(data["text"])

    for i in range(n_items):
        text = data["text"][i].strip()
        conf = float(data["conf"][i])

        # Skip empty entries and low-confidence noise
        if not text or conf < 0:
            continue

        words.append(OcrWord(
            text=text,
            x=data["left"][i],
            y=data["top"][i],
            width=data["width"][i],
            height=data["height"][i],
            confidence=conf,
        ))

    return OcrPageResult(
        words=words,
        page_width=image.width,
        page_height=image.height,
        full_text=full_text,
    )


def ocr_page_text(image: Image.Image, lang: str = "grc+lat+eng") -> str:
    """Simple text-only OCR without bounding box data."""
    return pytesseract.image_to_string(image, lang=lang)
