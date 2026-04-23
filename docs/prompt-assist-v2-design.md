# Prompt Assist v2 — Design Doc

*Date: 2026-04-23. Status: proposal, not yet scoped to a build.*

## What we're building

Press `ctrl+f9` → Koda speaks an opening question in a user-chosen voice → short slot-filling Q&A (max 3 turns) → assembles a structured prompt → pastes into the focused app. Replaces today's silent one-shot `refine_prompt()` path with a conversational elicitation flow.

## Why

Current prompt-assist (`prompt_assist.py`) is passive: it reformats whatever the user said. But users rarely speak a complete prompt on the first try — they leave out context, format, and constraints. The quality ceiling of a one-shot refinement is bounded by what the user thought to say.

A short voice Q&A, tuned to ask for *exactly the dimensions that matter*, lifts the ceiling without asking the user to think like a prompt engineer.

## Market context

Research (2026-04-23) confirms no shipped product does voice-first + conversational + prompt-as-artifact + OS-paste:

- **Wispr Flow / Superwhisper** — one-shot dictation, reformat to text, no elicitation
- **PromptPerfect / Promptable / PromptFolk** — text-only prompt builders, no voice, no paste
- **ChatGPT Voice / Gemini Live** — conversational but generate *answers*, don't hand back a reusable prompt
- **Pipecat / LiveKit Agents / Vocode** — frameworks, not products; closest building blocks but nobody has shipped a prompt-builder on top

The wedge is real. Closest prior art is Alexa's slot-filling dialog model, which is what this design borrows from.

## Design principles (from research)

1. **Slot-filling, not open conversation.** Each turn asks for exactly one dimension. Alexa's model works; free-form "tell me more" fails.
2. **3-turn ceiling, hard cap at 4.** NN/g and Voice UX Design Institute: every extra turn doubles abandonment. Total interaction ≤30 seconds.
3. **Explicit end-of-turn signal.** Short audio cue ("ding") when Koda starts listening. VAD alone is unreliable.
4. **One-word early-exit.** User can say "go" / "done" / "that's enough" at any turn to skip ahead and assemble with what we have.
5. **Don't narrate.** Never say "I'll now ask you three questions" — just ask the first one.
6. **Confirm only at the end, optionally.** Spoken preview of the assembled prompt is a V2 feature; MVP skips it.

## The three slots

Collapsing Anthropic/OpenAI/CO-STAR/RTF prompt-engineering frameworks, three dimensions capture ~80% of the quality gain:

1. **Task** — "What do you want the AI to do?"
   *Required. Non-negotiable first slot.*

2. **Context** — "What does it need to know that it doesn't already?"
   *Highest-leverage dimension per Anthropic's context-engineering work. Background, inputs, constraints.*

3. **Format** — "What should the answer look like?"
   *Forecloses rambling. Cheap ask, enormous quality lift.*

**Deliberately skipped on turn 1:** role, tone, audience, examples. Infer role from task; let the user add the rest by speaking naturally inside the three answers. The existing `_extract_details()` in `prompt_assist.py` already pulls tech stack, numbers, file paths from free speech — that machinery keeps its job.

## State machine

```
IDLE
  └── [hotkey_press] ──> SPEAKING_OPENING
                           │
                           └── [tts_done] ──> LISTENING_TASK
                                                │
                                                ├── [answer + silence] ──> ASSESSING_TASK
                                                ├── [user says "go"] ───> ASSEMBLING
                                                └── [hotkey re-press]──> CANCELLED

ASSESSING_TASK
  ├── [task captured] ──> SPEAKING_CONTEXT_Q
  └── [task empty]    ──> SPEAKING_TASK_RETRY (once, then give up)

SPEAKING_CONTEXT_Q ──> LISTENING_CONTEXT ──> ASSESSING_CONTEXT ──> SPEAKING_FORMAT_Q
SPEAKING_FORMAT_Q  ──> LISTENING_FORMAT  ──> ASSEMBLING

ASSEMBLING ──> PASTING ──> IDLE
```

Exit conditions at every state: `hotkey_press` (cancel), `"cancel"` / `"never mind"` (cancel), 8s silence after last TTS (move to assemble with what we have).

## Architecture fit

**Hook point.** `voice.py:1230-1238` already routes `prompt_press` / `prompt_release` / `prompt_toggle`. Today each calls `start_recording("prompt")` → after release, `refine_prompt()` at voice.py:880. v2 adds a conditional branch gated by `config["prompt_assist"]["conversational"]` — default off for MVP ship, opt-in via settings.

**New module: `prompt_conversation.py`.** State-machine class that owns the full Q&A lifecycle. Keeps `prompt_assist.py` untouched (existing `refine_prompt()` still works for non-conversational mode and is the final-assembly step for conversational mode).

```python
# voice.py:1230-ish
elif event == "prompt_press":
    if config["prompt_assist"].get("conversational", False):
        start_conversation_mode()   # prompt_conversation.run()
    else:
        start_recording("prompt")   # existing path
```

**TTS integration.** Reuses existing `_get_tts()` / pyttsx3 path at voice.py:1061. No new code for MVP. Piper upgrade is a separate track (see below).

**Recording integration.** Reuses existing audio capture but with per-turn start/stop — each slot is a bounded mini-recording. VAD already exists for silence detection.

## Voice selection — first-run picker

Separate but paired feature (already captured in `.claude/next.md`). Sits in `configure.py:625` after hotkey setup:

```
Pick your Koda voice:
  1. [Zira]     "Hi, I'm Koda. Press F9 when you want to prompt AI."
  2. [Hazel]    "Hi, I'm Koda. Press F9 when you want to prompt AI."
  3. [David]    "Hi, I'm Koda. Press F9 when you want to prompt AI."

Choose 1-3: _
```

Each option plays a sample line via `voice.speak_with_voice(voice_id, sample_text)` (new helper, wraps existing `_get_tts()`). Selection saves to `config["tts"]["voice"]`. Existing `get_available_voices()` at voice.py:1088 enumerates the candidates.

## TTS quality — Piper vs. pyttsx3

**MVP ships with pyttsx3 + SAPI5 (Zira).** Robotic-ish but zero new dependencies, zero install complexity, works today.

**V2 upgrade path: Piper TTS via NaturalVoiceSAPIAdapter.** Research recommendation. Offline, Windows-native, neural-quality (orders of magnitude better than SAPI5), free, ~50-200ms synthesis on CPU. The adapter makes Piper voices surface through the SAPI5 API, so existing pyttsx3 code keeps working — user just installs the adapter once and picks a Piper voice in the first-run picker.

**Rejected alternatives:** Azure Neural (cloud dependency), ElevenLabs (metered cost), StyleTTS2/XTTS (GPU-heavy, slow cold-start — wrong tradeoff for a tray app).

## MVP scope (cut)

Ship in one PR. Target: functional Q&A flow, ugly voice, no confirmation, no barge-in.

- [ ] `prompt_conversation.py` — state machine, 3 slots, early-exit phrases, cancel paths
- [ ] `voice.py` — conditional branch at `prompt_press` event
- [ ] `config.py` — `"prompt_assist": {"conversational": True, ...}` default ON for dogfooding
- [ ] `text_processing.py` or new helper — detect one-word exit phrases ("go", "done", "cancel", "never mind")
- [ ] Audio cue — short "ding" on LISTENING state entry (reuse `sounds/start.wav` or a new tone)
- [ ] Opening question string configurable in config: `"prompt_assist": {"opener": "what are we building with AI today?"}`
- [ ] `test_features.py` — state machine unit tests (no audio hardware deps)
- [ ] Documentation — README section + configure.py notes

**Out of scope for MVP (V2):**
- Confirmation step ("here's what I'll send — say go or edit")
- Barge-in (user interrupts Koda's TTS by pressing hotkey / speaking)
- Piper voice swap
- Follow-up question logic ("you said Python — do you want it async?")
- Voice picker in configure.py (separate PR, captured in next.md)

**Out of scope for V2 (V3):**
- Session memory ("same as last time but shorter")
- Prompt history playback
- Multi-language opener
- Custom slot definitions per user

## Open questions (resolve before building)

1. **Default-on or default-off?** The existing silent one-shot flow is perfectly fine for users who already know how to prompt. Conversational mode is a superpower for users who don't — but if it's default-on, experienced users will be annoyed by having to say "go" every time. *Proposal: default off, enable via settings GUI toggle OR a separate hotkey (`ctrl+shift+f9`) so both modes coexist.*

2. **Should the assembled prompt be spoken back before paste?** Research says confirm only when stakes are high — pasting into a chat input isn't high-stakes (user sees it before hitting send). *Proposal: skip for MVP; revisit if users report runaway prompts.*

3. **Cancel ergonomics.** Hotkey re-press feels natural but conflicts with the hold-mode press semantics. *Proposal: hotkey tap cancels if in conversation; hold does nothing (already captured for press). Spoken "cancel" is the primary path.*

4. **What if the user says the whole prompt in the first turn?** e.g. opener: "what are we building?" → user: "a Python script that reads CSVs and removes duplicates by email address." That's task + context + format implicit. *Proposal: after slot 1, if `refine_prompt(answer).length > 40 words` OR `detect_intent != general`, treat as "enough info" and short-circuit to ASSEMBLING. Skip slots 2-3. Ship an early-exit without requiring the user to learn "go".*

## Risk / what could go wrong

- **TTS latency at cold start.** pyttsx3 lazy-init + SAPI first call can be 300-800ms. User presses hotkey and hears nothing for a second. *Mitigate: warm TTS at Koda startup (call `_get_tts()` + say a zero-length string) so the engine is hot when the hotkey fires.*

- **Overlay confusion.** Current tray badges don't communicate "I'm listening for slot 2 of 3". *Mitigate: reuse the existing overlay infrastructure to show compact slot state ("1/3 Task" → "2/3 Context" → "3/3 Format").*

- **VAD false-triggers.** User pauses mid-sentence, Koda thinks they're done, moves to next slot. *Mitigate: 1.5s silence threshold (matches existing `vad.silence_timeout_ms`), and only advance on 2 consecutive silences or an explicit word boundary.*

- **Robotic voice kills the vibe.** If SAPI Zira sounds sterile enough that users turn it off on day 1, MVP flops. *Mitigate: ship the voice picker (3 options) alongside MVP so users have agency; prioritize the Piper V2 upgrade if feedback confirms this risk.*

- **Feature creep in `prompt_conversation.py`.** Multi-turn state machines breed edge cases. *Mitigate: hard line — MVP ships exactly the 3 slots + early-exit + cancel. Every other dimension waits for V2.*

## Work estimate

- MVP build: ~1 full session (state machine + voice.py integration + tests + config wiring)
- Voice picker in configure.py: ~0.5 session
- Piper V2 upgrade: ~0.5 session (adapter install docs + voice selection update)
- End-to-end runtime test: ~0.25 session

Total to ship MVP + voice picker: ~1.5 sessions.

## Next steps

1. Alex reads this doc and the entries in `.claude/next.md`.
2. Resolve open questions 1-4 above.
3. Confirm MVP scope cut is right before building.
4. Approve opener text, exit phrases, and default on/off.
5. Build MVP on a `feat/prompt-assist-v2` branch, runtime-test, PR.

## References

- Anthropic — [Prompt-engineering best practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices)
- Anthropic — [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- Alexa Skills Kit — [Dialog Management / Slot Filling](https://developer.amazon.com/en-US/docs/alexa/custom-skills/define-the-dialog-to-collect-and-confirm-required-information.html)
- NN/g — [Intelligent Assistants Have Poor Usability](https://www.nngroup.com/articles/intelligent-assistant-usability/)
- Google Design — [Speaking the Same Language (VUI)](https://design.google/library/speaking-the-same-language-vui)
- Piper TTS — [rhasspy/piper VOICES.md](https://github.com/rhasspy/piper/blob/master/VOICES.md)
- NaturalVoiceSAPIAdapter — [gexgd0419/NaturalVoiceSAPIAdapter](https://github.com/gexgd0419/NaturalVoiceSAPIAdapter)
- Pipecat Conversation Flows — [pipecat-ai/pipecat](https://github.com/pipecat-ai/pipecat)
- CO-STAR framework — [portkey.ai/blog/what-is-costar-prompt-engineering/](https://portkey.ai/blog/what-is-costar-prompt-engineering/)
