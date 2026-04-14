# Koda — Session Status

> **Updated:** 2026-04-14 (Session 23)
> **Version:** v4.2.0 | **Tests:** 208 passing (`test_features.py` + `test_e2e.py`) | **Branch:** master

---

## Phase Status

| Phase | Status | Notes |
|-------|--------|-------|
| 9 — Beta Stability | PARTIAL | Tests 1 (mic) + 2 (sleep/wake) PASS. Test 3 (RDP) pending |
| 10 — Custom Vocabulary | DONE | Session 13, commit 68ce846 |
| 11 — Per-App Profiles | DONE | Session 14, commit cd9d3c8 |
| 12 — Filler Words + Snippets GUI | DONE | Session 17. Smoke test PASS. |
| 13 — Installer / Distribution | IN PROGRESS | KodaSetup-4.2.0.exe built (529MB). Pending: work PC install test, feature gates, license keys, LemonSqueezy, landing page. |

---

## Next Session Actions (Priority Order)

1. **Work PC install test** — Install KodaSetup-4.2.0.exe on work PC, verify wizard + hotkeys + transcription
2. **RDP test** — Phase 9 Test 3; connect from work PC to home PC via RDP, verify Ctrl+Space fires
3. **Prompt Coach research** — Generate deep research prompt for new product (separate session, separate repo)
4. **Phase 13 feature gates** — start free/Personal/Pro tier checks in code + license key system

---

## Non-Obvious Reminders (things that bite us)

- Kill ALL python before restart: `taskkill //f //im pythonw.exe` AND `taskkill //f //im python.exe`
- Run from source: `cmd //c "C:\Users\alexi\Projects\koda\start.bat"` — no installer builds during dev
- Tests: `venv/Scripts/python -m pytest test_features.py` — use venv python, NOT plain python
- Hotkeys: ONLY `ctrl+alt+letter` or F-keys — no backtick, no Ctrl+Shift
- Paste: `keyboard.send("ctrl+v")` — NOT pyautogui
- Sound: `winsound` — NOT sounddevice
- `mic_device = null` — never hardcode device indices
- `filler_words.json` — lives in project root, created on first Save in Settings
- Sleep/wake test = actual Sleep (Power → Sleep), NOT lock screen — ✅ DONE session 17
- `configure.py` UnicodeEncodeError in bash — cosmetic only, config.json is already correct
- `test_stress.py` — standalone only, NOT via pytest
- GitHub CLI: `"C:\Program Files\GitHub CLI\gh.exe"`, auth as `Moonhawk80`
- Phase 13 distribution = exe only — no git clone, no personal credentials on work PC
- NO CUDA — Intel UHD 770 only; GPU Power Mode feature is untestable here
- **settings_gui runs as pythonw** — save_and_restart kills parent by PID (os.getppid()), NOT all pythonw
- Domain chosen: kodaspeak.com

---

## Key Files (with sizes — check before full reads)

| File | Lines | What's in it |
|------|-------|--------------|
| `voice.py` | ~1700 | Main app, tray, hotkey handling, audio loop, watchdog |
| `settings_gui.py` | ~900 | Tabbed settings window (5 tabs, light theme) |
| `text_processing.py` | ~300 | Pipeline: snippets → filler → vocab → format → capitalize |
| `config.py` | ~80 | DEFAULT_CONFIG, load/save helpers |
| `test_features.py` | ~1100 | All 176 tests |
| `audio_processing.py` | ~200 | Mic capture, VAD, Whisper transcription |
| `build_exe.py` | ~107 | PyInstaller build script (already fully configured) |

---

## DO NOTs (permanent)

- DO NOT suggest Product Hunt
- DO NOT re-run market research (saved to memory)
- DO NOT build/install exe during dev
- DO NOT ask for mid-task confirmation — take obvious next steps
- DO NOT use Ollama (off by default, not required)
- DO NOT enable wake word (off by default)
- DO NOT call sd._terminate() while stream is running — kills the stream (PaErrorCode -9988)
- DO NOT kill all pythonw from within settings_gui — it IS pythonw; kill parent PID only
