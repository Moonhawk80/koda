@echo off
echo Creating Windows startup shortcut...
powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut(\"$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup\Voice-to-Claude.lnk\"); $s.TargetPath = '%~dp0start.bat'; $s.WorkingDirectory = '%~dp0'; $s.WindowStyle = 7; $s.Description = 'Voice-to-Claude push-to-talk'; $s.Save()"
echo Done! Voice-to-Claude will now start automatically when you log in.
echo.
echo You can also double-click start.bat to launch it manually.
pause
