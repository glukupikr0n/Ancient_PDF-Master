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

    # Build the final PDF using pikepdf
    output_pdf = pikepdf.Pdf.new()

    for i, (image, ocr_result) in enumerate(zip(images, ocr_results)):
        # Create image layer
        image_pdf_bytes = _create_image_pdf_page(image, dpi)

        # Create text layer
        text_pdf_bytes = _create_text_layer_pdf(ocr_result, dpi)

        # Open both as pikepdf objects
        image_pdf = pikepdf.Pdf.open(io.BytesIO(image_pdf_bytes))
        text_pdf = pikepdf.Pdf.open(io.BytesIO(text_pdf_bytes))

        # Get the image page and overlay text layer
        image_page = image_pdf.pages[0]
        text_page = text_pdf.pages[0]

        # Merge text layer content stream into image page
        image_page_content = image_page.Contents
        text_page_content = text_page.Contents

        # Add text layer resources to image page
        if "/Font" in text_page.get("/Resources", {}):
            if "/Resources" not in image_page:
                image_page["/Resources"] = pikepdf.Dictionary()
            if "/Font" not in image_page["/Resources"]:
                image_page["/Resources"]["/Font"] = pikepdf.Dictionary()

            for font_name, font_ref in text_page["/Resources"]["/Font"].items():
                copied = output_pdf.copy_foreign(font_ref)
                image_page["/Resources"]["/Font"][font_name] = copied

        # Append text content stream to image page
        if isinstance(image_page_content, pikepdf.Array):
            streams = list(image_page_content)
        else:
            streams = [image_page_content]

        if isinstance(text_page_content, pikepdf.Array):
            for s in text_page_content:
                copied = output_pdf.copy_foreign(s)
                streams.append(copied)
        else:
            copied = output_pdf.copy_foreign(text_page_content)
            streams.append(copied)

        image_page.Contents = pikepdf.Array(streams)

        # Copy merged page to output
        output_pdf.pages.append(output_pdf.copy_foreign(image_page))

        if progress_callback:
            progress_callback(i + 1, len(images))

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
