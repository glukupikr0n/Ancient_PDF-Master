"""Tests for toc_builder module."""

from ancient_pdf_master.toc_builder import TocEntry


def test_toc_entry_defaults():
    e = TocEntry(title="Chapter 1", page=0)
    assert e.level == 0


def test_toc_entry_nested():
    entries = [
        TocEntry("Part I", 0, level=0),
        TocEntry("Chapter 1", 1, level=1),
        TocEntry("Section 1.1", 2, level=2),
        TocEntry("Chapter 2", 5, level=1),
        TocEntry("Part II", 10, level=0),
    ]
    assert len(entries) == 5
    assert entries[0].level == 0
    assert entries[2].level == 2
    assert entries[4].title == "Part II"
