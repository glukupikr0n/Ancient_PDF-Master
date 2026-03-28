"""Tests for image_handler module."""

import tempfile
from pathlib import Path

import pytest
from PIL import Image

from ancient_pdf_master.image_handler import (
    FileType,
    get_file_type,
    get_supported_filter,
    load_images,
)


def test_get_file_type_image():
    assert get_file_type(Path("test.png")) == FileType.IMAGE
    assert get_file_type(Path("test.jpg")) == FileType.IMAGE
    assert get_file_type(Path("test.jpeg")) == FileType.IMAGE
    assert get_file_type(Path("test.tif")) == FileType.IMAGE
    assert get_file_type(Path("test.tiff")) == FileType.IMAGE


def test_get_file_type_pdf():
    assert get_file_type(Path("test.pdf")) == FileType.PDF


def test_get_file_type_unsupported():
    assert get_file_type(Path("test.doc")) == FileType.UNSUPPORTED
    assert get_file_type(Path("test.txt")) == FileType.UNSUPPORTED


def test_load_images_png():
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        img = Image.new("RGB", (100, 100), color="white")
        img.save(f.name)
        images = load_images(f.name)
        assert len(images) == 1
        assert images[0].size == (100, 100)


def test_load_images_file_not_found():
    with pytest.raises(FileNotFoundError):
        load_images("/nonexistent/file.png")


def test_load_images_unsupported_format():
    with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
        f.write(b"dummy")
        with pytest.raises(ValueError, match="Unsupported file format"):
            load_images(f.name)


def test_get_supported_filter():
    filt = get_supported_filter()
    assert "*.pdf" in filt
    assert "*.png" in filt
    assert "*.jpg" in filt
