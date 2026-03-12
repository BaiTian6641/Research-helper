#!/usr/bin/env bash
# ───────────────────────────────────────────────
#  Research Field Intelligence Tool — Launcher
# ───────────────────────────────────────────────
set -e

echo ""
echo "  Research Field Intelligence Tool"
echo "  ================================"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "[ERROR] Python3 not found. Install Python 3.11+ first."
    exit 1
fi

# Virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi
source .venv/bin/activate

echo "Installing dependencies..."
pip install -q -r requirements.txt

# Check Ollama
echo ""
echo "Checking Ollama..."
if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    echo "[OK] Ollama is running."
else
    echo "[WARN] Ollama is not running. LLM features will use heuristic fallback."
    echo "       Start Ollama and pull a model: ollama pull qwen3.5-reasoning"
fi

# Start FastAPI backend
echo ""
echo "Starting FastAPI backend on http://localhost:8000 ..."
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!

# Wait for backend
sleep 3

# Start Streamlit UI
echo "Starting Streamlit UI on http://localhost:8501 ..."
streamlit run src/ui/app.py --server.port 8501 &
UI_PID=$!

echo ""
echo "  Both services are running:"
echo "    Backend:  http://localhost:8000/docs"
echo "    UI:       http://localhost:8501"
echo ""
echo "  Press Ctrl+C to stop."

# Cleanup on exit
trap "kill $BACKEND_PID $UI_PID 2>/dev/null" EXIT
wait
