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

# Detect OS
OS=$(uname -s)
echo "Detected OS: $OS"
echo ""

# Check/install Python
echo "Checking Python..."
if ! command -v python3 &> /dev/null; then
  echo "⚠️  Python 3 not found. Installing..."

  if [ "$OS" = "Darwin" ]; then
    # macOS
    if command -v brew &> /dev/null; then
      echo "  Installing via Homebrew..."
      brew install python@3.11
    else
      echo "❌ Homebrew not found. Please install from https://brew.sh"
      echo "   Then run this script again."
      exit 1
    fi
  elif [ "$OS" = "Linux" ]; then
    # Linux
    if command -v apt &> /dev/null; then
      echo "  Installing via apt..."
      sudo apt-get update -qq
      sudo apt-get install -y python3 python3-venv python3-dev
    elif command -v yum &> /dev/null; then
      echo "  Installing via yum..."
      sudo yum install -y python3 python3-devel
    elif command -v pacman &> /dev/null; then
      echo "  Installing via pacman..."
      sudo pacman -S python
    else
      echo "❌ Could not find package manager. Please install Python 3.11+ manually."
      exit 1
    fi
  else
    echo "❌ Unsupported OS: $OS"
    echo "   Please install Python 3.11+ manually from https://python.org"
    exit 1
  fi
fi

# Check/install Node.js
echo "Checking Node.js..."
if ! command -v node &> /dev/null; then
  echo "⚠️  Node.js not found. Installing..."

  if [ "$OS" = "Darwin" ]; then
    # macOS
    if command -v brew &> /dev/null; then
      echo "  Installing via Homebrew..."
      brew install node
    else
      echo "❌ Homebrew not found. Please install from https://brew.sh"
      exit 1
    fi
  elif [ "$OS" = "Linux" ]; then
    # Linux - use NodeSource repo for latest version
    if command -v apt &> /dev/null; then
      echo "  Installing via apt..."
      sudo apt-get update -qq
      sudo apt-get install -y nodejs npm
    elif command -v yum &> /dev/null; then
      echo "  Installing via yum..."
      sudo yum install -y nodejs npm
    elif command -v pacman &> /dev/null; then
      echo "  Installing via pacman..."
      sudo pacman -S nodejs npm
    else
      echo "❌ Could not find package manager. Please install Node.js 18+ manually."
      exit 1
    fi
  else
    echo "❌ Unsupported OS: $OS"
    echo "   Please install Node.js 18+ manually from https://nodejs.org"
    exit 1
  fi
fi

echo ""
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
echo "All dependencies installed:"
echo "  ✓ Python 3 (installed/verified)"
echo "  ✓ Node.js (installed/verified)"
echo "  ✓ Python packages (venv + requirements)"
echo "  ✓ Node packages (npm dependencies)"
echo "  ✓ Environment config (.env)"
echo ""
echo "📖 NEXT STEPS (IMPORTANT):"
echo ""
echo "1. Make sure Ollama is installed and running:"
echo "   # Download from https://ollama.ai"
echo "   ollama serve"
echo ""
echo "2. Download AI models (one-time, takes 5-10 minutes):"
echo "   # Download qwen2.5-coder:1.5b or gemma2:9b"
echo "   ollama pull qwen2.5-coder:1.5b"
echo ""
echo "3. Start Cody-Local:"
echo "   cd \"$SCRIPT_DIR\""
echo "   make run"
echo ""
echo "4. Open in browser:"
echo "   http://localhost:3000"
echo ""
echo "5. (Optional) Add GitHub token:"
echo "   Edit: $SCRIPT_DIR/backend/.env"
echo ""
echo "🚀 That's it! You're ready to code offline."
echo ""
echo "For offline deployment on USB/external drive, see PORTABLE.md"
