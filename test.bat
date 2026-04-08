@echo off
echo Running Voice-to-Claude Stress Test...
echo.
cd /d "%~dp0"
call venv\Scripts\activate
python test_stress.py
echo.
pause
