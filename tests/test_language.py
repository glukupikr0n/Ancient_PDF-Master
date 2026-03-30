"""Tests for language module."""

from unittest.mock import patch

import pytest

from ancient_pdf_master.language import (
    DEFAULT_LANG,
    SUPPORTED_LANGUAGES,
    validate_languages,
)


def test_default_lang_contains_core_languages():
    for code in ["grc", "lat", "eng"]:
        assert code in DEFAULT_LANG


def test_supported_languages_has_required():
    assert "grc" in SUPPORTED_LANGUAGES
    assert "lat" in SUPPORTED_LANGUAGES
    assert "eng" in SUPPORTED_LANGUAGES


@patch("ancient_pdf_master.language.get_installed_languages")
def test_validate_languages_success(mock_installed):
    mock_installed.return_value = ["eng", "lat", "grc", "osd"]
    result = validate_languages("grc+lat+eng")
    assert result == "grc+lat+eng"


@patch("ancient_pdf_master.language.get_installed_languages")
def test_validate_languages_missing(mock_installed):
    mock_installed.return_value = ["eng"]
    with pytest.raises(ValueError, match="Missing Tesseract language packs"):
        validate_languages("grc+lat+eng")


@patch("ancient_pdf_master.language.get_installed_languages")
def test_validate_single_language(mock_installed):
    mock_installed.return_value = ["eng", "lat", "grc"]
    result = validate_languages("eng")
    assert result == "eng"
