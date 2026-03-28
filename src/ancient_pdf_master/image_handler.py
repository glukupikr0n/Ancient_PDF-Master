"""Image loading, preprocessing, and PDF-to-image conversion."""

from __future__ import annotations

import enum
from pathlib import Path
from typing import Iterator

from PIL import Image

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"}
PDF_EXTENSIONS = {".pdf"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | PDF_EXTENSIONS


class FileType(enum.Enum):
    IMAGE = "image"
    PDF = "pdf"
    UNSUPPORTED = "unsupported"


def get_file_type(path: Path) -> FileType:
    """Determine the file type from extension."""
    suffix = path.suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return FileType.IMAGE
    if suffix in PDF_EXTENSIONS:
        return FileType.PDF
    return FileType.UNSUPPORTED


def load_images(file_path: str | Path, dpi: int = 300) -> list[Image.Image]:
    """Load a file and return a list of PIL Images (one per page).

    Supports image files (PNG, JPG, TIFF, etc.) and PDF files.
    Multi-page TIFFs are expanded into separate images.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    file_type = get_file_type(path)

    if file_type == FileType.UNSUPPORTED:
        raise ValueError(
            f"Unsupported file format: {path.suffix}\n"
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    if file_type == FileType.PDF:
        return _load_pdf(path, dpi)

    return _load_image(path)


def _load_image(path: Path) -> list[Image.Image]:
    """Load an image file, handling multi-frame TIFFs."""
    img = Image.open(path)
    images = []

    try:
        frame = 0
        while True:
            img.seek(frame)
            # Convert to RGB to ensure consistency
            images.append(img.copy().convert("RGB"))
            frame += 1
    except EOFError:
        pass

    return images


def _load_pdf(path: Path, dpi: int) -> list[Image.Image]:
    """Convert PDF pages to images using pdf2image."""
    from pdf2image import convert_from_path

    return convert_from_path(str(path), dpi=dpi)


def get_supported_filter() -> str:
    """Return a file filter string for Qt file dialogs."""
    exts = " ".join(f"*{ext}" for ext in sorted(SUPPORTED_EXTENSIONS))
    img_exts = " ".join(f"*{ext}" for ext in sorted(IMAGE_EXTENSIONS))
    return (
        f"All Supported Files ({exts});;"
        f"PDF Files (*.pdf);;"
        f"Image Files ({img_exts});;"
        f"All Files (*)"
    )
