# NEXT:

## Voice-product ship sequence (locked 2026-04-24)

- [x] **Auto-polish on Send path — SHIPPED (commit `7afd41b`, pushed).** `prompt_assist.py:380` gate now fires when `refine_backend in ("ollama","api")` OR `llm_refine=True`. Regression-tested via 3 new cases in test_features.py (commit `f44d720`). 431/431 tests. Pre-push gate clean (forge-deslop 0, forge-review 0 after N1 resolved). Runtime verification = live mic test (below).
- [ ] **PR 1 — Finish live mic test of `feat/prompt-assist-v2` → merge → tag v4.4.0-beta1.** Re-run from source via `.\start.bat` with all 6 live-test fixes + auto-polish + Koda Dark v2 overlay (WIP commit `7440cfd` — visually untested, MUST eyeball before merge). Validate: Zira opener, beep cue, 2-slot Q&A (Task + Context only, NO Format), overlay renders cleanly (brand header + K mark + intent pill + layered body + 3-tier buttons + fade-in), Ollama polishes the prompt (Boca Tanning Club test: raw stitch → natural polished prompt), voice-confirm ("say send"), Escape cancels. **If overlay design doesn't land on live-eyeball, iterate on overlay.py only — auto-polish fix is locked.**
- [ ] **PR 2 — `feat/piper-tts` — Piper direct subprocess, Amy (en_US-amy-medium) as stock voice.** Bundle piper.exe + voice in installer (~80MB bloat). New `piper_tts.py` module, `config["tts"]["backend"]` toggle. Rejected NaturalVoiceSAPIAdapter — third-party SAPI DLL, trust issues.
- [ ] **PR 3 — `feat/koda-signature-voice` — Alex's wife's voice as Koda default.** Record ~30 min-2 hr clean audio, train Piper custom model, ship `.onnx` as default. Amy stays selectable. See `project_voice_roadmap.md` memory for full plan.

## Small fixes (discovered during live-test)

- [ ] **Port v2 pickers to Inno Setup installer** — `configure.py` has `setup_prompt_voice` + `setup_prompt_backend` (Step 9 + Step 10 of Python wizard) but Inno installer bypasses configure.py entirely. End users never see the v2 pickers unless they manually run `venv\Scripts\python configure.py` post-install. Port to Pascal `[Code]` pages in `installer/koda.iss`.
- [ ] **VAD tuning** — expose `VAD_RMS_THRESHOLD` (currently hardcoded 0.005 in slot_record) and silence_seconds in config. Defaults don't handle music or ambient noise; live-test session surfaced this.
- [ ] **Template simplification follow-through** — audit code/debug/explain/review/write templates for further 2022-era boilerplate per `project_template_philosophy.md`. Removed `Context:` block + general closer this session; intent-specific scaffolding kept, but worth another pass.
- [ ] **Clean up configure.py dual-"polish" summary** — "LLM polish" (legacy command-mode) vs "Prompt polish" (new v2 backend) are two different things; summary lists both, confusing.
- [ ] **Re-add cancel-via-hotkey-repress for prompt-assist v2** — `cancel_slot_record` API was removed by forge-deslop (no producer); add cleanly if/when prompt_press-during-active-conversation needs to cancel.
- [ ] **Fix `statusline-command.sh`** to render `.claude/next.md` first uncompleted item — currently only shows model + context bar.

## Runtime-test carried over

- [ ] Runtime-test `feat/voice-app-launch` (PR #28 from session 43): golden path ("open word"), prefix invariant ("please open word" must NOT fire), error fallback ("open gibberish"). Still pending.

## Separate projects (NOT v2 side-quests)

- [ ] **Multi-turn session mode (V3)** — per `feedback_multi_turn_vision.md`: Ctrl+F9 within 60s of paste → skip slots 2-3, ask "What's next?", reuse prior context. Own PR after Piper ships.
- [ ] Phase 16 licensing — blocks v2 paywall wrap (not the build). Tier count, subscription vs one-time, offline activation, "beta tester" marker. Beta testers grandfather into free tier 2.
- [ ] Signing approach (Azure Trusted Signing $10/mo recommended) — wire into `.github/workflows/build-release.yml`
- [ ] Whisper "dash" dropout fix direction — read `project_dash_word_dropout.md` memory first
- [ ] Wake word decision — train custom "hey koda" via openwakeword OR rip feature
- [ ] Phase 9 RDP test (pending since session 35)
- [ ] V2 app-launch: chaining ("open powershell and type git status"), window-ready check, "switch to X"
- [ ] Memory sync across machines — home PC writes to `C--Users-alexi/`, work PC to `C--Users-alex/`. Parked per Alex's request. Options: rename Windows user / OneDrive symlink / private git repo.

## Completed this session (work-PC session 45)

- [x] Voice-driven confirmation shipped (commit `75e5366`) — pre-push gate clean (forge-deslop 0, forge-review 0), 428/428 tests
- [x] Hotkey default regression fixed (commit `7c79237`) — configure.py now defaults to ctrl+f9 with Ctrl+F* picker options
- [x] Ship sequence locked (commit `b5987a8`) — 3-PR voice-product roadmap
- [x] Installer rebuilt as v4.4.0-beta1 — uninstalled v4.3.1, wiped config, fresh install, configure.py walked
- [x] Live-test bug-fix loop (batched commit this handover):
    - [x] Cross-module globals bridge for `_slot_chunks` / `_slot_recording`
    - [x] pyttsx3 → direct SAPI COM via comtypes (multi-thread safe)
    - [x] VAD voice_detected gate before silence-stop
    - [x] Format slot dropped (2-slot Q&A: Task + Context only)
    - [x] Template junk stripped (Context: block + generic closer + URL regex fix)
    - [x] Overlay redesign (flat Label-buttons, logo, Send→Paste, side="bottom" pack fix, dark palette, header + keyboard hints)
- [x] Whisper model bump base → small (cached locally, zero download)
- [x] Handover + 6 new memory entries

## Waiting / Blocked

- **Coworker re-test of v4.3.1 mic-hotplug + music-bleed** — needs installer re-share first (carried from session 41)
- **Memory sync across work PC / home PC** — deferred per Alex
