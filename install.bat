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

echo [1/4] Python found:
python --version
echo.

:: Create venv
echo [2/4] Creating virtual environment...
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
echo [3/4] Installing dependencies (this may take a few minutes)...
call venv\Scripts\activate
pip install -r requirements.txt --quiet
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)
echo        Dependencies installed.
echo.

:: Download Whisper model
echo [4/4] Downloading Whisper speech model (first time only, ~150MB)...
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
echo To start Voice-to-Claude:
echo   Double-click "start.bat"
echo.
echo To run on Windows startup:
echo   Double-click "install_startup.bat"
echo.
echo To run the stress test:
echo   Double-click "test.bat"
echo.
pause
