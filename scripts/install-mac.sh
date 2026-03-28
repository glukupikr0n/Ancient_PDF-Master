#!/bin/bash
# Install Ancient PDF Master as a macOS .app
# Usage: ./scripts/install-mac.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

APP_NAME="Ancient PDF Master"
APP_SUPPORT_DIR="$HOME/Library/Application Support/$APP_NAME"

echo "=== $APP_NAME — macOS Install ==="
echo ""

# ── 1. Check system dependencies ──
echo "[1/6] Checking system dependencies..."

# Check Homebrew
if ! command -v brew &>/dev/null; then
  echo "ERROR: Homebrew is required."
  echo "Install: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
  exit 1
fi

# Check Node.js
if ! command -v node &>/dev/null; then
  echo "  Installing Node.js..."
  brew install node
fi

NODE_VERSION=$(node -v | sed 's/v//' | cut -d. -f1)
if [ "$NODE_VERSION" -lt 18 ]; then
  echo "ERROR: Node.js 18+ required (found v$NODE_VERSION). Run: brew upgrade node"
  exit 1
fi
echo "  [OK] Node.js $(node -v)"

# Check Python 3 — prefer Homebrew over Xcode
PYTHON3=""
BREW_PYTHON="$(brew --prefix)/bin/python3"
if [ -x "$BREW_PYTHON" ]; then
  PYTHON3="$BREW_PYTHON"
elif command -v python3 &>/dev/null; then
  PY_PATH="$(which python3)"
  if [[ "$PY_PATH" == *"Xcode"* || "$PY_PATH" == *"CommandLineTools"* ]]; then
    echo "  Xcode Python detected — installing Homebrew Python..."
    brew install python3
    PYTHON3="$(brew --prefix)/bin/python3"
  else
    PYTHON3="python3"
  fi
else
  echo "  Installing Python 3..."
  brew install python3
  PYTHON3="$(brew --prefix)/bin/python3"
fi
echo "  [OK] Python $($PYTHON3 --version)"

# Check Tesseract
if ! command -v tesseract &>/dev/null; then
  echo "  Installing Tesseract OCR..."
  brew install tesseract
fi
echo "  [OK] Tesseract $(tesseract --version 2>&1 | head -1)"

# Check Poppler
if ! command -v pdftoppm &>/dev/null; then
  echo "  Installing Poppler..."
  brew install poppler
fi
echo "  [OK] Poppler installed"

# Check qpdf (required by pikepdf if no pre-built wheel available)
if ! brew list qpdf &>/dev/null 2>&1; then
  echo "  Installing qpdf (needed by pikepdf)..."
  brew install qpdf
fi
echo "  [OK] qpdf installed"

# Check language packs
TESS_LANGS=$(tesseract --list-langs 2>&1)
NEED_LANG=false
for LANG_CODE in grc lat; do
  if ! echo "$TESS_LANGS" | grep -q "$LANG_CODE"; then
    NEED_LANG=true
    break
  fi
done

if [ "$NEED_LANG" = true ]; then
  echo "  Installing Tesseract language packs (Ancient Greek, Latin)..."
  brew install tesseract-lang
fi
echo "  [OK] Language packs: grc, lat, eng"
echo ""

# ── 2. Create Python venv in Application Support ──
echo "[2/6] Setting up Python environment..."
mkdir -p "$APP_SUPPORT_DIR"
VENV_DIR="$APP_SUPPORT_DIR/.venv"

if [ ! -d "$VENV_DIR" ]; then
  echo "  Creating virtual environment..."
  "$PYTHON3" -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

echo "  Upgrading pip..."
pip install --upgrade pip setuptools wheel --quiet 2>&1 || {
  echo "  WARNING: pip upgrade failed, continuing..."
}

echo "  Installing Python packages..."
# Set C/C++ flags so pikepdf can find qpdf headers if building from source
BREW_PREFIX="$(brew --prefix)"
export CFLAGS="-I$BREW_PREFIX/include"
export LDFLAGS="-L$BREW_PREFIX/lib"
export CPPFLAGS="-I$BREW_PREFIX/include"
export PKG_CONFIG_PATH="$BREW_PREFIX/lib/pkgconfig"

if ! pip install pytesseract Pillow pdf2image pikepdf reportlab 2>&1 | tail -3; then
  echo ""
  echo "ERROR: pip install failed."
  echo "  Try: $VENV_DIR/bin/pip install pytesseract Pillow pdf2image pikepdf reportlab"
  exit 1
fi
echo "  [OK] Python packages installed"
echo "  [OK] venv: $VENV_DIR"
echo ""

# Also create local .venv for dev mode (npm start)
LOCAL_VENV="$PROJECT_DIR/.venv"
if [ ! -d "$LOCAL_VENV" ]; then
  echo "  Creating local dev venv..."
  "$PYTHON3" -m venv "$LOCAL_VENV"
  "$LOCAL_VENV/bin/pip" install --upgrade pip --quiet 2>/dev/null || true
  "$LOCAL_VENV/bin/pip" install -e . --quiet 2>&1 || true
fi

# ── 3. Install Node.js dependencies ──
echo "[3/6] Installing Node.js dependencies..."
if ! npm install 2>&1 | tail -5; then
  echo "ERROR: npm install failed. Try: rm -rf node_modules && npm install"
  exit 1
fi
echo "  [OK] Node.js packages installed"
echo ""

# ── 4. Build .app bundle ──
echo "[4/6] Building .app bundle..."
if ! npx electron-builder --mac dir --config.mac.identity=null 2>&1 | tail -5; then
  echo ""
  echo "WARNING: .app build failed. You can still run: npm start"
  echo ""
fi

# ── 5. Copy to /Applications ──
APP_SRC=$(find dist -name "*.app" -maxdepth 3 -type d 2>/dev/null | head -1)

if [ -z "$APP_SRC" ]; then
  echo "WARNING: .app not found in dist/"
  echo "  You can run in dev mode: npm start"
  echo "  Or retry: npx electron-builder --mac dir --config.mac.identity=null"
  exit 0
fi

echo "[5/6] Installing to /Applications..."
if [ -d "/Applications/$APP_NAME.app" ]; then
  echo "  Removing previous installation..."
  rm -rf "/Applications/$APP_NAME.app"
fi

cp -R "$APP_SRC" "/Applications/$APP_NAME.app"
echo "  [OK] Installed to /Applications/$APP_NAME.app"
echo ""

# ── 6. Clear quarantine (so macOS doesn't block unsigned app) ──
echo "[6/6] Clearing quarantine attribute..."
xattr -rd com.apple.quarantine "/Applications/$APP_NAME.app" 2>/dev/null || true
echo "  [OK] Quarantine cleared"

echo ""
echo "==========================================="
echo "  Installation Complete!"
echo "==========================================="
echo ""
echo "  Launch:"
echo "    Spotlight:  Cmd+Space → '$APP_NAME'"
echo "    Finder:     /Applications/$APP_NAME.app"
echo "    Terminal:    open '/Applications/$APP_NAME.app'"
echo ""
echo "  Dev mode (no .app needed):"
echo "    npm start"
echo ""
echo "  If macOS still blocks the app:"
echo "    System Settings → Privacy & Security → Open Anyway"
echo ""
