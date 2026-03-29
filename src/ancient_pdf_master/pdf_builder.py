"""Searchable PDF generation with invisible OCR text layer."""

from __future__ import annotations

import io
import tempfile
from pathlib import Path

import pikepdf
from PIL import Image
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

from .ocr_engine import OcrPageResult


def _pixels_to_points(pixels: float, dpi: int) -> float:
    """Convert pixel measurement to PDF points (1 point = 1/72 inch)."""
    return pixels * 72.0 / dpi


def _create_image_pdf_page(image: Image.Image, dpi: int) -> bytes:
    """Create a single-page PDF containing just the raster image."""
    buf = io.BytesIO()
    page_w = _pixels_to_points(image.width, dpi)
    page_h = _pixels_to_points(image.height, dpi)

    c = canvas.Canvas(buf, pagesize=(page_w, page_h))

    # Save image to temporary buffer for reportlab
    img_buf = io.BytesIO()
    image.save(img_buf, format="PNG")
    img_buf.seek(0)

    from reportlab.lib.utils import ImageReader
    c.drawImage(ImageReader(img_buf), 0, 0, width=page_w, height=page_h)
    c.showPage()
    c.save()

    return buf.getvalue()


def _create_text_layer_pdf(
    ocr_result: OcrPageResult, dpi: int
) -> bytes:
    """Create a single-page PDF with invisible text at OCR bounding box positions.

    The text is rendered in mode 3 (invisible) so it can be selected and
    searched but does not appear visually.
    """
    buf = io.BytesIO()
    page_w = _pixels_to_points(ocr_result.page_width, dpi)
    page_h = _pixels_to_points(ocr_result.page_height, dpi)

    c = canvas.Canvas(buf, pagesize=(page_w, page_h))
    c.setFont("Helvetica", 12)

    for word in ocr_result.words:
        # Convert pixel coordinates to points
        x_pt = _pixels_to_points(word.x, dpi)
        # Flip Y axis: Tesseract uses top-left origin, PDF uses bottom-left
        y_pt = page_h - _pixels_to_points(word.y + word.height, dpi)
        w_pt = _pixels_to_points(word.width, dpi)
        h_pt = _pixels_to_points(word.height, dpi)

        # Calculate font size to roughly match bounding box height
        font_size = max(h_pt * 0.85, 4)
        c.setFont("Helvetica", font_size)

        # Render mode 3 = invisible text
        text_obj = c.beginText(x_pt, y_pt)
        text_obj.setTextRenderMode(3)
        text_obj.textLine(word.text)
        c.drawText(text_obj)

    c.showPage()
    c.save()

    return buf.getvalue()


def _render_text_lines(c, lines, page_h: float, dpi: int):
    """Render OCR text as invisible lines with consistent font sizing.

    Each line is rendered as a single text run with spaces between words,
    ensuring continuous text selection in PDF viewers.
    """
    from reportlab.pdfbase.pdfmetrics import stringWidth

    for line in lines:
        if not line.words:
            continue

        # Use line height for consistent font size across the line
        h_pt = _pixels_to_points(line.height, dpi)
        font_size = max(h_pt * 0.8, 4)
        font_name = "Helvetica"

        # Line start position
        x_pt = _pixels_to_points(line.x, dpi)
        y_pt = page_h - _pixels_to_points(line.y + line.height, dpi)
        line_w_pt = _pixels_to_points(line.width, dpi)

        # Build full line text
        line_text = " ".join(w.text for w in line.words)

        # Scale font to fit the line width
        natural_width = stringWidth(line_text, font_name, font_size)
        if natural_width > 0 and line_w_pt > 0:
            h_scale = min(line_w_pt / natural_width, 1.5)
            # Use character spacing to stretch/compress
            if h_scale < 0.5:
                # Text way too wide — reduce font size instead
                font_size = font_size * (line_w_pt / natural_width)
                font_size = max(font_size, 3)
        else:
            h_scale = 1.0

        c.setFont(font_name, font_size)

        text_obj = c.beginText(x_pt, y_pt)
        text_obj.setTextRenderMode(3)  # invisible
        text_obj.setHorizScale(h_scale * 100)
        text_obj.textLine(line_text)
        c.drawText(text_obj)


def _render_text_words(c, words, page_h: float, dpi: int):
    """Fallback: render text word-by-word (old behavior)."""
    c.setFont("Helvetica", 12)
    for word in words:
        x_pt = _pixels_to_points(word.x, dpi)
        y_pt = page_h - _pixels_to_points(word.y + word.height, dpi)
        h_pt = _pixels_to_points(word.height, dpi)

        font_size = max(h_pt * 0.85, 4)
        c.setFont("Helvetica", font_size)

        text_obj = c.beginText(x_pt, y_pt)
        text_obj.setTextRenderMode(3)
        text_obj.textLine(word.text)
        c.drawText(text_obj)


def build_searchable_pdf(
    images: list[Image.Image],
    ocr_results: list[OcrPageResult],
    output_path: str | Path,
    dpi: int = 300,
    progress_callback=None,
    page_label_ranges=None,
    toc_entries=None,
) -> Path:
    """Build a searchable PDF by overlaying invisible OCR text on scanned images.

    Args:
        images: List of page images.
        ocr_results: Corresponding OCR results for each page.
        output_path: Where to save the final PDF.
        dpi: Resolution of the source images.
        progress_callback: Optional callable(page_num, total_pages) for progress.
        page_label_ranges: Optional list of PageLabelRange for page numbering.
        toc_entries: Optional list of TocEntry for PDF bookmarks.

    Returns:
        Path to the output file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Build the final PDF using pikepdf.
    # Strategy: create a combined reportlab PDF (image + text per page),
    # then open it with pikepdf for post-processing.
    combined_buf = io.BytesIO()
    page_sizes = []

    for i, (image, ocr_result) in enumerate(zip(images, ocr_results)):
        page_w = _pixels_to_points(image.width, dpi)
        page_h = _pixels_to_points(image.height, dpi)
        page_sizes.append((page_w, page_h))

    # Build all pages in a single reportlab canvas
    c = canvas.Canvas(combined_buf)

    for i, (image, ocr_result) in enumerate(zip(images, ocr_results)):
        page_w, page_h = page_sizes[i]
        c.setPageSize((page_w, page_h))

        # Draw image
        img_buf = io.BytesIO()
        # Ensure RGB mode for reportlab
        save_img = image.convert("RGB") if image.mode not in ("RGB", "L") else image
        save_img.save(img_buf, format="PNG")
        img_buf.seek(0)

        from reportlab.lib.utils import ImageReader
        c.drawImage(ImageReader(img_buf), 0, 0, width=page_w, height=page_h)

        # Draw invisible text layer — line-by-line for consistent sizing
        # and continuous text selection in PDF viewers
        if ocr_result.lines:
            _render_text_lines(c, ocr_result.lines, page_h, dpi)
        else:
            # Fallback: word-by-word if no line data
            _render_text_words(c, ocr_result.words, page_h, dpi)

        c.showPage()

        if progress_callback:
            progress_callback(i + 1, len(images))

    c.save()

    # Open with pikepdf for post-processing (page labels, TOC)
    combined_buf.seek(0)
    output_pdf = pikepdf.Pdf.open(combined_buf)

    # Apply page labels (Roman numerals, Arabic, etc.)
    if page_label_ranges:
        from .page_labels import apply_page_labels
        apply_page_labels(output_pdf, page_label_ranges)

    # Embed TOC as PDF bookmarks
    if toc_entries:
        from .toc_builder import embed_toc
        embed_toc(output_pdf, toc_entries)

    output_pdf.save(str(output_path))
    return output_path
