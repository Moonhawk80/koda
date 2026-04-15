# Alex Session 27 Handover — 2026-04-14

## Branch
`master` — clean, up to date with `origin/master`. All changes pushed.

---

## What Was Built This Session

### 1. Formula Mode (`formula_mode.py`) — NEW
Full Excel / Google Sheets speech-to-formula feature.

- **Tier 1 — rules-based** (no dependencies): SUM, AVERAGE, COUNT, COUNTA, MAX, MIN, TODAY, NOW, IF, VLOOKUP, CONCAT, PERCENTAGE
- Range parser: "column B rows 2 to 10" → B2:B10, "B2 to B10" → B2:B10, "A1:B10" pass-through
- **Tier 2 — Ollama fallback** if `llm_polish.enabled = true` in config
- Falls back to raw paste if no formula matches — regular dictation in Excel still works
- Window detection: `excel.exe` process + Google Sheets title patterns
- **File:** `formula_mode.py`

### 2. Formula mode wired into voice.py transcription pipeline
- Hook runs after voice commands, before pasting
- Checks `formula_mode.enabled` + active window via `get_active_window_info()`
- Graceful error handling — debug logs only, never silently drops text
- **File:** `voice.py` lines ~724–735

### 3. Config + Settings
- `"formula_mode": {"enabled": False, "auto_detect_apps": True}` added to `DEFAULT_CONFIG`
- "Formula mode (Excel / Google Sheets)" checkbox in Settings Features (default: off)
- `save()` in settings_gui.py writes `formula_mode.enabled`
- **Files:** `config.py`, `settings_gui.py`

### 4. Installer wizard — 4 custom pages
Added `[Code]` Pascal section to `installer/koda.iss`:

| Page | Caption | Default |
|------|---------|---------|
| 1 | Your Microphone | Informational only |
| 2 | Activation Method | Hold to talk |
| 3 | Transcription Quality | Accurate (small, bundled) |
| 4 | Formula Assistant | Disabled |

- Writes `%APPDATA%\Koda\config.json` at `ssPostInstall` — only if file doesn't exist (fresh install)
- Installer rebuilt: `dist/KodaSetup-4.2.0.exe` (531 MB) — Inno Setup compiled cleanly
- **File:** `installer/koda.iss`

### 5. Model path debug logging (`voice.py`)
- `logger.debug("Model search: base_dir=..., bundled_path=..., exists=...")` before load
- `logger.debug("Loading bundled model from: ...")` when bundled path found
- `logger.debug("Bundled model not found ... may download")` when not found
- Future "loading model" stuck tooltip issues now diagnosable via `debug.log`

### 6. Tests — 25 new formula mode tests
- `TestFormulaMode` (19 tests): SUM, AVERAGE, COUNT, MAX, MIN, TODAY, NOW, IF, VLOOKUP, CONCAT, percentage, no-match, case-insensitive
- `TestFormulaAppDetection` (6 tests): Excel process detection, Google Sheets title, non-formula apps
- **233 tests passing** (was 208)

### 7. User guide updated
- `docs/user-guide.md` — added Formula Mode section with examples table
- `docs/user-guide.html` — added styled Formula Mode section

### 8. Personal GitHub credentials removed from work PC
- Deleted `LegacyGeneric:target=git:https://github.com` (Moonhawk80 HTTPS token)
- Deleted `LegacyGeneric:target=gh:github.com:` (unnamed personal gh CLI token that was hijacking browser login)
- Remaining: only `gh:github.com:Alex-Alternative` and `GitHub - https://api.github.com/Alex-Alternative` (work account — correct)

---

## Decisions Made

### Formula mode default = off, user opts in
Not all Koda users use Excel. Installer page 4 lets users turn it on at install time.

### Page 3 model default = Accurate (small, bundled)
Session 25 prompt said default should be "Balanced" (base). Changed to "Accurate" (small) because:
- Only `_model_small` is bundled in the exe — base/tiny require internet download
- Coworker install failure was caused by exactly this mismatch. Not repeating it.

### No direct pushes to Moonhawk80 repos from work PC — PRs only
Personal GitHub credentials removed. Future workflow on work PC:
- Commit locally → push feature branch → `gh pr create`
- First PR will prompt browser login for Moonhawk80 (clean, no wrong account hijack)

### Formula mode as pipeline transform, not profiles.py
Session prompt suggested wiring formula mode through profiles.py as a recognized profile mode. Instead wired directly in voice.py pipeline with active-window detection. Profiles handle config overrides; formula mode is a text transformation — different concern.

---

## User Feedback & Corrections

- **"also did we develop the excel thing?"** — Formula mode hadn't been built yet. Built this session.
- **"we also need to fix the user guide for the excel function"** — Done.
- **"desktop shortcut what does it do when I got mad was with the overlay"** — Confirmed: the floating overlay (not the desktop shortcut) was what frustrated the user. Both are now fixed/removed separately.
- **"only the alex-alternative credentials should be here"** — Confirmed work account is correct. Removed both personal tokens.
- **"for my personal git I never want you to push again only do PRs"** — Saved to memory. PRs only for all Moonhawk80 repos going forward.
- **"remove my credentials for my personal git from this pc"** — Done (see above).
- **"what is that? remove it I couldn't do log in with browser because it opened my personal account"** — The unnamed `gh:github.com:` was the old Moonhawk80 gh CLI token. Removed.

---

## Waiting On

- **Installer wizard manual test** — `KodaSetup-4.2.0.exe` needs to be run on a clean machine to verify all 4 pages appear and `%APPDATA%\Koda\config.json` is written correctly
- **Formula mode end-to-end test** — Open Excel/Sheets, enable in Settings, verify "sum B2 to B10" → `=SUM(B2:B10)`
- **Coworker follow-up** — Did the session 25 model mismatch fix resolve their install? Any usage feedback?
- **RDP test** — Phase 9 Test 3 still pending (work PC → home PC via RDP, Ctrl+Space)
- **GitHub Release** — `KodaSetup-4.2.0.exe` not published; blocked on wizard test + coworker confirmation
- **kodaspeak.com** — Verify domain is actually registered before building landing page

---

## Next Session Priorities

1. **Test installer wizard** — run `KodaSetup-4.2.0.exe`, verify 4 pages, check `%APPDATA%\Koda\config.json` after install
2. **Test formula mode** — open Excel, enable formula mode in Settings, try: "sum B2 to B10", "today", "if A1 is greater than 10 then yes else no"
3. **Coworker follow-up** — confirm model mismatch fix resolved their issue; get feedback
4. **GitHub Release** — publish `KodaSetup-4.2.0.exe` once wizard + formula tests pass
5. **RDP test** — Phase 9 Test 3

---

## Files Changed

| File | Change |
|------|--------|
| `formula_mode.py` | NEW — speech-to-formula conversion, Tier 1 rules + Tier 2 Ollama |
| `voice.py` | Formula mode pipeline hook + model path debug logging |
| `config.py` | `formula_mode` added to `DEFAULT_CONFIG` |
| `settings_gui.py` | Formula mode toggle in Features + `save()` |
| `build_exe.py` | `formula_mode.py` added to `DATA_FILES` |
| `installer/koda.iss` | 4 custom wizard pages + `[Code]` section |
| `test_features.py` | `TestFormulaMode` + `TestFormulaAppDetection` (25 new tests) |
| `docs/user-guide.md` | Formula Mode section added |
| `docs/user-guide.html` | Styled Formula Mode section added |
| `docs/sessions/alex-session-26-handover.md` | Session 26 handover (written mid-session) |

---

## Key Reminders

- **PRs only for Moonhawk80/koda on work PC** — no direct pushes. Personal credentials removed. Browser login will prompt cleanly for Moonhawk80 now.
- **model_size default = "small"** — must always match bundled model. Installer page 3 defaults to Accurate/small.
- **Formula mode off by default** — user enables in Settings or installer page 4. No impact on users who don't use Excel.
- **Installer writes config only on fresh install** — `FileExists` check in Pascal; upgrades preserve existing config
- **233 tests passing** — do not regress
- **Overlay off by default** — if user reports missing overlay, it's a Settings toggle (not a bug)
- **Work PC exe path:** `C:\Users\alex\AppData\Local\Programs\Koda\Koda.exe`
- **taskkill on work PC bash:** `cmd //c "taskkill /F /IM Koda.exe /IM pythonw.exe /IM python.exe"`
- **CLAUDE.md in repo has home PC paths (alexi)** — correct on home PC, misleading on work PC

---

## Migration Status

None this session.

---

## Test Status

| Suite | Count | Status |
|-------|-------|--------|
| `test_features.py` | 212 | ✅ All passing |
| `test_e2e.py` | 21 | ✅ All passing |
| **Total** | **233** | **✅** |
