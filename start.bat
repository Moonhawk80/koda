@echo off
cd /d "%~dp0"
taskkill /f /im Koda.exe >nul 2>&1
taskkill /f /im pythonw.exe >nul 2>&1
taskkill /f /im python.exe >nul 2>&1
timeout /t 1 /nobreak >nul
call venv\Scripts\activate
start /min pythonw voice.py
