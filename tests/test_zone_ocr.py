"""Tests for zone_ocr module."""

from PIL import Image

from ancient_pdf_master.zone_ocr import (
    ZONE_PRESETS,
    ZoneConfig,
    ZoneType,
    _crop_zone,
    preset_classical_left_margin,
    preset_classical_both_margins,
    preset_full_page,
)


def test_presets_exist():
    assert "full_page" in ZONE_PRESETS
    assert "left_margin" in ZONE_PRESETS
    assert "both_margins" in ZONE_PRESETS


def test_full_page_preset():
    zones = preset_full_page()
    assert len(zones) == 1
    assert zones[0].zone_type == ZoneType.BODY
    assert zones[0].x_start == 0.0
    assert zones[0].y_end == 1.0


def test_left_margin_preset():
    zones = preset_classical_left_margin(margin_width=0.15)
    assert len(zones) == 2
    margin = zones[0]
    body = zones[1]
    assert margin.zone_type == ZoneType.LEFT_MARGIN
    assert margin.x_end == 0.15
    assert margin.psm == 11  # Sparse text mode
    assert body.zone_type == ZoneType.BODY
    assert body.x_start == 0.15
    assert body.psm == 3


def test_both_margins_preset():
    zones = preset_classical_both_margins(left_margin=0.10, right_margin=0.12)
    assert len(zones) == 3
    assert zones[0].zone_type == ZoneType.LEFT_MARGIN
    assert zones[1].zone_type == ZoneType.BODY
    assert zones[2].zone_type == ZoneType.RIGHT_MARGIN
    assert zones[2].x_start == 0.88  # 1.0 - 0.12


def test_crop_zone():
    img = Image.new("RGB", (1000, 800), color="white")
    zone = ZoneConfig(
        zone_type=ZoneType.LEFT_MARGIN,
        x_start=0.0, y_start=0.1, x_end=0.12, y_end=0.9,
    )
    cropped = _crop_zone(img, zone)
    assert cropped.width == 120  # 0.12 * 1000
    assert cropped.height == 640  # (0.9 - 0.1) * 800


def test_crop_zone_minimum_size():
    """Ensure very small zones don't produce zero-size images."""
    img = Image.new("RGB", (100, 100))
    zone = ZoneConfig(
        zone_type=ZoneType.LEFT_MARGIN,
        x_start=0.0, y_start=0.0, x_end=0.01, y_end=0.01,
    )
    cropped = _crop_zone(img, zone)
    assert cropped.width >= 10
    assert cropped.height >= 10


def test_zone_config_custom_lang():
    zone = ZoneConfig(
        zone_type=ZoneType.LEFT_MARGIN,
        x_start=0.0, y_start=0.0, x_end=0.1, y_end=1.0,
        psm=11, lang="eng",
    )
    assert zone.lang == "eng"
    assert zone.psm == 11
