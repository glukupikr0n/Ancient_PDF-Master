#!/bin/bash
# Quick-start for development (no .app build needed)
# Usage: ./scripts/run-dev.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "=== Ancient PDF Master - Dev Mode ==="

# Check critical dependencies
for cmd in node tesseract; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "ERROR: $cmd not found."
    echo ""
    if [ "$cmd" = "tesseract" ]; then
      echo "Install: brew install tesseract tesseract-lang"
    elif [ "$cmd" = "node" ]; then
      echo "Install: brew install node"
    fi
    echo ""
    echo "Or run the full installer: ./scripts/install-mac.sh"
    exit 1
  fi
done

# Find best Python — prefer Homebrew over Xcode
PYTHON3=""
if command -v brew &>/dev/null; then
  BREW_PYTHON="$(brew --prefix)/bin/python3"
  [ -x "$BREW_PYTHON" ] && PYTHON3="$BREW_PYTHON"
fi
if [ -z "$PYTHON3" ]; then
  if command -v python3 &>/dev/null; then
    PYTHON3="python3"
  else
    echo "ERROR: python3 not found. Install: brew install python3"
    exit 1
  fi
fi

# Setup venv if needed
VENV_DIR="$PROJECT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment..."
  "$PYTHON3" -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

# Ensure pip is up to date
pip install --upgrade pip setuptools wheel --quiet 2>/dev/null || true

# Ensure Python deps are installed
if ! python3 -c "import pytesseract" 2>/dev/null; then
  echo "Installing Python dependencies..."
  # Set flags for pikepdf/qpdf compilation if needed
  if command -v brew &>/dev/null; then
    BREW_PREFIX="$(brew --prefix)"
    export CFLAGS="-I$BREW_PREFIX/include"
    export LDFLAGS="-L$BREW_PREFIX/lib"
    export CPPFLAGS="-I$BREW_PREFIX/include"
  fi
  if ! pip install -e . 2>&1 | tail -3; then
    echo ""
    echo "ERROR: pip install failed."
    echo "Try: brew install qpdf && $VENV_DIR/bin/pip install -e ."
    exit 1
  fi
fi

# Ensure Node deps are installed
if [ ! -d "node_modules" ]; then
  echo "Installing Node.js dependencies..."
  npm install
fi

echo "Launching..."
npm start
