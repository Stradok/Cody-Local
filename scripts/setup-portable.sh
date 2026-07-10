#!/usr/bin/env bash
# Complete portable setup: dependencies + Ollama + models + app
# Run: bash scripts/setup-portable.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║           Cody-Local Portable Setup (Complete)                 ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "This script will:"
echo "  1. Check/install Ollama (if needed)"
echo "  2. Download recommended AI models"
echo "  3. Setup Python venv + Node dependencies"
echo "  4. Configure environment"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
log_step() { echo -e "${BLUE}▸ $1${NC}"; }
log_ok() { echo -e "${GREEN}✓ $1${NC}"; }
log_warn() { echo -e "${YELLOW}⚠ $1${NC}"; }
log_error() { echo -e "${RED}✗ $1${NC}"; }

# 1. Check prerequisites
echo -e "${BLUE}Step 1/4: Checking prerequisites...${NC}"
echo ""

MISSING=0

if ! command -v python3 &> /dev/null; then
  log_error "Python 3 not found"
  MISSING=1
else
  log_ok "Python 3 installed"
fi

if ! command -v node &> /dev/null; then
  log_error "Node.js not found"
  MISSING=1
else
  log_ok "Node.js installed"
fi

if [ $MISSING -eq 1 ]; then
  echo ""
  log_error "Missing dependencies. Install Python 3.11+ and Node.js 18+ first:"
  echo ""
  echo "  macOS (Homebrew):"
  echo "    brew install python@3.11 node"
  echo ""
  echo "  Ubuntu/Debian:"
  echo "    sudo apt-get install python3 nodejs"
  echo ""
  echo "  Windows: Download from python.org and nodejs.org"
  echo ""
  exit 1
fi

echo ""

# 2. Check/install Ollama
echo -e "${BLUE}Step 2/4: Setting up Ollama...${NC}"
echo ""

if command -v ollama &> /dev/null; then
  OLLAMA_VERSION=$(ollama --version)
  log_ok "Ollama already installed: $OLLAMA_VERSION"
else
  log_warn "Ollama not installed. Installing..."
  echo ""

  OS=$(uname -s)

  if [ "$OS" = "Darwin" ]; then
    # macOS
    if command -v brew &> /dev/null; then
      brew install ollama
      log_ok "Ollama installed via Homebrew"
    else
      echo "Visit https://ollama.ai to download Ollama for macOS"
      exit 1
    fi
  elif [ "$OS" = "Linux" ]; then
    # Linux
    echo "Installing Ollama for Linux..."
    curl -fsSL https://ollama.ai/install.sh | sh
    log_ok "Ollama installed"
  else
    echo "Unsupported OS. Visit https://ollama.ai to download"
    exit 1
  fi
fi

echo ""

# 3. Download models
echo -e "${BLUE}Step 3/4: Downloading AI models...${NC}"
echo ""

# Check if Ollama is running
if ! curl -s http://localhost:11434/api/health &>/dev/null; then
  log_warn "Ollama is not running. Starting Ollama in background..."
  echo ""
  echo "⏳ Wait a moment while Ollama starts..."

  if [ "$(uname -s)" = "Darwin" ]; then
    open -a Ollama &
  else
    ollama serve &
    OLLAMA_PID=$!
  fi

  # Wait for Ollama to be ready
  for i in {1..30}; do
    if curl -s http://localhost:11434/api/health &>/dev/null; then
      log_ok "Ollama is ready"
      break
    fi
    echo -ne "  Waiting... ($i/30)\r"
    sleep 1
  done
  echo ""
fi

# Download models
MODELS=(
  "qwen2.5-coder:1.5b"    # Main model - best for RAG + coding
  "nomic-embed-text"      # Embedding model for RAG
)

log_step "Pulling models (this may take 5-10 minutes)..."
echo ""

for model in "${MODELS[@]}"; do
  echo "  📥 Downloading $model..."
  ollama pull "$model"
  log_ok "$model ready"
done

echo ""
log_ok "Models downloaded successfully"
echo ""

# Verify models
echo "Available models:"
ollama list
echo ""

# 4. Setup Python + Node
echo -e "${BLUE}Step 4/4: Setting up application...${NC}"
echo ""

# Backend
log_step "Setting up backend..."
cd "$SCRIPT_DIR/backend"

if [ ! -d venv ]; then
  python3 -m venv venv
fi

./venv/bin/pip install -q -r requirements.txt
log_ok "Backend ready"

# Frontend
log_step "Setting up frontend..."
cd "$SCRIPT_DIR/frontend"

npm install --silent --no-audit
log_ok "Frontend ready"

# Environment
log_step "Configuring environment..."
if [ ! -f "$SCRIPT_DIR/backend/.env" ]; then
  cp "$SCRIPT_DIR/backend/.env.example" "$SCRIPT_DIR/backend/.env"
  log_ok ".env created"
else
  log_ok ".env already exists"
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                    ✅ Setup Complete!                          ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "🚀 To start Cody-Local:"
echo ""
echo "   cd $SCRIPT_DIR"
echo "   make run"
echo ""
echo "📖 Or use the portable setup:"
echo ""
echo "   bash portable-setup.sh  # Minimal setup"
echo "   make portable           # Complete portable setup with models"
echo ""
echo "🌐 Access the app:"
echo ""
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""
echo "📚 For offline/external drive deployment, see PORTABLE.md"
echo ""
