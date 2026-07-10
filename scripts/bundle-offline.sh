#!/usr/bin/env bash
# Bundle Cody-Local for offline distribution
# Creates a tar archive with all dependencies pre-installed

set -e

OUTPUT_FILE="${1:-.}/cody-local-offline.tar.gz"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "📦 Bundling Cody-Local for offline distribution..."
echo ""
echo "Source:  $SCRIPT_DIR"
echo "Output:  $OUTPUT_FILE"
echo ""

# Verify setup is complete
if [ ! -d "$SCRIPT_DIR/backend/venv" ]; then
  echo "❌ Backend not set up. Run: bash portable-setup.sh"
  exit 1
fi

if [ ! -d "$SCRIPT_DIR/frontend/node_modules" ]; then
  echo "❌ Frontend not set up. Run: bash portable-setup.sh"
  exit 1
fi

echo "Compressing... (this may take a minute)"

# Create archive, excluding unnecessary files
tar -czf "$OUTPUT_FILE" \
  --exclude='.git' \
  --exclude='.next' \
  --exclude='node_modules/.cache' \
  --exclude='backend/venv/lib/python3.*/site-packages/tests' \
  --exclude='backend/venv/lib/python3.*/site-packages/__pycache__' \
  --exclude='logs/*' \
  --exclude='*.log' \
  -C "$SCRIPT_DIR/.." \
  "$(basename "$SCRIPT_DIR")"

SIZE=$(du -h "$OUTPUT_FILE" | cut -f1)
echo ""
echo "✅ Bundle created!"
echo "   File:  $OUTPUT_FILE"
echo "   Size:  $SIZE"
echo ""
echo "To use:"
echo "  1. Transfer $OUTPUT_FILE to external drive or target machine"
echo "  2. Extract: tar -xzf $OUTPUT_FILE"
echo "  3. Run: cd cody-local && make run"
echo ""
echo "For models, transfer separately:"
echo "  tar -czf models.tar.gz ~/.ollama/models/"
