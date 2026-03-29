"""Tests for page range parsing."""

from ancient_pdf_master.bridge import _parse_page_range


def test_single_pages():
    assert _parse_page_range("1, 3, 5", 10) == [0, 2, 4]


def test_range():
    assert _parse_page_range("1-5", 10) == [0, 1, 2, 3, 4]


def test_mixed():
    assert _parse_page_range("1-3, 7, 9-10", 10) == [0, 1, 2, 6, 8, 9]


def test_out_of_bounds():
    assert _parse_page_range("1, 5, 100", 5) == [0, 4]


def test_empty():
    assert _parse_page_range("", 10) == []


def test_dedup():
    assert _parse_page_range("1, 1, 1-3", 10) == [0, 1, 2]


def test_invalid():
    assert _parse_page_range("abc, x-y", 10) == []
