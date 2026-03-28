#!/bin/bash
# Quick-start for development (no .app build needed)
# Usage: ./scripts/run-dev.sh
set -e

cd "$(dirname "$0")/.."

# Ensure Python deps are installed
pip3 install -e . --quiet 2>/dev/null

# Ensure Node deps are installed
if [ ! -d "node_modules" ]; then
  npm install --silent
fi

# Launch Electron in dev mode
npm start
