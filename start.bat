@echo off
REM ───────────────────────────────────────────────
REM  Research Field Intelligence Tool — Launcher
REM ───────────────────────────────────────────────
echo.
echo  Research Field Intelligence Tool
echo  ================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Install Python 3.11+ first.
    pause
    exit /b 1
)

REM Install dependencies if needed
if not exist ".venv" (
    echo Creating virtual environment...
    python -m venv .venv
)
call .venv\Scripts\activate.bat

echo Installing dependencies...
pip install -q -r requirements.txt

REM Check Ollama
echo.
echo Checking Ollama...
curl -s http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
    echo [WARN] Ollama is not running. LLM features will use heuristic fallback.
    echo       Start Ollama and pull a model: ollama pull qwen3.5-reasoning
) else (
    echo [OK] Ollama is running.
)

REM Start FastAPI backend
echo.
echo Starting FastAPI backend on http://localhost:8000 ...
start "FastAPI Backend" cmd /c ".venv\Scripts\python.exe -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000"

REM Wait for backend
timeout /t 3 /nobreak >nul

REM Start Streamlit UI
echo Starting Streamlit UI on http://localhost:8501 ...
start "Streamlit UI" cmd /c ".venv\Scripts\streamlit run src/ui/app.py --server.port 8501"

echo.
echo  Both services are starting:
echo    Backend:  http://localhost:8000/docs
echo    UI:       http://localhost:8501
echo.
echo  Close this window to stop.
pause
