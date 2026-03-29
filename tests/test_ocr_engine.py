"""Tests for ocr_engine module."""

from unittest.mock import patch

import pytest
from PIL import Image

from ancient_pdf_master.ocr_engine import OcrLine, OcrPageResult, OcrWord, ocr_page, retry_low_confidence_words


def test_ocr_page_result_confidence():
    result = OcrPageResult(
        words=[
            OcrWord("hello", 0, 0, 50, 20, 95.0),
            OcrWord("world", 60, 0, 50, 20, 85.0),
        ],
        page_width=200,
        page_height=100,
    )
    assert result.page_confidence == 90.0
    assert result.word_count == 2


def test_ocr_page_result_empty():
    result = OcrPageResult()
    assert result.page_confidence == 0.0
    assert result.word_count == 0


@patch("ancient_pdf_master.ocr_engine.pytesseract")
def test_ocr_page_filters_empty_text(mock_tess):
    mock_tess.image_to_data.return_value = {
        "text": ["hello", "", " ", "world"],
        "conf": [90.0, -1.0, -1.0, 85.0],
        "left": [10, 0, 0, 60],
        "top": [10, 0, 0, 10],
        "width": [50, 0, 0, 50],
        "height": [20, 0, 0, 20],
        "block_num": [1, 1, 1, 1],
        "par_num": [1, 1, 1, 1],
        "line_num": [1, 1, 1, 1],
    }
    mock_tess.image_to_string.return_value = "hello world"
    mock_tess.Output = type("Output", (), {"DICT": "dict"})()

    img = Image.new("RGB", (200, 100))
    result = ocr_page(img, lang="eng")

    assert result.word_count == 2
    assert result.words[0].text == "hello"
    assert result.words[1].text == "world"


@patch("ancient_pdf_master.ocr_engine.pytesseract")
def test_retry_low_confidence_improves(mock_tess):
    """Words below threshold get retried; higher-confidence result is kept."""
    mock_tess.Output = type("Output", (), {"DICT": "dict"})()

    # Retry returns a better result for the low-confidence word
    mock_tess.image_to_data.return_value = {
        "text": ["world"],
        "conf": [98.0],
        "left": [0],
        "top": [0],
        "width": [50],
        "height": [20],
    }

    img = Image.new("RGB", (200, 100), "white")
    word1 = OcrWord("hello", 10, 10, 50, 20, 96.0)  # above threshold
    word2 = OcrWord("wrold", 80, 10, 50, 20, 60.0)   # below threshold → retry
    line = OcrLine(words=[word1, word2])
    line.compute_bounds()

    initial = OcrPageResult(
        words=[word1, word2],
        lines=[line],
        page_width=200,
        page_height=100,
        full_text="hello wrold",
    )

    result = retry_low_confidence_words(img, initial, min_confidence=95.0)

    assert result.word_count == 2
    # First word unchanged (was above threshold)
    assert result.words[0].text == "hello"
    assert result.words[0].confidence == 96.0
    # Second word improved
    assert result.words[1].text == "world"
    assert result.words[1].confidence == 98.0
    # Lines must be preserved
    assert len(result.lines) == 1
    assert result.lines[0].words[1].text == "world"
    assert result.lines[0].words[1].confidence == 98.0


def test_retry_low_confidence_no_retry_needed():
    """When all words are above threshold, nothing changes."""
    img = Image.new("RGB", (200, 100), "white")
    word1 = OcrWord("hello", 10, 10, 50, 20, 97.0)
    word2 = OcrWord("world", 80, 10, 50, 20, 96.0)
    line = OcrLine(words=[word1, word2])
    line.compute_bounds()

    initial = OcrPageResult(
        words=[word1, word2],
        lines=[line],
        page_width=200,
        page_height=100,
        full_text="hello world",
    )

    result = retry_low_confidence_words(img, initial, min_confidence=95.0)

    assert result.word_count == 2
    assert result.words[0].confidence == 97.0
    assert result.words[1].confidence == 96.0
    # Lines preserved
    assert len(result.lines) == 1
