@echo off
setlocal EnableDelayedExpansion
REM =============================================================
REM  Research Field Intelligence Tool -- Launcher
REM  Auto-detects GPU platform, installs deps, starts services
REM =============================================================
echo.
echo  Research Field Intelligence Tool
echo  ================================
echo.

REM =============================================================
REM  STEP 1 -- Detect GPU platform (PowerShell / Get-CimInstance)
REM =============================================================
echo [1/5] Detecting GPU platform...
set GPU_PLATFORM=cpu
set "GPU_NAME=Unknown"

for /f "usebackq delims=" %%G in (`powershell -NoProfile -Command "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name"`) do (
    echo %%G | findstr /i "Arc" >nul 2>&1
    if not errorlevel 1 (
        if "!GPU_PLATFORM!"=="cpu" (
            set GPU_PLATFORM=intel_arc
            set "GPU_NAME=%%G"
        )
    )
    echo %%G | findstr /i "NVIDIA" >nul 2>&1
    if not errorlevel 1 (
        if "!GPU_PLATFORM!"=="cpu" (
            set GPU_PLATFORM=nvidia
            set "GPU_NAME=%%G"
        )
    )
    echo %%G | findstr /i "AMD Radeon" >nul 2>&1
    if not errorlevel 1 (
        if "!GPU_PLATFORM!"=="cpu" (
            set GPU_PLATFORM=amd
            set "GPU_NAME=%%G"
        )
    )
)

if "!GPU_PLATFORM!"=="intel_arc" (
    echo [OK] Intel Arc GPU detected: !GPU_NAME!
) else if "!GPU_PLATFORM!"=="nvidia" (
    echo [OK] NVIDIA GPU detected: !GPU_NAME!
) else if "!GPU_PLATFORM!"=="amd" (
    echo [WARN] AMD GPU detected: !GPU_NAME! ^(CPU-only -- ROCm not supported on Windows^)
) else (
    echo [WARN] No dedicated GPU found. CPU-only mode.
)

REM =============================================================
REM  STEP 2 -- Locate conda
REM =============================================================
echo.
echo [2/5] Locating conda...
set "CONDA_EXE="

if exist "%USERPROFILE%\.conda\Scripts\conda.exe"      set "CONDA_EXE=%USERPROFILE%\.conda\Scripts\conda.exe"
if not defined CONDA_EXE (
if exist "C:\ProgramData\miniforge3\Scripts\conda.exe" set "CONDA_EXE=C:\ProgramData\miniforge3\Scripts\conda.exe"
)
if not defined CONDA_EXE (
if exist "%USERPROFILE%\miniforge3\Scripts\conda.exe"  set "CONDA_EXE=%USERPROFILE%\miniforge3\Scripts\conda.exe"
)
if not defined CONDA_EXE (
if exist "C:\ProgramData\miniconda3\Scripts\conda.exe" set "CONDA_EXE=C:\ProgramData\miniconda3\Scripts\conda.exe"
)
if not defined CONDA_EXE (
if exist "%USERPROFILE%\miniconda3\Scripts\conda.exe"  set "CONDA_EXE=%USERPROFILE%\miniconda3\Scripts\conda.exe"
)
if not defined CONDA_EXE (
if exist "C:\ProgramData\anaconda3\Scripts\conda.exe"  set "CONDA_EXE=C:\ProgramData\anaconda3\Scripts\conda.exe"
)
if not defined CONDA_EXE (
if exist "%USERPROFILE%\anaconda3\Scripts\conda.exe"   set "CONDA_EXE=%USERPROFILE%\anaconda3\Scripts\conda.exe"
)
if not defined CONDA_EXE (
    where conda >nul 2>&1
    if not errorlevel 1 set "CONDA_EXE=conda"
)

if not defined CONDA_EXE (
    echo [ERROR] Conda not found. Please install Miniforge:
    echo         https://conda-forge.org/download/
    pause
    exit /b 1
)
echo [OK] Conda: %CONDA_EXE%

REM =============================================================
REM  STEP 3 -- Create / verify conda env "llm" + install packages
REM =============================================================
echo.
echo [3/5] Checking conda env "llm"...

set "CONDA_ENV_PYTHON="
set "CONDA_ENV_SCRIPTS="

if exist "%USERPROFILE%\.conda\envs\llm\python.exe" (
    set "CONDA_ENV_PYTHON=%USERPROFILE%\.conda\envs\llm\python.exe"
    set "CONDA_ENV_SCRIPTS=%USERPROFILE%\.conda\envs\llm\Scripts"
)
if not defined CONDA_ENV_PYTHON (
if exist "C:\ProgramData\miniforge3\envs\llm\python.exe" (
    set "CONDA_ENV_PYTHON=C:\ProgramData\miniforge3\envs\llm\python.exe"
    set "CONDA_ENV_SCRIPTS=C:\ProgramData\miniforge3\envs\llm\Scripts"
))
if not defined CONDA_ENV_PYTHON (
if exist "%USERPROFILE%\miniforge3\envs\llm\python.exe" (
    set "CONDA_ENV_PYTHON=%USERPROFILE%\miniforge3\envs\llm\python.exe"
    set "CONDA_ENV_SCRIPTS=%USERPROFILE%\miniforge3\envs\llm\Scripts"
))
if not defined CONDA_ENV_PYTHON (
if exist "C:\ProgramData\miniconda3\envs\llm\python.exe" (
    set "CONDA_ENV_PYTHON=C:\ProgramData\miniconda3\envs\llm\python.exe"
    set "CONDA_ENV_SCRIPTS=C:\ProgramData\miniconda3\envs\llm\Scripts"
))
if not defined CONDA_ENV_PYTHON (
if exist "%USERPROFILE%\miniconda3\envs\llm\python.exe" (
    set "CONDA_ENV_PYTHON=%USERPROFILE%\miniconda3\envs\llm\python.exe"
    set "CONDA_ENV_SCRIPTS=%USERPROFILE%\miniconda3\envs\llm\Scripts"
))

if not defined CONDA_ENV_PYTHON (
    echo [INFO] Env "llm" not found. Creating with Python 3.11...
    "%CONDA_EXE%" create -n llm python=3.11 -y
    if errorlevel 1 ( echo [ERROR] Failed to create conda env. & pause & exit /b 1 )
    if exist "%USERPROFILE%\.conda\envs\llm\python.exe" (
        set "CONDA_ENV_PYTHON=%USERPROFILE%\.conda\envs\llm\python.exe"
        set "CONDA_ENV_SCRIPTS=%USERPROFILE%\.conda\envs\llm\Scripts"
    )
    if not defined CONDA_ENV_PYTHON (
        echo [ERROR] Env created but python.exe not found. Check conda config.
        pause & exit /b 1
    )
)
echo [OK] Env python: %CONDA_ENV_PYTHON%

REM -- Install / verify PyTorch backend
"%CONDA_ENV_PYTHON%" -c "import torch" >nul 2>&1
if errorlevel 1 (
    echo [INFO] PyTorch not found. Installing for platform: !GPU_PLATFORM!...
    if "!GPU_PLATFORM!"=="intel_arc" (
        "%CONDA_ENV_PYTHON%" -m pip install --pre --upgrade "ipex-llm[xpu_2.6]" --extra-index-url https://download.pytorch.org/whl/xpu
    ) else if "!GPU_PLATFORM!"=="nvidia" (
        "%CONDA_ENV_PYTHON%" -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
    ) else (
        "%CONDA_ENV_PYTHON%" -m pip install torch torchvision torchaudio
    )
    if errorlevel 1 ( echo [ERROR] PyTorch install failed. & pause & exit /b 1 )
    echo [OK] PyTorch installed.
) else (
    echo [OK] PyTorch already present.
)

REM -- Install / verify project requirements
"%CONDA_ENV_PYTHON%" -c "import fastapi, streamlit, sqlalchemy" >nul 2>&1
if errorlevel 1 (
    echo [INFO] Project packages missing. Installing requirements...
    "%CONDA_ENV_PYTHON%" -m pip install -q -r requirements.txt -r requirements-llm.txt
    if errorlevel 1 ( echo [ERROR] requirements install failed. & pause & exit /b 1 )
    echo [OK] Requirements installed.
) else (
    echo [OK] Project requirements already satisfied.
)

REM =============================================================
REM  STEP 4 -- Download GGUF + launch llama-server (llama.cpp)
REM  Uses OpenAI-compatible API on port 8080
REM  Supports all GGUF architectures (qwen35, etc.) natively
REM =============================================================
echo.
echo [4/5] Setting up llama-server (llama.cpp)...

REM -- Common GGUF paths
set "GGUF_DIR=%USERPROFILE%\ollama-models"
set "GGUF_FILE=!GGUF_DIR!\Qwen3.5-27B.Q4_K_M.gguf"
set "GGUF_URL=https://huggingface.co/Jackrong/Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled-GGUF/resolve/main/Qwen3.5-27B.Q4_K_M.gguf"

REM -- Select llama.cpp binary variant by GPU platform
if "!GPU_PLATFORM!"=="intel_arc" (
    set "LLAMA_FILTER=*sycl*x64*"
    set "LLAMA_DIR=%USERPROFILE%\llama-cpp-sycl"
    set "LLAMA_NGL=99"
) else if "!GPU_PLATFORM!"=="nvidia" (
    set "LLAMA_FILTER=*cuda-cu12*x64*"
    set "LLAMA_DIR=%USERPROFILE%\llama-cpp-cuda"
    set "LLAMA_NGL=99"
) else (
    set "LLAMA_FILTER=*avx2*x64*"
    set "LLAMA_DIR=%USERPROFILE%\llama-cpp-avx2"
    set "LLAMA_NGL=0"
)
set "LLAMA_EXE=!LLAMA_DIR!\llama-server.exe"
set "LLAMA_ZIP=%TEMP%\llama-cpp.zip"

REM -- Intel Arc: verify XPU and set Level Zero env vars
if "!GPU_PLATFORM!"=="intel_arc" (
    "%CONDA_ENV_PYTHON%" -c "import torch; assert torch.xpu.is_available()" >nul 2>&1
    if errorlevel 1 (
        echo [WARN] XPU not accessible. Check driver at:
        echo        https://www.intel.com/content/www/us/en/download/785597/
    ) else (
        echo [OK] Intel Arc XPU backend ready.
    )
    set ONEAPI_DEVICE_SELECTOR=level_zero:0
    set ZES_ENABLE_SYSMAN=1
    set SYCL_PI_LEVEL_ZERO_USE_IMMEDIATE_COMMANDLISTS=1
) else if "!GPU_PLATFORM!"=="nvidia" (
    "%CONDA_ENV_PYTHON%" -c "import torch; assert torch.cuda.is_available()" >nul 2>&1
    if errorlevel 1 (
        echo [WARN] NVIDIA CUDA not accessible. Check CUDA drivers.
    ) else (
        echo [OK] NVIDIA CUDA ready.
    )
) else (
    echo [INFO] CPU-only mode.
)

REM -- Auto-download llama.cpp binary if llama-server.exe is missing
if not exist "!LLAMA_EXE!" (
    echo [INFO] Fetching latest llama.cpp release URL for !LLAMA_FILTER!...
    powershell -NoProfile -Command "$r=Invoke-RestMethod 'https://api.github.com/repos/ggml-org/llama.cpp/releases/latest'; $a=$r.assets|Where-Object{$_.name -like '!LLAMA_FILTER!'}; if($a){$a[0].browser_download_url}else{''}" > "%TEMP%\llama_url.txt" 2>nul
    set /p LLAMA_DL_URL=<"%TEMP%\llama_url.txt"
    del "%TEMP%\llama_url.txt" >nul 2>&1
    if "!LLAMA_DL_URL!"=="" (
        echo [WARN] Could not find a llama.cpp release matching !LLAMA_FILTER!
        echo        Download manually from https://github.com/ggml-org/llama.cpp/releases
        echo        and place llama-server.exe in: !LLAMA_DIR!
    ) else (
        echo [INFO] Downloading llama.cpp: !LLAMA_DL_URL!
        curl -L --progress-bar -o "!LLAMA_ZIP!" "!LLAMA_DL_URL!"
        if errorlevel 1 (
            echo [WARN] Download failed. LLM features degraded.
        ) else (
            if not exist "!LLAMA_DIR!" mkdir "!LLAMA_DIR!"
            powershell -NoProfile -Command "Expand-Archive -Path '!LLAMA_ZIP!' -DestinationPath '!LLAMA_DIR!' -Force; Remove-Item '!LLAMA_ZIP!'"
            REM -- Flatten sub-folder when zip extracts into a named sub-directory
            if not exist "!LLAMA_EXE!" (
                powershell -NoProfile -Command "$f=Get-ChildItem '!LLAMA_DIR!' -Recurse -Filter 'llama-server.exe'|Select-Object -First 1; if($f){Get-ChildItem $f.DirectoryName|Copy-Item -Destination '!LLAMA_DIR!' -Force}"
            )
            echo [OK] llama.cpp installed to !LLAMA_DIR!
        )
    )
) else (
    echo [OK] llama-server already installed: !LLAMA_EXE!
)

REM -- Download GGUF model if not on disk
if not exist "!GGUF_FILE!" (
    echo [INFO] Downloading Qwen3.5-27B Q4_K_M GGUF ^(~16 GB^)...
    echo [INFO] Source: !GGUF_URL!
    if not exist "!GGUF_DIR!" mkdir "!GGUF_DIR!"
    curl -L --progress-bar -C - -o "!GGUF_FILE!" "!GGUF_URL!"
    if errorlevel 1 (
        echo [WARN] GGUF download failed. Run manually:
        echo         curl -L -o "!GGUF_FILE!" "!GGUF_URL!"
    ) else (
        echo [OK] GGUF saved to !GGUF_FILE!
    )
) else (
    echo [OK] GGUF already on disk: !GGUF_FILE!
)

REM -- Start llama-server if not already running on port 8080
curl -sf http://localhost:8080/health >nul 2>&1
if errorlevel 1 (
    if exist "!LLAMA_EXE!" if exist "!GGUF_FILE!" (
        echo [INFO] Starting llama-server on http://127.0.0.1:8080 ...
        if "!GPU_PLATFORM!"=="intel_arc" (
            start "llama-server (Intel Arc SYCL)" cmd /k "set PATH=!LLAMA_DIR!;%PATH% && set ONEAPI_DEVICE_SELECTOR=level_zero:0 && set ZES_ENABLE_SYSMAN=1 && set SYCL_PI_LEVEL_ZERO_USE_IMMEDIATE_COMMANDLISTS=1 && "!LLAMA_EXE!" -m "!GGUF_FILE!" -c 8192 --alias qwen35-reasoning --port 8080 --host 127.0.0.1"
        ) else (
            start "llama-server" cmd /k "set PATH=!LLAMA_DIR!;%PATH% && "!LLAMA_EXE!" -m "!GGUF_FILE!" -ngl !LLAMA_NGL! -c 8192 --alias qwen35-reasoning --port 8080 --host 127.0.0.1"
        )
        echo [INFO] Waiting for llama-server to load the 27B model ^(up to 120 s^)...
        call :_wait_for_llama
    ) else (
        echo [WARN] llama-server or GGUF not found -- LLM features degraded.
        if not exist "!LLAMA_EXE!" echo [WARN]   Missing: !LLAMA_EXE!
        if not exist "!GGUF_FILE!" echo [WARN]   Missing: !GGUF_FILE!
    )
) else (
    echo [OK] llama-server already running on http://localhost:8080
)

REM =============================================================
REM  STEP 5 -- Start application services
REM =============================================================
echo.
echo [5/5] Starting application services...
echo.

echo Starting FastAPI backend on http://localhost:8000 ...
start "FastAPI Backend" cmd /c ""%CONDA_ENV_PYTHON%" -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000"

timeout /t 3 /nobreak >nul

echo Starting Streamlit UI on http://localhost:8501 ...
start "Streamlit UI" cmd /c ""%CONDA_ENV_SCRIPTS%\streamlit.exe" run src/ui/app.py --server.port 8501"

echo.
echo  Both services are starting:
echo    Backend:  http://localhost:8000/docs
echo    UI:       http://localhost:8501
echo.
echo  Close this window to stop.
pause
endlocal
goto :eof

REM =============================================================
REM  Subroutine: poll llama-server /health up to 120 s
REM  Must be a subroutine (called via CALL) -- goto inside
REM  parenthesised blocks is not legal in cmd.exe
REM =============================================================
:_wait_for_llama
set /a _WAIT_TRIES=0
:_wfl_loop
timeout /t 10 /nobreak >nul
curl -sf http://localhost:8080/health >nul 2>&1
if not errorlevel 1 (
    echo [OK] llama-server ready on http://localhost:8080
    goto :eof
)
set /a _WAIT_TRIES+=1
if !_WAIT_TRIES! LSS 12 (
    echo [INFO]   Still loading... ^(!_WAIT_TRIES! x 10 s^)
    goto :_wfl_loop
)
echo [WARN] llama-server did not respond within 120 s.
echo [WARN] The model may still be loading -- check the server window.
echo [WARN] The app will start anyway and retry on first LLM use.
goto :eof