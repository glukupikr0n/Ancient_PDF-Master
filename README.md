<p align="center">
  <img src="assets/icon.png" alt="Ancient PDF Master" width="128" height="128">
</p>

<h1 align="center">Ancient PDF Master</h1>

<p align="center">
  <strong>OCR tool for Ancient Greek, Latin, and English texts</strong><br>
  Turn scanned images and PDFs into fully searchable documents.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-blue" alt="Platform">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/electron-33-teal" alt="Electron">
  <img src="https://img.shields.io/badge/python-3.10%2B-yellow" alt="Python">
</p>

---

## Features

### OCR & Text Processing
- **Multi-language OCR** — Ancient Greek (`grc`), Latin (`lat`), and English (`eng`) simultaneously via Tesseract
- **Searchable PDF output** — Invisible text layer overlay enables copy, paste, and search in any PDF viewer
- **Line-by-line text rendering** — Continuous text selection across lines (not fragmented word boxes)
- **Smart confidence retry** — Re-OCR low-confidence words with alternative PSM modes; skips plausible text
- **Parallel OCR** — Multi-threaded processing (up to 4 threads) for faster batch jobs
- **Page range selection** — OCR only specific pages (e.g. `1-5, 8, 10-12`)

### Layout & Zones
- **Auto column detection** — Automatically detects single or double-column layouts per page
- **Two-column OCR** — Splits at the detected gap and OCRs each column independently
- **Zone presets** — Full Page, Left Margin, Both Margins, Body Only, Auto Detect
- **Custom zones** — Define arbitrary OCR regions with per-zone PSM and language settings
- **Auto text region detection** — Tesseract block-level analysis with draggable/resizable boxes

### Image Preprocessing
- **Auto deskew** — Two-pass correction (coarse ±10°, fine ±1°) using projection variance
- **Grayscale / Black & White** — With adjustable threshold
- **Denoise & Auto Contrast** — Clean up noisy scans
- **Per-page crop** — Interactive crop area with drag handles; apply to all pages

### Bilingual Split
- **Split bilingual PDFs** — Separate alternating-language pages into two files
- **Custom page assignment** — Assign pages to Language A, Language B, or Common (duplicated)
- **Full OCR on both** — Each split PDF is independently searchable

### Page Numbering & TOC
- **Roman + Arabic numbering** — Configurable page label ranges (i, ii, iii → 1, 2, 3)
- **Auto TOC detection** — Scans pages for "Title ... PageNum" patterns and heading structures
- **Manual TOC entry** — Add, edit, or import from text with hierarchical levels
- **PDF bookmarks** — TOC entries embedded as navigable PDF outline

### Desktop App
- **Dark-themed Electron GUI** — Clean macOS-native look with hidden title bar
- **Drag & drop** — Drop PDF/image files directly onto the app
- **Live preview** — Page navigation, zoom, overlay toggles for zones/crop/preprocessing
- **Interactive margin adjustment** — Drag handles for 4-edge margin control (top/bottom/left/right)
- **Auto-updater** — Checks GitHub Releases for new versions with one-click install
- **Cross-platform** — macOS (DMG), Linux (AppImage/deb), Windows (NSIS installer)

---

## Quick Start

### Prerequisites

| Dependency | macOS | Linux (Debian/Ubuntu) |
|------------|-------|-----------------------|
| Tesseract OCR | `brew install tesseract tesseract-lang` | `sudo apt install tesseract-ocr tesseract-ocr-grc tesseract-ocr-lat` |
| Poppler | `brew install poppler` | `sudo apt install poppler-utils` |
| Python 3.10+ | `brew install python3` | `sudo apt install python3 python3-venv` |
| Node.js 18+ | `brew install node` | [nodejs.org](https://nodejs.org/) |
| qpdf (for pikepdf) | `brew install qpdf` | `sudo apt install qpdf` |

### One-Line Install (macOS)

```bash
git clone https://github.com/glukupikr0n/Ancient_PDF-Master.git
cd Ancient_PDF-Master
./scripts/install-mac.sh
```

This installs all dependencies, builds the `.app` bundle, and copies it to `/Applications`.
Launch via **Spotlight (Cmd+Space) → "Ancient PDF Master"**.

### Development Mode

Run without building a `.app`:

```bash
git clone https://github.com/glukupikr0n/Ancient_PDF-Master.git
cd Ancient_PDF-Master

# Python virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -e .

# Node.js dependencies
npm install

# Launch
npm start
```

Or use the helper script:

```bash
./scripts/run-dev.sh
```

---

## Building Installers

| Platform | Command | Output |
|----------|---------|--------|
| macOS DMG | `npm run build:dmg` | `dist/Ancient PDF Master-1.0.0.dmg` |
| macOS .app | `npm run build:mac` | `dist/mac-universal/` |
| Linux AppImage | `npm run build:linux` | `dist/Ancient PDF Master-1.0.0.AppImage` |
| Linux .deb | `npm run build:linux` | `dist/ancient-pdf-master_1.0.0_amd64.deb` |
| Windows | `npm run build:win` | `dist/Ancient PDF Master Setup 1.0.0.exe` |

The Python backend is automatically bundled into the app's `resources/python/` directory.
On first launch, the app creates a virtual environment in the user's Application Support folder
and installs required Python packages.

---

## Architecture

```
┌─────────────────┐     IPC      ┌──────────────────┐   stdio JSON-RPC   ┌─────────────────┐
│  Electron GUI   │ ◄──────────► │   Main Process   │ ◄────────────────► │ Python Backend  │
│                 │              │                  │                    │                 │
│  renderer.js    │              │  index.js        │                    │  bridge.py      │
│  index.html     │              │  python-bridge.js│                    │  ocr_engine.py  │
│  main.css       │              │  preload.js      │                    │  pdf_builder.py │
│                 │              │  auto-updater.js │                    │  zone_ocr.py    │
└─────────────────┘              └──────────────────┘                    │  preprocess.py  │
                                                                        │  ...            │
                                                                        └─────────────────┘
```

**Communication protocol:** Newline-delimited JSON over stdin/stdout.
- Startup: Python sends `{"ready": true}` after import checks
- Request: `{"id": 1, "method": "start_ocr", "params": {...}}`
- Response: `{"id": 1, "result": {...}}`
- Progress: `{"id": null, "event": "progress", "data": {...}}`

---

## Project Structure

```
electron/
  main/
    index.js            # Electron main process, IPC handlers
    preload.js          # Context bridge (renderer ↔ main API)
    python-bridge.js    # Python child process manager, auto venv setup
    auto-updater.js     # GitHub Releases auto-update
  renderer/
    index.html          # UI layout
    renderer.js         # Frontend logic, preview, drag interactions
    styles/main.css     # Dark theme styles
src/ancient_pdf_master/
    bridge.py           # stdio JSON-RPC server, request dispatcher
    ocr_engine.py       # Tesseract wrapper, column detection, confidence retry
    pdf_builder.py      # Searchable PDF with invisible text layer
    pdf_splitter.py     # Bilingual PDF splitting
    zone_ocr.py         # Zone-based OCR (margins, body, columns)
    preprocess.py       # Deskew, denoise, B&W, contrast
    image_handler.py    # Image/PDF loading (PNG, JPG, TIFF, PDF)
    page_labels.py      # Roman/Arabic page numbering
    toc_builder.py      # TOC bookmark embedding
    language.py         # Language pack validation
scripts/
    install-mac.sh      # Full macOS install (deps + build + /Applications)
    run-dev.sh          # Quick dev launch
assets/
    icon.png            # App icon (1024×1024)
    icon.ico            # Windows icon
    entitlements.mac.plist
tests/
    test_*.py           # Unit tests (51 tests)
```

---

## Testing

```bash
source .venv/bin/activate
pip install -e ".[dev]"
python3 -m pytest
```

---

## Troubleshooting

| Symptom | Solution |
|---------|----------|
| `error: externally-managed-environment` | Activate venv first: `source .venv/bin/activate` |
| `pikepdf` build fails | Install qpdf: `brew install qpdf` (macOS) or `sudo apt install qpdf` (Linux) |
| `tesseract not found` | Install Tesseract + language packs (see Prerequisites) |
| `npm start` fails | Run `npm install`, ensure Node.js 18+ |
| macOS blocks the app | System Settings → Privacy & Security → Open Anyway |
| Python backend timeout | Check `~/.local/share/Ancient PDF Master/` (Linux) or `~/Library/Application Support/` (macOS) for venv issues |

---

## License

MIT
