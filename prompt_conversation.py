"""
Conversational prompt assist — state machine for slot-filling Q&A.

Design: docs/prompt-assist-v2-design.md
Replaces silent one-shot refine_prompt() with TTS opener -> 3-slot Q&A
(Task / Context / Format) -> confirmation overlay -> paste.

Integration: voice.py routes the 'prompt_press' hotkey here when
config['prompt_assist']['conversational'] is True (default).

I/O bindings (TTS, per-slot recorder, overlay preview, paste) are
injectable so the state machine is unit-testable without real audio.
"""

import logging
import threading
from typing import Callable, Optional

from active_window import detect_platform, refocus_window
from prompt_assist import (
    _extract_details,
    detect_intent,
    refine_prompt,
)

logger = logging.getLogger("koda")


# State labels — mainly for logging and the test snapshot
S_OPENING = "opening"
S_LISTENING_TASK = "listening_task"
S_LISTENING_CONTEXT = "listening_context"
S_LISTENING_FORMAT = "listening_format"
S_ASSEMBLING = "assembling"
S_CONFIRMING = "confirming"
S_PASTING = "pasting"
S_CANCELLED = "cancelled"
S_DONE = "done"


# Spoken control phrases — design §"Design principles" + §"Confirmation step"
SLOT_EXIT_PHRASES = {"go", "done", "that's enough", "thats enough", "enough"}
CANCEL_PHRASES = {"cancel", "never mind", "nevermind", "stop", "forget it"}
CONFIRM_SEND_PHRASES = {"send", "go", "yes", "yep", "send it", "ok"}
CONFIRM_REFINE_PHRASES = {"refine", "polish", "improve"}
CONFIRM_EXPLAIN_PHRASES = {"explain", "read it back", "read back", "read"}

# Default opener — overrideable via config['prompt_assist']['opener']
DEFAULT_OPENER = "What are we working on with AI today?"
SLOT_QUESTIONS = {
    "context": "What does it need to know that it doesn't already?",
    "format": "What should the answer look like?",
}

# Conservative no-auto-send timeout per design §state machine
CONFIRM_TIMEOUT_S = 15.0


def _normalize(text: str) -> str:
    if not text:
        return ""
    return text.strip().strip(".!?,;:").lower()


def classify_slot_response(text: str) -> tuple[str, str]:
    """Classify a slot answer.

    Returns (kind, payload):
      "cancel"  — abort the whole flow
      "exit"    — done answering, advance / short-circuit
      "content" — normal answer (payload = original text)
    """
    norm = _normalize(text)
    if norm in CANCEL_PHRASES:
        return ("cancel", "")
    if norm in SLOT_EXIT_PHRASES:
        return ("exit", "")
    return ("content", text or "")


def classify_confirm_response(text: str) -> tuple[str, str]:
    """Classify a confirmation-step answer.

    Returns (kind, payload). 'add' carries the trailing speech as payload.
    """
    norm = _normalize(text)
    if norm in CANCEL_PHRASES:
        return ("cancel", "")
    if norm in CONFIRM_SEND_PHRASES:
        return ("send", "")
    if norm in CONFIRM_REFINE_PHRASES:
        return ("refine", "")
    if norm in CONFIRM_EXPLAIN_PHRASES:
        return ("explain", "")
    if norm == "add" or norm.startswith("add "):
        trailing = text.strip()[3:].strip() if text and text.strip().lower() != "add" else ""
        return ("add", trailing)
    return ("unknown", text or "")


def is_slot_complete(text: str) -> bool:
    """Short-circuit gate for slot 1 — design §"Completeness detection".

    True when answer > 40 words AND a recognized intent (not 'general')
    AND >= 1 extracted detail.
    """
    if not text:
        return False
    if len(text.split()) <= 40:
        return False
    if detect_intent(text) == "general":
        return False
    return len(_extract_details(text)) >= 1


def _combine_slots(task: str, context: str, fmt: str) -> str:
    """Stitch slot answers into raw text for refine_prompt() to template."""
    parts = []
    if task:
        parts.append(task.strip().rstrip("."))
    if context:
        parts.append("Additional context: " + context.strip().rstrip("."))
    if fmt:
        parts.append("Desired format: " + fmt.strip().rstrip("."))
    return ". ".join(parts) + "." if parts else ""


def _summarize_for_speech(prompt: str) -> str:
    """Short TTS summary — never speak the full prompt (design §confirm)."""
    if not prompt:
        return "Empty prompt. Cancel?"
    lead = {
        "code": "Got a code prompt",
        "debug": "Got a debug prompt",
        "explain": "Got an explanation prompt",
        "review": "Got a review prompt",
        "write": "Got a writing prompt",
        "general": "Drafted a prompt",
    }.get(detect_intent(prompt), "Drafted a prompt")
    first_words = " ".join(prompt.split()[:12])
    return f"{lead}: {first_words}. Send?"


# ============================================================
# Default I/O bindings — real impls; tests inject mocks
# ============================================================

def _default_tts_speak(text: str) -> None:
    try:
        from voice import _get_tts
        engine = _get_tts()
        if not engine:
            logger.warning("TTS unavailable; cannot speak: %r", text[:80])
            return
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        logger.error("Default TTS speak failed: %s", e, exc_info=True)


def _default_record_slot(slot_name: str, config: dict) -> str:
    try:
        from voice import slot_record
        return slot_record(slot_name, config)
    except Exception as e:
        logger.error("slot_record failed: %s", e, exc_info=True)
        return ""


def _default_show_preview(prompt: str, callbacks: dict) -> None:
    try:
        from overlay import show_prompt_preview
        show_prompt_preview(prompt, callbacks)
    except Exception as e:
        logger.error("show_prompt_preview failed: %s", e, exc_info=True)
        # Fall back to immediate cancel so the conversation thread doesn't hang
        cb = callbacks.get("on_cancel")
        if cb:
            cb()


def _default_paste(text: str) -> None:
    try:
        import pyautogui
        import pyperclip
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
    except Exception as e:
        logger.error("Paste failed: %s", e, exc_info=True)


def _default_record_confirm_voice(config, *, cancel_event=None, max_seconds=6.0):
    """Voice-confirm listener's recorder. Fast no-op when audio is unavailable
    so tests that don't inject a fake don't pay any real cost."""
    try:
        import voice as v
        if getattr(v, "model", None) is None or getattr(v, "stream", None) is None:
            return ""
        return v.slot_record(
            "confirm", config,
            max_seconds=max_seconds, cancel_event=cancel_event,
        )
    except Exception as e:
        logger.debug("confirm voice record: %s", e)
        return ""


# ============================================================
# State machine entry point
# ============================================================

def run_conversation(
    config: dict,
    *,
    tts_speak: Optional[Callable[[str], None]] = None,
    record_slot: Optional[Callable[[str, dict], str]] = None,
    record_confirm_voice: Optional[Callable[..., str]] = None,
    show_preview: Optional[Callable[[str, dict], None]] = None,
    paste_text: Optional[Callable[[str], None]] = None,
) -> dict:
    """Run the conversational prompt-assist flow.

    Returns a snapshot for tests / callers:
      {"final_state": str, "prompt": str, "slots": {task, context, format},
       "cancelled": bool, "raw": str}
    """
    speak = tts_speak or _default_tts_speak
    record = record_slot or _default_record_slot
    record_voice_confirm = record_confirm_voice or _default_record_confirm_voice
    preview = show_preview or _default_show_preview
    paste = paste_text or _default_paste

    pa_cfg = config.get("prompt_assist", {})
    opener = pa_cfg.get("opener", DEFAULT_OPENER)

    target = detect_platform()
    logger.info("prompt-assist target: platform=%s exe=%s", target["platform"], target["exe"])

    slots = {"task": "", "context": "", "format": ""}
    snapshot = {
        "final_state": S_OPENING,
        "prompt": "",
        "slots": slots,
        "cancelled": False,
        "raw": "",
        "target": target,
    }

    def _cancel(reason: str) -> dict:
        logger.info("Conversation cancelled: %s", reason)
        snapshot["final_state"] = S_CANCELLED
        snapshot["cancelled"] = True
        return snapshot

    speak(opener)

    snapshot["final_state"] = S_LISTENING_TASK
    answer = record("task", config)
    kind, payload = classify_slot_response(answer)
    if kind == "cancel":
        return _cancel("user said cancel at task slot")
    slots["task"] = payload
    short_circuit = (kind == "exit") or is_slot_complete(slots["task"])

    if not short_circuit:
        snapshot["final_state"] = S_LISTENING_CONTEXT
        speak(SLOT_QUESTIONS["context"])
        answer = record("context", config)
        kind, payload = classify_slot_response(answer)
        if kind == "cancel":
            return _cancel("user said cancel at context slot")
        if kind == "content":
            slots["context"] = payload
        # 'exit' here just means: done with context, advance.

        snapshot["final_state"] = S_LISTENING_FORMAT
        speak(SLOT_QUESTIONS["format"])
        answer = record("format", config)
        kind, payload = classify_slot_response(answer)
        if kind == "cancel":
            return _cancel("user said cancel at format slot")
        if kind == "content":
            slots["format"] = payload

    snapshot["final_state"] = S_ASSEMBLING
    raw = _combine_slots(slots["task"], slots["context"], slots["format"])
    snapshot["raw"] = raw
    assembled = refine_prompt(raw, config)
    snapshot["prompt"] = assembled

    snapshot["final_state"] = S_CONFIRMING
    speak(_summarize_for_speech(assembled))

    decision = {"kind": None, "payload": ""}
    decision_event = threading.Event()
    voice_cancel_event = threading.Event()

    def _on_confirm():
        voice_cancel_event.set()
        decision["kind"] = "send"
        decision_event.set()

    def _on_refine():
        voice_cancel_event.set()
        decision["kind"] = "refine"
        decision_event.set()

    def _on_add(text: str = ""):
        voice_cancel_event.set()
        decision["kind"] = "add"
        decision["payload"] = text or ""
        decision_event.set()

    def _on_cancel():
        voice_cancel_event.set()
        decision["kind"] = "cancel"
        decision_event.set()

    preview(assembled, {
        "on_confirm": _on_confirm,
        "on_refine": _on_refine,
        "on_add": _on_add,
        "on_cancel": _on_cancel,
    })

    # Voice-driven confirmation — listens in parallel with the overlay buttons.
    # Both input sources route through the same callbacks; whichever fires
    # first wins (overlay's _fire() guards against a second callback via its
    # own decided flag). Button press also sets voice_cancel_event so the
    # listener stops recording immediately instead of waiting for VAD silence.
    def _voice_listener():
        attempts = 0
        while attempts < 3 and not decision_event.is_set() and not voice_cancel_event.is_set():
            heard = record_voice_confirm(
                config, cancel_event=voice_cancel_event, max_seconds=6.0,
            )
            if voice_cancel_event.is_set() or decision_event.is_set():
                return
            if not heard:
                attempts += 1
                continue
            kind, payload = classify_confirm_response(heard)
            if kind == "unknown":
                attempts += 1
                continue
            if kind == "explain":
                # Speak the full prompt, then loop to listen again.
                speak(assembled)
                attempts += 1
                continue
            if kind == "send":
                _on_confirm()
            elif kind == "refine":
                _on_refine()
            elif kind == "add":
                _on_add(payload)
            elif kind == "cancel":
                _on_cancel()
            return

    voice_thread = threading.Thread(target=_voice_listener, daemon=True)
    voice_thread.start()

    if not decision_event.wait(timeout=CONFIRM_TIMEOUT_S):
        voice_cancel_event.set()
        voice_thread.join(timeout=0.3)
        return _cancel(f"no decision within {CONFIRM_TIMEOUT_S}s")

    # Main thread won; make sure voice listener exits promptly before we return
    # so tests and callers observe a fully-settled state.
    voice_cancel_event.set()
    voice_thread.join(timeout=0.3)

    if decision["kind"] == "cancel":
        return _cancel("user cancelled at confirm")

    if decision["kind"] == "refine":
        forced_cfg = {**config, "prompt_assist": {**pa_cfg, "llm_refine": True}}
        assembled = refine_prompt(raw, forced_cfg)
        snapshot["prompt"] = assembled
    elif decision["kind"] == "add" and decision["payload"]:
        raw = raw.rstrip(".") + ". " + decision["payload"].rstrip(".") + "."
        snapshot["raw"] = raw
        assembled = refine_prompt(raw, config)
        snapshot["prompt"] = assembled

    snapshot["final_state"] = S_PASTING
    refocus_window(target.get("hwnd"))
    paste(assembled)
    snapshot["final_state"] = S_DONE
    return snapshot
