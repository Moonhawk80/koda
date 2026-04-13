# Koda — Home/Work PC Session Prompt

Copy the code block below and paste it into a new Claude Code session opened in the koda folder.

---

```
cd C:\Users\alexi\Projects\koda

Read STATUS.md for full context.
  Koda project — push-to-talk voice-to-text Windows tray app.
  Repo: github.com/Moonhawk80/koda. 176 tests passing.
  Kill ALL python/pythonw processes before restarting Koda.
  Running from source. DO NOT suggest Product Hunt. DO NOT re-run market research.
  Do not ask for mid-task confirmation. Run /handover at ~40% context.

  Continuing from session 17. v4.2.0 running.

  ENVIRONMENT NOTES (this machine):
  - This is the HOME or WORK PC — not the primary dev machine.
  - Python and venv may need to be set up fresh (see Setup section below).
  - No NVIDIA GPU assumed — Intel integrated graphics only.
  - GitHub CLI may not be installed — use `gh auth login` if needed.

  SETUP CHECKLIST (first time on this machine):
  1. git pull — to get latest code
  2. python -m venv venv — if venv doesn't exist
  3. venv/Scripts/pip install -r requirements.txt — install dependencies
  4. venv/Scripts/python -m pytest test_features.py — verify 176 tests pass

  SESSION GOALS (in order):
  1. Rebuild dist/Koda.exe — run: venv/Scripts/python build_exe.py
     Current exe in dist/ predates the snippets fix + save_and_restart fix (session 17).
     build_exe.py is fully configured — just run it. Takes 3-5 minutes.
  2. Verify Koda.exe works — run dist/Koda.exe, check tray icon appears, test Ctrl+Space
  3. Phase 13 — Installer/distribution package for work PC
     Goal: a self-contained folder or single exe that a non-developer can run.
     Deliverables: Koda.exe + fresh config.json + filler_words.json + README.
  4. Phase 9 Test 3 — RDP: connect to this PC via RDP from another machine,
     verify Ctrl+Space fires and transcription works over RDP.

  Key context:
  - settings_gui runs as pythonw — save_and_restart kills parent by os.getppid(), not all pythonw
  - Snippets now included in light_config (dictation mode) — don't revert
  - Tray menu cut to 10 items; Settings window is now tabbed with light theme
  - Domain chosen: kodaspeak.com
  - filler_words.json lives in project root, created on first Save in Settings
  - config.json is gitignored — a fresh one will be generated on first run
  - GitHub CLI auth: Moonhawk80
  - GitHub CLI path: "C:\Program Files\GitHub CLI\gh.exe" (if installed)
```
