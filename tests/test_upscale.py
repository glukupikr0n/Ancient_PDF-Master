"""Tests for image upscaling module."""

from PIL import Image

from ancient_pdf_master.upscale import upscale_image, upscale_images


def test_upscale_image_2x():
    img = Image.new("RGB", (100, 50), "white")
    result = upscale_image(img, 2.0)
    assert result.size == (200, 100)


def test_upscale_image_3x():
    img = Image.new("RGB", (100, 50), "white")
    result = upscale_image(img, 3.0)
    assert result.size == (300, 150)


def test_upscale_image_no_change_at_1x():
    img = Image.new("RGB", (100, 50), "white")
    result = upscale_image(img, 1.0)
    assert result.size == (100, 50)


def test_upscale_image_no_change_below_1x():
    img = Image.new("RGB", (100, 50), "white")
    result = upscale_image(img, 0.5)
    assert result.size == (100, 50)


def test_upscale_images_list():
    imgs = [Image.new("RGB", (80, 60), "white") for _ in range(3)]
    results = upscale_images(imgs, 2.0)
    assert len(results) == 3
    for r in results:
        assert r.size == (160, 120)


def test_upscale_images_progress_callback():
    imgs = [Image.new("RGB", (40, 30), "white") for _ in range(2)]
    calls = []
    def cb(current, total, msg):
        calls.append((current, total))
    upscale_images(imgs, 2.0, progress_callback=cb)
    assert len(calls) == 2
    assert calls[0] == (1, 2)
    assert calls[1] == (2, 2)
