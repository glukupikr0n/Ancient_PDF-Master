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


def retry_low_confidence_words(
    image: Image.Image,
    result: OcrPageResult,
    lang: str = "grc+lat+eng",
    min_confidence: float = 95.0,
    padding: int = 5,
) -> OcrPageResult:
    """Re-OCR words below min_confidence with alternative PSM modes.

    For each low-confidence word, crops the bounding box region from
    the original image and re-runs OCR with PSM 7 (single line) and
    PSM 8 (single word). Keeps the result with highest confidence.

    Args:
        image: Original page image.
        result: Initial OCR result.
        lang: Language string.
        min_confidence: Retry words below this threshold.
        padding: Extra pixels around the crop region.

    Returns:
        Updated OcrPageResult with improved word confidences.
    """
    retry_psm_modes = [7, 8, 13]  # single line, single word, raw line
    improved_words = []
    retried = 0
    improved_count = 0

    for word in result.words:
        if word.confidence >= min_confidence:
            improved_words.append(word)
            continue

        retried += 1
        best_word = word  # keep original as fallback

        # Crop the word region with padding
        x1 = max(0, word.x - padding)
        y1 = max(0, word.y - padding)
        x2 = min(image.width, word.x + word.width + padding)
        y2 = min(image.height, word.y + word.height + padding)

        if x2 <= x1 or y2 <= y1:
            improved_words.append(word)
            continue

        crop = image.crop((x1, y1, x2, y2))

        # Try each PSM mode
        for psm in retry_psm_modes:
            try:
                config = f"--psm {psm}"
                data = pytesseract.image_to_data(
                    crop, lang=lang, config=config, output_type=Output.DICT
                )

                for j in range(len(data["text"])):
                    text = data["text"][j].strip()
                    conf = float(data["conf"][j])

                    if text and conf > best_word.confidence:
                        best_word = OcrWord(
                            text=text,
                            x=word.x,
                            y=word.y,
                            width=word.width,
                            height=word.height,
                            confidence=conf,
                        )
            except Exception:
                continue

        if best_word.confidence > word.confidence:
            improved_count += 1

        improved_words.append(best_word)

    return OcrPageResult(
        words=improved_words,
        page_width=result.page_width,
        page_height=result.page_height,
        full_text=result.full_text,
    )


def ocr_page_text(image: Image.Image, lang: str = "grc+lat+eng") -> str:
    """Simple text-only OCR without bounding box data."""
    return pytesseract.image_to_string(image, lang=lang)
