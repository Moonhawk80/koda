# Alex Session 19 Handover — 2026-04-13

## Branch
`master` — clean, up to date with `origin/master`. All changes committed and pushed.

## What Was Built This Session

### PR #1 — Silent hook death watchdog (`hotkey_service.py` + `voice.py`)
Merged via `fix/silent-hook-death-watchdog` branch.

**Problem:** `WH_KEYBOARD_LL` hook can die silently while `keyboard._listener` thread stays alive and `keyboard._hooks` stays populated. The existing ping/pong health check passed (process alive, hooks dict non-empty) but no key events were delivered. Koda showed green, heartbeats continued, but hotkeys did nothing for 1+ hours.

**Fix — `hotkey_service.py`:**
- Added `_last_any_key_time` global (monotonic) + `_lock`
- Added `keyboard.on_press(_touch_last_key)` catch-all after hotkey registration — any key delivery proves the Windows hook is alive
- Pong response changed from `"pong"` to `("pong", last_key_mono)` — carries the timestamp of the last actual key delivery

**Fix — `voice.py`:**
- Added `_last_key_event_mono` global (near `_hotkey_pong`) — updated when tuple pong arrives
- `setup_hotkeys()` resets `_last_key_event_mono = time.monotonic()` — grace period for fresh restarts
- Event thread handles both `"pong"` (legacy) and `("pong", float)` (new)
- Watchdog checks staleness every 15s: WARNING at 10 min no key events, restart + yellow dot at 15 min
- Added `"#f1c40f": "warning"` to `_COLOR_TO_STATE` — yellow dot for hook-suspected-dead state

### PR #2 — Screen lock/unlock hotkey recovery (`voice.py`)
Merged via `fix/screen-lock-hotkey-recovery` branch.

**Problem:** The real failure mode was screen lock corrupting the `keyboard` library's modifier state (Ctrl/Shift appear stuck-pressed). Hook stays alive, catch-all `_touch_last_key` fires (user typing updates timestamp), so PR #1's staleness check never triggers. `Ctrl+Space` combination silently stops matching. Icon stays green. Sleep/wake detection doesn't help because screen lock without system sleep causes no watchdog gap.

**Fix — `voice.py`:**
- `import ctypes` added
- `_is_screen_locked()` function — uses `OpenInputDesktop` + `GetUserObjectInformationW` to check if desktop name is "Default" (unlocked) or "Winlogon"/inaccessible (locked)
- `_screen_was_locked` bool tracked across watchdog 15s ticks
- On `locked → unlocked` transition: `setup_hotkeys()` + `update_tray("#2ecc71", "Koda: Ready")` — fresh subprocess = clean modifier state

### Docs — Combined home PC session prompt
- `docs/sessions/home-pc-session-prompt.md` — single paste-ready prompt for home PC covering: correct sync order (commit local work FIRST, then pull), RegisterHotKey rewrite task, Whisper hallucination fix task
- `docs/sessions/alex-session-18-handover.md` — committed (was untracked from session 18)

## Decisions Made

### Root cause diagnosis: screen lock, not hook death
Initial theory was WH_KEYBOARD_LL hook dying (session 18's failure). The PR #1 staleness fix didn't catch it because users typing updates `_last_any_key_time`, so the pong carries a recent timestamp even when hotkeys are broken. The actual failure is modifier state corruption during screen lock. PR #2 fixes this by restarting hotkeys on every unlock.

### PRs for all code changes, even urgent ones
User set this expectation early: "open a PR I guess for my personal git to have me review." Enforced by hook throughout session. Docs-only commits were allowed to push directly (but the hook still caught one attempt and the user had to push manually).

### Permanent fix deferred to home PC
`RegisterHotKey` rewrite (replacing `keyboard` library entirely) is the proper long-term fix — survives screen lock/unlock natively without needing any watchdog intervention. Deferred because it's 2-3 hours of work and the user didn't want to spend more work tokens today. Captured in `home-pc-session-prompt.md`.

### Run from source for dev, installer only for distribution
Reinforced from sessions 15/16. `pythonw voice.py` for daily use. `build_exe.py` only when testing distribution.

### taskkill syntax in bash shell
On Windows with bash (Git Bash), `/F` is interpreted as a drive path. Must use `cmd //c "taskkill /F /IM pythonw.exe"` or the user runs it directly.

## User Feedback & Corrections

- **"koda is off again wtf is happening today is it because I moved it to my person git?"** — Moving to personal GitHub (Moonhawk80) is just a remote URL change, zero effect on Koda running locally. The issue was the same dead-hook pattern.
- **"and it is giving a false positive to the status light on the logo"** — Prompted adding the yellow dot (`#f1c40f`) to the watchdog warning path so the icon honestly reflects hook health.
- **"since we are running locally can you make the fixes here locally?"** — Interpreted as "apply to local master so Koda can restart with the fix now." Hook blocked direct master merge; resolved by user merging PR on GitHub then pulling.
- **"Why does this keep happening? What can we do to prevent this from repeating over and over?"** — Led to honest diagnosis of WH_KEYBOARD_LL fragility and the RegisterHotKey permanent fix proposal.
- **"I need a prompt for my home pc to do it I dont want to spend work tokens on this"** — Prompted capturing all pending work into `home-pc-session-prompt.md`.
- **"but remember that I have pushes on my home pc that are not done yet"** — Caught wrong order in the prompt (pull before checking local changes). Fixed to: commit local home PC work first, then pull.

## Waiting On

- **Alex to test the screen-lock fix** — Lock screen (Win+L), walk away, come back, confirm hotkeys work without manual restart. Should see `"Screen unlock detected — restarting hotkeys"` in debug.log.
- **Home PC session** — RegisterHotKey rewrite + Whisper hallucination fix (prompt ready in `docs/sessions/home-pc-session-prompt.md`).

## Next Session Priorities

1. **Verify screen-lock fix works** — test Win+L → unlock → Ctrl+Space before starting any new work
2. **RegisterHotKey rewrite** (`hotkey_service.py`) — permanent fix, eliminates the entire class of WH_KEYBOARD_LL fragility. Full spec in `home-pc-session-prompt.md`.
3. **Whisper hallucination fix** — check for conflicting STT apps first, then diagnose Whisper params. Full spec in `home-pc-session-prompt.md`.
4. **Tray icon polish** — flagged as overdue in memory, needs a proper designed icon (current is functional but ugly per user feedback in earlier session)

## Files Changed

| File | Change |
|------|--------|
| `hotkey_service.py` | Added `_last_any_key_time` tracking + catch-all `keyboard.on_press`; pong now sends tuple with timestamp; `threading` import added |
| `voice.py` | Added `_last_key_event_mono` global; screen lock detection (`_is_screen_locked`, `_screen_was_locked`); watchdog yellow dot + restart on stale key events; restart on screen unlock; `ctypes` import added; `#f1c40f` warning color in `_COLOR_TO_STATE` |
| `docs/sessions/alex-session-18-handover.md` | Committed (was untracked since session 18) |
| `docs/sessions/home-pc-session-prompt.md` | New — combined home PC session prompt (sync + RegisterHotKey + hallucination fix) |

## Key Reminders

- **WH_KEYBOARD_LL is fundamentally fragile** — Windows kills it on screen lock, UAC, fast user switching. Current fixes are workarounds. RegisterHotKey is the proper fix.
- **Screen lock without sleep doesn't trigger the >30s gap watchdog** — the sleep/wake detector only fires on a >30s watchdog gap. Screen lock keeps the watchdog running normally.
- **`_touch_last_key` fires on ALL key presses** — so typing in any app updates the staleness timer. The staleness check only catches "hook completely dead AND user typing nothing for 15 min" — rarer than screen-lock corruption.
- **taskkill in bash** — use `cmd //c "taskkill /F /IM pythonw.exe"`, not `taskkill /F /IM pythonw.exe` (bash treats `/F` as a path).
- **PR required for all code changes** — hook enforces this. Docs-only commits can go direct.
- **GitHub remote is now `Moonhawk80/koda`** — was `Alex-Alternative/koda`. No effect on local dev.
- **Koda v4.2.0, 197 tests passing** — up from 176 (21 tests added in sessions 15-18, test infrastructure improvements).
- **Home PC has unpushed local work** — the home PC prompt now correctly says: commit and push local work BEFORE pulling work PC changes.

## Migration Status
N/A — no database/schema work this session.

## Test Status
197 passing — unchanged from what was running. No new tests added this session (watchdog changes are runtime behavior, not unit-testable without mocking Windows APIs).

---

## New Session Prompt

```
cd C:\Users\alex\Projects\koda

Continue from session 19 handover (docs/sessions/alex-session-19-handover.md).

## What we were working on
Koda's hotkeys kept dying silently throughout the workday. Diagnosed two failure
modes: (1) WH_KEYBOARD_LL hook dying with false-positive green icon, (2) screen
lock corrupting keyboard modifier state. Shipped two PRs fixing both. Permanent
fix (RegisterHotKey rewrite) deferred to home PC session.

## Next up
1. Verify screen-lock fix: Win+L → unlock → Ctrl+Space should work immediately.
   Check debug.log for "Screen unlock detected — restarting hotkeys to restore hook state"
2. RegisterHotKey rewrite — replace keyboard library in hotkey_service.py with
   ctypes RegisterHotKey + Win32 message loop. Full spec in home-pc-session-prompt.md.
3. Whisper hallucination fix — long dictation hallucinates (e.g. "paid in full" →
   "patent"). Full spec in home-pc-session-prompt.md.

## Key context
- Branch: master, clean, all pushed.
- 197 tests passing.
- GitHub: https://github.com/Moonhawk80/koda (personal account, was Alex-Alternative)
- Home PC has unpushed local changes — commit and push those BEFORE git pull.
- Combined home PC prompt at: docs/sessions/home-pc-session-prompt.md
- taskkill in bash: cmd //c "taskkill /F /IM pythonw.exe" (slash handling)
```

**Copy the block above into a new session to pick up where we left off.**
