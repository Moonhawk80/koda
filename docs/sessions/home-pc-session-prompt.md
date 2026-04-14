# Koda — Home/Work PC Session Prompt

---

## SESSION 25 PROMPT — Installer Customization Wizard

Copy the block below and paste into a new Claude Code session in `C:\Users\alexi\Projects\koda`.

```
cd C:\Users\alexi\Projects\koda

Read STATUS.md and docs/sessions/alex-session-24-handover.md for full context.
Koda project — push-to-talk voice-to-text Windows tray app.
208 tests passing. Branch: master, clean.
DO NOT suggest Product Hunt. Do not ask for mid-task confirmation.
Run /handover at ~40% context.

## STEP 1 — Sync
git pull origin master
venv/Scripts/python -m pytest test_features.py test_e2e.py -q
Expected: 208 passed. If not, stop and investigate before proceeding.

## TASK — Installer customization wizard pages

### Goal
The Inno Setup installer (installer/koda.iss) currently shows only the
standard wizard pages (welcome, license, install dir, desktop shortcut,
auto-start). We want to add 2 custom wizard pages that ask the user setup
questions BEFORE the files are copied, then write their answers into
%APPDATA%\Koda\config.json at the end of installation.

### The three questions to add

PAGE 1 — "Your microphone" (informational + verification)
  This is NOT a question — it's a check + guidance page.

  At the top, run a quick mic detection: use Exec() to call a one-liner
  Python helper (written to a temp file by the [Code] section) that uses
  sounddevice to list input devices and prints the count + default device name.
  Read the output back. Show either:
    ✓ Microphone detected: <device name>
      "Koda will use your Windows default microphone. You can change
       this in Settings after installation."
  OR if no mic found:
    ✗ No microphone detected.
      "Please connect a microphone before using Koda."

  Below the detection result, always show mic guidance:

  "Koda works with any microphone. Here's what to expect:"
    Built-in laptop mic     Works. Background noise may reduce accuracy.
                            Best in a quiet room.
    USB headset / earbuds   Good quality. Affordable ($15–40).
    Dedicated USB mic       Best accuracy. ($50–100, e.g. Blue Yeti, HyperX)

  "Tip: A quiet environment matters more than mic quality."

  No user choice needed — this page is informational only (Next button only).
  The mic detection result does NOT block installation — even if no mic is
  found, the user can still install and plug one in later.

  Implementation note: The Python mic-detection helper only works if Python
  is on PATH or we use the bundled exe. Simpler fallback: just show the
  guidance text without live detection, and add a note "Make sure your mic
  is set as the default recording device in Windows Sound Settings."
  Use the live detection only if it works cleanly; fall back to static text.

PAGE 2 — "How would you like to use your microphone?"
  Option A: Hold to talk  (hotkey_mode = "hold")   ← default, recommended
  Option B: Toggle        (hotkey_mode = "toggle")
  Radio buttons. Caption: "Hold: press and hold Ctrl+Space while speaking.
  Toggle: press once to start, press again to stop."

PAGE 3 — "Choose transcription quality"
  Option A: Fast     — "Fastest response, good for short commands"  (model_size = "tiny")
  Option B: Balanced — "Recommended for most users"                 (model_size = "base")  ← default
  Option C: Accurate — "Most accurate, uses more CPU"               (model_size = "small")
  Radio buttons. Sub-caption: "This can be changed later in Settings."

### What to write to config.json
At install completion ([Code] CurStepChanged(ssPostInstall)), write
%APPDATA%\Koda\config.json with the answers from Pages 2 and 3.

Simplest approach: write a minimal config.json with only the two chosen keys:
  {"hotkey_mode": "hold", "model_size": "base"}
Koda's load_config() does _deep_merge(DEFAULT_CONFIG, user_config) so the
rest of the defaults will be applied automatically on first run.

The file goes to: ExpandConstant('{userappdata}') + '\Koda\config.json'
Create the Koda directory if it doesn't exist.

### Inno Setup implementation approach
Use the [Code] section Pascal scripting. Inno Setup 6 supports custom wizard
pages via CreateCustomPage / CreateInputOptionPage.

Key Inno Setup functions:
  CreateInputOptionPage(AfterID, Caption, SubCaption, Prompt, Exclusive, ListBox)
  Page.Values[0] / Page.Values[1] — read radio button state
  CurStepChanged(CurStep: TSetupStep) — hook for ssPostInstall
  ExpandConstant('{userappdata}') — resolves to C:\Users\<user>\AppData\Roaming
  SaveStringToFile(Filename, Content, Append) — write config.json
  ForceDirectories(Dir) — create the Koda dir if needed

Insert the pages after the existing [Tasks] page (PageID = wpSelectTasks).

### Proposal rule
Read the current installer/koda.iss first. Propose the Pascal code for the
[Code] section and get approval before editing. Show what the two wizard pages
will look like (describe each page's caption, sub-caption, and options).

### After implementing
1. Rebuild the installer: venv/Scripts/python installer/build_installer.py
2. Run KodaSetup-4.2.0.exe — confirm the three new pages appear in the wizard
3. Page 1: verify mic detection shows your mic name (or graceful fallback text)
4. Pages 2 & 3: make selections, complete install
5. Check %APPDATA%\Koda\config.json — verify hotkey_mode and model_size
   reflect what you chose
6. Launch Koda — confirm it starts with those settings (Settings window
   should show the chosen model and hotkey mode)
7. Test the other path: run the installer again with different choices,
   verify config.json updates correctly

### Key files
- installer/koda.iss          — the Inno Setup script to edit
- config.py                   — DEFAULT_CONFIG reference (model_size, hotkey_mode)
- %APPDATA%\Koda\config.json  — written at install time, read by Koda on launch

### Current state
- KodaSetup-4.2.0.exe was built on the work PC (C:\Users\alex\) 2026-04-14
- Exe has the staleness fix (hotkey_service.py line 305)
- No customization wizard pages yet — those are what this session adds
- The existing [Tasks] in koda.iss (desktop shortcut + autostart) stay as-is

Run /handover at session end.
```

---

## OLDER PROMPTS (sessions 17–24)

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


---
<!-- Additional content from home PC sessions -->

# Home PC Session — Combined Prompt
**Captured:** 2026-04-13 (work laptop, session 19)
**Covers:** Session startup sync + 2 feature tasks. Do them in order.

---

## Paste this into Claude Code on the home PC

```
cd C:\Users\alex\Projects\koda

## STEP 1: Sync and verify before anything else

IMPORTANT — do these in this exact order to avoid conflicts:

1. Check for uncommitted work on THIS machine first (before pulling):
   git status
   If there are any changes (modified, untracked, staged), commit and push
   them NOW before doing anything else:
     git add -p   (stage selectively) or git add <specific files>
     git commit -m "WIP: home PC work from last session"
     git push origin master
   Do not skip this — pulling with local changes can cause conflicts or
   silently overwrite work.

2. Now pull the work PC changes:
   git pull origin master
   If there are merge conflicts, resolve them before proceeding.

3. Run from source (do NOT rebuild the installer for dev work):
   venv\Scripts\activate
   pythonw voice.py
   The installer is for distributing to OTHER people. For daily dev use,
   run from source. If you need to test the installer specifically:
     python build_exe.py
     python installer\build_installer.py
   Publisher is "Alex Concepcion" (was "Alex Alternative"). Build includes
   tkinter (was crashing before session 15 fix).

4. Verify Koda is working: Ctrl+Space, hold to talk, release to paste.
   Check debug.log for "Koda v4.2.0 fully initialized".
   Then lock screen (Win+L), unlock, verify hotkeys still work — we fixed
   a screen-lock hook bug today, confirm it's working on this machine too.

ALWAYS git pull at start of session, git push at end. Cross-PC sync depends on it.

---

## TASK 1 (do after sync): Rewrite hotkey_service.py to use RegisterHotKey

### Why
The keyboard library uses WH_KEYBOARD_LL hooks which Windows kills silently
in multiple scenarios (screen lock, UAC, fast user switching). Hotkeys broke
3+ times in one workday (session 19). We've been patching failure modes one
by one. The permanent fix is RegisterHotKey — the Windows-native hotkey API
that registers with the OS Window Manager and survives all of the above.

Current workarounds in voice.py (keep as defense-in-depth after the rewrite):
- Screen lock/unlock detection → restart hotkeys on unlock
- Key-event staleness check → yellow dot + restart after 15 min
- Sleep/wake gap detection → full recovery
- Ping-based liveness check → restart if subprocess dies

### What RegisterHotKey is
ctypes.windll.user32.RegisterHotKey(hwnd, id, modifiers, vk) registers a
hotkey directly with the OS Window Manager. Delivers WM_HOTKEY (0x0312)
messages to a thread's message queue via GetMessage(). Never silently
killed, survives screen lock/unlock and sleep/wake natively, no 300ms
timeout constraint.

### Current hotkey_service.py architecture
- Runs as multiprocessing.Process (subprocess of voice.py)
- Communicates via multiprocessing.Pipe (bidirectional)
- Parent sends: "ping", "quit"
- Child sends: "ready", ("pong", last_key_mono), "hooks_dead",
  "dictation_press", "dictation_release", "command_press",
  "command_release", "prompt_press", "prompt_release",
  "dictation_toggle", "command_toggle", "prompt_toggle",
  "correction", "readback", "readback_selected"
- Hold mode: _press on keydown, _release on trigger key up
- Toggle mode: _toggle on keydown only
- DO NOT change voice.py's side of the pipe — same protocol must be kept

### New implementation plan for hotkey_service.py

**Main thread — Win32 message loop**
GetMessage() handles:
  WM_HOTKEY  (0x0312) → look up ID → send "dictation_press" / etc.
  WM_APP+1   (0x8001) → read from thread-safe queue → process "ping" or "quit"
  WM_QUIT             → break loop, clean up

**Daemon thread — pipe reader**
conn.recv() → puts command in queue → PostThreadMessage(main_thread_id, WM_APP+1)
This lets blocking conn.recv() coexist with a message loop without polling.

**Companion WH_KEYBOARD_LL hook — hold-mode releases only**
RegisterHotKey only fires on keydown. For hold mode, need keyup on trigger key.
SetWindowsHookExW(WH_KEYBOARD_LL, ...) watching ONLY WM_KEYUP on trigger VK codes.
NOT the full keyboard library — just 3 keys max.
Not needed for toggle mode.

**Hotkey ID → event map (hold mode)**
  1 → "dictation_press"     (dictation hotkey keydown)
  2 → "command_press"       (command hotkey keydown)
  3 → "prompt_press"        (prompt hotkey keydown)
  4 → "correction"          (f7)
  5 → "readback"            (f6)
  6 → "readback_selected"   (f5)
Toggle mode: same IDs, events become "dictation_toggle" etc., no companion hook.

**Hotkey string → VK + modifiers parser**
  "ctrl+space"  → MOD_CONTROL | MOD_NOREPEAT,           VK=0x20
  "ctrl+alt+d"  → MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, VK=0x44
  "f8"          → MOD_NOREPEAT,                          VK=0x77
MOD_NOREPEAT on all — prevents WM_HOTKEY spam during hold.

**_last_any_key_time staleness fix**
RegisterHotKey doesn't receive every key press — only registered hotkeys.
The 15-min staleness restart in voice.py would false-positive on an idle user.
Fix: also update _last_any_key_time whenever "ping" is processed in the message
loop. Pings arrive every ~30s from voice.py, so the staleness clock never goes
stale as long as the message loop is alive — which is exactly what we want to prove.

**Failure modes**
RegisterHotKey fails (another app owns hotkey) → log error, send "hooks_dead"
  → voice.py restarts and notifies user
Companion hook dies → WM_HOTKEY press events still work; release events stop
  until restart (voice.py watchdog handles this)

**Protocol unchanged** — same pipe messages in/out. voice.py needs zero changes.
After the rewrite, "Screen unlock detected — restarting hotkeys" should NEVER
appear in debug.log since RegisterHotKey survives lock natively.

### RegisterHotKey constants
MOD_ALT      = 0x0001
MOD_CONTROL  = 0x0002
MOD_SHIFT    = 0x0004
MOD_WIN      = 0x0008
MOD_NOREPEAT = 0x4000  # prevents WM_HOTKEY spam on key hold

### Key VK codes
VK_SPACE     = 0x20
VK_F1..F12   = 0x70..0x7B
VK_A..Z      = 0x41..0x5A (uppercase ASCII)
Example: "ctrl+space" → modifiers=MOD_CONTROL|MOD_NOREPEAT, vk=VK_SPACE
Example: "f8"         → modifiers=MOD_NOREPEAT, vk=0x77

### last_key_mono tracking
Update _last_any_key_time on every WM_HOTKEY received and on every trigger
key-up from the companion hook. Send in pong tuple as before.

### Proposal before building (Alex's workflow rule)
Read the current hotkey_service.py first, then propose the new design and
get approval before writing code.

### Tests
Run: venv\Scripts\python.exe -m pytest test_features.py test_e2e.py -x -q
Should pass 197 tests. Then manually test:
- Ctrl+Space hold-to-talk (dictation)
- F8 command mode
- F9 prompt assist
- Win+L to lock screen, unlock, verify hotkeys work WITHOUT needing restart
- Sleep/wake, verify hotkeys still work
- Check debug.log — should NOT see "Screen unlock detected — restarting"
  since RegisterHotKey survives lock natively

---

## TASK 2 (do after Task 1): Fix Whisper hallucination on long dictation

### Symptom
Koda transcribes short utterances correctly but during longer dictation it
hallucinates words. Example: said "paid in full", transcribed "patent".
Gets worse the longer the session runs.

### IMPORTANT: Check for conflicting STT software first
Koda opens the mic in SHARED mode (sounddevice.InputStream). Another STT
app recording simultaneously can corrupt the audio buffer and produce
exactly this symptom. Before touching Whisper params, ask Alex to run:

  Get-Process | Where-Object {$_.ProcessName -match "wispr|dragon|otter|talon|voiceattack|speech"}

If another STT tool is running, that may be the whole problem.

Known conflict points in Koda:
- No detection of other STT apps (Dragon, Wispr Flow, Win+H, Otter, Talon)
- Single-instance mutex only blocks other KODA instances (voice.py ~line 1726)
- SAPI5 TTS read-back can clash with Windows Narrator or other TTS engines

### Likely Whisper causes (diagnose before fixing)
1. Audio buffer too long — Whisper hallucinates on audio >30s or with long
   silences; no VAD to split on natural pauses
2. condition_on_previous_text=True — one bad transcription poisons the next
3. Missing hallucination suppression params (no_speech_threshold,
   logprob_threshold, compression_ratio_threshold not tuned)
4. Temperature too high / no fallback temperature ladder

### Approach
1. Read voice.py transcription pipeline — how audio is chunked and passed
   to Whisper, current Whisper params
2. Diagnose root cause
3. Propose fix BEFORE implementing (Alex's workflow rule)
4. Likely fix: set condition_on_previous_text=False, tune thresholds,
   and/or add VAD chunking (faster-whisper has built-in VAD support)

---

## Current state
- Branch: master, clean, up to date with origin/master
- Koda v4.2.0, Python 3.14, venv at C:\Users\alex\Projects\koda\venv
- 197 tests passing (test_features.py + test_e2e.py)
- GitHub: https://github.com/Moonhawk80/koda
- No NVIDIA GPU — Intel UHD 770 only, Whisper runs on CPU (int8)
- Desktop path: C:\Users\alex\OneDrive\Desktop (OneDrive sync)
- Hotkeys: Ctrl+Space=dictation, F8=command, F9=prompt assist,
  F7=correction, F6=read back, F5=read selected
- Alex's workflow rules: proposals before building, full drafts on edits,
  PRs for review, run /handover at session end, git pull at start/push at end
- Most recent handover: docs/sessions/ (check for latest session number)
```
