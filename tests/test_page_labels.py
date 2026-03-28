"""Tests for page_labels module."""

from ancient_pdf_master.page_labels import PageLabelRange, STYLE_MAP


def test_style_map_has_required_styles():
    assert "roman_lower" in STYLE_MAP
    assert "roman_upper" in STYLE_MAP
    assert "arabic" in STYLE_MAP


def test_page_label_range_defaults():
    r = PageLabelRange(start_page=0)
    assert r.style == "arabic"
    assert r.prefix == ""
    assert r.start_number == 1


def test_page_label_range_custom():
    r = PageLabelRange(start_page=5, style="roman_lower", prefix="App-", start_number=3)
    assert r.start_page == 5
    assert r.style == "roman_lower"
    assert r.prefix == "App-"
    assert r.start_number == 3
