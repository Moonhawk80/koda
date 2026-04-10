"""
Koda — Push-to-talk voice input for any app.

System tray app with two modes:
  Dictation = raw transcription with light cleanup
  Command   = full cleanup with filler removal, code vocab, optional LLM polish

Features: hold-to-talk, toggle mode, VAD auto-stop, wake word ("Hey Koda"),
correction mode, local LLM prompt polishing, noise reduction.
"""

import sys
import os
import time
import threading
import multiprocessing
import logging
import winsound
import numpy as np
import sounddevice as sd
import keyboard  # used only for keyboard.send() — hooks run in hotkey_service subprocess
import pyperclip
import pyautogui
import pystray
from PIL import Image, ImageDraw

from config import load_config, save_config, open_config_file
from text_processing import process_text, apply_custom_vocabulary
from history import init_db, save_transcription
from overlay import KodaOverlay
from profiles import ProfileMonitor
from voice_commands import extract_and_execute_commands
from stats import init_stats_db as init_stats, log_transcription_stats, log_command_stats
from plugin_manager import PluginManager
from prompt_assist import refine_prompt


# --- Logging ---
logging.basicConfig(
    filename=os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug.log"),
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("koda")
logger.setLevel(logging.DEBUG)  # Koda's own logger is DEBUG, but library noise is WARNING+

# --- Version ---
VERSION = "4.1.0"

# --- Globals ---
recording = False
audio_chunks = []
model = None
tray_icon = None
stream = None
config = {}
vad_model = None
last_speech_time = 0
recording_mode = "dictation"
last_transcription = None
wake_word_active = False
wake_word_thread = None
wake_buffer = []  # rolling buffer for wake word detection
wake_buffer_lock = threading.Lock()
overlay = None  # Floating status overlay
profile_monitor = None  # Per-app profile switcher
base_config = {}  # Original config before profile overrides
plugins = PluginManager()  # Plugin system

# --- Hotkey service (separate process) ---
_hotkey_proc = None       # multiprocessing.Process
_hotkey_conn = None       # parent end of Pipe
_hotkey_listener = None   # thread reading events from subprocess
_hotkey_pong = threading.Event()  # set by event thread when "pong" arrives


# ============================================================
# ICON
# ============================================================

def create_branded_icon(size=64, dot_color=None):
    """Koda branded icon — dark rounded square, bold font K, colored status dot.

    Uses Segoe UI Bold font for crisp anti-aliased K at any size.
    Used for both tray icon and floating overlay.
    """
    from PIL import ImageFont

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s = size / 64

    # Dark rounded square — more rounded corners
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(18 * s), fill="#1a1a2e")

    # Bahnschrift — modern geometric DIN-like font
    try:
        font = ImageFont.truetype("bahnschrift.ttf", int(42 * s))
    except Exception:
        try:
            font = ImageFont.truetype("C:/Windows/Fonts/bahnschrift.ttf", int(42 * s))
        except Exception:
            font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), "K", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) // 2 - bbox[0]
    y = (size - th) // 2 - bbox[1] - int(2 * s)
    draw.text((x, y), "K", fill="white", font=font)

    # Status dot (bottom-right)
    if dot_color:
        dr = int(7 * s)
        cx, cy = size - int(10 * s), size - int(10 * s)
        draw.ellipse([cx - dr - 2, cy - dr - 2, cx + dr + 2, cy + dr + 2], fill="#1a1a2e")
        draw.ellipse([cx - dr, cy - dr, cx + dr, cy + dr], fill=dot_color)

    return img


def create_icon(color="gray"):
    """Tray icon — branded K on dark bg with colored status dot."""
    # Map state color to dot color
    if color == "gray":
        return create_branded_icon(64, dot_color=None)
    elif color == "#2ecc71":
        return create_branded_icon(64, dot_color="#2ecc71")
    else:
        return create_branded_icon(64, dot_color=color)




# ============================================================
# SOUND EFFECTS
# ============================================================

SOUNDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")


def _play_wav(filename):
    """Play a .wav file through the system default output device."""
    filepath = os.path.join(SOUNDS_DIR, filename)
    if not os.path.exists(filepath):
        return
    # Play synchronously inside a thread (SND_ASYNC + daemon thread = sound gets killed)
    threading.Thread(
        target=lambda: winsound.PlaySound(filepath, winsound.SND_FILENAME | winsound.SND_NODEFAULT),
        daemon=True,
    ).start()


def play_start_sound():
    if config.get("sound_effects", True):
        _play_wav("start.wav")


def play_stop_sound():
    if config.get("sound_effects", True):
        _play_wav("stop.wav")


def play_success_sound():
    if config.get("sound_effects", True):
        _play_wav("success.wav")


def play_error_sound():
    if config.get("sound_effects", True):
        _play_wav("error.wav")


def play_wakeword_sound():
    """Distinct beep pattern — wake word confirmed. Uses system beep so it's always audible."""
    if config.get("sound_effects", True):
        winsound.Beep(500, 120)
        winsound.Beep(600, 120)


# ============================================================
# TRAY
# ============================================================

# Map tray colors to overlay states
_COLOR_TO_STATE = {
    "#2ecc71": "ready",
    "#e74c3c": "recording",
    "#f39c12": "transcribing",
    "#9b59b6": "reading",
    "#3498db": "listening",
    "gray": "ready",
}


def update_tray(color, tooltip):
    if tray_icon:
        tray_icon.icon = create_icon(color)
        tray_icon.title = tooltip
    # Update floating overlay
    if overlay:
        state = _COLOR_TO_STATE.get(color, "ready")
        # Extract preview text from tooltip if it has one
        preview = ""
        if ": " in tooltip:
            preview_part = tooltip.split(": ", 1)[1]
            if preview_part not in ("Ready", "Loading model...", "Transcribing...",
                                     "Recording (Dictation)...", "Recording (Command)...",
                                     "Listening...", "Reading..."):
                preview = preview_part
        overlay.set_state(state, preview)


def notify(message, title="Koda"):
    if config.get("notifications", False) and tray_icon:
        try:
            tray_icon.notify(message[:200], title)
        except Exception:
            pass


def error_notify(message):
    """Show a tray notification for errors — always shown regardless of config."""
    logger.error("User notification: %s", message)
    if tray_icon:
        try:
            tray_icon.notify(message[:200], "Koda Error")
        except Exception:
            pass


# ============================================================
# MODEL
# ============================================================

def load_whisper_model():
    global model
    from faster_whisper import WhisperModel
    model_size = config.get("model_size", "small")

    try:
        # When running as PyInstaller exe, use the bundled model
        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        bundled = os.path.join(base_dir, f"_model_{model_size}")
        if os.path.isdir(bundled):
            model = WhisperModel(bundled, device="cpu", compute_type="int8")
        else:
            model = WhisperModel(model_size, device="cpu", compute_type="int8")
        logger.info("Whisper model '%s' loaded successfully", model_size)
    except Exception as e:
        logger.error("Failed to load Whisper model: %s", e, exc_info=True)
        error_notify(f"Failed to load speech model '{model_size}'. Check internet connection for first download.")
        raise


# ============================================================
# LLM PROMPT POLISHING (Ollama)
# ============================================================

def polish_with_llm(text):
    """Use a local LLM via Ollama to clean up speech into a clear instruction."""
    if not config.get("llm_polish", {}).get("enabled", False):
        return text
    try:
        import ollama
        llm_model = config.get("llm_polish", {}).get("model", "phi3:mini")
        response = ollama.chat(
            model=llm_model,
            messages=[{
                "role": "system",
                "content": (
                    "You are a speech-to-text post-processor. The user dictated a message "
                    "by voice and it may contain filler words, false starts, or rambling. "
                    "Rewrite it as a clear, concise instruction or message. "
                    "Keep the original intent and meaning. Do not add information. "
                    "Do not explain what you did. Just output the cleaned text."
                ),
            }, {
                "role": "user",
                "content": text,
            }],
        )
        result = response["message"]["content"].strip()
        return result if result else text
    except Exception:
        return text


def translate_with_llm(text, target_language):
    """Use a local LLM via Ollama to translate text to the target language."""
    try:
        import ollama
        llm_model = config.get("llm_polish", {}).get("model", "phi3:mini")
        response = ollama.chat(
            model=llm_model,
            messages=[{
                "role": "system",
                "content": (
                    f"You are a translator. Translate the following text to {target_language}. "
                    "Output ONLY the translated text, nothing else. "
                    "Keep the tone and meaning. Do not explain."
                ),
            }, {
                "role": "user",
                "content": text,
            }],
        )
        result = response["message"]["content"].strip()
        return result if result else text
    except Exception:
        return text


# ============================================================
# VAD (Voice Activity Detection)
# ============================================================

def init_vad():
    global vad_model
    if not config.get("vad", {}).get("enabled", True):
        return
    try:
        from faster_whisper.vad import SileroVADModel
        vad_model = SileroVADModel()
    except Exception:
        vad_model = None


def check_vad_silence(audio_chunk):
    if vad_model is not None:
        try:
            chunk_size = 512
            if len(audio_chunk) >= chunk_size:
                segment = audio_chunk[:chunk_size].astype(np.float32)
                result = vad_model({"speech_prob": 0.5}, segment)
                if hasattr(result, 'get'):
                    return result.get("speech_prob", 0) > 0.5
        except Exception:
            pass
    rms = np.sqrt(np.mean(audio_chunk ** 2))
    return rms > 0.01


def vad_monitor_thread(silence_override=None):
    global recording, last_speech_time
    silence_timeout = (silence_override or config.get("vad", {}).get("silence_timeout_ms", 1500)) / 1000.0
    while recording:
        time.sleep(0.1)
        if not audio_chunks:
            continue
        latest = audio_chunks[-1].flatten()
        if check_vad_silence(latest):
            last_speech_time = time.time()
        elif time.time() - last_speech_time > silence_timeout:
            stop_recording()
            return


# ============================================================
# WAKE WORD (openwakeword — proper neural network detection)
# ============================================================

oww_model = None  # openwakeword model


def start_wake_word_listener():
    """Start background thread that listens for the wake word."""
    global wake_word_active, wake_word_thread, oww_model
    if not config.get("wake_word", {}).get("enabled", False):
        return
    try:
        from openwakeword.model import Model as OWWModel
        oww_model = OWWModel(
            wakeword_models=["alexa_v0.1"],
            inference_framework="onnx",
        )
        wake_word_active = True
        wake_word_thread = threading.Thread(target=_wake_word_loop, daemon=True)
        wake_word_thread.start()
    except Exception:
        pass


def stop_wake_word_listener():
    global wake_word_active
    wake_word_active = False


def _wake_word_loop():
    """Listen for wake word using openwakeword (like Alexa/Siri — dedicated tiny NN)."""
    global wake_word_active
    threshold = config.get("wake_word", {}).get("threshold", 0.7)

    while wake_word_active:
        if recording:
            time.sleep(0.5)
            continue

        # Wait for enough audio to accumulate (~1.5 seconds)
        time.sleep(1.5)

        if not wake_word_active or recording:
            continue

        # Grab audio from the shared buffer
        with wake_buffer_lock:
            if not wake_buffer:
                continue
            audio = np.concatenate(wake_buffer, axis=0).flatten()
            wake_buffer.clear()

        # Only process if there's actual speech (not just background noise)
        peak = np.max(np.abs(audio))
        if peak < 0.03:
            continue
        # Normalize to ~50% range (not full — avoids amplifying noise into false triggers)
        audio_normalized = audio / peak * 0.5
        audio_int16 = (audio_normalized * 32767).astype(np.int16)
        detected = False

        for i in range(0, len(audio_int16) - 1280, 1280):
            oww_model.predict(audio_int16[i:i + 1280])

            for name, scores in oww_model.prediction_buffer.items():
                if len(scores) > 0 and scores[-1] > threshold:
                    detected = True
                    break
            if detected:
                break

        if not detected:
            oww_model.reset()
            continue

        # Wake word detected!
        oww_model.reset()
        play_wakeword_sound()
        update_tray("#3498db", "Koda: Listening...")
        time.sleep(0.5)  # Let the confirmation chime finish before recording beep

        with wake_buffer_lock:
            wake_buffer.clear()

        start_recording("dictation", force_vad=True, vad_timeout_ms=800)

        while recording:
            time.sleep(0.1)

        # Cooldown
        with wake_buffer_lock:
            wake_buffer.clear()
        oww_model.reset()
        time.sleep(2)


# ============================================================
# RECORDING
# ============================================================

def audio_callback(indata, frames, time_info, status):
    if recording:
        audio_chunks.append(indata.copy())
    # Always feed wake word buffer (when not recording)
    if wake_word_active and not recording:
        with wake_buffer_lock:
            wake_buffer.append(indata.copy())
            # Keep only last 3 seconds (16000 samples/sec, ~31 chunks/sec at 512 samples)
            max_chunks = int(3 * 16000 / frames) if frames > 0 else 100
            while len(wake_buffer) > max_chunks:
                wake_buffer.pop(0)


streaming_text = ""  # Latest partial transcription


def _streaming_thread():
    """Periodically transcribe accumulated audio during recording for live preview."""
    global streaming_text
    while recording:
        time.sleep(2)
        if not recording or len(audio_chunks) < 10:
            continue
        try:
            audio = np.concatenate(audio_chunks, axis=0).flatten()
            stream_kwargs = {"beam_size": 1, "vad_filter": False}
            stream_lang = config.get("language", "en")
            if stream_lang != "auto":
                stream_kwargs["language"] = stream_lang
            segments, _ = model.transcribe(audio, **stream_kwargs)
            text = " ".join(seg.text for seg in segments).strip()
            if text:
                streaming_text = text
                # Show partial text in tray tooltip and overlay
                preview = text[:80] + "..." if len(text) > 80 else text
                update_tray("#e74c3c", f"Koda: {preview}")
                if overlay:
                    overlay.set_preview(text)
        except Exception as e:
            logger.error("Streaming transcription error: %s", e)


def start_recording(mode="dictation", force_vad=False, vad_timeout_ms=None):
    global recording, audio_chunks, last_speech_time, recording_mode, streaming_text
    if recording:
        return
    audio_chunks = []
    streaming_text = ""
    recording_mode = mode
    last_speech_time = time.time()
    recording = True

    play_start_sound()
    labels = {"dictation": "Dictation", "command": "Command", "prompt": "Prompt Assist"}
    label = labels.get(mode, mode.title())
    update_tray("#e74c3c", f"Koda: Recording ({label})...")

    # Start streaming transcription in background
    if config.get("streaming", True):
        threading.Thread(target=_streaming_thread, daemon=True).start()

    # Use VAD auto-stop in toggle mode OR when triggered by wake word
    if force_vad or config.get("hotkey_mode", "hold") == "toggle":
        threading.Thread(target=vad_monitor_thread, args=(vad_timeout_ms,), daemon=True).start()


_last_stop_time = 0


def stop_recording():
    global recording, _last_stop_time
    if not recording:
        return
    now = time.time()
    if now - _last_stop_time < 1.0:
        return
    _last_stop_time = now
    recording = False

    play_stop_sound()
    update_tray("#f39c12", "Koda: Transcribing...")

    if not audio_chunks:
        update_tray("#2ecc71", "Koda: Ready")
        return

    threading.Thread(target=_transcribe_and_paste, daemon=True).start()


def _load_custom_words():
    """Load custom vocabulary from custom_words.json."""
    custom_words_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_words.json")
    try:
        import json
        with open(custom_words_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning("Could not load custom words: %s", e)
        return {}


def _transcribe_and_paste():
    global last_transcription
    try:
        rec_start = time.time()
        audio = np.concatenate(audio_chunks, axis=0).flatten()

        # Noise reduction
        if config.get("noise_reduction", False):
            try:
                import noisereduce as nr
                audio = nr.reduce_noise(y=audio, sr=16000, stationary=True)
            except Exception as e:
                logger.warning("Noise reduction failed: %s", e)

        # Load custom vocabulary for initial_prompt and post-processing
        custom_words = _load_custom_words()

        # Build transcription kwargs
        translation_cfg = config.get("translation", {})
        translate_enabled = translation_cfg.get("enabled", False)
        target_lang = translation_cfg.get("target_language", "English")

        transcribe_kwargs = {
            "beam_size": 1,
            "vad_filter": True,
        }

        # Whisper's built-in translate task: any language → English
        if translate_enabled and target_lang.lower() == "english":
            transcribe_kwargs["task"] = "translate"
            # Don't set source language — let Whisper auto-detect
        else:
            # Language: "auto" means omit the language param to let Whisper auto-detect
            language = config.get("language", "en")
            if language != "auto":
                transcribe_kwargs["language"] = language

        # Pass custom words as initial_prompt to bias Whisper recognition
        if custom_words:
            prompt_words = " ".join(custom_words.values())
            transcribe_kwargs["initial_prompt"] = prompt_words

        # Transcribe with VAD filter + repetition penalty to prevent hallucinated repeats
        segments, info = model.transcribe(audio, **transcribe_kwargs)
        # Deduplicate consecutive identical segments (Whisper hallucination guard)
        seg_texts = []
        for seg in segments:
            t = seg.text.strip()
            if t and (not seg_texts or t != seg_texts[-1]):
                seg_texts.append(t)
        text = " ".join(seg_texts).strip()
        logger.debug("Whisper raw: %r", text)

        if not text:
            update_tray("#2ecc71", "Koda: Ready")
            return

        # Apply custom vocabulary replacements
        if custom_words:
            text = apply_custom_vocabulary(text, custom_words)
            logger.debug("After custom vocab: %r", text)

        # Post-processing
        if recording_mode == "prompt":
            # Prompt Assist mode — structure speech into an effective LLM prompt
            update_tray("#f39c12", "Koda: Refining prompt...")
            processed = refine_prompt(text, config)
        elif recording_mode == "command":
            processed = process_text(text, config)
            # LLM polish for command mode
            processed = polish_with_llm(processed)
        else:
            light_config = {
                "post_processing": {
                    "remove_filler_words": config.get("post_processing", {}).get("remove_filler_words", True),
                    "code_vocabulary": False,
                    "auto_capitalize": config.get("post_processing", {}).get("auto_capitalize", True),
                    "auto_format": config.get("post_processing", {}).get("auto_format", True),
                }
            }
            processed = process_text(text, light_config)

        # Run plugin text processors
        if plugins.loaded:
            processed = plugins.run_text_processors(processed, config)

        logger.debug("After process_text: %r", processed)

        # Translation: if target is not English, use LLM to translate
        # (Whisper handles → English natively via task="translate")
        if translate_enabled and target_lang.lower() != "english":
            update_tray("#f39c12", f"Koda: Translating to {target_lang}...")
            processed = translate_with_llm(processed, target_lang)

        if processed:
            duration = time.time() - rec_start

            # Check for voice editing commands (e.g. "select all", "undo")
            if config.get("voice_commands", True):
                processed, cmds = extract_and_execute_commands(processed)
                if cmds and not processed:
                    # Entire utterance was a command — no text to paste
                    play_success_sound()
                    try:
                        save_transcription(f"[cmd: {', '.join(cmds)}]", recording_mode, duration)
                        for cmd in cmds:
                            log_command_stats(cmd)
                    except Exception:
                        pass
                    update_tray("#2ecc71", "Koda: Ready")
                    return

            last_transcription = processed

            output_mode = config.get("output_mode", "auto_paste")
            if output_mode == "clipboard":
                pyperclip.copy(processed)
                play_success_sound()
            else:
                pyperclip.copy(processed)
                time.sleep(0.15)
                # Use keyboard.send instead of pyautogui — pyautogui's
                # synthetic Ctrl conflicts with the keyboard library's hooks
                keyboard.send("ctrl+v")
                play_success_sound()

            # Save to history and stats
            try:
                save_transcription(processed, recording_mode, duration)
                app_name = ""
                prof_name = ""
                if profile_monitor:
                    try:
                        from profiles import get_active_window_info
                        app_name, _ = get_active_window_info()
                        prof_name = profile_monitor.current_profile or ""
                    except Exception as e:
                        logger.warning("Profile detection error: %s", e)
                log_transcription_stats(processed, recording_mode, duration, app_name, prof_name)
            except Exception as e:
                logger.error("Failed to save stats: %s", e)

    except Exception as e:
        logger.error("Transcription pipeline error: %s", e, exc_info=True)
        error_notify("Transcription failed. Check debug.log for details.")
        play_error_sound()
    finally:
        update_tray("#2ecc71", "Koda: Ready")


# ============================================================
# CORRECTION MODE
# ============================================================

def undo_and_rerecord():
    """Undo the last paste and start a new recording."""
    if last_transcription:
        # Select all the text that was just pasted and delete it
        # Use Ctrl+Z to undo the paste
        pyautogui.hotkey("ctrl", "z")
        time.sleep(0.2)
    # Start recording in the same mode as last time
    start_recording(recording_mode)


# ============================================================
# READ-BACK (Text-to-Speech)
# ============================================================

tts_engine = None
tts_speaking = False

TTS_SPEED_MAP = {
    "slow": 120,
    "normal": 160,
    "fast": 220,
}


def init_tts():
    """Placeholder — TTS is initialized lazily on first use to avoid COM threading issues."""
    pass


def _get_tts():
    """Get or create TTS engine (lazy init to avoid COM conflicts)."""
    global tts_engine
    if tts_engine is None:
        try:
            import pyttsx3
            tts_engine = pyttsx3.init()
            speed_name = config.get("tts", {}).get("rate", "normal")
            rate = TTS_SPEED_MAP.get(speed_name, 160) if isinstance(speed_name, str) else speed_name
            tts_engine.setProperty('rate', rate)
            # Set voice if configured
            voice_name = config.get("tts", {}).get("voice", None)
            if voice_name:
                for v in tts_engine.getProperty('voices'):
                    if voice_name.lower() in v.name.lower():
                        tts_engine.setProperty('voice', v.id)
                        break
        except Exception:
            return None
    return tts_engine


def get_available_voices():
    """List available TTS voices."""
    try:
        import pyttsx3
        engine = pyttsx3.init()
        return [(v.name, v.id) for v in engine.getProperty('voices')]
    except Exception:
        return []


def read_back():
    """Read aloud the last transcription or whatever is on the clipboard."""
    global tts_speaking
    engine = _get_tts()
    if not engine:
        return

    if tts_speaking:
        engine.stop()
        tts_speaking = False
        update_tray("#2ecc71", "Koda: Ready")
        return

    text = last_transcription or pyperclip.paste()
    if not text:
        return

    tts_speaking = True
    update_tray("#9b59b6", "Koda: Reading...")

    def _speak():
        global tts_speaking
        try:
            e = _get_tts()
            if e:
                e.say(text)
                e.runAndWait()
        except Exception:
            pass
        tts_speaking = False
        update_tray("#2ecc71", "Koda: Ready")

    threading.Thread(target=_speak, daemon=True).start()


def read_selected():
    """Read aloud whatever text is currently selected on screen."""
    global tts_speaking
    engine = _get_tts()
    if not engine:
        return

    if tts_speaking:
        engine.stop()
        tts_speaking = False
        update_tray("#2ecc71", "Koda: Ready")
        return

    original = pyperclip.paste()
    pyautogui.hotkey("ctrl", "c")
    time.sleep(0.2)
    text = pyperclip.paste()
    pyperclip.copy(original)

    if not text:
        return

    tts_speaking = True
    update_tray("#9b59b6", "Koda: Reading...")

    def _speak():
        global tts_speaking
        try:
            e = _get_tts()
            if e:
                e.say(text)
                e.runAndWait()
        except Exception:
            pass
        tts_speaking = False
        update_tray("#2ecc71", "Koda: Ready")

    threading.Thread(target=_speak, daemon=True).start()


# ============================================================
# HOTKEYS
# ============================================================

_hotkeys_registered = False  # Track if hotkeys are active


def _hotkey_event_thread():
    """Read events from the hotkey service subprocess and dispatch them."""
    global _hotkey_conn
    logger.info("Hotkey event listener started")
    while _hotkey_conn is not None:
        try:
            if _hotkey_conn.poll(1.0):
                event = _hotkey_conn.recv()
            else:
                continue
        except (EOFError, OSError):
            logger.warning("Hotkey service pipe closed")
            break
        except Exception as e:
            logger.error("Hotkey event read error: %s", e)
            time.sleep(0.5)
            continue

        try:
            if event == "ready":
                logger.info("Hotkey service reports ready")
            elif event == "pong":
                _hotkey_pong.set()  # Signal watchdog that service is responsive
            elif event == "dictation_press":
                start_recording("dictation")
            elif event == "dictation_release":
                if recording:
                    threading.Thread(target=stop_recording, daemon=True).start()
            elif event == "command_press":
                start_recording("command")
            elif event == "command_release":
                if recording:
                    threading.Thread(target=stop_recording, daemon=True).start()
            elif event == "dictation_toggle":
                if recording:
                    threading.Thread(target=stop_recording, daemon=True).start()
                else:
                    start_recording("dictation")
            elif event == "command_toggle":
                if recording:
                    threading.Thread(target=stop_recording, daemon=True).start()
                else:
                    start_recording("command")
            elif event == "prompt_press":
                start_recording("prompt")
            elif event == "prompt_release":
                if recording:
                    threading.Thread(target=stop_recording, daemon=True).start()
            elif event == "prompt_toggle":
                if recording:
                    threading.Thread(target=stop_recording, daemon=True).start()
                else:
                    start_recording("prompt")
            elif event == "correction":
                threading.Thread(target=undo_and_rerecord, daemon=True).start()
            elif event == "readback":
                threading.Thread(target=read_back, daemon=True).start()
            elif event == "readback_selected":
                threading.Thread(target=read_selected, daemon=True).start()
            else:
                logger.debug("Unknown hotkey event: %s", event)
        except Exception as e:
            logger.error("Error dispatching hotkey event %s: %s", event, e)


def _build_hotkey_config():
    """Build the config dict sent to the hotkey service subprocess."""
    log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "debug.log")
    return {
        "hotkey_dictation": config.get("hotkey_dictation", "ctrl+space"),
        "hotkey_command": config.get("hotkey_command", "ctrl+alt+d"),
        "hotkey_prompt": config.get("hotkey_prompt", "f9"),
        "hotkey_correction": config.get("hotkey_correction", "ctrl+shift+z"),
        "hotkey_readback": config.get("hotkey_readback", "ctrl+alt+r"),
        "hotkey_readback_selected": config.get("hotkey_readback_selected", "ctrl+alt+t"),
        "hotkey_mode": config.get("hotkey_mode", "hold"),
        "_log_path": log_path,
    }


def _stop_hotkey_service():
    """Stop the hotkey service subprocess if running."""
    global _hotkey_proc, _hotkey_conn, _hotkey_listener
    if _hotkey_conn is not None:
        try:
            _hotkey_conn.send("quit")
        except Exception:
            pass
        try:
            _hotkey_conn.close()
        except Exception:
            pass
        _hotkey_conn = None
    if _hotkey_proc is not None:
        try:
            _hotkey_proc.join(timeout=3)
        except Exception:
            pass
        if _hotkey_proc.is_alive():
            logger.warning("Hotkey service didn't exit, terminating")
            _hotkey_proc.terminate()
        _hotkey_proc = None
    _hotkey_listener = None


def setup_hotkeys():
    """Start (or restart) the hotkey service subprocess.

    Keyboard hooks run in a dedicated process so they are immune to GIL
    contention from Whisper transcription in the main process.
    """
    global _hotkey_proc, _hotkey_conn, _hotkey_listener, _hotkeys_registered

    # Stop any existing service first
    _stop_hotkey_service()

    from hotkey_service import service_main

    parent_conn, child_conn = multiprocessing.Pipe()
    _hotkey_conn = parent_conn

    _hotkey_proc = multiprocessing.Process(
        target=service_main,
        args=(child_conn, _build_hotkey_config()),
        daemon=True,
        name="koda-hotkey-service",
    )
    _hotkey_proc.start()
    logger.info("Hotkey service process started (pid=%d)", _hotkey_proc.pid)

    # Start event listener thread
    _hotkey_listener = threading.Thread(target=_hotkey_event_thread, daemon=True)
    _hotkey_listener.start()

    _hotkeys_registered = True
    logger.info("Hotkey setup complete (subprocess mode, mode=%s)",
                config.get("hotkey_mode", "hold"))


# ============================================================
# HEALTH WATCHDOG
# ============================================================

_watchdog_running = False


def _watchdog_thread():
    """Monitor Koda's health and auto-recover from failures.

    Checks every 15 seconds:
    - Audio stream is active
    - Keyboard hooks are alive (re-registers if dead)
    - Logs heartbeat every 5 minutes for diagnostics
    """
    global _watchdog_running
    _watchdog_running = True
    check_count = 0
    logger.info("Watchdog started")

    while _watchdog_running:
        time.sleep(15)
        check_count += 1
        try:
            # Heartbeat every 5 minutes (20 checks at 15s intervals)
            if check_count % 20 == 0:
                mem_mb = 0
                try:
                    import psutil
                    mem_mb = psutil.Process().memory_info().rss / (1024 * 1024)
                except Exception:
                    pass
                hk_pid = _hotkey_proc.pid if _hotkey_proc and _hotkey_proc.is_alive() else 0
                stream_ok = stream.active if stream else False
                logger.info("Watchdog heartbeat: hotkey_pid=%d stream=%s mem=%.0fMB",
                            hk_pid, stream_ok, mem_mb)

            # Check audio stream health
            if stream and not stream.active:
                logger.warning("Audio stream died — restarting")
                try:
                    stream.stop()
                except Exception:
                    pass
                try:
                    stream.start()
                    logger.info("Audio stream restarted successfully")
                    error_notify("Microphone recovered automatically.")
                except Exception as e:
                    logger.error("Failed to restart audio stream: %s", e)
                    error_notify("Microphone disconnected. Check your mic and restart Koda.")
                    update_tray("#e74c3c", "Koda: Mic error")

            # Check hotkey service subprocess is alive
            # With hooks in a separate process, the GIL issue is eliminated.
            # We just need to ensure the subprocess hasn't crashed.
            if _hotkeys_registered and _hotkey_proc is not None:
                try:
                    if not _hotkey_proc.is_alive():
                        logger.warning("Hotkey service process died (exitcode=%s) — restarting",
                                       _hotkey_proc.exitcode)
                        setup_hotkeys()
                        error_notify("Hotkeys recovered automatically. You're good to go.")
                        update_tray("#2ecc71", "Koda: Ready (recovered)")
                    elif check_count % 4 == 0 and _hotkey_conn is not None:
                        # Ping the service every ~60s to verify it's responsive
                        try:
                            _hotkey_pong.clear()
                            _hotkey_conn.send("ping")
                            if not _hotkey_pong.wait(timeout=3.0):
                                logger.warning("Hotkey service not responding to ping — restarting")
                                setup_hotkeys()
                                error_notify("Hotkeys recovered automatically. You're good to go.")
                        except Exception as e:
                            logger.error("Hotkey ping error: %s — restarting", e)
                            setup_hotkeys()
                except Exception as e:
                    logger.error("Hotkey health check error: %s", e)
                    try:
                        setup_hotkeys()
                        logger.info("Force restarted hotkey service after check error")
                    except Exception:
                        pass

        except Exception as e:
            logger.error("Watchdog error: %s", e)


# ============================================================
# TRAY MENU
# ============================================================

def build_menu():
    hotkey_dict = config.get("hotkey_dictation", "ctrl+space").upper()
    hotkey_cmd = config.get("hotkey_command", "ctrl+alt+d").upper()
    hotkey_prompt = config.get("hotkey_prompt", "f9").upper()
    hotkey_corr = config.get("hotkey_correction", "ctrl+shift+z").upper()
    hotkey_read = config.get("hotkey_readback", "ctrl+shift+r").upper()
    hotkey_read_sel = config.get("hotkey_readback_selected", "ctrl+shift+t").upper()
    mode = config.get("hotkey_mode", "hold")
    mode_label = "Hold-to-talk" if mode == "hold" else "Toggle (auto-stop)"
    wake_enabled = config.get("wake_word", {}).get("enabled", False)
    output_mode = config.get("output_mode", "auto_paste")
    output_label = "Auto-paste" if output_mode == "auto_paste" else "Clipboard only"

    return pystray.Menu(
        pystray.MenuItem(f"Koda v{VERSION}", None, enabled=False),
        pystray.MenuItem(f"{hotkey_dict} = Dictation  |  {hotkey_cmd} = Command", None, enabled=False),
        pystray.MenuItem(f"{hotkey_prompt} = Prompt Assist  |  {hotkey_corr} = Redo", None, enabled=False),
        pystray.MenuItem(f"{hotkey_read} = Read back  |  Mode: {mode_label}", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            "Sound effects",
            toggle_setting("sound_effects"),
            checked=lambda item: config.get("sound_effects", True),
        ),
        pystray.MenuItem(
            "Remove filler words",
            toggle_post_processing("remove_filler_words"),
            checked=lambda item: config.get("post_processing", {}).get("remove_filler_words", True),
        ),
        pystray.MenuItem(
            "Code vocabulary",
            toggle_post_processing("code_vocabulary"),
            checked=lambda item: config.get("post_processing", {}).get("code_vocabulary", False),
        ),
        pystray.MenuItem(
            "Voice commands (select all, undo...)",
            toggle_setting("voice_commands"),
            checked=lambda item: config.get("voice_commands", True),
        ),
        pystray.MenuItem(
            "Auto-format (numbers, dates)",
            toggle_post_processing("auto_format"),
            checked=lambda item: config.get("post_processing", {}).get("auto_format", True),
        ),
        pystray.MenuItem(
            "Noise reduction",
            toggle_setting("noise_reduction"),
            checked=lambda item: config.get("noise_reduction", False),
        ),
        pystray.MenuItem(
            "LLM polish (Ollama)",
            toggle_llm_polish,
            checked=lambda item: config.get("llm_polish", {}).get("enabled", False),
        ),
        pystray.MenuItem(
            "Translation",
            pystray.Menu(*_build_translation_menu_items()),
        ),
        pystray.MenuItem(
            f'Wake word ("Hey Koda")',
            toggle_wake_word,
            checked=lambda item: config.get("wake_word", {}).get("enabled", False),
        ),
        pystray.MenuItem(
            f"Output: {output_label}",
            toggle_output_mode,
        ),
        pystray.MenuItem(
            "Read-back voice",
            pystray.Menu(*_build_voice_menu_items()),
        ),
        pystray.MenuItem(
            "Read-back speed",
            pystray.Menu(*_build_speed_menu_items()),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            "Switch to Toggle mode" if mode == "hold" else "Switch to Hold mode",
            switch_mode,
        ),
        pystray.MenuItem(
            f"Per-app profiles{' (' + profile_monitor.current_profile + ')' if profile_monitor and profile_monitor.current_profile else ''}",
            toggle_profiles,
            checked=lambda item: config.get("profiles_enabled", True),
        ),
        pystray.MenuItem(
            "Floating overlay",
            toggle_overlay,
            checked=lambda item: overlay is not None and overlay.is_visible,
        ),
        pystray.MenuItem("Transcribe audio file", lambda icon, item: _open_transcribe_file()),
        pystray.MenuItem("Install Explorer right-click menu", lambda icon, item: _install_context_menu()),
        pystray.MenuItem("Edit custom words", lambda icon, item: _open_custom_words()),
        pystray.MenuItem("Edit app profiles", lambda icon, item: _open_profiles()),
        pystray.MenuItem("Usage stats", lambda icon, item: _open_stats()),
        pystray.MenuItem("Settings window", lambda icon, item: _open_settings_gui()),
        pystray.MenuItem("Open config file", lambda icon, item: open_config_file()),
        # Plugin menu items
        *[pystray.MenuItem(label, lambda icon, item, cb=cb: cb())
          for label, cb in plugins.get_all_menu_items()],
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", on_quit),
    )


def _build_voice_menu_items():
    """Build radio button menu items for available TTS voices."""
    current_voice = config.get("tts", {}).get("voice", "")
    voices = get_available_voices()
    if not voices:
        return [pystray.MenuItem("No voices available", None, enabled=False)]

    items = []
    for name, vid in voices:
        short = name.replace("Microsoft ", "").replace(" Desktop", "")

        def make_handler(vname):
            def handler(icon, item):
                global tts_engine
                tts = config.setdefault("tts", {})
                tts["voice"] = vname
                save_config(config)
                tts_engine = None  # Reset so it picks up new voice
                icon.menu = build_menu()
            return handler

        items.append(pystray.MenuItem(
            short,
            make_handler(name),
            checked=lambda item, n=name: n.lower() in config.get("tts", {}).get("voice", "").lower(),
            radio=True,
        ))
    return items


def _build_speed_menu_items():
    """Build radio button menu items for TTS read-back speed."""
    current_speed = config.get("tts", {}).get("rate", "normal")
    items = []
    for label, key in [("Slow (120 wpm)", "slow"), ("Normal (160 wpm)", "normal"), ("Fast (220 wpm)", "fast")]:
        def make_handler(speed_key):
            def handler(icon, item):
                global tts_engine
                tts = config.setdefault("tts", {})
                tts["rate"] = speed_key
                save_config(config)
                tts_engine = None  # Reset so it picks up new rate
                icon.menu = build_menu()
            return handler

        items.append(pystray.MenuItem(
            label,
            make_handler(key),
            checked=lambda item, k=key: config.get("tts", {}).get("rate", "normal") == k,
            radio=True,
        ))
    return items


def _build_translation_menu_items():
    """Build submenu items for translation target language."""
    trans = config.get("translation", {})
    enabled = trans.get("enabled", False)
    target = trans.get("target_language", "English")

    items = [
        pystray.MenuItem(
            "Off" if enabled else "Off (current)",
            lambda icon, item: _set_translation(icon, False, ""),
            checked=lambda item: not config.get("translation", {}).get("enabled", False),
            radio=True,
        ),
    ]

    # Whisper native: any → English
    languages = [
        ("English", "Speak any language → type English (Whisper)"),
        ("Spanish", "Type in Spanish (LLM)"),
        ("French", "Type in French (LLM)"),
        ("German", "Type in German (LLM)"),
        ("Portuguese", "Type in Portuguese (LLM)"),
        ("Japanese", "Type in Japanese (LLM)"),
        ("Korean", "Type in Korean (LLM)"),
        ("Chinese", "Type in Chinese (LLM)"),
        ("Italian", "Type in Italian (LLM)"),
        ("Russian", "Type in Russian (LLM)"),
    ]

    for lang, desc in languages:
        def make_handler(l):
            return lambda icon, item: _set_translation(icon, True, l)
        items.append(pystray.MenuItem(
            f"→ {lang}",
            make_handler(lang),
            checked=lambda item, l=lang: (
                config.get("translation", {}).get("enabled", False) and
                config.get("translation", {}).get("target_language", "") == l
            ),
            radio=True,
        ))

    return items


def _set_translation(icon, enabled, target):
    trans = config.setdefault("translation", {})
    trans["enabled"] = enabled
    trans["target_language"] = target
    save_config(config)
    icon.menu = build_menu()


def _open_settings_gui():
    """Launch the settings GUI in a separate process."""
    import subprocess
    settings_py = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings_gui.py")
    subprocess.Popen([sys.executable, settings_py])


def toggle_setting(key):
    def handler(icon, item):
        config[key] = not config.get(key, True)
        save_config(config)
        icon.menu = build_menu()
    return handler


def toggle_post_processing(key):
    def handler(icon, item):
        pp = config.setdefault("post_processing", {})
        pp[key] = not pp.get(key, False)
        save_config(config)
        icon.menu = build_menu()
    return handler


def toggle_llm_polish(icon, item):
    llm = config.setdefault("llm_polish", {"enabled": False, "model": "phi3:mini"})
    llm["enabled"] = not llm.get("enabled", False)
    save_config(config)
    icon.menu = build_menu()


def toggle_wake_word(icon, item):
    ww = config.setdefault("wake_word", {"enabled": False, "phrase": "hey koda"})
    ww["enabled"] = not ww.get("enabled", False)
    save_config(config)
    if ww["enabled"]:
        start_wake_word_listener()
    else:
        stop_wake_word_listener()
    icon.menu = build_menu()


def toggle_output_mode(icon, item):
    current = config.get("output_mode", "auto_paste")
    config["output_mode"] = "clipboard" if current == "auto_paste" else "auto_paste"
    save_config(config)
    icon.menu = build_menu()


def _on_profile_change(profile_name, merged_config):
    """Called when the active window changes to a different profile."""
    global config
    if profile_name:
        config = merged_config
        notify(f"Profile: {profile_name}")
        if overlay:
            overlay.set_state("ready", f"Profile: {profile_name}")
    else:
        config = base_config.copy()


def toggle_profiles(icon, item):
    global profile_monitor
    if config.get("profiles_enabled", True):
        config["profiles_enabled"] = False
        if profile_monitor:
            profile_monitor.stop()
            profile_monitor = None
    else:
        config["profiles_enabled"] = True
        profile_monitor = ProfileMonitor(base_config, on_profile_change=_on_profile_change)
        profile_monitor.start()
    save_config(config)
    icon.menu = build_menu()


def toggle_overlay(icon, item):
    if overlay:
        overlay.toggle_visible()
        config["overlay_enabled"] = overlay.is_visible
        save_config(config)
        icon.menu = build_menu()


def _open_custom_words():
    """Open custom_words.json in the default editor."""
    custom_words_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_words.json")
    if not os.path.exists(custom_words_path):
        import json
        with open(custom_words_path, "w", encoding="utf-8") as f:
            json.dump({"coda": "Koda", "claude code": "Claude Code"}, f, indent=2)
    os.startfile(custom_words_path)


def _open_stats():
    """Open the usage stats dashboard."""
    from stats_gui import StatsDashboard
    dash = StatsDashboard()
    dash.show()


def _open_transcribe_file():
    """Open the audio file transcription window."""
    from transcribe_file import TranscribeFileWindow
    win = TranscribeFileWindow(model, config)
    win.show()


def _install_context_menu():
    """Install the 'Transcribe with Koda' right-click context menu."""
    import subprocess
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "context_menu.py")
    result = subprocess.run([sys.executable, script, "install"], capture_output=True, text=True)
    if result.returncode == 0:
        notify("Context menu installed! Right-click audio files to transcribe.")
    else:
        notify(f"Failed: {result.stderr[:100]}")


def _open_profiles():
    """Open profiles.json in the default editor."""
    from profiles import load_profiles, PROFILES_PATH
    load_profiles()  # Ensure file exists
    os.startfile(PROFILES_PATH)


def switch_mode(icon, item):
    current = config.get("hotkey_mode", "hold")
    config["hotkey_mode"] = "toggle" if current == "hold" else "hold"
    save_config(config)
    setup_hotkeys()  # restarts the hotkey service subprocess with new mode
    icon.menu = build_menu()


# ============================================================
# LIFECYCLE
# ============================================================

def on_quit(icon, item):
    global stream, wake_word_active, _watchdog_running
    logger.info("Koda shutting down")
    _watchdog_running = False
    wake_word_active = False
    _stop_hotkey_service()
    if plugins.loaded:
        plugins.unload_all()
    if profile_monitor:
        profile_monitor.stop()
    if overlay:
        overlay.stop()
    if stream:
        stream.stop()
        stream.close()
    icon.stop()


def run_setup():
    global stream, overlay, profile_monitor, base_config

    update_tray("gray", "Koda: Loading model...")

    # Start floating overlay (if enabled — default on)
    if config.get("overlay_enabled", True):
        overlay = KodaOverlay()
        overlay.start()

    # Start per-app profile monitor
    base_config = config.copy()
    if config.get("profiles_enabled", True):
        profile_monitor = ProfileMonitor(base_config, on_profile_change=_on_profile_change)
        profile_monitor.start()

    load_whisper_model()
    init_vad()
    init_tts()
    init_db()
    init_stats()

    # Load plugins
    plugins.discover_and_load(config)
    if plugins.loaded:
        logger.info("Loaded %d plugin(s): %s", len(plugins.loaded), ", ".join(plugins.loaded))
        # Register plugin voice commands
        plugin_cmds = plugins.get_all_commands()
        if plugin_cmds:
            from voice_commands import register_extra_commands
            register_extra_commands(plugin_cmds)
            logger.info("Registered %d plugin command(s)", len(plugin_cmds))

    mic_device = config.get("mic_device")
    stream = sd.InputStream(
        samplerate=16000,
        channels=1,
        dtype="float32",
        device=mic_device,
        callback=audio_callback,
    )
    stream.start()

    setup_hotkeys()
    start_wake_word_listener()

    # Start health watchdog
    threading.Thread(target=_watchdog_thread, daemon=True).start()

    update_tray("#2ecc71", "Koda: Ready")
    logger.info("Koda v%s fully initialized", VERSION)


_lock_handle = None


def _find_stale_koda_pids():
    """Find pythonw/python PIDs running voice.py (i.e., other Koda instances)."""
    import subprocess
    pids = []
    try:
        # WMIC gives us the command line of each process
        result = subprocess.run(
            ["wmic", "process", "where",
             "name='pythonw.exe' or name='python.exe'",
             "get", "processid,commandline"],
            capture_output=True, text=True, timeout=5
        )
        for line in result.stdout.splitlines():
            if "voice.py" in line and str(os.getpid()) not in line:
                # Extract PID (last number on the line)
                parts = line.strip().split()
                if parts:
                    try:
                        pids.append(int(parts[-1]))
                    except ValueError:
                        pass
    except Exception as e:
        logger.warning("Could not scan for stale Koda processes: %s", e)
    return pids


def _acquire_single_instance():
    """Ensure only one Koda instance runs at a time using a mutex.

    If a stale Koda is detected (mutex exists but process is ours to claim),
    kill the stale process and take ownership.
    """
    global _lock_handle
    import ctypes
    _lock_handle = ctypes.windll.kernel32.CreateMutexW(None, True, "KodaVoiceAppMutex")
    if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
        stale_pids = _find_stale_koda_pids()
        if stale_pids:
            import subprocess
            logger.info("Found stale Koda process(es): %s — killing", stale_pids)
            for pid in stale_pids:
                try:
                    subprocess.run(["taskkill", "//f", "//pid", str(pid)],
                                   capture_output=True, timeout=5)
                except Exception:
                    pass
            # Wait briefly for processes to die, then reclaim mutex
            time.sleep(1)
            ctypes.windll.kernel32.ReleaseMutex(_lock_handle)
            ctypes.windll.kernel32.CloseHandle(_lock_handle)
            _lock_handle = ctypes.windll.kernel32.CreateMutexW(None, True, "KodaVoiceAppMutex")
        else:
            # Mutex exists but no stale Koda found — a live instance is running
            print("Koda is already running. Exiting.")
            sys.exit(0)


def main():
    global tray_icon, config

    _acquire_single_instance()

    config = load_config()

    tray_icon = pystray.Icon(
        "koda",
        create_icon("gray"),
        "Koda: Loading...",
        build_menu(),
    )

    threading.Thread(target=run_setup, daemon=True).start()
    tray_icon.run()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
