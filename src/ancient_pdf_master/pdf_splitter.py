"""Bilingual PDF splitting with common page duplication."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from .ocr_engine import OcrPageResult
from .pdf_builder import build_searchable_pdf


def parse_page_ranges(spec: str, total_pages: int) -> list[int]:
    """Parse a page range string (1-based) into 0-indexed page numbers.

    Examples:
        "1-3, 5"     -> [0, 1, 2, 4]
        "odd"        -> [0, 2, 4, ...]
        "even"       -> [1, 3, 5, ...]
        "1, 3, 5-7"  -> [0, 2, 4, 5, 6]
    """
    spec = spec.strip().lower()

    if spec == "odd":
        return list(range(0, total_pages, 2))
    if spec == "even":
        return list(range(1, total_pages, 2))

    pages: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start = int(start_s.strip())
            end = int(end_s.strip())
            for p in range(start, end + 1):
                if 1 <= p <= total_pages:
                    pages.add(p - 1)
        else:
            p = int(part)
            if 1 <= p <= total_pages:
                pages.add(p - 1)

    return sorted(pages)


def split_bilingual_pdf(
    images: list[Image.Image],
    ocr_results: list[OcrPageResult],
    lang_a_pages: list[int],
    lang_b_pages: list[int],
    common_pages: list[int],
    output_a_path: str | Path,
    output_b_path: str | Path,
    dpi: int = 300,
    progress_callback=None,
) -> tuple[Path, Path]:
    """Split a bilingual PDF into two language-specific PDFs.

    Common pages are duplicated into both output PDFs at their original positions.

    Args:
        images: All page images from the source document.
        ocr_results: OCR results for each page.
        lang_a_pages: 0-indexed page numbers for language A.
        lang_b_pages: 0-indexed page numbers for language B.
        common_pages: 0-indexed page numbers to include in both outputs.
        output_a_path: Output path for language A PDF.
        output_b_path: Output path for language B PDF.
        dpi: Source image DPI.
        progress_callback: Optional callable(step, total_steps, message).

    Returns:
        Tuple of (path_a, path_b).
    """
    # Merge common pages into both sets, preserving original order
    pages_a = sorted(set(lang_a_pages) | set(common_pages))
    pages_b = sorted(set(lang_b_pages) | set(common_pages))

    total_steps = 2
    if progress_callback:
        progress_callback(0, total_steps, "Building language A PDF...")

    # Build language A PDF
    images_a = [images[i] for i in pages_a]
    ocr_a = [ocr_results[i] for i in pages_a]
    path_a = build_searchable_pdf(images_a, ocr_a, output_a_path, dpi=dpi)

    if progress_callback:
        progress_callback(1, total_steps, "Building language B PDF...")

    # Build language B PDF
    images_b = [images[i] for i in pages_b]
    ocr_b = [ocr_results[i] for i in pages_b]
    path_b = build_searchable_pdf(images_b, ocr_b, output_b_path, dpi=dpi)

    if progress_callback:
        progress_callback(2, total_steps, "Splitting complete")

    return path_a, path_b
