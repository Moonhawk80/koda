# Alex Session 32 Handover — 2026-04-15

## Branch
`fix-voice-commands-pyautogui-conflict` — 2 commits ahead of `master` (committed), plus 2 files with **uncommitted changes**. **PR #9 open** at Moonhawk80/koda#9.

---

## What Was Built This Session

### 1. PR #7 Merged + GitHub Release v4.2.0 Published

- Merged `session-30-excel-actions-user-guide` → `master` via PR #7
- Existing release `v4.2.0` had no installer asset — uploaded `dist/KodaSetup-4.2.0.exe` (559 MB)
- Updated release notes to include Terminal Mode and Excel Voice Actions (sessions 30+31)
- Release URL: https://github.com/Moonhawk80/koda/releases/tag/v4.2.0

### 2. Voice Commands Fix — pyautogui → keyboard.send (PR #8, MERGED)

**Root cause:** `voice_commands.py` used `pyautogui` for every key action. `pyautogui`'s synthetic Ctrl conflicts with the `keyboard` library's hooks, causing commands to silently fail.

**Fix:** Replaced all `pyautogui` calls in `voice_commands.py` with `keyboard.send()` (same library already used for paste in `voice.py`).

Updated test mocks from `voice_commands.pyautogui` → `voice_commands.keyboard`. Added `test_undo` assertion for `keyboard.send("ctrl+z")`.

PR #8 merged at 18:27 UTC. This commit is on `master`.

### 3. Terminal-Mode Voice Command Overrides (PR #9, OPEN — partially working)

**Problem:** In terminal, GUI keyboard shortcuts behave differently:
- `Ctrl+A` = go to start of line, not select all
- Forward Delete does nothing without a selection
- `Ctrl+Backspace` less reliable than readline `Ctrl+W`

**Built:** `TERMINAL_OVERRIDES` dict in `voice_commands.py` maps command descriptions to readline-appropriate actions. `extract_and_execute_commands()` accepts `in_terminal=False` and uses overrides when True. `voice.py` passes `_in_terminal` through.

**Testing results (live):**
- `"select all"` — first attempt: cleared entire line (Ctrl+E + Ctrl+U — wrong, was using clear-line override). Revised: now sends `Ctrl+A` + `Shift+End` to select current input. Second test: cursor moved to start then end but no visual highlight in terminal. **Status: not fully satisfying but not harmful.**
- `"undo"` — fires (debug log shows `keyboard.send("ctrl+z")` + "done"), but user reports no visible effect in terminal.
- `"delete"` — fires (`keyboard.send("ctrl+k")` + "done"), user reports no visible effect.

**Critical insight not yet acted on:** `Ctrl+K` (kill to EOL) does nothing because after Koda pastes, cursor is already at EOL — there's nothing after it to kill. Should be `Ctrl+U` (kill to BOL). `Ctrl+Z` for undo in PSReadLine may not undo synthetic ctrl+v pastes.

### 4. Debug Logging Added (UNCOMMITTED)

Added to `voice_commands.py`:
- `_focused_window()` — calls `GetForegroundWindow()` / `GetWindowTextW()` to log which window has focus when a command fires
- Logging in `_run()` before and after each command: `focus: hwnd=XXXX "Window Title"`
- `_action_terminal_select_all()` — select current input line via `Ctrl+A` + `Shift+End`

**These changes are uncommitted.** Koda was restarted with them running, but the user paused to run handover before seeing the focus log output.

### 5. Memory Saved

`feedback_test_before_pr.md` — "Always test that a fix actually works before creating a PR". Triggered because PR #8 and #9 were opened without live testing first, and commands still didn't work.

---

## Decisions Made

### "Test before PR" rule
**Why:** Created PR #8 (pyautogui fix) and PR #9 (terminal overrides) based purely on code reasoning without running Koda and verifying the fix. User tested and commands still didn't work. Cost: wasted PRs and iteration time.
**How to apply:** For any fix to Koda's input/output loop, restart Koda from source and have the user do a live test before opening a PR.

### "select all" in terminal = select the current input line
**Why:** User said "I don't like it deleting shit until I tell you to." — clearing the line was wrong. "Select all" should select so the user can then decide what to do.
**How to apply:** Terminal "select all" → `Ctrl+A` + `Shift+End`. But this doesn't visually highlight in Windows Terminal — still needs investigation.

### Ctrl+K is wrong for "delete" in terminal
**Discovered but not yet acted on.** After paste, cursor is at EOL. `Ctrl+K` kills from cursor to EOL — nothing to kill. Should be `Ctrl+U` (kill to BOL from current cursor = clears everything typed). Fix ready but not implemented.

---

## User Feedback & Corrections

- **"none of the commands worked we need to test before we do a PR going forward save that to memory"** — critical process feedback. Saved to memory. Commands fire (debug confirms) but have no visible effect.
- **"I did select all and it deleted everything. I didn't say undo, I said select all"** — original terminal "select all" override used Ctrl+E + Ctrl+U which clears the line. User wanted SELECT not DELETE.
- **"I don't like it, it should be something better, like I want to select all I say that don't delete shit until I tell you to"** — confirmed: select all must highlight only, not delete. Revised to Ctrl+A + Shift+End.
- **"Well, I did select all and it went to the beginning and then the end immediately it didn't highlight shit. And undo and delete are not working"** — Ctrl+A + Shift+End fires but no visual selection. Undo and delete fire but no visible effect. Session ended here to run handover first.

---

## Waiting On

- **Live test focus log** — Koda is running with `GetForegroundWindow` debug logging. User needs to try "undo" and "delete" in terminal and paste the debug log. This will confirm whether the keystrokes are going to the right window.
- **Fix Ctrl+K → Ctrl+U for "delete" in terminal** — confirmed wrong, not yet changed.
- **Fix undo in terminal** — `Ctrl+Z` may not undo synthetic paste in PSReadLine. Should likely be `Ctrl+U` (clear line = undo the paste).
- **PR #9 merge** — Moonhawk80/koda#9 has terminal overrides + user guide. Still open, not yet approved/merged.
- **New PR for debug logging + select/delete fixes** — uncommitted changes need to be committed and PRed once the fix is confirmed working.
- **Coworker follow-up** — share GitHub Release v4.2.0 URL, confirm install works.
- **Live test Excel actions** — ctrl+f9 in Excel: navigation, table creation, formula.
- **Installer wizard test** — run fresh `KodaSetup-4.2.0.exe` on a clean machine.

---

## Next Session Priorities

1. **Check focus log** — start by reading `debug.log` after user tests "undo"/"delete". Confirm `hwnd` + title matches terminal. If focus is wrong, fix timing/focus. If focus is right, the issue is the wrong key binding.
2. **Fix "delete" in terminal** — change `Ctrl+K` → `Ctrl+U` in `TERMINAL_OVERRIDES`. Ctrl+K kills to EOL (cursor already there after paste = nothing). Ctrl+U kills to BOL (clears what was typed).
3. **Fix "undo" in terminal** — likely needs terminal override: `Ctrl+U` (clear line) is more reliable than `Ctrl+Z` which may not undo synthetic paste in PSReadLine.
4. **Fix "select all" highlighting** — `Ctrl+A` + `Shift+End` fires but may not visually highlight in Windows Terminal. Investigate PSReadLine selection behavior or use Windows Terminal native `Ctrl+Shift+A` (selects all viewport text).
5. **Live test all three** — undo, delete, select all — confirm working before opening any PR.
6. **Commit + PR** — once all three work, commit debug logging removal + fixes, open PR.
7. **Coworker follow-up** — share https://github.com/Moonhawk80/koda/releases/tag/v4.2.0

---

## Files Changed This Session

| File | Status | Change |
|---|---|---|
| `voice_commands.py` | **Uncommitted** | pyautogui→keyboard.send (in PR #8 on master); terminal overrides, `_action_terminal_select_all`, `_action_terminal_clear_line`, `_action_terminal_kill_end`, `_action_terminal_delete_word`, `TERMINAL_OVERRIDES`; `_focused_window()` debug helper; logging in `_run()` |
| `voice.py` | Committed (PR #8 merged) | Initialize `_in_terminal = False` before if/elif/else block; pass `in_terminal=_in_terminal` to `extract_and_execute_commands` |
| `test_features.py` | **Uncommitted** | Updated mocks from `voice_commands.pyautogui` → `voice_commands.keyboard`; 4 new terminal override tests; updated `test_terminal_select_all` from clear-line to select-line assertions |
| `docs/user-guide.md` | Committed | "Voice commands in a terminal" subsection |
| `docs/user-guide.html` | Committed | "Voice commands in a terminal" table in Terminal Mode section |
| `memory/feedback_test_before_pr.md` | Written | New memory: test before PR rule |

---

## Key Reminders

- **Test before PR** — NEVER open a PR for a voice/keyboard fix without restarting Koda and confirming the fix works live. Test suite passing is not enough.
- **Ctrl+K is wrong for delete in terminal** — cursor is at EOL after paste, Ctrl+K kills nothing. Use Ctrl+U.
- **keyboard.send() fires correctly** — confirmed by debug logging showing "done" without errors. The issue is the wrong key binding, not the send mechanism.
- **Hotkey service uses RegisterHotKey (no suppress)** — Ctrl+Space is NOT suppressed. The terminal receives Ctrl+Space keystrokes too (may cause PSReadLine mark-set). No stuck modifier state.
- **Kill Koda (work PC):** `taskkill //F //IM pythonw.exe` (use `//F` not `/F` in bash)
- **Start from source:** `cmd //c "C:\Users\alex\Projects\koda\start.bat"` — background with `&`
- **351 tests passing** — `venv/Scripts/python -m pytest test_features.py test_e2e.py -q`
- **Two config.json** — `C:\Users\alex\Projects\koda\config.json` (source) and `%APPDATA%\Koda\config.json` (installed exe)
- **PRs only for Moonhawk80** — no direct pushes
- **GitHub Release v4.2.0 now has installer** — https://github.com/Moonhawk80/koda/releases/tag/v4.2.0

---

## Migration Status

None this session.

---

## Test Status

| Suite | Count | Status |
|---|---|---|
| `test_features.py` | 330 | ✅ All passing |
| `test_e2e.py` | 21 | ✅ All passing |
| **Total** | **351** | **✅** |

New tests added: 4 terminal override tests (`test_terminal_select_all_selects_line`, `test_terminal_delete_kills_to_eol`, `test_terminal_delete_word_uses_ctrl_w`, `test_gui_select_all_unchanged`).
Note: 2 tests updated — `test_undo` now asserts `keyboard.send("ctrl+z")`, `test_new_line` asserts `keyboard.send("enter")`.
