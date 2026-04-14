# Alex Session 23 Handover — 2026-04-14

## Branch
`master` — fully pushed to origin. Latest commit: `18ac78f`

---

## What Was Built This Session

### 1. Critical Exe Runtime Fix — `voice.py`, `config.py`, `build_exe.py`

Three separate bugs in the exe that were all discovered by actually running `dist/Koda.exe` for the first time (K1 cold boot test):

**Bug 1 — logprob_threshold typo still in exe (commit 18ac78f)**
The `logprob_threshold` → `log_prob_threshold` fix was committed in session 22 (`5c7046f`), but the exe was built in the same session BEFORE the fix was committed. Result: every transcription attempt failed silently in the exe. Fix: rebuild.

**Bug 2 — VAD model not bundled (`build_exe.py` line 53)**
`faster_whisper` needs `silero_vad_v6.onnx` at runtime (Silero VAD). This file was not in the PyInstaller `--add-data` list. Symptom: `[ONNXRuntimeError] NO_SUCHFILE: faster_whisper/assets/silero_vad_v6.onnx`. Fix: added:
```python
f"--add-data={os.path.join(SCRIPT_DIR, 'venv/Lib/site-packages/faster_whisper/assets')};faster_whisper/assets",
```

**Bug 3 — Exe always used DEFAULT_CONFIG, never user's config.json (`config.py`)**
PyInstaller `--onefile` extracts to a temp `sys._MEIPASS` directory each run. `config.py` used `os.path.dirname(os.path.abspath(__file__))` which in frozen mode resolves to `sys._MEIPASS` — a new temp dir every launch. So `config.json` was never found, and the exe always ran with `DEFAULT_CONFIG` (base model, `ctrl+shift+.` hotkey, no snippets). Fix: detect `sys.frozen` and use `%APPDATA%\Koda\` for all persistent user data.

**Related fix — debug.log and .koda_initialized (`voice.py`)**
Same `sys._MEIPASS` path issue. `debug.log` was written to a different temp dir every run (unreadable), and `.koda_initialized` was always missing (welcome message fired on every launch). Fixed to use `_DATA_DIR = %APPDATA%\Koda\` when frozen.

**Result:** `%APPDATA%\Koda\` is now the persistent data dir for the exe:
- `config.json` — user settings
- `debug.log` — persistent across runs
- `.koda_initialized` — first-run flag (won't show welcome every time)

### 2. Exe + Installer Rebuilt

After all three fixes:
- `dist/Koda.exe` rebuilt (529MB) — all bugs fixed, VAD bundled, config path correct
- `dist/KodaSetup-4.2.0.exe` rebuilt (530MB) — installer wraps the fixed exe
- Both were tested: transcription confirmed working

### 3. K1 Cold Boot Test — Completed (Partial)

- Startup shortcut (`dist/Koda.exe`) loaded after ~1-2 min (normal — Windows spin-up + Whisper model load)
- Welcome message appeared ✅
- Hotkeys registered ✅
- Transcription initially failed (exe bugs above) → fixed → transcription confirmed working ✅
- K1 is now PASS

---

## Decisions Made

### Always Test the Exe Immediately After Building
**Decision:** Any session that rebuilds the exe must test Ctrl+Space in the exe before closing. Source tests passing ≠ exe works.
**Why:** Session 22 built the exe before committing the logprob fix. The exe was broken for the entire cold boot test. User rightfully called this out as embarrassing for a product demo.
**Saved to memory:** `feedback_exe_testing.md`

### Exe Config Path — APPDATA, not exe directory
**Decision:** Store all persistent user data in `%APPDATA%\Koda\` when frozen, not next to the exe.
**Why:** The installed exe lives in `C:\Program Files\Koda\` which is read-only for standard users. Using exe directory for config would break on install. APPDATA is the standard Windows location for per-user app data.
**Note:** For the startup shortcut dev case (`dist/Koda.exe`), this means config is in APPDATA, not in `dist/`. That's fine — config.json in project root is still used by source runs.

### New Product — Prompt Coach (working title)
**Decision:** Not building this into Koda or Lode. Standalone product.
**Why:** Koda is offline/voice-first, no dialogue UI — wrong home. Lode's audience is developers already in Claude Code — not the target user. The target user (SMB owners, creative non-technical people, "AI as Google" users) needs a zero-friction web app with no install.
**Concept:** Two modes — (1) Build it: adaptive questions → polished prompt. (2) Fix it: paste bad prompt → diagnosis + rewrite. Claude API on backend. Free tier (3/day), paid $12/month.
**Name not decided** — user noted "Prompt Assist" is too generic. "Prompt" in the name might be jargon the target audience doesn't use.
**Next step:** Deep research session (separate from Koda) to define product properly.

---

## User Feedback & Corrections

- **"this is why I ask to stress test everything"** + **"these are the kind of bugs that when I present them to my people I will get laughed at"** — User was right to be frustrated. Exe was broken at the K1 cold boot test due to the build-before-fix ordering mistake. Rule saved to memory. Never build exe at the start of a session and assume it's final.
- **"are you listening to me? it works"** — User confirmed transcription working after VAD fix. Classic direct Alexi feedback — works means works, acknowledge and move on.
- **Vision for prompt coach** — "so many creative people who are not SMB owners that could benefit by the use of AI properly instead of a stupid expanded google." Very clear target audience statement. Not developers. Not enterprise. Creative people and small business owners who've tried AI and given up because it felt like Google with worse results.

---

## Waiting On

- **Work PC install test** — Install `KodaSetup-4.2.0.exe` on work PC, verify wizard branding + hotkeys work post-install. User was going to bed, not done yet.
- **RDP test** — Phase 9 Test 3 still pending. Connect from work PC to home PC via RDP, verify Ctrl+Space fires.
- **Prompt Coach deep research** — User wants a dedicated session with deep research + reasoning to define what to build. Separate from Koda entirely.
- **Phase 13 feature gates** — Free/Personal/Pro tier checks in code, license key system, LemonSqueezy, landing page. Not started.
- **KodaSetup-4.2.0.exe not on GitHub Release** — Still pending work PC test before publishing.
- **Prompt Assist feature (F9 in Koda)** — User wants to revisit/improve this. Deferred, not discussed in detail.

---

## Next Session Priorities

1. **Work PC install result** — Did the installer run? Did transcription work post-install?
2. **RDP test** — Phase 9 Test 3; remote into home PC, press Ctrl+Space
3. **Prompt Coach research prompt** — Generate a deep research prompt for a fresh session to define product
4. **Phase 13 feature gates kickoff** — Once work PC is confirmed, start coding free/Personal/Pro tier logic

---

## Files Changed This Session

| File | Change |
|------|--------|
| `config.py` | Added `_resolve_config_dir()` — uses `%APPDATA%\Koda\` when `sys.frozen`, project root otherwise |
| `voice.py` | Added `_get_data_dir()` + `_DATA_DIR` global — log, `.koda_initialized` use `_DATA_DIR`; hotkey log path also fixed |
| `build_exe.py` | Added `faster_whisper/assets` to `--add-data` so `silero_vad_v6.onnx` is bundled |
| `dist/Koda.exe` | Rebuilt — all three runtime bugs fixed (not in git, dist/ is gitignored) |
| `dist/KodaSetup-4.2.0.exe` | Rebuilt — wraps fixed exe (not in git) |

**Uncommitted (intentional — local only):**
- `CLAUDE.md` — session notes
- `config.json` — dev snippets + Zira TTS voice (project root; APPDATA copy is the live one for exe)

---

## Key Reminders

- **ALWAYS test the exe after building** — Ctrl+Space in the exe, not just source. Source passing ≠ exe works. This burned us two sessions in a row.
- **APPDATA\Koda\ is the exe's data dir** — `config.json`, `debug.log`, `.koda_initialized` all live there when running as exe. Source runs still use project root.
- **Startup shortcut → `dist/Koda.exe`** — NOT start.bat. Dev work uses start.bat manually. Do NOT change this back.
- **KodaSetup-4.2.0.exe is NOT uploaded to GitHub Release** — pending work PC install test
- **New pricing: $79 Personal / $149 Pro / $29/yr updates** — not yet in code
- **30/day free tier limit agreed** — not yet implemented
- **Kill ALL Koda before restart:** `taskkill //f //im Koda.exe` (and python.exe / pythonw.exe for source runs)
- **Full test suite:** `venv/Scripts/python -m pytest test_features.py test_e2e.py -q` (208 tests)
- **Prompt Coach is a NEW project** — do not build into Koda or Lode. Needs its own repo.
- **No CUDA** — Intel UHD 770 only
- **settings_gui runs as pythonw** — save_and_restart kills parent by os.getppid() only

---

## Migration Status

None. No database changes this session.

---

## Test Status

| Suite | Count | Status |
|-------|-------|--------|
| `test_features.py` | 187 | ✅ All passing |
| `test_e2e.py` | 21 | ✅ All passing |
| `test_stress.py` | 17/17 | ✅ Standalone only |
| **Total** | **208** | **✅** |

### Manual Tests Run This Session
| Test | Result |
|------|--------|
| K1 — cold boot (startup shortcut → exe) | ✅ Works after exe rebuild |
| Exe transcription (Ctrl+Space) | ✅ Confirmed working after VAD + logprob fixes |
| Source test suite (187 tests) | ✅ All passing |
