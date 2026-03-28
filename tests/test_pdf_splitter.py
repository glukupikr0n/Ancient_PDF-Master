"""Tests for pdf_splitter module."""

import pytest

from ancient_pdf_master.pdf_splitter import parse_page_ranges


def test_parse_page_ranges_simple():
    assert parse_page_ranges("1, 3, 5", 10) == [0, 2, 4]


def test_parse_page_ranges_range():
    assert parse_page_ranges("1-3, 5", 10) == [0, 1, 2, 4]


def test_parse_page_ranges_odd():
    assert parse_page_ranges("odd", 6) == [0, 2, 4]


def test_parse_page_ranges_even():
    assert parse_page_ranges("even", 6) == [1, 3, 5]


def test_parse_page_ranges_clamps_to_total():
    # Pages beyond total are ignored
    assert parse_page_ranges("1, 5, 100", 5) == [0, 4]


def test_parse_page_ranges_empty():
    assert parse_page_ranges("", 10) == []
