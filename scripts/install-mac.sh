#!/bin/bash
# Install Ancient PDF Master as a macOS .app
# Usage: ./scripts/install-mac.sh
set -e

echo "=== Ancient PDF Master - macOS Install ==="
echo ""

# ── 1. Check system dependencies ──
echo "[1/5] Checking system dependencies..."

missing=()

if ! command -v brew &>/dev/null; then
  echo "ERROR: Homebrew is required. Install from https://brew.sh"
  exit 1
fi

if ! command -v tesseract &>/dev/null; then
  missing+=("tesseract")
fi

if ! command -v node &>/dev/null; then
  missing+=("node")
fi

if ! command -v python3 &>/dev/null; then
  missing+=("python3")
fi

# Check poppler (required by pdf2image)
if ! command -v pdftoppm &>/dev/null; then
  missing+=("poppler")
fi

if [ ${#missing[@]} -gt 0 ]; then
  echo "Installing missing dependencies: ${missing[*]}"
  brew install "${missing[@]}"
fi

# Install Tesseract language packs (Ancient Greek, Latin)
echo "Checking Tesseract language packs..."
TESS_LANGS=$(tesseract --list-langs 2>&1)
if ! echo "$TESS_LANGS" | grep -q "grc"; then
  echo "Installing tesseract language packs (includes Ancient Greek, Latin)..."
  brew install tesseract-lang
fi

echo "[OK] System dependencies ready"

# ── 2. Install Python backend ──
echo ""
echo "[2/5] Installing Python backend..."
pip3 install -e . --quiet
echo "[OK] Python backend installed"

# ── 3. Install Node.js dependencies ──
echo ""
echo "[3/5] Installing Node.js dependencies..."
npm install --silent
echo "[OK] Node.js dependencies installed"

# ── 4. Build .app bundle ──
echo ""
echo "[4/5] Building .app bundle..."
npx electron-builder --mac dir --config.mac.identity=null 2>&1 | tail -3
echo "[OK] App bundle built"

# ── 5. Copy to /Applications ──
APP_NAME="Ancient PDF Master"
APP_SRC=$(find dist -name "*.app" -maxdepth 3 | head -1)

if [ -z "$APP_SRC" ]; then
  echo "ERROR: .app bundle not found in dist/"
  exit 1
fi

echo ""
echo "[5/5] Installing to /Applications..."
if [ -d "/Applications/$APP_NAME.app" ]; then
  echo "Removing previous installation..."
  rm -rf "/Applications/$APP_NAME.app"
fi

cp -R "$APP_SRC" "/Applications/$APP_NAME.app"
echo "[OK] Installed to /Applications/$APP_NAME.app"

echo ""
echo "=== Installation Complete! ==="
echo ""
echo "You can now:"
echo "  1. Open from Spotlight: Cmd+Space → 'Ancient PDF Master'"
echo "  2. Open from Finder: /Applications/Ancient PDF Master.app"
echo "  3. Open from terminal: open '/Applications/Ancient PDF Master.app'"
echo ""
