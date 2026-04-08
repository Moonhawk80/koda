@echo off
cd /d "%~dp0"
call venv\Scripts\activate
python configure.py
pause
