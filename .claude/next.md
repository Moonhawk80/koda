# NEXT:

- [x] Merge open PRs: #24 (session 41 handover), #26 (perf), #27 (session 42 handover), #28 (app-launch MVP), #29 (pre-push gate rule), #30 (session 43 handover), #31 (session 43 addendum)
- [ ] Runtime-test `feat/voice-app-launch` (PR #28): golden path ("open word"), prefix invariant ("please open word" must NOT fire), error fallback ("open gibberish")
- [ ] Prompt-assist v2 — conversational Q&A: press `ctrl+f9` → Koda opens with a chosen voice ("what are we building with AI today?") → short Q&A (intent, stakes, format) → assembled prompt pastes to active window. Today it's silent/one-shot. Needs: opening-question TTS, multi-turn capture loop, follow-up question ruleset in `prompt_assist.py`, exit condition ("done" / timeout). Market research + design doc pending (agent dispatched 2026-04-23, results feed `docs/prompt-assist-v2-design.md`).
- [ ] Voice picker in `configure.py` first-run wizard — enumerate SAPI voices via `voice.get_available_voices()`, play a sample line ("Hi, I'm Koda") per voice, user picks 1/2/3, save to `config["tts"]["voice"]`. Add after the hotkey setup step around `configure.py:625`. Pairs with prompt-assist v2 above — both need a chosen voice.
- [ ] Decide signing approach (Azure Trusted Signing $10/mo recommended) and wire into `.github/workflows/build-release.yml`
- [ ] Pick direction for Whisper "dash" dropout fix — read `project_dash_word_dropout.md` memory before proposing
- [ ] Home-PC smoke test of public v4.3.1 installer (carried from session 41)
- [ ] Wake word decision: train custom "hey koda" via openwakeword OR rip feature (currently detects "Alexa" behind the label)
- [ ] Phase 9 RDP test (pending since session 35)
- [ ] Phase 16 license-system decisions — tier count, subscription vs one-time, offline activation
- [ ] V2 app-launch: chaining ("open powershell and type git status"), window-ready check, "switch to X" for existing windows

## Waiting / Blocked

- **Coworker re-test of v4.3.1 mic-hotplug + music-bleed** — needs installer re-share first
