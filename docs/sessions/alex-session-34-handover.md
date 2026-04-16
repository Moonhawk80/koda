# Alex Session 34 Handover — 2026-04-16

## Branch
`master` — all work merged. PRs #10, #11, #12, #13 merged this session. Clean state.

---

## What Was Built This Session

### 1. PR #10 Merged (Terminal Voice Commands — Session 33 Work)
Merged the open PR from session 33. Fixes: undo/delete in terminal using Ctrl+U, false positive reduction, prefix matching removed.

### 2. PR #11 — PSReadLine Windows Mode Fix + Suffix Command Ordering
**Root cause found:** Home PC runs PSReadLine in Windows mode (default), not Emacs mode. Ctrl+U prints `^U` literally instead of killing to BOL.

**Fixes:**
- `voice_commands.py`: `_action_terminal_kill_bol()` and `_action_terminal_clear_line()` → send `escape` instead of `ctrl+u`. Escape = `RevertLine` in PSReadLine Windows mode, clears current input line.
- `voice.py`: Suffix commands now **deferred** — `extract_and_execute_commands` returns a third value `deferred_fn` (callable or None). Voice.py fires it AFTER `keyboard.send("ctrl+v")` with a 50ms delay. Previously Enter was firing before paste.
- `start.bat`: Now kills `Koda.exe` (installed exe) before starting from source — 3 installed Koda.exe instances were stealing hotkeys on startup.

**Return signature change:** `extract_and_execute_commands` now returns `(text, cmds, deferred_fn)` — all test callers updated to `text, cmds, _ = ...`.

### 3. PR #12 — User Guide Updates
- undo/delete in terminal: documented as Escape (RevertLine)
- suffix command tip added: "text pastes first, then command fires"
- select all: corrected to Ctrl+A moves cursor to BOL (no visual highlight in terminal)

### 4. KodaSetup-4.2.0.exe Rebuilt (×2)
Built and uploaded to GitHub Release v4.2.0 twice this session — once after PR #11, once after PR #13.

### 5. PR #13 — Stress Test Fixes (Major)

**"delete word" false positive:**
- `voice_commands.py`: Added `"Delete previous word"` to `_WHOLE_UTTERANCE_ONLY` set.
- "I want to delete word" no longer fires Ctrl+Backspace.
- 2 new tests: `test_delete_word_in_sentence_not_stripped2`, `test_delete_word_alone_still_works`.

**Terminal lowercase:**
- `terminal_mode.py`: `normalize_for_terminal()` now lowercases all input first (`text.strip().lower()`).
- Whisper capitalizes "Git" → "Git", "ls" → "LS" — now forced lowercase in terminal mode.

**Whisper hyphenation handling:**
- `terminal_mode.py`: Added rules before `_DASH_FLAG`:
  - `-dash-` → `--` (Whisper outputs "get-dash-version" for "git dash dash version")
  - `-dash$` → `--` (trailing)
  - `(\w)--(\w)` → `\1 --\2` (space before double-dash flags)
  - `([a-z]{2,})-([a-z])` → `\1 -\2` (single-letter flag: "ls-l" → "ls -l")

**Stutter deduplication fix:**
- `text_processing.py`: Added `"dash"` and `"dot"` to `_STUTTER_SAFE`.
- `_remove_stutters()` was stripping "dash dash" → "dash" (one removed as stutter). Now both survive.
- "dot dot" also preserved → "../" works correctly.

**"double dash" confirmed, "dash dash" doesn't work:**
- Whisper hears "git dash dash version" and outputs "git-v" (semantic compression).
- "double dash" passes through literally: "git double dash version" → `git --version`.
- User guide updated to show "double dash" in all examples.

**Custom words for terminal:**
- `custom_words.json`: Added git, npm, grep, pwd, chmod, sudo, mkdir, rmdir, bash, python, pip.
- These go into Whisper's `initial_prompt` to bias recognition. "git" now recognized instead of "get".

**Correction mode — VAD auto-stop fix:**
- `voice.py`: `undo_and_rerecord()` now calls `start_recording(recording_mode, force_vad=True)`.
- In hold mode, VAD auto-stop only activates when `force_vad=True`. Without it, correction recording hung open indefinitely — user had to press Ctrl+Space to trigger paste.

**Correction mode — terminal undo fix:**
- `voice.py`: `undo_and_rerecord()` now detects active window. In terminal → sends `escape` (RevertLine). In GUI → sends `ctrl+z`.

**Correction hotkey remapped:**
- `config.json`: `hotkey_correction`: f7 → `ctrl+alt+c` (F7 = brightness key on home PC laptop)
- `config.json`: `hotkey_readback`: f6 → `ctrl+alt+r` (F6 = dim key on home PC laptop)
- `hotkey_readback_selected`: remains f5 (not a hardware conflict)
- Note: Ctrl+Alt+Z was tried first but minimized windows (Intel/system hotkey). Ctrl+Alt+C works.

**Correction event logging:**
- Added `logger.info("Correction mode triggered")` to event dispatch.
- Added `logger.info("undo_and_rerecord: last_transcription=%r recording_mode=%r", ...)` to function.
- These were added to diagnose whether the event was firing at all (it was — no log = no event).

**UNRESOLVED:** Correction mode (Ctrl+Alt+C) — the VAD fix and logging were added but NOT fully confirmed working live. User said "nope" and called stop before next test. Need to verify next session.

### 6. Hotkey Conflict Investigation
- Discovered 3 `Koda.exe` installed instances running on startup, consuming all hotkeys (err=1409).
- `start.bat` fixed to kill `Koda.exe` before starting source version.
- Root cause: KodaSetup was installed on this machine AND Koda.lnk in shell:startup.

---

## Decisions Made

### Escape instead of Ctrl+U for terminal undo
**Why:** Home PC uses PSReadLine Windows mode (default). Ctrl+U is only bound in Emacs mode. Escape = `RevertLine` in Windows mode — clears current input line after paste.
**Impact:** Works cross-machine (Windows mode is the default everywhere).

### Suffix commands deferred to after paste
**Why:** "write something new line" was firing Enter before text was pasted — command fired inside `extract_and_execute_commands` before voice.py did Ctrl+V. Now returns `deferred_fn` callable, fired after paste + 50ms delay.

### "double dash" not "dash dash"
**Why:** Whisper interprets "dash dash" semantically and compresses to a hyphen or abbreviation. "double dash" is passed through literally. Confirmed live: "git double dash version" → `git --version`.

### force_vad=True for correction mode recording
**Why:** In hold mode, VAD only auto-stops if `force_vad=True`. Correction mode has no hotkey release to stop recording, so it hung open forever without this flag.

### Ctrl+Alt+C for correction (not Ctrl+Alt+Z)
**Why:** Ctrl+Alt+Z minimized windows on this PC (likely Intel display driver hotkey). Ctrl+Alt+C doesn't conflict with known system shortcuts.

### F6/F7 remapped to Ctrl+Alt combos
**Why:** Home PC laptop uses F6 = screen dim, F7 = screen brightness. These are hardware keys captured before Windows. Remapped to Ctrl+Alt+R (readback) and Ctrl+Alt+C (correction).

---

## User Feedback & Corrections

- **"select all worked before this last fix"** — confirmed select all is unchanged; the confusion was testing in the Claude Code terminal (bash) vs standalone PowerShell. Select all = Ctrl+A, works in GUI apps and separate terminals.
- **"it wrote something twice"** — for "write something new line" in PowerShell: PowerShell's `Write` alias runs `Write-Output`, printing "something" as output. Not a bug — the suffix timing fix was confirmed working.
- **"I said undo it didn't do it so I said it again"** — clarified the double `^U^U` was two separate hotkey presses, not a double-fire bug.
- **"is it git as in JIT?"** — user unfamiliar with git pronunciation. Explained: hard G, rhymes with "bit".
- **"you don't hold Fn F7 right"** — correct, press and release. But F7 wasn't reaching Koda regardless (hardware key captures it first).
- **"we have to stop here do a PR and handover"** — session ended mid-correction-mode debugging.

---

## Waiting On

- **Correction mode live test** — Ctrl+Alt+C with VAD fix and logging. Need to verify next session it actually: (1) clears previous paste, (2) opens mic, (3) records, (4) auto-stops, (5) pastes replacement.
- **Readback test (Ctrl+Alt+R)** — Block 4, test 17. Not tested.
- **Readback selected test (F5)** — Block 4, test 18. Not tested.
- **Block 5 edge cases** — silent dictation, long dictation, background noise, "we should undo the changes" (whole-sentence false positive) — not tested.
- **Excel actions live test** — Ctrl+F9 in Excel: navigation, table creation, formula mode. Still untested.
- **Installer wizard test** — fresh install of KodaSetup-4.2.0.exe on a clean machine.
- **Coworker follow-up** — share https://github.com/Moonhawk80/koda/releases/tag/v4.2.0
- **RDP test** — Ctrl+Space via RDP.
- **Next phase planning** — user explicitly requested planning for next phases after stress test.

---

## Next Session Priorities

1. **Finish stress test Block 4** — test correction mode (Ctrl+Alt+C), readback (Ctrl+Alt+R), readback selected (F5). Check debug.log to confirm correction event is firing.
2. **Finish stress test Block 5** — edge cases: silence, long dictation, background noise, command words in sentences.
3. **Excel actions live test** — open Excel, hold Ctrl+F9, test navigation and table creation.
4. **Phase planning** — user explicitly asked for this. Plan next development phases for Koda.
5. **Rebuild installer** if any more bugs fixed (current build includes all PR #13 fixes).

---

## Files Changed This Session

| File | Change |
|---|---|
| `start.bat` | Kills Koda.exe + pythonw before starting — prevents hotkey conflicts |
| `voice_commands.py` | Escape instead of Ctrl+U; suffix deferred return; "Delete previous word" in _WHOLE_UTTERANCE_ONLY |
| `voice.py` | Deferred suffix in paste flow; correction mode: terminal-aware undo, force_vad=True, logging |
| `terminal_mode.py` | Lowercase; Whisper hyphenation rules; -dash- → -- |
| `text_processing.py` | "dash" and "dot" added to _STUTTER_SAFE |
| `config.json` | hotkey_correction: ctrl+alt+c, hotkey_readback: ctrl+alt+r |
| `custom_words.json` | Added git, npm, grep, pwd, chmod, sudo, mkdir, rmdir, bash, python, pip |
| `test_features.py` | Updated all `text, cmds =` to `text, cmds, _ =`; 2 new delete-word tests |
| `docs/user-guide.md` | Double dash examples; terminal undo/delete as Escape |
| `docs/user-guide.html` | Same updates as .md |

---

## Key Reminders

- **Kill ALL before starting from source:** `taskkill //f //im Koda.exe && taskkill //f //im pythonw.exe` — start.bat now does this automatically.
- **Home PC hotkeys:** Ctrl+Space (dictation), F8 (command), Ctrl+F9 (prompt), **Ctrl+Alt+C** (correction), **Ctrl+Alt+R** (readback), F5 (readback selected).
- **Work PC hotkeys may differ** — config.json is machine-specific, not committed for work PC.
- **PSReadLine Windows mode** — home PC default. Ctrl+U doesn't work. Escape = RevertLine.
- **"double dash" not "dash dash"** — Whisper semantically compresses "dash dash".
- **extract_and_execute_commands returns 3-tuple** — `(text, cmds, deferred_fn)`. All callers must unpack 3 values.
- **Correction mode unconfirmed** — VAD + logging fix applied but not live-tested. Check log for "Correction mode triggered" entry on next test.
- **GitHub Release v4.2.0** — https://github.com/Moonhawk80/koda/releases/tag/v4.2.0 — installer uploaded twice, latest build from end of this session.
- **339 tests passing** — `venv/Scripts/python -m pytest test_features.py -q`
- **Run from source** — `cmd //c "C:\Users\alexi\Projects\koda\start.bat"` (or just double-click start.bat)

---

## Migration Status

None this session.

---

## Test Status

| Suite | Count | Status |
|---|---|---|
| `test_features.py` | 339 | ✅ All passing |
| **Total** | **339** | **✅** |

Tests added this session (+2 from 337):
- `test_delete_word_in_sentence_not_stripped2` — "I want to delete word" → no command
- `test_delete_word_alone_still_works` — bare "delete word" → fires command

All 18 test callers updated from 2-tuple to 3-tuple unpacking.
