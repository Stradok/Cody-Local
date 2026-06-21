#!/usr/bin/env bash
set -e

echo "=== Cody Local ==="

# Start backend
echo "[1/2] Starting backend..."
cd "$(dirname "$0")/backend"
if [ ! -d venv ]; then
  python3 -m venv venv
  ./venv/bin/pip install -r requirements.txt -q
fi
./venv/bin/uvicorn main:app --reload --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

# Start frontend
echo "[2/2] Starting frontend..."
cd "$(dirname "$0")/frontend"
npm install --silent 2>/dev/null
npx next dev --port 5173 &
FRONTEND_PID=$!

echo ""
echo "  Backend:  http://127.0.0.1:8000"
echo "  Frontend: http://localhost:5173"
echo "  API docs: http://127.0.0.1:8000/docs"
echo ""
echo "Press Ctrl+C to stop both"

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
