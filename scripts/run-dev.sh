#!/bin/bash
# Quick-start for development (no .app build needed)
# Usage: ./scripts/run-dev.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$(dirname "$SCRIPT_DIR")"

echo "=== Ancient PDF Master - Dev Mode ==="

# Check critical dependencies
for cmd in python3 node tesseract; do
  if ! command -v "$cmd" &>/dev/null; then
    echo "ERROR: $cmd not found. Run ./scripts/install-mac.sh first."
    exit 1
  fi
done

# Ensure Python deps are installed
if ! python3 -c "import pytesseract" 2>/dev/null; then
  echo "Installing Python dependencies..."
  pip3 install -e . --quiet
fi

# Ensure Node deps are installed
if [ ! -d "node_modules" ]; then
  echo "Installing Node.js dependencies..."
  npm install
fi

echo "Launching..."
npm start
