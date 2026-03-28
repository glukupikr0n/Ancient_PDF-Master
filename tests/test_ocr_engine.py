"""Tests for ocr_engine module."""

from unittest.mock import patch

import pytest
from PIL import Image

from ancient_pdf_master.ocr_engine import OcrPageResult, OcrWord, ocr_page


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
    }
    mock_tess.image_to_string.return_value = "hello world"
    mock_tess.Output = type("Output", (), {"DICT": "dict"})()

    img = Image.new("RGB", (200, 100))
    result = ocr_page(img, lang="eng")

    assert result.word_count == 2
    assert result.words[0].text == "hello"
    assert result.words[1].text == "world"
