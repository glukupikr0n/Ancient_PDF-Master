#!/bin/bash
# Quick-start for development (no .app build needed)
# Usage: ./scripts/run-dev.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "=== Ancient PDF Master - Dev Mode ==="

# Check critical dependencies
for cmd in python3 node tesseract; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "ERROR: $cmd not found. Run ./scripts/install-mac.sh first."
    exit 1
  fi
done

# Setup venv if needed
VENV_DIR="$PROJECT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment..."
  python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

# Ensure Python deps are installed
if ! python3 -c "import pytesseract" 2>/dev/null; then
  echo "Installing Python dependencies..."
  pip install -e . --quiet
fi

# Ensure Node deps are installed
if [ ! -d "node_modules" ]; then
  echo "Installing Node.js dependencies..."
  npm install
fi

echo "Launching..."
npm start
