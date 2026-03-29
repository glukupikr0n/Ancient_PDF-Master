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
class OcrLine:
    """A line of text with its bounding box and constituent words."""
    words: list[OcrWord] = field(default_factory=list)
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    def compute_bounds(self):
        """Recompute line bounds from words."""
        if not self.words:
            return
        self.x = min(w.x for w in self.words)
        self.y = min(w.y for w in self.words)
        x2 = max(w.x + w.width for w in self.words)
        y2 = max(w.y + w.height for w in self.words)
        self.width = x2 - self.x
        self.height = y2 - self.y


@dataclass
class OcrPageResult:
    """OCR results for a single page."""
    words: list[OcrWord] = field(default_factory=list)
    lines: list[OcrLine] = field(default_factory=list)
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


def ocr_page(image: Image.Image, lang: str = "grc+lat+eng", psm: int = 3) -> OcrPageResult:
    """Run OCR on a single page image and return structured results.

    Args:
        image: PIL Image of the page.
        lang: Tesseract language string (e.g. 'grc+lat+eng').
        psm: Tesseract page segmentation mode.

    Returns:
        OcrPageResult with word-level bounding boxes, lines, and confidence.
    """
    config = f"--psm {psm}"
    data = pytesseract.image_to_data(image, lang=lang, config=config, output_type=Output.DICT)
    full_text = pytesseract.image_to_string(image, lang=lang, config=config)

    words = []
    # Group words into lines using Tesseract's block/par/line hierarchy
    line_groups: dict[tuple[int, int, int], list[OcrWord]] = {}
    n_items = len(data["text"])

    for i in range(n_items):
        text = data["text"][i].strip()
        conf = float(data["conf"][i])

        if not text or conf < 0:
            continue

        word = OcrWord(
            text=text,
            x=data["left"][i],
            y=data["top"][i],
            width=data["width"][i],
            height=data["height"][i],
            confidence=conf,
        )
        words.append(word)

        # Group by (block_num, par_num, line_num)
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        line_groups.setdefault(key, []).append(word)

    # Build line objects sorted by reading order (top-to-bottom, left-to-right)
    lines = []
    for key in sorted(line_groups.keys()):
        line_words = sorted(line_groups[key], key=lambda w: w.x)
        line = OcrLine(words=line_words)
        line.compute_bounds()
        lines.append(line)

    return OcrPageResult(
        words=words,
        lines=lines,
        page_width=image.width,
        page_height=image.height,
        full_text=full_text,
    )


def _is_plausible_word(text: str) -> bool:
    """Check if a word looks like valid text (not OCR garbage).

    Words that are mostly alphanumeric/punctuation with consistent
    character patterns are likely valid even at lower confidence.
    """
    import re
    if not text or len(text) < 1:
        return False
    # Allow Greek, Latin, common punctuation, digits
    # If >60% are "real" characters, consider it plausible
    clean = re.sub(r'[\s]', '', text)
    if not clean:
        return False
    alpha_count = sum(1 for c in clean if c.isalpha() or c.isdigit() or c in '.,;:!?\'"-()[]')
    return (alpha_count / len(clean)) >= 0.6


def retry_low_confidence_words(
    image: Image.Image,
    result: OcrPageResult,
    lang: str = "grc+lat+eng",
    min_confidence: float = 95.0,
    padding: int = 5,
    max_retries_per_page: int = 30,
) -> OcrPageResult:
    """Re-OCR words below min_confidence with alternative PSM modes.

    Smart retry logic:
    - Skip pages where average confidence is already >= min_confidence
    - Skip words that look like plausible text (valid chars, >= 70% conf)
    - Early exit per word once a good result is found
    - Cap total retries per page to avoid slowdowns

    Args:
        image: Original page image.
        result: Initial OCR result.
        lang: Language string.
        min_confidence: Retry words below this threshold.
        padding: Extra pixels around the crop region.
        max_retries_per_page: Maximum words to retry per page.

    Returns:
        Updated OcrPageResult with improved word confidences.
    """
    # Skip page entirely if already good enough
    if result.page_confidence >= min_confidence:
        return result

    # Only retry words that are both low-confidence AND look like garbage
    retry_psm_modes = [8, 7]  # single word first (faster), then single line
    improved_words = []
    retried = 0

    for word in result.words:
        # Skip if above threshold
        if word.confidence >= min_confidence:
            improved_words.append(word)
            continue

        # Skip if the word looks like valid text at reasonable confidence
        if word.confidence >= 70.0 and _is_plausible_word(word.text):
            improved_words.append(word)
            continue

        # Cap retries per page
        if retried >= max_retries_per_page:
            improved_words.append(word)
            continue

        retried += 1
        best_word = word

        # Crop the word region with padding
        x1 = max(0, word.x - padding)
        y1 = max(0, word.y - padding)
        x2 = min(image.width, word.x + word.width + padding)
        y2 = min(image.height, word.y + word.height + padding)

        if x2 <= x1 or y2 <= y1:
            improved_words.append(word)
            continue

        crop = image.crop((x1, y1, x2, y2))

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
                            text=text, x=word.x, y=word.y,
                            width=word.width, height=word.height,
                            confidence=conf,
                        )
            except Exception:
                continue

            # Early exit: if we got a good result, no need to try more PSM modes
            if best_word.confidence >= min_confidence:
                break

        improved_words.append(best_word)

    # Rebuild lines with improved words
    # Create a map from (x, y, text) of original word to improved word
    word_map = {}
    for old_w, new_w in zip(result.words, improved_words):
        word_map[id(old_w)] = new_w

    improved_lines = []
    for line in result.lines:
        new_line_words = []
        for w in line.words:
            new_line_words.append(word_map.get(id(w), w))
        new_line = OcrLine(words=new_line_words)
        new_line.compute_bounds()
        improved_lines.append(new_line)

    return OcrPageResult(
        words=improved_words,
        lines=improved_lines,
        page_width=result.page_width,
        page_height=result.page_height,
        full_text=result.full_text,
    )


def detect_columns(image: Image.Image) -> tuple[int, float]:
    """Detect if a page has 1 or 2 text columns.

    Uses vertical projection profile: sum pixel intensity per column.
    A two-column layout has a clear gap (high white-space) in the middle.

    Returns:
        (num_columns, split_fraction) — split_fraction is the x-position
        of the gap center as a fraction of image width (0.0–1.0).
        For single-column, split_fraction is 0.5 (unused).
    """
    gray = image.convert("L")

    # Downscale for speed
    target_w = 600
    scale = target_w / gray.width if gray.width > target_w else 1.0
    if scale < 1.0:
        gray = gray.resize((target_w, int(gray.height * scale)))

    w, h = gray.size
    data = gray.tobytes()

    # Only analyze the middle 80% of the page height (skip headers/footers)
    y_start = int(h * 0.1)
    y_end = int(h * 0.9)

    # Vertical projection: sum of dark pixels per column
    projections = []
    for x in range(w):
        col_sum = sum(1 for y in range(y_start, y_end) if data[y * w + x] < 128)
        projections.append(col_sum)

    # Smooth the projection with a moving average to reduce noise
    kernel = max(3, w // 60)
    smoothed = []
    for x in range(w):
        start = max(0, x - kernel)
        end = min(w, x + kernel + 1)
        smoothed.append(sum(projections[start:end]) / (end - start))

    # Look for a gap in the middle 40% of the page
    mid_start = int(w * 0.30)
    mid_end = int(w * 0.70)
    if mid_start >= mid_end:
        return 1, 0.5

    mid_smoothed = smoothed[mid_start:mid_end]

    # Compute stats for left and right halves (text regions)
    left_avg = sum(smoothed[:mid_start]) / mid_start if mid_start > 0 else 0
    right_avg = sum(smoothed[mid_end:]) / (w - mid_end) if (w - mid_end) > 0 else 0
    text_avg = (left_avg + right_avg) / 2 if (left_avg + right_avg) > 0 else 1

    # Find the minimum in the middle region
    min_val = min(mid_smoothed) if mid_smoothed else text_avg
    min_idx = mid_smoothed.index(min_val) + mid_start

    # Two-column if the gap is significantly lower than the text regions
    # and both sides have substantial text
    if (text_avg > 0
            and min_val < text_avg * 0.3
            and left_avg > text_avg * 0.3
            and right_avg > text_avg * 0.3):
        split_frac = min_idx / w
        return 2, split_frac

    return 1, 0.5


def ocr_page_two_column(
    image: Image.Image,
    lang: str = "grc+lat+eng",
    split_frac: float = 0.5,
) -> OcrPageResult:
    """OCR a two-column page by splitting into left and right halves.

    Each column is OCR'd separately with PSM 4 (single column mode),
    then results are merged with correct coordinates.

    Args:
        image: Full page image.
        lang: Tesseract language string.
        split_frac: Where to split (0.0–1.0), from detect_columns().
    """
    w, h = image.size
    split_x = int(w * split_frac)

    # Add small overlap at the split to avoid cutting through characters
    overlap = int(w * 0.01)
    left_img = image.crop((0, 0, min(split_x + overlap, w), h))
    right_img = image.crop((max(split_x - overlap, 0), 0, w, h))
    right_offset = max(split_x - overlap, 0)

    left_result = ocr_page(left_img, lang=lang, psm=4)
    right_result = ocr_page(right_img, lang=lang, psm=4)

    # Offset right column words/lines to full-page coordinates
    all_words = list(left_result.words)
    all_lines = list(left_result.lines)

    for word in right_result.words:
        all_words.append(OcrWord(
            text=word.text,
            x=word.x + right_offset,
            y=word.y,
            width=word.width,
            height=word.height,
            confidence=word.confidence,
        ))

    for line in right_result.lines:
        offset_words = [
            OcrWord(
                text=lw.text, x=lw.x + right_offset, y=lw.y,
                width=lw.width, height=lw.height, confidence=lw.confidence,
            )
            for lw in line.words
        ]
        new_line = OcrLine(words=offset_words)
        new_line.compute_bounds()
        all_lines.append(new_line)

    # Sort lines: left column first (top to bottom), then right column
    all_lines.sort(key=lambda ln: (ln.x > split_x * 0.8, ln.y))

    full_text = "\n".join(ln.text for ln in all_lines)

    return OcrPageResult(
        words=all_words,
        lines=all_lines,
        page_width=w,
        page_height=h,
        full_text=full_text,
    )


def ocr_page_text(image: Image.Image, lang: str = "grc+lat+eng") -> str:
    """Simple text-only OCR without bounding box data."""
    return pytesseract.image_to_string(image, lang=lang)
