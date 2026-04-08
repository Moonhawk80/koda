@echo off
echo Removing Voice-to-Claude from Windows startup...
del "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\Voice-to-Claude.lnk" 2>nul
if %errorlevel% equ 0 (
    echo Done! Voice-to-Claude will no longer start automatically.
) else (
    echo No startup shortcut found — nothing to remove.
)
pause
