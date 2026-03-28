"""PDF page label support (Roman numerals, Arabic, etc.)."""

from __future__ import annotations

from dataclasses import dataclass

import pikepdf

# PDF page label style mapping
STYLE_MAP = {
    "roman_lower": pikepdf.Name("/r"),
    "roman_upper": pikepdf.Name("/R"),
    "arabic": pikepdf.Name("/D"),
    "alpha_lower": pikepdf.Name("/a"),
    "alpha_upper": pikepdf.Name("/A"),
}


@dataclass
class PageLabelRange:
    """Defines a page numbering range.

    Attributes:
        start_page: 0-indexed page where this range begins.
        style: One of 'roman_lower', 'roman_upper', 'arabic', 'alpha_lower', 'alpha_upper'.
        prefix: Optional prefix string (e.g. "A-" for "A-1, A-2, ...").
        start_number: Starting number within the range (default 1).
    """
    start_page: int
    style: str = "arabic"
    prefix: str = ""
    start_number: int = 1


def apply_page_labels(pdf: pikepdf.Pdf, ranges: list[PageLabelRange]) -> None:
    """Set the /PageLabels number tree on the PDF document catalog.

    This allows PDF viewers to display the correct page numbers
    (e.g., Roman numerals for front matter, Arabic for body).
    """
    if not ranges:
        return

    # Sort ranges by start_page
    ranges = sorted(ranges, key=lambda r: r.start_page)

    # Build the /Nums array: [page_index, label_dict, page_index, label_dict, ...]
    nums = []
    for r in ranges:
        label_dict = pikepdf.Dictionary()

        if r.style in STYLE_MAP:
            label_dict["/S"] = STYLE_MAP[r.style]

        if r.prefix:
            label_dict["/P"] = pikepdf.String(r.prefix)

        if r.start_number != 1:
            label_dict["/St"] = r.start_number

        nums.append(r.start_page)
        nums.append(label_dict)

    pdf.Root["/PageLabels"] = pikepdf.Dictionary({
        "/Nums": pikepdf.Array(nums),
    })
