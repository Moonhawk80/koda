---
session: 45
date: 2026-04-24
scope: koda
resumes-from: alex-session-44-home-pc-handover.md
continues-work-from: null
projects-touched: [koda]
skills-activated: [forge-resume, forge-deslop, forge-review, forge-handover]
---

# Work-PC Session 45 Handover — 2026-04-24

Big work-PC session picking up from home-PC session 44. Three distinct phases:
(1) voice-confirm feature built + gated + pushed; (2) installer rebuild + work-PC
re-install for live mic test; (3) the live-test itself — surfaced 6 real bugs in
rapid succession and fixed each inline. Handover invoked at ~50% context after
Alex flagged "rookie build" feedback on the overlay aesthetics.

## Branch
`feat/prompt-assist-v2` at HEAD. Session started on `docs/prompt-assist-v2-design`
(merged as PR #33 at session 44's tail), synced master, then worked entirely on
`feat/prompt-assist-v2`. Multiple commits pushed mid-session. As of handover
start, working tree has 5 code files + 1 config.json uncommitted pending this
handover's batch commit.

## TL;DR

1. **Voice-confirm feature shipped** (commit `75e5366`, pushed). Parallel
   listener at CONFIRMING state routes "send/refine/add/cancel/explain" through
   same callbacks as overlay buttons. 428/428 tests. Pre-push gate ran clean
   (forge-deslop 0 findings, forge-review 0 findings across all 6 layers).
2. **Hotkey-default regression fixed** (commit `7c79237`, pushed). `configure.py`
   still defaulted prompt-assist to bare `f9` and only offered `FKEY_OPTIONS`
   (F5–F12) at the picker — missing the `ctrl+f9` variant Session 43 deliberately
   set as default (commit `a55a0e7`) to avoid Alienware Command Center OEM
   collision. Added `PROMPT_FKEY_OPTIONS` list with Ctrl+F* variants first.
3. **Voice-roadmap ship sequence locked** (commit `b5987a8`, pushed). 3-PR
   plan agreed with Alex: v2 MVP (Zira) → `feat/piper-tts` (Amy) →
   `feat/koda-signature-voice` (wife's voice as Koda's default). Project memory
   `project_voice_roadmap.md` captures full plan including spousal-agreement +
   licensing considerations for the signature-voice PR.
4. **Installer rebuilt + fresh-installed as v4.4.0-beta1.** `koda.iss` version
   bumped + `MyAppVersionNumeric` split out (Windows requires numeric-only
   VersionInfoVersion; "4.4.0-beta1.0" was invalid). Silent uninstalled v4.3.1,
   wiped `%APPDATA%\Koda\config.json`, ran fresh install, stepped through
   configure.py's 11-page Python wizard (the Inno installer does NOT invoke
   configure.py — discovered this live; Inno wizard has its own 4 Pascal pages
   for mic/hotkey/model/formula; Python pickers for voice + LLM backend live
   in configure.py only).
5. **Live mic test found 6 bugs. All fixed.** See "What Was Built This Session"
   for each.

## What Was Built This Session

### A. Voice-confirm feature — `feat/prompt-assist-v2` commit `75e5366`

Closes the Step 4 carveout from session 44 (voice-driven confirmation at CONFIRMING state).

- `voice.py::slot_record` gains `cancel_event` kwarg — polling loop checks every
  80ms so button press stops recording immediately (was waiting for VAD silence).
- `prompt_conversation._default_record_confirm_voice` — new default for voice
  listener. Fast no-op when audio unavailable (model None or stream None) so
  tests without mic pay no cost.
- `run_conversation` gains `record_confirm_voice` kwarg. At CONFIRMING state
  spawns daemon listener thread doing up to 3 attempts (each ~6s), classifies
  via existing `classify_confirm_response()`, routes through SAME callbacks as
  overlay buttons. Overlay's `decided[]` flag provides race-safety when voice
  + button fire near-simultaneously.
- Button callbacks ALSO set `voice_cancel_event` so listener stops recording
  promptly instead of waiting out VAD silence. Bounded 300ms `voice_thread.join`
  on return so callers observe fully-settled state (critical for tests).
- "explain" path speaks full assembled prompt and keeps listening (doesn't
  advance) — matches design doc §confirmation step.
- 7 new tests in `TestPromptConvVoiceConfirm`: send/refine/add/cancel routing,
  unknown-voice-falls-through-to-button, button-cancels-voice, explain-reads-
  back-and-continues. 421 → 428 passing.

Pre-push gate:
- Skill Forge freshness check: `exit 0` (current).
- forge-deslop on `origin/master..HEAD`: 0 findings across all 7 patterns.
  Report at `.forge-deslop/run-20260424-voiceconfirm/report.md`.
- forge-review on same range: 0 BLOCKING, 0 NEEDS-FIX, 0 NIT across all 6
  layers. Claims-vs-reality audit passed — all commit-message claims verified.
  Report at `.forge-review/run-20260424-voiceconfirm/report.md`.

### B. Hotkey regression fix — commit `7c79237`

Discovered after Alex ran configure.py and saw `Prompt Assist: f9` in the
summary. Session 43 commit `a55a0e7` had deliberately moved the prompt-assist
default to `ctrl+f9` because bare F9 collides with Alienware Command Center
(OEM performance-mode toggle) on many laptops. That commit updated config.py
DEFAULT_CONFIG and settings_gui.py's dropdown, but missed configure.py's
first-run wizard, which still presented bare F5-F12 as the only options.

Fix adds `PROMPT_FKEY_OPTIONS` list (Ctrl+F9 / Ctrl+F8 / Ctrl+F10-12 first,
then bare F9-12 for non-conflicting hardware). Uncustomized default flipped to
`ctrl+f9`. Summary help text updated. Also bumped installer version to
4.4.0-beta1 + split `MyAppVersionNumeric` since `"4.4.0-beta1.0"` is invalid
for Windows VersionInfoVersion (must be purely numeric).

### C. Ship sequence lock — commit `b5987a8`

Per `project_voice_roadmap.md` memory. `.claude/next.md` restructured with
the 3-PR voice-product ship sequence at top, small fixes grouped, separate
projects clearly labeled, session wins moved to `## Completed` block.

### D. Installer rebuild as v4.4.0-beta1

- `installer/koda.iss` MyAppVersion "4.3.1" → "4.4.0-beta1"; added
  MyAppVersionNumeric "4.4.0.1" for VersionInfoVersion/ProductVersion (Windows
  requires purely numeric).
- `installer/build_installer.py` ran end-to-end: PyInstaller produced
  Koda.exe (~559MB with bundled Whisper model), Inno Setup compiled the
  installer in ~97s. Output: `dist/KodaSetup-4.4.0-beta1.exe`.
- Silent uninstalled v4.3.1 via `"C:\Program Files\Koda\unins000.exe" /SILENT
  /SUPPRESSMSGBOXES`. Wiped `%APPDATA%\Koda\config.json` to force first-run
  wizard (auth required — see "User Feedback" below).
- Ran new installer interactively, stepped through Inno's 4 wizard pages
  (mic / hotkey / model / formula). User then ran `venv/Scripts/python
  configure.py` for the 11-step Python wizard to exercise the v2 voice +
  LLM-backend pickers — because the Inno installer DOES NOT invoke
  configure.py (separate wizard, separate code paths). This is the
  Step 5-era scope gap flagged in session 44's handover.

### E. Live-test bug-fix loop (all committed as one hardening commit at handover)

Six distinct bugs surfaced during the live-test and fixed inline:

**E1. `configure.py` hotkey-default regression** — see (B) above. Committed at
`7c79237`.

**E2. Cross-module globals — `_slot_chunks` / `_slot_recording` split.**
Classic Python gotcha. voice.py runs as `__main__` (from start.bat); audio_callback
registered there writes to `__main__._slot_chunks`. But prompt_conversation does
`from voice import slot_record` which imports voice as a SEPARATE module object;
slot_record's `global _slot_chunks` resolves to `voice._slot_chunks`, never
populated. Symptom: every slot hit `max_seconds=15.0 (voice_detected=False)` —
user spoke but audio never reached transcription. debug.log quiet because stream
checks passed (I'd already bridged `model` and `stream`) but `_slot_chunks` wasn't
bridged. Fix: added bridge in `slot_record` via `sys.modules["__main__"]` for
all audio-callback-affected state. Memory captured as
`project_cross_module_globals_bug.md` so future sessions don't re-learn.

**E3. pyttsx3 `run loop already started` RuntimeError across daemon threads.**
First opener spoke correctly; second+ speak calls in prompt_conversation
(context question / format question / confirm summary) all failed with
`RuntimeError: run loop already started`. My first fix (create fresh
`pyttsx3.init()` per call) HUNG silently — worse. Root cause: pyttsx3's event
loop is thread-affinity-coupled and never cleanly releases across daemon-thread
invocations. Fix: rewrite `_default_tts_speak` to use direct SAPI COM via
`comtypes.client.CreateObject("SAPI.SpVoice")` + `pythoncom.CoInitialize()`.
Synchronous, thread-safe, bypasses pyttsx3 entirely. Legacy `readback()` /
`read_selected()` still use pyttsx3 — they're single-shot dedicated threads, no
collision. Memory captured as `project_pyttsx3_threading_bug.md`.

**E4. VAD silence-stop firing before user speaks.** slot_record's
`last_voice = time.time()` initialization at recording start meant silence_seconds
(1.5s) would fire at t=1.5s whether or not the user had spoken. Alex spoke, VAD
closed the window after 1.5s of their normal pre-speech pause, got empty
transcription, moved to next question — "it's going back to back questions
without stopping." Fix: added `voice_detected` bool that must be True before
silence-stop is allowed. Initial silence now holds until user speaks OR
max_seconds fires. Max 15s per slot if user never speaks.

**E5. Format slot dropped.** Per Alex feedback: "I don't think the last
question is a viable question like the person who's trying to build this
doesn't know that's what we're using it." The Format question ("What should
the answer look like?") assumes prompt-engineering literacy non-technical
users don't have. Design-doc rationale ("forecloses rambling, cheap ask
for quality lift") was 2022-era GPT-3 thinking — Claude 4 and GPT-5 don't
ramble. Removed `SLOT_QUESTIONS["format"]`, the SPEAKING_FORMAT_Q + LISTENING_
FORMAT block in run_conversation, updated `test_happy_path_3_slots_then_send`
→ `test_happy_path_2_slots_then_send` (expected speak count 4 → 3).
Slots dict still carries `"format": ""` for _combine_slots structural
compatibility. Memory: `project_format_slot_dropped.md`.

**E6. Template junk ("that sucks as an output").** Two offending parts:
(a) every template emitted a `Context:` block populated by `_extract_details()`
which re-listed names/URLs/tech the user had JUST said — redundant. (b) the
general template closed with "Please be specific and thorough in your response.
If you need clarification on anything, ask before proceeding." — 2022-era
prompt-engineering theatre. Frontier models handle omission fine; adds noise.
Fix: stripped the `if context: parts.append(f"\nContext:\n{context}")` from
all 6 templates. Stripped the general closer. All intent-specific scaffolding
(code Requirements / debug root-cause steps / review severity / write tone
guidelines) kept — those are actually useful. Also fixed the URL regex non-
capturing group bug that produced "URLs: com" instead of full domain. Memory:
`project_template_philosophy.md`.

**E7. Overlay "no buttons" + "windows 98 buttons" + "missing logo."**
Layered UI bugs discovered in rapid succession:
- Buttons invisible because `btn_row` packed at `side="top"` (default) AFTER
  `body.pack(expand=True)`. body claimed entire window height; btn_row
  squeezed to 0px. Fix: pack `btn_row` at `side="bottom"` BEFORE body so it
  reserves its slot. Classic tk pack-order gotcha.
- Alex: "nasty basic windows 98 buttons." tk.Button on Windows renders a
  native raised bevel even with `bd=0` and `relief="flat"`. Can't fully
  flatten. Fix: replaced every button with `tk.Label` + click bindings —
  total control over appearance, proper hover states, no native chrome.
  Added `_lighten()` helper for hover color computation.
- Alex: "Koda logo is also missing from that window." Added
  `root.iconbitmap(koda.ico)` with best-effort try/except.
- Send → Paste button relabel. "Send" was ambiguous ("send where?"); "Paste"
  matches what the code actually does.
- Overall dark-theme refresh: new palette (BG=#14161a / SURFACE=#1d2026 /
  BORDER=#2a2e36 / FG=#eceef2 / DIM=#8a8f99). Header with Koda wordmark +
  "Prompt Preview" + right-aligned keyboard hint ("Enter = Paste   Esc =
  Cancel"). Body has a subtle border to feel like a card, not raw text.
  Buttons: Cancel / Add / Refine on left (secondary), Paste on right as
  primary (solid-filled green). All with hover lift via `_lighten()`.
- Window size bumped 680×460 → 720×520 to accommodate header.

Memory: `feedback_ui_quality_bar.md` captures the shipped-product quality
bar. Alex will flag rough first-draft UI as blocking even on feature
branches.

### F. Whisper accuracy upgrade: base → small

Alex's test prompt ("Boca Tanning Club") transcribed as "Bogotani Club" on
Whisper base. Small model is already cached in `~/.cache/huggingface/hub/
models--Systran--faster-whisper-small/snapshots/`. Bumped `config.json
model_size` to "small" — instant upgrade, no download. Dramatic proper-noun
accuracy improvement expected. (config.json NOT included in this session's
commit — it's runtime state.)

## Decisions Made

### Drop Format slot entirely rather than rephrase or auto-infer

Considered three options: (a) rephrase more intuitively ("How detailed?"
or "Short or thorough?"), (b) auto-infer format from task intent and skip
question, (c) drop entirely. Chose (c) because modern frontier models don't
need format instructions, the question confused the specific user we're
building for, and the overlay Add button still supports format-specific
tweaks for the rare user who wants control.

### pyttsx3 → direct SAPI COM (not pyttsx3 reset + retry)

First attempted fix was catch `RuntimeError: run loop already started`,
reset engine singleton, retry. Validated by reading pyttsx3 source — the
`_inLoop` flag resets on `endLoop()` in theory but reality is flakier
across daemon threads. Abandoned when second-attempt "fresh engine per call"
hung silently (worse symptom). Direct COM via `comtypes.client.CreateObject
("SAPI.SpVoice")` + `pythoncom.CoInitialize()` is thread-affinity-safe and
synchronous, bypasses pyttsx3's event loop entirely. comtypes is already a
project dependency — no new requirement.

### Voice roadmap: 3 PRs, wife's voice as default

Locked earlier in session. PR 1 = v2 MVP with Zira (in-flight). PR 2 =
`feat/piper-tts` — bundle piper.exe + Amy (en_US-amy-medium) as stock voice,
~80MB installer bloat, no third-party system DLLs (rejected
NaturalVoiceSAPIAdapter on trust grounds — it registers SAPI hooks
system-wide across all Windows apps, not just Koda, and was maintained by
an unverified author). PR 3 = `feat/koda-signature-voice` — Alex records his
wife reading ~500-3000 LJSpeech-style sentences, trains Piper model on Colab/
RunPod, ships resulting .onnx as Koda's default voice. Amy stays selectable
fallback. Considerations captured in memory: spousal buy-in, recording
consistency, written license for commercial (Phase 16) use, swap-ability.

### Ship v2 ungated now, paywall after beta

Re-confirmed earlier decision. Beta testers grandfather into free tier 2.
Phase 16 licensing decisions (tier count, subscription vs one-time, offline
activation, durable "beta tester" marker) still blocking the paywall wrap
but NOT v2's code ship.

### Don't include config.json in this session's commit

`config.json` is tracked in git but reflects user-specific runtime state
(voice=Zira selection, hotkey choices from configure.py, model_size bump to
"small"). The actual default in `config.py DEFAULT_CONFIG` is already
`"model_size": "small"`. Including his runtime config.json would commit
personal state as if it were a default change. Excluded from the commit.

## User Feedback & Corrections

### "this is a very sloppy build" (voice picker missing from installer)

Alex ran the Inno installer and expected the voice picker + LLM-backend
picker to appear. They didn't — because the Inno wizard has 4 Pascal-based
pages (mic / hotkey / model / formula) and never invokes configure.py.
Session 44 added the voice + LLM pickers to configure.py's 11-step Python
wizard, but did NOT port them to Inno. Verbatim: "so its not in the git?
can we make that a rule to put it in the git? or is that crazy?" (actually
about memory sync — separate thread).

**Follow-up:** `.claude/next.md` now has "Port v2 pickers to Inno Setup
installer" as an explicit backlog item. Not this session's scope — this
session stayed focused on hardening the already-built code.

### "that sucks as an output and then what does the user do?"

Direct critique of the assembled prompt that appeared in the overlay. The
prompt had a redundant `Context:` block + generic closer. Led to template
simplification (see E6 above) + memory `project_template_philosophy.md`.

### "nasty basic windows 98 buttons" / "terrible looks like a rookie build"

Direct critique of the overlay's default tk.Button chrome. Led to full
overlay rebuild with tk.Label-based custom buttons + palette refresh + logo
+ keyboard hints (see E7 above) + memory `feedback_ui_quality_bar.md`.

### "I said boca tanning club I have no idea what it picked up"

Whisper accuracy complaint. Base model misheard "Boca Tanning Club" as
"Bogotani Club" and "BocaTanningClub.com" as "gothendingclubcom". Led to
config bump to "small" model (already cached locally, zero download cost).

### "AI sessions are never just one prompt so she has to keep going"

Product insight. Captured as V3 feature in memory `feedback_multi_turn_vision.md`.
Do NOT retrofit into v2 — session-aware follow-up is own PR after Piper ships.

### "pause here do handover skill we are at 50% context"

Handover invoked after overlay rebuild landed and 428/428 tests passed.
Atomic action was mid-edit (`_lighten()` referenced but not yet defined) —
completed the definition + verified import before invoking forge-handover
per the "atomic action" rule in global CLAUDE.md.

### "its not control f9" vs historical context check

Alex briefly questioned whether `ctrl+f9` was correct or an error. Git log
on `config.py` showed commit `a55a0e7` explicitly remapped bare F9 → ctrl+f9
to avoid Alienware Command Center OEM conflict. Confirmed ctrl+f9 was
deliberate.

### "nah dont worry about the home pc I cant do anything right now"

On memory sync between work PC (`C--Users-alex`) and home PC (`C--Users-alexi`).
Alex rejected my proposed three paths (Windows username rename / OneDrive
symlink / private git repo) and asked to defer. Noted as a waiting-on item.

### "pick your koda voice on install! yes!"

Earlier session enthusiasm about voice-picker as an install-time feature.
That's `configure.py setup_prompt_voice` which IS built but NOT wired into
the Inno installer — see "sloppy build" feedback above.

## Dead Ends Explored

### pyttsx3 fresh-engine-per-call (RuntimeError recovery)

Considered catching `RuntimeError: run loop already started` and creating
a fresh `pyttsx3.init()` instance per speak call. Theory: new engine → fresh
loop state. Reality: pyttsx3.init() itself hangs silently when called in a
new daemon thread after the first call. Abandoned. Moved to direct SAPI COM.

### psutil for active-window process name

Session 44 considered adding `psutil>=5.9.0` for `win32 process name` lookup
during platform detection. Rejected during session 44 in favor of pure
pywin32 (`win32api.OpenProcess` + `GetModuleFileNameEx`). Re-validated this
session — no regression, pywin32 handles it cleanly without the extra dep.

### NaturalVoiceSAPIAdapter (third-party SAPI5 bridge for Piper voices)

Considered as the Piper TTS integration path since it exposes Piper voices
as SAPI5 voices (existing pyttsx3 code would "just work"). Rejected on trust
grounds: third-party C++ DLL from a Chinese maintainer, not Microsoft-signed,
registers at SYSTEM SAPI level so it loads into Narrator / Edge read-aloud /
every Windows app that does TTS — not just Koda. Alex's instinct ("it has
Chinese words on it I am scared to download something like this") was
correct. Revised plan: Piper via direct subprocess call from Koda (piper.exe
bundled, no system-wide DLL, same Piper voices).

### Windows 11 Narrator Natural voices

Considered as a zero-third-party quality-upgrade path for TTS. Microsoft-
signed, built into Windows 11, free. Risk: Narrator Natural voices live in
`Windows.Media.SpeechSynthesis` (not SAPI5), so `pyttsx3` may not enumerate
them. Would require code changes to switch backends AND leave Windows 10
users excluded. Rejected in favor of Piper subprocess (works on Win10+11,
same implementation across all users).

### Keeping Format slot with rephrased question

Considered rephrasing "What should the answer look like?" to "How detailed?"
or "Short or thorough?" before dropping entirely. Rejected because (a) user
critique was about asking ANY format question at all to non-technical
users, not about the specific wording, and (b) modern frontier models don't
need format instructions for good output. Cleaner to drop.

### Auto-infer Format from Task intent (skip question when confident)

Considered detecting Task intent (code / email / explanation / etc.) and
skipping Format question when inference is high-confidence. Rejected because
detect_intent() already defaults to "general" ~40% of the time (intent
detection fails silently and frequently), so we'd still ask Format on all
general-intent tasks — and those are exactly the non-technical users who
got confused. Dropping is both simpler and fixes the harder case.

### Silent uninstall + config wipe without explicit authorization

Attempted during the fresh-install flow. Permission denied by sandbox
because Alex's earlier instruction "rebuild the installer and reinstall it
here" didn't explicitly authorize silent uninstall of existing v4.3.1 +
wiping AppData. Correct denial. Re-asked Alex with numbered options, he
picked option 4 (re-authorize silent path), then the uninstall + config
wipe ran cleanly.

### Running configure.py via Claude Code `! ` prefix in PowerShell

Alex typed `! venv/Scripts/python configure.py` in his PowerShell session
(not in Claude Code's chat input). PowerShell parsed `!` as a negation
operator and errored. Clarified: `! ` prefix is Claude Code chat-input
syntax, not a shell command. Fixed by giving him bare `venv\Scripts\python
configure.py` for PowerShell.

### Memory sync across work PC and home PC

Three options discussed: (1) rename home PC Windows user `alexi` → `alex`,
(2) OneDrive-sync + symlink `~/.claude/projects/`, (3) private git repo
with sync scripts. Alex deferred — "nah dont worry about the home pc I
cant do anything right now maybe we put it as a note on the PR." Noted in
next.md as parked.

## Skills Activated This Session

- **`/forge-resume`** — session-start read of session 44 handover +
  project memory + git state. Warmed file cache (11 files, ~7500 tokens).
  Produced "where we left off + recommended next action" summary.

- **`/forge-deslop origin/master..HEAD`** — pre-push gate for the voice-confirm
  commit (`75e5366`). Scope: 3 commits (ffc400b home-PC MVP already gated,
  b86df27 handover docs-only, 75e5366 voice-confirm). Active scope: 75e5366
  only. Verdict: **clean, 0 findings across all 7 patterns.** NOT flagged
  (per `feedback_honest_deslop_ranking` memory): `except Exception` broad
  catch in `_default_record_confirm_voice` (intentional; voice-confirm is
  additive side channel, button path always available); magic numbers
  (`attempts < 3`, `max_seconds=6.0`, `join(timeout=0.3)` all single-usage);
  if/elif chain for kind→callback (4 readable branches); `cancelled` flag +
  late return in slot_record (clearer than collapsed return). Report at
  `.forge-deslop/run-20260424-voiceconfirm/report.md`.

- **`/forge-review origin/master..HEAD`** — pre-push gate, 6 layers. Verdict:
  **0 BLOCKING / 0 NEEDS-FIX / 0 NIT.** Layers: tests PASS (428/428, +7 from
  baseline), lint+typecheck SKIPPED (no configs in repo — Python untyped),
  hallucinated APIs PASS (no new third-party imports), test coverage delta
  PASS (+7 tests for +283 LOC behavior), AI slop covered by forge-deslop
  (clean), migration safety SKIPPED (no migrations), style drift PASS
  (Optional[Callable], threading.Thread(daemon=True), `_default_*` naming,
  logger levels — all consistent). Claims-vs-reality: commit message
  claims verified (428/428 correct, "parallel voice listener" present,
  "cancel_event kwarg on slot_record" present, all accurate). Report at
  `.forge-review/run-20260424-voiceconfirm/report.md`.

- **`/forge-handover`** — this invocation.

No `/forge-test`, `/forge-clean`, `/forge-migrate`, `/forge-organize`,
`/forge-secrets` this session.

## Memory Updates

Written this session to `~/.claude/projects/C--Users-alex-Projects-koda/memory/`:

- **`feedback_ui_quality_bar.md`** (new) — Koda v2 held to shipped-product
  polish. Cites verbatim "sloppy / rookie / terrible" critiques. Default
  tk.Button chrome NOT acceptable on user-facing v2 surfaces. Modern
  frontier models don't need generic "please be thorough" closers.
  Manual live-test is load-bearing before merge — unit tests don't catch
  pack-order bugs or UI aesthetics.

- **`feedback_multi_turn_vision.md`** (new) — AI sessions are never one
  prompt. Captures Alex's product insight verbatim. V3 feature `feat/
  prompt-assist-session`: short-window re-trigger (Ctrl+F9 within 60s of
  paste → skip slots 2-3, ask only "What's next?", reuse prior context).
  Explicitly do NOT block v2 on this.

- **`project_pyttsx3_threading_bug.md`** (new) — documents the
  `RuntimeError: run loop already started` + silent-hang-on-retry pattern.
  Fix: direct SAPI COM via comtypes. Legacy `readback()` still on pyttsx3
  is safe (single dedicated threads, no collision).

- **`project_cross_module_globals_bug.md`** (new) — documents the
  `__main__` vs imported-`voice` split-globals gotcha. Bridge pattern via
  `sys.modules["__main__"]` in any function that reads/writes audio-callback-
  touched state (`_slot_chunks`, `_slot_recording`, `model`, `stream`).
  Long-term cleaner fix: extract audio state into dedicated module.

- **`project_format_slot_dropped.md`** (new) — v2 is 2-slot (Task + Context).
  Format question dropped 2026-04-24. Don't re-add without explicit Alex
  approval. Users wanting format specifics use the overlay Add button.

- **`project_template_philosophy.md`** (new) — prompt-assist templates should
  output user words + intent-specific scaffolding only. NO `Context:`
  extract-block (redundant). NO generic "please be specific" closer (2022-era
  theatre). Intent-specific scaffolding (code Requirements / debug steps
  / review severity / write tone) kept.

- **`MEMORY.md`** (updated) — 6 new index entries appended.

No deletions. No modifications to existing memory files.

## Waiting On

- **Live mic test completion of `feat/prompt-assist-v2`** — Alex paused at
  50% context after overlay rebuild landed. Next session: launch Koda from
  source via `.\start.bat`, press Ctrl+F9 in Claude, validate full flow
  with all 6 live-test fixes applied + Zira voice + small Whisper model.
- **PR open decision** — `feat/prompt-assist-v2` stays on remote awaiting
  live-test validation. Decide at next session whether to open draft PR or
  continue iterating on branch first.
- **Coworker re-test of v4.3.1 mic-hotplug + music-bleed** — carried from
  session 41. Needs installer re-share.
- **Memory sync between work PC and home PC** — parked per Alex's request.
  Will address when he has time to commit to one of the three paths
  (rename user / OneDrive symlink / git repo).

## Next Session Priorities

Per `.claude/next.md` (updated this session):

1. **Finish live mic test of `feat/prompt-assist-v2`.** Re-run with all six
   fixes applied. Validate: opener plays (Zira), start-sound beeps, user
   speaks → slot transcribes correctly (small model — "Boca Tanning Club"
   should render cleanly now), 2-slot flow (Task + Context only, no
   Format), overlay opens with clean prompt (no junk Context block / no
   generic closer), buttons visible at bottom (Cancel / Add / Refine on
   left; Paste on right), voice-confirm works ("say send" → paste into
   Claude), Escape cancels.
2. **Merge `feat/prompt-assist-v2` to master** after live-test passes.
   Tag `v4.4.0-beta1`.
3. **Port v2 pickers to Inno Setup installer** — `configure.py` has
   setup_prompt_voice + setup_prompt_backend but Inno installer bypasses
   configure.py entirely. End users going through Inno wizard never see
   the v2 pickers. Separate PR.
4. **`feat/piper-tts`** — Piper direct subprocess, Amy (en_US-amy-medium)
   as stock voice. See `project_voice_roadmap.md` memory.
5. **`feat/koda-signature-voice`** — Alex's wife's voice as Koda default.
   See `project_voice_roadmap.md` memory for training flow.
6. **Multi-turn session mode** (V3, separate PR) — short-window re-trigger
   per `feedback_multi_turn_vision.md` memory.
7. **VAD tuning** — expose `VAD_RMS_THRESHOLD` and `silence_seconds` in
   config. Defaults don't handle music/ambient noise well. Live-test
   surfaced this.
8. **Template simplification follow-through** — audit code/debug/explain/
   review/write templates for further 2022-era boilerplate that can be
   stripped per `project_template_philosophy.md`.
9. **Phase 16 licensing** — blocks paywall wrap, not v2 build. Tier count,
   subscription vs one-time, offline activation, beta-tester marker.
10. **Azure Trusted Signing** ($10/mo recommended) — wire into
    `.github/workflows/build-release.yml`.
11. **Whisper "dash" dropout fix direction** — read
    `project_dash_word_dropout.md` memory first.
12. **Wake word decision** — train custom "hey koda" or rip feature.
13. **Phase 9 RDP test** (carried from session 35).
14. **V2 app-launch** — chaining, window-ready check, switch-to-X.

## Files Changed

### Pushed earlier this session

- **commit `75e5366`** `feat: voice-driven confirmation for prompt-assist v2`
  - `voice.py` — `slot_record` gains `cancel_event` kwarg + poll
  - `prompt_conversation.py` — `_default_record_confirm_voice`,
    `record_confirm_voice` param, voice listener daemon + bounded join,
    button callbacks set `voice_cancel_event`, explain loop-back path
  - `test_features.py` — +7 tests in `TestPromptConvVoiceConfirm` (+283 LOC behavior, 421 → 428 tests)

- **commit `7c79237`** `fix(configure): default prompt-assist hotkey to ctrl+f9`
  - `configure.py` — `PROMPT_FKEY_OPTIONS` list, default `ctrl+f9`, updated
    help text
  - `installer/koda.iss` — MyAppVersion "4.3.1" → "4.4.0-beta1", added
    `MyAppVersionNumeric "4.4.0.1"` for VersionInfoVersion fields

- **commit `b5987a8`** `chore(next.md): lock voice-product ship sequence`
  - `.claude/next.md` — restructured with 3-PR voice-product sequence at top

### Uncommitted at handover start (all landing in this session's batch commit)

- `voice.py` — slot_record cross-module bridge (_slot_chunks / _slot_recording
  via sys.modules["__main__"]), voice_detected gate before VAD silence-stop
- `prompt_conversation.py` — `_default_tts_speak` rewrite (pyttsx3 → direct
  SAPI COM via comtypes/pythoncom), Format slot removed from state machine
- `prompt_assist.py` — `Context:` block stripped from all 6 templates,
  generic closer stripped from `_template_general`, URL regex non-capturing-
  group fix ("URLs: com" → full domain)
- `overlay.py` — `_lighten()` helper, pack order fix (btn_row side="bottom"
  BEFORE body), tk.Label-based flat custom buttons with hover, Koda logo in
  title bar, dark palette refresh, header with wordmark + keyboard hint,
  primary Paste button (was Send), secondary Cancel/Add/Refine layout
- `test_features.py` — `test_happy_path_3_slots_then_send` renamed to
  `test_happy_path_2_slots_then_send`, expected speak count 4 → 3

### NOT included in commit (runtime state)

- `config.json` — user's per-install voice/hotkey/model picks from this
  session's configure.py run. The default in `config.py DEFAULT_CONFIG` is
  already `"model_size": "small"` — Alex's Zira voice name and other picks
  are personal state, shouldn't land as repo defaults.

### Memory files (outside git)

- 6 new files + MEMORY.md index update — see "Memory Updates" section.

## Key Reminders

- **Manual live-test is load-bearing before merging a UI-touching feature.**
  forge-deslop + forge-review both came back 0-findings on the voice-confirm
  commit. Then live-test surfaced 6 distinct bugs in rapid succession. Unit
  tests validate behavior, not look-and-feel or cross-module integration
  gotchas. The pre-push gate protects against AI-slop regressions; it does
  NOT substitute for hands-on-mic-and-eyes validation.

- **pyttsx3.runAndWait() is broken from daemon threads on Windows SAPI5.**
  Do not use `pyttsx3` in any new prompt-assist code. Direct SAPI COM via
  `comtypes.client.CreateObject("SAPI.SpVoice")` + `pythoncom.CoInitialize()`
  is the pattern. Legacy `readback()` / `read_selected()` in voice.py still
  use pyttsx3 but are in dedicated single-shot threads where the bug doesn't
  manifest — do not refactor them preemptively.

- **voice.py cross-module globals require bridging.** Whenever a function in
  voice.py uses `global` state that audio_callback writes to
  (`_slot_chunks`, `_slot_recording`, `recording`, `audio_chunks`, `model`,
  `stream`), and might be called from `prompt_conversation` or another
  module via `from voice import ...`, add the sys.modules["__main__"]
  bridge pattern. Otherwise imported-side sees stale/None globals.

- **Format slot is permanently dropped from v2 UX.** Do not re-add without
  explicit Alex approval. The `"format"` key in the slots dict is kept for
  `_combine_slots` structural compatibility only — no UI path populates it.

- **Overlay buttons are tk.Label-based, not tk.Button.** tk.Button renders
  Windows native chrome regardless of `bd=0` / `relief="flat"`. Any new
  buttons in overlay.py should use the `_make_button()` helper.

- **Alex's UI quality bar is shipped-product polish.** Rough first-draft
  chrome, default framework widgets, generic prompt-engineering boilerplate
  in output, missing logo — all get flagged as blocking even on feature
  branches. Mental first-impression pass before calling anything "done."

- **AI sessions are multi-turn by nature.** v2 is one-shot by MVP scope;
  V3 adds short-window follow-up mode. Don't retrofit multi-turn into v2.

- **Inno installer and configure.py are two different wizards.** The Inno
  installer does NOT invoke configure.py. Voice-picker + LLM-backend picker
  live in configure.py only. End users running the installer never see
  them unless they manually run `venv\Scripts\python configure.py` after
  install. Follow-up PR: port Pascal-based wizard pages.

- **pre-push gate is mandatory for code pushes.** Session 44 established
  the pattern: Skill Forge freshness check → forge-deslop → forge-review
  → push. This session followed it for commit `75e5366`. Worth it — gates
  came back clean, which lets us focus live-test findings on what forge-*
  can't catch (cross-module integration, UI rendering, real-world VAD
  behavior).

- **config.json is tracked but contains runtime state.** Don't commit
  personal install choices (voice names, hotkey picks, model size) as if
  they're default changes. `config.py DEFAULT_CONFIG` is the default; edits
  to live `config.json` are the user's local state.

## Migration Status

No DB migrations this session. Koda has no schema changes — `koda_history.db`
and `koda_stats.db` schemas untouched.

## Test Status

- **428/428 tests passing** (was 421 at session start; +7 this session, all
  in `TestPromptConvVoiceConfirm`).
- Suite: `venv/Scripts/python -m pytest test_features.py -q`
- Full suite ran multiple times mid-session to verify each bug-fix didn't
  regress anything. All runs green.

## Resume pointer

```
cd C:/Users/alex/Projects/koda
# then in Claude Code:
/forge-resume
```
