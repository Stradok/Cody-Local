#!/usr/bin/env bash
# Portable setup for Cody-Local
# Works from any location: external drive, local machine, USB stick, etc.
# No internet required after downloading dependencies

set -e

# Get the script's directory (works even if called from different dir)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "🚀 Cody-Local Portable Setup"
echo "================================"
echo ""
echo "Location: $SCRIPT_DIR"
echo ""

# Check prerequisites
echo "Checking prerequisites..."
if ! command -v python3 &> /dev/null; then
  echo "❌ Python 3 not found. Please install Python 3.11+ first."
  exit 1
fi

if ! command -v node &> /dev/null; then
  echo "❌ Node.js not found. Please install Node.js 18+ first."
  exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
NODE_VERSION=$(node --version)
echo "✓ Python $PYTHON_VERSION"
echo "✓ Node $NODE_VERSION"
echo ""

# Setup backend
echo "📦 Setting up backend..."
cd "$SCRIPT_DIR/backend"

if [ ! -d venv ]; then
  echo "  Creating virtual environment..."
  python3 -m venv venv
fi

echo "  Installing Python dependencies..."
./venv/bin/pip install -q -r requirements.txt

echo "✓ Backend ready"
echo ""

# Setup frontend
echo "📦 Setting up frontend..."
cd "$SCRIPT_DIR/frontend"

echo "  Installing Node.js dependencies..."
npm install --silent --no-audit

echo "✓ Frontend ready"
echo ""

# Setup .env if it doesn't exist
echo "⚙️  Configuring environment..."
if [ ! -f "$SCRIPT_DIR/backend/.env" ]; then
  echo "  Creating .env from .env.example..."
  cp "$SCRIPT_DIR/backend/.env.example" "$SCRIPT_DIR/backend/.env"
  echo "  ✓ .env created. Edit it to add your GitHub token if needed."
else
  echo "  ✓ .env already exists"
fi

echo ""
echo "================================"
echo "✅ Setup complete!"
echo ""
echo "📖 Next steps:"
echo ""
echo "1. To start Cody-Local:"
echo "   cd \"$SCRIPT_DIR\""
echo "   make run"
echo ""
echo "2. Make sure Ollama is running:"
echo "   ollama serve"
echo ""
echo "3. (Optional) Edit .env for GitHub token:"
echo "   nano $SCRIPT_DIR/backend/.env"
echo ""
echo "4. Open http://localhost:3000 in your browser"
echo ""
echo "For offline mode, see PORTABLE.md for pre-downloading models."
