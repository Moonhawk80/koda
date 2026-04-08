@echo off
echo ============================================
echo   Voice-to-Claude Installer
echo ============================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [1/5] Python found:
python --version
echo.

:: Create venv
echo [2/5] Creating virtual environment...
if exist venv (
    echo        Virtual environment already exists, skipping.
) else (
    python -m venv venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)
echo.

:: Install dependencies
echo [3/5] Installing dependencies (this may take a few minutes)...
call venv\Scripts\activate
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo        Dependencies installed.
echo.

:: Generate sound effects
echo [4/5] Generating sound effects...
python generate_sounds.py
echo.

:: Download Whisper model (will be re-downloaded if user picks a different size in setup)
echo [5/5] Downloading default speech model (first time only, ~150MB)...
python -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu', compute_type='int8'); print('        Model downloaded and verified.')"
if %errorlevel% neq 0 (
    echo [ERROR] Failed to download Whisper model.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   Installation complete!
echo ============================================
echo.
echo Now launching the setup wizard...
echo.

:: Run interactive setup
python configure.py
