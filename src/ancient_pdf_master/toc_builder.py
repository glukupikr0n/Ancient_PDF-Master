"""PDF Table of Contents (bookmarks/outlines) embedding."""

from __future__ import annotations

from dataclasses import dataclass

import pikepdf


@dataclass
class TocEntry:
    """A single TOC entry.

    Attributes:
        title: Display title for the bookmark.
        page: 0-indexed page number this entry points to.
        level: Nesting level (0 = top level, 1 = child, 2 = grandchild, etc.).
    """
    title: str
    page: int
    level: int = 0


def embed_toc(pdf: pikepdf.Pdf, entries: list[TocEntry]) -> None:
    """Embed TOC entries as PDF outline bookmarks.

    Converts a flat list of TocEntry (with level-based nesting) into
    a hierarchical PDF outline structure.
    """
    if not entries:
        return

    with pdf.open_outline() as outline:
        outline.root.clear()
        _build_outline(outline.root, entries, 0)


def _build_outline(
    parent_list,
    entries: list[TocEntry],
    start_idx: int,
) -> int:
    """Recursively build the outline tree from a flat entry list.

    Returns the index of the next unprocessed entry.
    """
    idx = start_idx
    base_level = entries[idx].level if idx < len(entries) else 0

    while idx < len(entries):
        entry = entries[idx]

        if entry.level < base_level:
            # Gone back up to parent level
            return idx

        if entry.level == base_level:
            # Create outline item at current level
            item = pikepdf.OutlineItem(entry.title, entry.page)
            parent_list.append(item)
            idx += 1

            # Check if next entries are children (deeper level)
            if idx < len(entries) and entries[idx].level > base_level:
                idx = _build_outline(item.children, entries, idx)
        else:
            # Deeper than expected without a parent — attach to last item
            if parent_list:
                idx = _build_outline(parent_list[-1].children, entries, idx)
            else:
                # No parent available, force it at current level
                item = pikepdf.OutlineItem(entry.title, entry.page)
                parent_list.append(item)
                idx += 1

    return idx
