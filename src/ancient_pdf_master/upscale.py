"""Image and PDF upscaling using high-quality Lanczos resampling."""

from __future__ import annotations

import io
from pathlib import Path

from PIL import Image


def upscale_image(image: Image.Image, scale: float) -> Image.Image:
    """Upscale an image using Lanczos resampling.

    Args:
        image: PIL Image to upscale.
        scale: Scale factor (e.g. 2.0 for 2x).

    Returns:
        Upscaled PIL Image.
    """
    if scale <= 1.0:
        return image

    new_w = int(image.width * scale)
    new_h = int(image.height * scale)
    return image.resize((new_w, new_h), Image.LANCZOS)


def upscale_images(
    images: list[Image.Image],
    scale: float,
    progress_callback=None,
) -> list[Image.Image]:
    """Upscale a list of images.

    Args:
        images: List of PIL Images.
        scale: Scale factor.
        progress_callback: Optional callable(current, total, message).

    Returns:
        List of upscaled PIL Images.
    """
    result = []
    total = len(images)
    for i, img in enumerate(images):
        if progress_callback:
            progress_callback(i + 1, total, f"Upscaling page {i + 1}/{total}...")
        result.append(upscale_image(img, scale))
    return result


def upscale_to_pdf(
    images: list[Image.Image],
    output_path: str | Path,
    dpi: int = 300,
    progress_callback=None,
) -> Path:
    """Save upscaled images as a PDF.

    Args:
        images: List of PIL Images (already upscaled).
        output_path: Destination PDF path.
        dpi: DPI metadata for the output PDF.
        progress_callback: Optional callable(current, total, message).

    Returns:
        Path to the output PDF.
    """
    output_path = Path(output_path)

    if progress_callback:
        progress_callback(0, len(images), "Saving upscaled PDF...")

    # Convert all images to RGB for PDF compatibility
    rgb_images = []
    for img in images:
        if img.mode != "RGB":
            rgb_images.append(img.convert("RGB"))
        else:
            rgb_images.append(img)

    # Save as PDF using Pillow
    if len(rgb_images) == 1:
        rgb_images[0].save(str(output_path), "PDF", resolution=dpi)
    else:
        rgb_images[0].save(
            str(output_path), "PDF", resolution=dpi,
            save_all=True, append_images=rgb_images[1:],
        )

    if progress_callback:
        progress_callback(len(images), len(images), "Upscale complete")

    return output_path


def upscale_to_images(
    images: list[Image.Image],
    output_dir: str | Path,
    fmt: str = "png",
    progress_callback=None,
) -> list[Path]:
    """Save upscaled images as individual files.

    Args:
        images: List of PIL Images (already upscaled).
        output_dir: Destination directory.
        fmt: Output format (png, jpg, tiff).
        progress_callback: Optional callable(current, total, message).

    Returns:
        List of output file paths.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    paths = []
    total = len(images)
    for i, img in enumerate(images):
        if progress_callback:
            progress_callback(i + 1, total, f"Saving page {i + 1}/{total}...")

        filename = f"page_{i + 1:04d}.{fmt}"
        out_path = output_dir / filename

        if fmt.lower() in ("jpg", "jpeg"):
            img.convert("RGB").save(str(out_path), "JPEG", quality=95)
        elif fmt.lower() == "tiff":
            img.save(str(out_path), "TIFF", compression="tiff_lzw")
        else:
            img.save(str(out_path), "PNG")

        paths.append(out_path)

    return paths
