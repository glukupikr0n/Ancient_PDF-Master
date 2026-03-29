"""Dataset download and conversion for OCR training.

Supports two dataset sources:
1. Lace — crowdsourced OCR corrections for ancient Greek (image + text pairs)
2. OpenGreekAndLatin (OGL) — TEI XML corpus (text only, generates synthetic images)

Downloaded datasets are cached locally and converted to the app's training format:
  line_NNNN.png + line_NNNN.gt.txt
"""

from __future__ import annotations

import io
import json
import os
import shutil
import tempfile
import threading
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


# ── Cancel flag (shared with bridge.py) ──

_cancel_flag = threading.Event()


# ── Dataset Catalog ──

@dataclass
class DatasetEntry:
    """Metadata for a downloadable dataset."""

    id: str
    name: str
    source: str          # "lace" | "ogl"
    language: str        # "grc" | "lat"
    description: str
    repo: str            # GitHub "owner/repo"
    archive_url: str     # direct ZIP download URL
    estimated_size_mb: int
    pair_count_estimate: int
    format: str          # "image_text_pairs" | "tei_xml"


DATASET_CATALOG: list[DatasetEntry] = [
    # ── Lace datasets ──
    DatasetEntry(
        id="lace_grc_sample",
        name="Lace Greek Sample",
        source="lace",
        language="grc",
        description="Sample of Lace-corrected ancient Greek OCR data (page images + ground truth text)",
        repo="brobertson/Lace2",
        archive_url="https://github.com/brobertson/Lace2/archive/refs/heads/master.zip",
        estimated_size_mb=15,
        pair_count_estimate=200,
        format="image_text_pairs",
    ),
    # ── OpenGreekAndLatin datasets ──
    DatasetEntry(
        id="ogl_first1k_sample",
        name="First1KGreek Sample",
        source="ogl",
        language="grc",
        description="Sample texts from First Thousand Years of Greek (TEI XML) — generates synthetic training images",
        repo="OpenGreekAndLatin/First1KGreek",
        archive_url="https://github.com/OpenGreekAndLatin/First1KGreek/archive/refs/heads/master.zip",
        estimated_size_mb=50,
        pair_count_estimate=500,
        format="tei_xml",
    ),
    DatasetEntry(
        id="ogl_canonical_lat",
        name="Canonical Latin Texts",
        source="ogl",
        language="lat",
        description="Latin texts from canonical-latinLit (TEI XML) — generates synthetic training images",
        repo="OpenGreekAndLatin/canonical-latinLit",
        archive_url="https://github.com/OpenGreekAndLatin/canonical-latinLit/archive/refs/heads/master.zip",
        estimated_size_mb=30,
        pair_count_estimate=400,
        format="tei_xml",
    ),
]

_CATALOG_BY_ID = {d.id: d for d in DATASET_CATALOG}


# ── Directories ──

def get_datasets_dir() -> Path:
    """Platform-specific directory for cached dataset downloads."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif os.uname().sysname == "Darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))

    datasets_dir = base / "Ancient PDF Master" / "datasets"
    datasets_dir.mkdir(parents=True, exist_ok=True)
    return datasets_dir


# ── Catalog Queries ──

def list_available_datasets() -> list[dict]:
    """Return the built-in catalog as dicts."""
    return [asdict(d) for d in DATASET_CATALOG]


def list_downloaded_datasets() -> list[dict]:
    """Return metadata for already-downloaded datasets."""
    datasets_dir = get_datasets_dir()
    results = []
    for meta_file in sorted(datasets_dir.glob("*/metadata.json")):
        try:
            meta = json.loads(meta_file.read_text())
            meta["path"] = str(meta_file.parent)
            results.append(meta)
        except (json.JSONDecodeError, OSError):
            continue
    return results


# ── Download ──

def download_dataset(dataset_id: str, progress_callback=None) -> dict:
    """Download a dataset archive from GitHub and extract it.

    Args:
        dataset_id: ID from the catalog.
        progress_callback: fn(bytes_downloaded, total_bytes, message)

    Returns:
        dict with keys: dataset_id, path, files_count
    """
    entry = _CATALOG_BY_ID.get(dataset_id)
    if not entry:
        raise ValueError(f"Unknown dataset: {dataset_id}")

    dest_dir = get_datasets_dir() / dataset_id
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
    dest_dir.mkdir(parents=True)

    _cancel_flag.clear()

    # Download ZIP
    if progress_callback:
        progress_callback(0, 0, f"Downloading {entry.name}...")

    zip_path = dest_dir / "archive.zip"
    _download_file(entry.archive_url, zip_path, progress_callback)

    if _cancel_flag.is_set():
        shutil.rmtree(dest_dir, ignore_errors=True)
        raise ValueError("Download cancelled.")

    # Extract
    if progress_callback:
        progress_callback(0, 0, "Extracting archive...")

    files_count = _extract_zip(zip_path, dest_dir)
    zip_path.unlink(missing_ok=True)

    # Save metadata
    meta = asdict(entry)
    meta["downloaded"] = True
    meta["files_count"] = files_count
    (dest_dir / "metadata.json").write_text(json.dumps(meta, indent=2))

    if progress_callback:
        progress_callback(1, 1, f"Downloaded {entry.name} ({files_count} files)")

    return {"dataset_id": dataset_id, "path": str(dest_dir), "files_count": files_count}


def _download_file(url: str, dest: Path, progress_callback=None) -> None:
    """Download a URL to a local file with progress reporting."""
    req = urllib.request.Request(url, headers={"User-Agent": "Ancient-PDF-Master/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        chunk_size = 64 * 1024

        with open(dest, "wb") as f:
            while True:
                if _cancel_flag.is_set():
                    return
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if progress_callback and total > 0:
                    progress_callback(
                        downloaded, total,
                        f"Downloading... {downloaded // (1024 * 1024)}MB / {total // (1024 * 1024)}MB"
                    )


def _extract_zip(zip_path: Path, dest_dir: Path) -> int:
    """Extract a ZIP archive, returning the number of extracted files."""
    count = 0
    with zipfile.ZipFile(zip_path, "r") as zf:
        for info in zf.infolist():
            if _cancel_flag.is_set():
                return count
            if info.is_dir():
                continue
            # Flatten: strip the top-level directory GitHub adds
            parts = info.filename.split("/", 1)
            if len(parts) < 2:
                continue
            rel_path = parts[1]
            if not rel_path:
                continue
            out_path = dest_dir / rel_path
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(out_path, "wb") as dst:
                shutil.copyfileobj(src, dst)
            count += 1
    return count


# ── Lace Conversion ──

_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp"}


def convert_lace_dataset(
    source_dir: str,
    output_dir: str,
    progress_callback=None,
) -> dict:
    """Convert Lace dataset to training format (line_NNNN.png + line_NNNN.gt.txt).

    Lace data can be:
    - Line-level: image files with matching .gt.txt or .txt files
    - Page-level: full page images with text files (needs splitting)

    Returns: dict with keys: pairs, output_dir, warnings
    """
    src = Path(source_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    warnings = []
    _cancel_flag.clear()

    # Find image + text pairs
    pairs = _find_lace_pairs(src)

    if not pairs:
        # Try to find page-level images and split them
        page_images = _find_images_recursive(src)
        if page_images:
            if progress_callback:
                progress_callback(0, len(page_images), "Splitting page images into lines...")
            pairs = _split_pages_to_lines(page_images, out, progress_callback)
        else:
            raise ValueError(f"No image files found in {source_dir}")

    # Write normalized training pairs
    total = len(pairs)
    if progress_callback:
        progress_callback(0, total, f"Converting {total} pairs...")

    written = 0
    for i, (img_path, text) in enumerate(pairs):
        if _cancel_flag.is_set():
            raise ValueError("Conversion cancelled.")

        name = f"line_{i:04d}"
        try:
            img = Image.open(img_path)
            img.save(out / f"{name}.png")
            (out / f"{name}.gt.txt").write_text(text.strip(), encoding="utf-8")
            written += 1
        except Exception as e:
            warnings.append(f"Skipped {img_path.name}: {e}")

        if progress_callback:
            progress_callback(i + 1, total, f"Converted {i + 1}/{total}")

    return {"pairs": written, "output_dir": str(out), "warnings": warnings}


def _find_lace_pairs(directory: Path) -> list[tuple[Path, str]]:
    """Find image + ground truth text pairs in a Lace export."""
    pairs = []
    for img_file in sorted(directory.rglob("*")):
        if img_file.suffix.lower() not in _IMAGE_EXTS:
            continue
        # Look for matching ground truth
        gt_file = img_file.with_suffix(".gt.txt")
        if not gt_file.exists():
            gt_file = img_file.with_suffix(".txt")
        if gt_file.exists():
            text = gt_file.read_text(encoding="utf-8").strip()
            if text:
                pairs.append((img_file, text))
    return pairs


def _find_images_recursive(directory: Path) -> list[Path]:
    """Find all image files recursively."""
    return sorted(
        f for f in directory.rglob("*")
        if f.suffix.lower() in _IMAGE_EXTS and f.is_file()
    )


def _split_pages_to_lines(
    page_images: list[Path],
    output_dir: Path,
    progress_callback=None,
) -> list[tuple[Path, str]]:
    """Split page images into line images using Tesseract detection."""
    import pytesseract
    from pytesseract import Output

    pairs = []
    line_idx = 0

    for page_num, img_path in enumerate(page_images):
        if _cancel_flag.is_set():
            break

        img = Image.open(img_path)
        data = pytesseract.image_to_data(img, lang="grc", output_type=Output.DICT)

        # Group by line
        lines: dict[tuple, list] = {}
        for i in range(len(data["text"])):
            text = data["text"][i].strip()
            if not text or float(data["conf"][i]) < 0:
                continue
            key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
            if key not in lines:
                lines[key] = {"x1": 99999, "y1": 99999, "x2": 0, "y2": 0, "words": []}
            ln = lines[key]
            ln["x1"] = min(ln["x1"], data["left"][i])
            ln["y1"] = min(ln["y1"], data["top"][i])
            ln["x2"] = max(ln["x2"], data["left"][i] + data["width"][i])
            ln["y2"] = max(ln["y2"], data["top"][i] + data["height"][i])
            ln["words"].append(text)

        # Extract each line
        for key in sorted(lines.keys()):
            ln = lines[key]
            if not ln["words"]:
                continue
            pad = 5
            x1 = max(0, ln["x1"] - pad)
            y1 = max(0, ln["y1"] - pad)
            x2 = min(img.width, ln["x2"] + pad)
            y2 = min(img.height, ln["y2"] + pad)
            line_img = img.crop((x1, y1, x2, y2))
            line_text = " ".join(ln["words"])

            name = f"line_{line_idx:04d}"
            line_img_path = output_dir / f"{name}.png"
            line_img.save(line_img_path)
            (output_dir / f"{name}.gt.txt").write_text(line_text, encoding="utf-8")
            pairs.append((line_img_path, line_text))
            line_idx += 1

        if progress_callback:
            progress_callback(page_num + 1, len(page_images),
                              f"Split page {page_num + 1}/{len(page_images)} ({line_idx} lines)")

    return pairs


# ── OGL TEI XML Conversion ──

# TEI namespace
_TEI_NS = {"tei": "http://www.tei-c.org/ns/1.0"}


def parse_tei_xml(xml_path: str) -> list[str]:
    """Extract text lines from a TEI XML file.

    Handles both namespaced and non-namespaced TEI.
    Returns list of non-empty text lines.
    """
    tree = ET.parse(xml_path)
    root = tree.getroot()

    # Try namespaced first
    body = root.find(".//tei:body", _TEI_NS)
    if body is None:
        # Try without namespace
        body = root.find(".//{http://www.tei-c.org/ns/1.0}body")
    if body is None:
        body = root.find(".//body")
    if body is None:
        # Fall back to full document text
        body = root

    text = _extract_element_text(body)
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    return lines


def _extract_element_text(element) -> str:
    """Recursively extract all text from an XML element."""
    parts = []
    if element.text:
        parts.append(element.text)
    for child in element:
        parts.append(_extract_element_text(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


def generate_synthetic_training_data(
    text_lines: list[str],
    output_dir: str,
    font_path: str = "",
    font_size: int = 32,
    dpi: int = 300,
    progress_callback=None,
) -> dict:
    """Render text lines as images to create synthetic training pairs.

    For each line, creates:
    - line_NNNN.png — rendered text image
    - line_NNNN.gt.txt — the text itself

    Returns: dict with pairs, output_dir
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    _cancel_flag.clear()

    font = _find_font(font_path, font_size)
    total = len(text_lines)
    written = 0

    for i, text in enumerate(text_lines):
        if _cancel_flag.is_set():
            raise ValueError("Generation cancelled.")
        if not text.strip():
            continue

        # Render text to image
        img = _render_text_line(text, font, dpi)
        name = f"line_{i:04d}"
        img.save(out / f"{name}.png")
        (out / f"{name}.gt.txt").write_text(text.strip(), encoding="utf-8")
        written += 1

        if progress_callback and i % 50 == 0:
            progress_callback(i + 1, total, f"Generated {i + 1}/{total} images")

    if progress_callback:
        progress_callback(total, total, f"Generated {written} training pairs")

    return {"pairs": written, "output_dir": str(out)}


def _find_font(font_path: str, size: int) -> ImageFont.FreeTypeFont:
    """Find a suitable font for rendering Greek/Latin text."""
    if font_path and Path(font_path).exists():
        return ImageFont.truetype(font_path, size)

    # Search common locations for Noto Serif / DejaVu / similar
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
        "/usr/share/fonts/noto/NotoSerif-Regular.ttf",
        "/usr/share/fonts/TTF/NotoSerif-Regular.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",
        # macOS
        "/Library/Fonts/Times New Roman.ttf",
        "/System/Library/Fonts/Supplemental/Times New Roman.ttf",
        "/System/Library/Fonts/Times.ttc",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue

    # Fall back to default
    return ImageFont.load_default()


def _render_text_line(text: str, font, dpi: int) -> Image.Image:
    """Render a single line of text as a PIL Image."""
    # Measure text size
    dummy = Image.new("L", (1, 1))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0] + 20  # padding
    h = bbox[3] - bbox[1] + 16

    # Render
    img = Image.new("L", (max(w, 10), max(h, 10)), color=255)
    draw = ImageDraw.Draw(img)
    draw.text((10, 8 - bbox[1]), text, font=font, fill=0)
    return img


def convert_ogl_dataset(
    source_dir: str,
    output_dir: str,
    mode: str = "synthetic",
    font_path: str = "",
    progress_callback=None,
) -> dict:
    """Convert OGL TEI XML files to training data.

    mode="synthetic": parse XML -> extract lines -> render as images
    mode="text_only": parse XML -> save .gt.txt files only (user provides images)

    Returns: dict with pairs, output_dir, warnings
    """
    src = Path(source_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    warnings = []
    _cancel_flag.clear()

    # Find all XML files
    xml_files = sorted(src.rglob("*.xml"))
    if not xml_files:
        raise ValueError(f"No XML files found in {source_dir}")

    if progress_callback:
        progress_callback(0, len(xml_files), f"Parsing {len(xml_files)} XML files...")

    # Extract text from all XML files
    all_lines = []
    for i, xml_file in enumerate(xml_files):
        if _cancel_flag.is_set():
            raise ValueError("Conversion cancelled.")
        try:
            lines = parse_tei_xml(str(xml_file))
            # Filter: skip very short or very long lines
            lines = [ln for ln in lines if 5 <= len(ln) <= 200]
            all_lines.extend(lines)
        except ET.ParseError as e:
            warnings.append(f"Skipped {xml_file.name}: {e}")
        except Exception as e:
            warnings.append(f"Error in {xml_file.name}: {e}")

        if progress_callback:
            progress_callback(i + 1, len(xml_files), f"Parsed {i + 1}/{len(xml_files)} files")

    if not all_lines:
        raise ValueError("No text extracted from XML files.")

    # Cap at a reasonable number of lines for training
    max_lines = 2000
    if len(all_lines) > max_lines:
        # Sample evenly across the corpus
        step = len(all_lines) / max_lines
        all_lines = [all_lines[int(i * step)] for i in range(max_lines)]

    if mode == "text_only":
        # Just save the text files
        for i, text in enumerate(all_lines):
            (out / f"line_{i:04d}.gt.txt").write_text(text.strip(), encoding="utf-8")
        return {"pairs": 0, "text_files": len(all_lines), "output_dir": str(out), "warnings": warnings}

    # Generate synthetic images
    if progress_callback:
        progress_callback(0, len(all_lines), "Generating synthetic training images...")

    result = generate_synthetic_training_data(
        all_lines, str(out), font_path=font_path, progress_callback=progress_callback,
    )
    result["warnings"] = warnings
    return result


# ── Delete ──

def delete_dataset(dataset_id: str) -> bool:
    """Remove a downloaded dataset from the cache."""
    dest_dir = get_datasets_dir() / dataset_id
    if dest_dir.exists():
        shutil.rmtree(dest_dir)
        return True
    return False


def cancel_dataset_operation():
    """Cancel any in-progress download or conversion."""
    _cancel_flag.set()
