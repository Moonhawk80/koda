# NEXT:

## Voice-product ship sequence (locked 2026-04-24)

- [ ] **PR 1 — live-test `feat/prompt-assist-v2` with Zira → merge → tag v4.4.0-beta1.** Kill installed Koda, run from source via `.\start.bat`, press Ctrl+F9 in any AI app. Validate: TTS opener plays, 3-slot Q&A, overlay (Send/Refine/Add/Cancel + Escape), voice-confirm ("send"/"refine"/"add X"/"cancel"), paste into original window. Edge cases: cancel mid-flow, short-circuit on long answer, 15s timeout. MVP ships with robotic voice — fine.
- [ ] **PR 2 — `feat/piper-tts` — Piper direct subprocess, Amy (en_US-amy-medium) as stock voice.** Bundle piper.exe + voice in installer (~80MB bloat, ~620MB total). New `piper_tts.py` module, `config["tts"]["backend"]` toggle (sapi5 / piper). Settings GUI dropdown. Rejected NaturalVoiceSAPIAdapter — system-wide DLL, trust issues.
- [ ] **PR 3 — `feat/koda-signature-voice` — Alex's wife's voice as Koda default.** Record ~30 min-2 hr clean audio, train Piper custom model (Colab overnight or RunPod ~$10), ship `.onnx` as default voice. Amy stays as selectable fallback. See `project_voice_roadmap.md` memory for full plan + considerations (spousal agreement, license, consistency).

## Known small fixes carried from today's live-test session

- [ ] Port v2 pickers to Inno Setup wizard — `configure.py` has `setup_prompt_voice` + `setup_prompt_backend` but the Inno installer never invokes them. Port to Pascal `[Code]` pages so end users hit the v2 pickers on first install.
- [ ] Clean up configure.py summary — "LLM polish" (legacy command-mode) vs "Prompt polish" (new v2 backend) are two different things; summary lists both, confusing.
- [ ] Re-add cancel-via-hotkey-repress for prompt-assist v2 — `cancel_slot_record` API was removed by forge-deslop (no producer); add cleanly if/when prompt_press-during-active-conversation needs to cancel.
- [ ] Fix `statusline-command.sh` to render `.claude/next.md` first uncompleted item — currently only shows model + context bar.

## Runtime-test carried over

- [ ] Runtime-test `feat/voice-app-launch` (PR #28): golden path ("open word"), prefix invariant ("please open word" must NOT fire), error fallback ("open gibberish").

## Separate projects (NOT v2 side-quests)

- [ ] Phase 16 licensing — blocks v2 paywall wrap (not the build). Tier count, subscription vs one-time, offline activation, "beta tester" marker. Beta testers grandfather into free tier 2.
- [ ] Signing approach (Azure Trusted Signing $10/mo recommended) — wire into `.github/workflows/build-release.yml`
- [ ] Whisper "dash" dropout fix direction — read `project_dash_word_dropout.md` memory first
- [ ] Wake word decision — train custom "hey koda" via openwakeword OR rip feature
- [ ] Phase 9 RDP test (pending since session 35)
- [ ] V2 app-launch: chaining ("open powershell and type git status"), window-ready check, "switch to X"
- [ ] Memory sync across machines — home PC writes to `C--Users-alexi/`, work PC to `C--Users-alex/`. Options: rename Windows user, OneDrive symlink, or private git repo. Parked.

## Completed this session

- [x] Merge PR #33 (prompt-assist v2 design doc)
- [x] Prompt-assist v2 MVP (session 44, home PC)
- [x] Voice-driven confirmation (2026-04-24 commit `75e5366`) — 428/428 tests, pre-push gate clean
- [x] Home-PC smoke test of v4.3.1
- [x] Fix `configure.py` prompt-assist hotkey default regression (f9 → ctrl+f9, commit `7c79237`)
- [x] Rebuilt installer as v4.4.0-beta1, live-installed on work PC

## Waiting / Blocked

- **Coworker re-test of v4.3.1 mic-hotplug + music-bleed** — needs installer re-share first
