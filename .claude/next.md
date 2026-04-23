# NEXT:

- [ ] Merge PR #33 (prompt-assist v2 design doc) once Alex reviews — `https://github.com/Moonhawk80/koda/pull/33`
- [ ] Runtime-test `feat/voice-app-launch` (PR #28): golden path ("open word"), prefix invariant ("please open word" must NOT fire), error fallback ("open gibberish"). Do FIRST — validates the shared voice.py hot path before v2 builds on it.
- [ ] **Prompt-assist v2 MVP** — build on `feat/prompt-assist-v2`. Full design: `C:\Users\alex\Projects\koda\docs\prompt-assist-v2-design.md`. Scope: state machine, 3 slots + confirmation, platform detection, install-wizard LLM picker (None / Ollama / BYO API), Credential Manager for secrets, voice picker, overlay preview mode, settings GUI dropdowns, unit tests across all three backends. Est. ~3.5 sessions.
- [ ] Phase 16 licensing — blocks prompt-assist v2 paywall wrap (not the build itself). Decisions needed: tier count, subscription vs one-time, offline activation, durable "beta tester" marker (signed config / first-N installs / timestamp). Beta testers grandfather into free tier 2.
- [ ] Decide signing approach (Azure Trusted Signing $10/mo recommended) and wire into `.github/workflows/build-release.yml`
- [ ] Pick direction for Whisper "dash" dropout fix — read `project_dash_word_dropout.md` memory before proposing
- [ ] Home-PC smoke test of public v4.3.1 installer (carried from session 41)
- [ ] Wake word decision: train custom "hey koda" via openwakeword OR rip feature (currently detects "Alexa" behind the label)
- [ ] Phase 9 RDP test (pending since session 35)
- [ ] V2 app-launch: chaining ("open powershell and type git status"), window-ready check, "switch to X" for existing windows

## Waiting / Blocked

- **Coworker re-test of v4.3.1 mic-hotplug + music-bleed** — needs installer re-share first
