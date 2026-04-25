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
import ctypes
import winsound
import numpy as np
import sounddevice as sd
import keyboard  # used only for keyboard.send() — hooks run in hotkey_service subprocess
import pyperclip
import pyautogui
import pystray
from PIL import Image, ImageDraw

# Windows DPI awareness. Without this, frozen tkinter apps render at legacy
# 96 DPI and Windows bitmap-upscales them — producing tiny blurry windows on
# any display scaled above 100%. Must be set before any Tk window is created.
if sys.platform == "win32":
    try:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)  # per-monitor DPI
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


# Windows SetPriorityClass constants — keep in a single source of truth.
_PRIORITY_CLASSES = {
    "normal": 0x00000020,         # NORMAL_PRIORITY_CLASS
    "above_normal": 0x00008000,   # ABOVE_NORMAL_PRIORITY_CLASS
    "high": 0x00000080,           # HIGH_PRIORITY_CLASS
}


def set_process_priority(level):
    """Raise the current process's Windows scheduling priority class.

    Under system load (many Node/Electron sessions, background builds, etc.)
    the default NORMAL_PRIORITY_CLASS causes Koda to round-robin with every
    other CPU-hungry process — Whisper transcription stalls for tens of
    seconds. ABOVE_NORMAL lets Windows preempt other normal-priority processes
    when Koda has work without starving the rest of the desktop. HIGH is more
    aggressive; never use REALTIME.

    No-op on non-Windows platforms. Unknown levels log a warning and fall
    through to NORMAL so the app still starts cleanly.
    """
    if sys.platform != "win32":
        return
    flag = _PRIORITY_CLASSES.get(level)
    if flag is None:
        logger.warning("Unknown process_priority %r — leaving at normal", level)
        return
    try:
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        ok = ctypes.windll.kernel32.SetPriorityClass(handle, flag)
        if not ok:
            err = ctypes.windll.kernel32.GetLastError()
            logger.warning("SetPriorityClass(%s) failed (GetLastError=%d)", level, err)
        else:
            logger.info("Process priority set to %s", level)
    except Exception as e:
        logger.warning("Could not set process priority: %s", e)

from config import CONFIG_DIR, load_config, save_config
from text_processing import process_text, apply_custom_vocabulary
from history import init_db, save_transcription
from overlay import KodaOverlay
from profiles import ProfileMonitor, get_active_window_info
from formula_mode import convert_to_formula, is_formula_app, execute_excel_action
from terminal_mode import is_terminal_app, normalize_for_terminal
from voice_commands import extract_and_execute_commands
from app_launch import extract_launch_intent, launch_app
from stats import init_stats_db as init_stats, log_transcription_stats, log_command_stats
from plugin_manager import PluginManager
from prompt_assist import refine_prompt
from updater import check_for_update


# --- Data directory (imported from config to keep source-vs-frozen resolution in one place) ---
_DATA_DIR = CONFIG_DIR

# --- Logging ---
logging.basicConfig(
    filename=os.path.join(_DATA_DIR, "debug.log"),
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("koda")
logger.setLevel(logging.DEBUG)  # Koda's own logger is DEBUG, but library noise is WARNING+

# --- Version ---
VERSION = "4.3.1"

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
_update_available = None  # (version, download_url) if update found
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
_last_key_event_mono = time.monotonic()  # last key delivery confirmed by hotkey service


# ============================================================
# ICON
# ============================================================

def _load_icon_base(size=64):
    """Load the professional icon from koda.ico at the requested size."""
    ico_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "koda.ico")
    try:
        img = Image.open(ico_path)
        img.load()
        return img.resize((size, size), Image.LANCZOS)
    except Exception:
        pass
    # Fallback: generate a simple icon if .ico is missing
    return _generate_fallback_icon(size)


def _generate_fallback_icon(size=64):
    """Fallback icon when koda.ico is not available."""
    from PIL import ImageFont
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    s = size / 64
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(18 * s), fill="#0f1023")
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
    return img


def create_branded_icon(size=64, dot_color=None):
    """Koda branded icon with optional colored status dot.

    Loads from koda.ico for the professional designed icon,
    falls back to code-generated if .ico is missing.
    """
    img = _load_icon_base(size)
    if dot_color:
        draw = ImageDraw.Draw(img)
        s = size / 64
        dr = int(7 * s)
        cx, cy = size - int(10 * s), size - int(10 * s)
        draw.ellipse([cx - dr - 2, cy - dr - 2, cx + dr + 2, cy + dr + 2], fill="#0f1023")
        draw.ellipse([cx - dr, cy - dr, cx + dr, cy + dr], fill=dot_color)
    return img


def create_icon(color="gray"):
    """Tray icon — branded K on dark bg with colored status dot."""
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


_pending_error_notifications = []


def error_notify(message):
    """Show a tray notification for errors — always shown regardless of config.

    Queues the message if called before tray_icon is initialized; flush_pending_error_notifications()
    drains the queue once the tray is up (e.g., during startup load paths like _load_custom_words
    that run before pystray.Icon() is constructed).
    """
    logger.error("User notification: %s", message)
    if tray_icon:
        try:
            tray_icon.notify(message[:200], "Koda Error")
        except Exception:
            pass
    else:
        _pending_error_notifications.append(message)


def flush_pending_error_notifications():
    if not tray_icon or not _pending_error_notifications:
        return
    for msg in _pending_error_notifications:
        try:
            tray_icon.notify(msg[:200], "Koda Error")
        except Exception:
            pass
    _pending_error_notifications.clear()


# Wire error_notify into voice_commands so its failure path reaches the user
# (direct import would cycle — voice_commands.py uses a set_notifier pattern).
import voice_commands as _vc_mod
_vc_mod.set_notifier(error_notify)


# ============================================================
# MODEL
# ============================================================

def dedup_segments(segments):
    """Join Whisper segments, dropping consecutive duplicates (hallucination guard)."""
    seg_texts = []
    for seg in segments:
        t = seg.text.strip()
        if t and (not seg_texts or t != seg_texts[-1]):
            seg_texts.append(t)
    return " ".join(seg_texts).strip()


def _discover_bundled_models(base_dir):
    """Return sorted list of bundled model sizes present at base_dir.

    PyInstaller bundles each model as a directory `_model_<size>` inside the
    frozen exe's extraction dir. A stale user config may point at a size the
    installer didn't ship — we use this to pick a working fallback instead of
    erroring out with "try reinstalling".
    """
    prefix = "_model_"
    try:
        entries = os.listdir(base_dir)
    except OSError:
        return []
    return sorted(
        name[len(prefix):]
        for name in entries
        if name.startswith(prefix) and os.path.isdir(os.path.join(base_dir, name))
    )


def load_whisper_model():
    global model
    from faster_whisper import WhisperModel
    model_size = config.get("model_size", "small")
    compute_type = config.get("compute_type", "int8")
    device = "cuda" if compute_type == "float16" else "cpu"

    base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    bundled = os.path.join(base_dir, f"_model_{model_size}")
    bundled_sizes = _discover_bundled_models(base_dir)
    logger.debug("Model search: base_dir=%s, bundled_path=%s, exists=%s, bundled_sizes=%s",
                 base_dir, bundled, os.path.isdir(bundled), bundled_sizes)

    # Cap faster-whisper/CTranslate2 thread pool. Default (0 = all cores) thrashes
    # the scheduler under system load — pinning to a small number lets each thread
    # keep its L3 cache and plays nice with other heavy processes.
    cpu_threads = int(config.get("cpu_threads", 4))

    def _load(m_size, dev, c_type):
        b = os.path.join(base_dir, f"_model_{m_size}")
        if os.path.isdir(b):
            logger.debug("Loading bundled model from: %s", b)
            return WhisperModel(b, device=dev, compute_type=c_type, cpu_threads=cpu_threads)
        logger.debug("Bundled model not found at %s — loading by name (may download)", b)
        return WhisperModel(m_size, device=dev, compute_type=c_type, cpu_threads=cpu_threads)

    def _try_bundled_fallback(original_error):
        global model
        alt = next((s for s in bundled_sizes if s != model_size), None)
        if alt is None:
            return False
        logger.warning(
            "Configured model '%s' unavailable (%s) — falling back to bundled '%s'",
            model_size, original_error, alt,
        )
        error_notify(f"Model '{model_size}' unavailable — using bundled '{alt}'.")
        try:
            fallback = _load(alt, "cpu", "int8")
        except Exception as e:
            logger.error("Bundled fallback '%s' also failed: %s", alt, e, exc_info=True)
            return False
        model = fallback
        config["model_size"] = alt
        config["compute_type"] = "int8"
        try:
            save_config(config)
        except Exception as e:
            logger.warning("Could not persist fallback model_size: %s", e)
        logger.info("Bundled fallback model '%s' loaded", alt)
        return True

    try:
        model = _load(model_size, device, compute_type)
        logger.info("Whisper model '%s' loaded (device=%s, compute=%s)", model_size, device, compute_type)
        return
    except Exception as e:
        primary_error = e

    if device == "cuda":
        logger.warning("GPU load failed (%s) — falling back to CPU Standard Mode", primary_error)
        error_notify("GPU unavailable — Koda switched to Standard Mode.")
        try:
            model = _load(model_size, "cpu", "int8")
            config["compute_type"] = "int8"
            try:
                save_config(config)
            except Exception as e:
                logger.warning("Could not persist compute_type: %s", e)
            logger.info("Fallback to %s/cpu/int8 succeeded", model_size)
            return
        except Exception as e2:
            logger.warning("CPU fallback of configured model also failed: %s", e2)
            primary_error = e2

    if _try_bundled_fallback(primary_error):
        return

    logger.error("Failed to load Whisper model '%s': %s", model_size, primary_error, exc_info=primary_error)
    error_notify(f"Failed to load speech model '{model_size}'. Try reinstalling Koda.")
    raise primary_error


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
    except Exception as e:
        global _polish_warned
        if not _polish_warned:
            logger.warning("LLM polish failed: %s", e)
            error_notify("LLM polish unavailable — using raw text. Is Ollama running?")
            _polish_warned = True
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
    except Exception as e:
        global _translate_warned
        if not _translate_warned:
            logger.warning("LLM translate failed: %s", e)
            error_notify("LLM translate unavailable — using raw text. Is Ollama running?")
            _translate_warned = True
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


_vad_warned = False
_polish_warned = False
_translate_warned = False
_wake_warned = False
_tts_warned = False


def check_vad_silence(audio_chunk):
    global _vad_warned
    if vad_model is not None:
        try:
            chunk_size = 512
            if len(audio_chunk) >= chunk_size:
                segment = audio_chunk[:chunk_size].astype(np.float32)
                result = vad_model({"speech_prob": 0.5}, segment)
                if hasattr(result, 'get'):
                    return result.get("speech_prob", 0) > 0.5
        except Exception as e:
            if not _vad_warned:
                logger.warning("Silero VAD inference failed: %s — falling back to RMS threshold", e)
                _vad_warned = True
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
    except Exception as e:
        global _wake_warned
        if not _wake_warned:
            logger.warning("Wake word init failed: %s", e, exc_info=True)
            error_notify("Wake word unavailable — hotkey only. Check debug.log.")
            _wake_warned = True


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
    if status:
        logger.warning("Audio stream status: %s", status)
    if recording:
        audio_chunks.append(indata.copy())
    if _slot_recording:
        _slot_chunks.append(indata.copy())
    # Always feed wake word buffer (when not recording or slot-capturing)
    if wake_word_active and not recording and not _slot_recording:
        with wake_buffer_lock:
            wake_buffer.append(indata.copy())
            # Keep only last 3 seconds (16000 samples/sec, ~31 chunks/sec at 512 samples)
            max_chunks = int(3 * 16000 / frames) if frames > 0 else 100
            while len(wake_buffer) > max_chunks:
                wake_buffer.pop(0)


# ============================================================
# Slot recording — synchronous, VAD-stopped capture for prompt-assist v2.
# Coexists with `recording` (dictation/command). audio_callback feeds both.
# ============================================================

_slot_recording = False
_slot_chunks = []


def slot_record(slot_name, config_dict, max_seconds=15.0, silence_seconds=None, cancel_event=None):
    """Record one conversational slot until VAD silence or max timeout, then transcribe.

    Synchronous — blocks until done. Designed for prompt_conversation.run_conversation()
    which runs in its own daemon thread. Returns transcribed text (possibly empty).

    If cancel_event is provided and set during the poll loop, the recording stops
    early and returns "" — used by the voice-confirm listener to stop promptly
    when a button press has already committed a decision.
    """
    global _slot_recording, _slot_chunks, model, stream
    if silence_seconds is None:
        silence_seconds = config_dict.get("vad", {}).get("silence_timeout_ms", 1500) / 1000.0

    # Cross-module bridge: when voice.py runs as __main__ (via start.bat or
    # PyInstaller onefile) but another module imports us via `from voice
    # import ...`, the importing side gets a separate `voice` module with
    # its own globals. audio_callback is registered by __main__ and writes
    # to __main__'s `_slot_recording` / `_slot_chunks` / `recording` /
    # `audio_chunks` / `model` / `stream`. We route state through __main__
    # when that's the case so audio buffers actually reach this function.
    import sys
    _my_name = __name__
    _main = sys.modules.get("__main__")
    bridge = _main if (_main is not None and _main is not sys.modules.get(_my_name)) else None

    # Reach across for the loaded Whisper model + audio stream if our view is empty.
    if bridge is not None:
        if model is None:
            cand = getattr(bridge, "model", None)
            if cand is not None:
                model = cand
        if stream is None:
            cand = getattr(bridge, "stream", None)
            if cand is not None:
                stream = cand

    if model is None:
        logger.warning("slot_record: whisper model not loaded; returning empty")
        return ""
    if stream is None or not stream.active:
        logger.warning("slot_record: audio stream not available; returning empty")
        return ""

    # Point _slot_recording / _slot_chunks at the module that audio_callback
    # actually writes to. If bridging, we flip the __main__ flags and read
    # chunks from __main__'s list; our own module's copies stay in sync for
    # any local readers.
    def _set_recording(flag):
        global _slot_recording
        _slot_recording = flag
        if bridge is not None:
            bridge._slot_recording = flag

    def _get_chunks():
        return bridge._slot_chunks if bridge is not None else _slot_chunks

    def _reset_chunks():
        global _slot_chunks
        _slot_chunks = []
        if bridge is not None:
            bridge._slot_chunks = []

    _reset_chunks()
    _set_recording(True)
    play_start_sound()  # audio cue per design §"Design principles"

    cancelled = False
    try:
        start = time.time()
        last_voice = time.time()
        voice_detected = False  # gate silence-stop until at least one voice event
        VAD_RMS_THRESHOLD = 0.005  # tuned for typical mic gain
        MIN_AUDIO_S = 0.5

        while True:
            if cancel_event is not None and cancel_event.is_set():
                logger.info("slot_record(%s): cancelled via event", slot_name)
                cancelled = True
                break
            if time.time() - start > max_seconds:
                logger.info("slot_record(%s): hit max_seconds=%s (voice_detected=%s, chunk_count=%d)",
                            slot_name, max_seconds, voice_detected, len(_get_chunks()))
                break
            time.sleep(0.08)
            current_chunks = _get_chunks()
            if current_chunks:
                recent = current_chunks[-6:] if len(current_chunks) >= 6 else current_chunks
                try:
                    arr = np.concatenate(recent, axis=0).flatten()
                    rms = float(np.sqrt(np.mean(arr * arr)))
                    if rms > VAD_RMS_THRESHOLD:
                        voice_detected = True
                        last_voice = time.time()
                except Exception:
                    pass
            # Silence-stop requires BOTH: user actually spoke at some point AND
            # silence_seconds have passed since their last voice event.
            if voice_detected and (time.time() - last_voice) >= silence_seconds and (time.time() - start) >= MIN_AUDIO_S:
                logger.info("slot_record(%s): VAD silence stop", slot_name)
                break
    finally:
        _set_recording(False)
        chunks = list(_get_chunks())  # snapshot before clearing
        _reset_chunks()

    if cancelled:
        return ""

    if not chunks:
        return ""
    audio = np.concatenate(chunks, axis=0).flatten()
    if len(audio) < int(16000 * MIN_AUDIO_S):
        return ""

    try:
        kwargs = {"beam_size": 1, "vad_filter": False}
        lang = config_dict.get("language", "en")
        if lang and lang != "auto":
            kwargs["language"] = lang
        segments, _ = model.transcribe(audio, **kwargs)
        text = " ".join(seg.text for seg in segments).strip()
        logger.info("slot_record(%s): transcribed %d chars", slot_name, len(text))
        return text
    except Exception as e:
        logger.error("slot_record transcribe failed: %s", e, exc_info=True)
        return ""


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
    if stream is None or not stream.active:
        # Mic unavailable — give audible + visible feedback instead of a misleading
        # start chime followed by silence. Watchdog keeps trying to recover in the
        # background, so the user can retry in a few seconds once a mic is plugged in.
        play_error_sound()
        error_notify("No microphone available. Plug one in and try again in a few seconds — Koda will recover automatically.")
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
    except (ValueError, OSError) as e:
        # ValueError covers json.JSONDecodeError (subclass).
        logger.warning("Could not load custom words: %s", e)
        error_notify("Custom vocabulary file is corrupt — using none. Check debug.log.")
        return {}


_SLOW_TRANSCRIPTION_WARN_SECS = 12.0


def _transcribe_and_paste():
    global last_transcription
    stage_start = time.perf_counter()
    timings = {}
    try:
        rec_start = time.time()
        audio = np.concatenate(audio_chunks, axis=0).flatten()
        timings["concat"] = time.perf_counter() - stage_start

        # Noise reduction
        if config.get("noise_reduction", False):
            nr_start = time.perf_counter()
            try:
                import noisereduce as nr
                audio = nr.reduce_noise(y=audio, sr=16000, stationary=True)
            except Exception as e:
                logger.warning("Noise reduction failed: %s", e)
            timings["noise_reduction"] = time.perf_counter() - nr_start

        # Build transcription kwargs
        translation_cfg = config.get("translation", {})
        translate_enabled = translation_cfg.get("enabled", False)
        target_lang = translation_cfg.get("target_language", "English")

        transcribe_kwargs = {
            "beam_size": 1,
            "vad_filter": True,
            "condition_on_previous_text": False,  # each press is independent; prevents prior mishear from poisoning next segment
            "no_speech_threshold": 0.6,           # explicit default — tunable
            "log_prob_threshold": -0.8,            # reject low-confidence guesses (default -1.0 too permissive)
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
        custom_vocab = config.get("custom_vocabulary", {})
        if custom_vocab:
            prompt_words = " ".join(custom_vocab.values())
            transcribe_kwargs["initial_prompt"] = prompt_words

        # Transcribe with VAD filter + repetition penalty to prevent hallucinated repeats
        whisper_start = time.perf_counter()
        segments, info = model.transcribe(audio, **transcribe_kwargs)
        text = dedup_segments(segments)
        timings["whisper"] = time.perf_counter() - whisper_start
        logger.debug("Whisper raw: %r", text)

        if not text:
            update_tray("#2ecc71", "Koda: Ready")
            return

        # Post-processing
        _in_terminal = False  # may be set to True inside the else branch below
        if recording_mode == "prompt":
            if custom_vocab:
                text = apply_custom_vocabulary(text, custom_vocab)
            # Formula mode: if F9 pressed while Excel/Sheets is active, convert to formula
            try:
                proc_name, win_title = get_active_window_info()
                _in_formula_app = is_formula_app(proc_name, win_title)
                logger.debug("Formula check: proc=%r title=%r in_formula_app=%s", proc_name, win_title, _in_formula_app)
            except Exception as e:
                logger.debug("Formula check error: %s", e)
                _in_formula_app = False
            if _in_formula_app:
                update_tray("#f39c12", "Koda: Formula mode...")
                # Try COM actions first (navigation, table creation — Pro tier)
                if execute_excel_action(text):
                    play_success_sound()
                    try:
                        save_transcription(f"[excel: {text}]", recording_mode, time.time() - rec_start)
                    except Exception:
                        pass
                    update_tray("#2ecc71", "Koda: Ready")
                    return
                # Fall through to formula conversion
                llm_enabled = config.get("llm_polish", {}).get("enabled", False)
                llm_cfg = config.get("llm_polish", {}) if llm_enabled else None
                formula = convert_to_formula(text, llm_enabled=llm_enabled, llm_config=llm_cfg)
                processed = formula if formula is not None else text
            else:
                # Prompt Assist mode — structure speech into an effective LLM prompt
                update_tray("#f39c12", "Koda: Refining prompt...")
                processed = refine_prompt(text, config)
        elif recording_mode == "command":
            processed = process_text(text, config)
            # LLM polish for command mode
            processed = polish_with_llm(processed)
        else:
            # Check for terminal mode before processing — disables auto-capitalize/format
            # so shell commands don't get capitalized or punctuated
            try:
                proc_name, win_title = get_active_window_info()
                _in_terminal = is_terminal_app(proc_name, win_title)
                logger.debug("Terminal check: proc=%r title=%r detected=%s", proc_name, win_title, _in_terminal)
            except Exception as e:
                logger.debug("Terminal mode check error: %s", e)

            light_config = {
                "post_processing": {
                    "remove_filler_words": config.get("post_processing", {}).get("remove_filler_words", True),
                    "code_vocabulary": False,
                    # Disable in terminal — "cd /users" must not become "Cd /users"
                    "auto_capitalize": False if _in_terminal else config.get("post_processing", {}).get("auto_capitalize", True),
                    # Disable in terminal — trailing periods break shell commands
                    "auto_format": False if _in_terminal else config.get("post_processing", {}).get("auto_format", True),
                },
                "custom_vocabulary": custom_vocab,
                "snippets": config.get("snippets", {}),
            }
            processed = process_text(text, light_config)

            if _in_terminal:
                update_tray("#f39c12", "Koda: Terminal mode...")
                processed = normalize_for_terminal(processed)
                update_tray("#2ecc71", "Koda: Ready")

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

            # App-launch intent runs first — "open word" should never fall through
            # to voice_commands, and must not get pasted as text.
            if config.get("app_launch_enabled", True):
                app_token, _ = extract_launch_intent(processed)
                if app_token:
                    ok, resolved = launch_app(app_token)
                    if ok:
                        play_success_sound()
                    else:
                        play_error_sound()
                        error_notify(f"Couldn't launch {app_token!r}. Edit apps.json to add it.")
                    try:
                        save_transcription(f"[launch: {app_token} -> {resolved}]", recording_mode, duration)
                    except Exception:
                        pass
                    update_tray("#2ecc71", "Koda: Ready")
                    return

            # Check for voice editing commands (e.g. "select all", "undo")
            deferred_cmd = None
            if config.get("voice_commands", True):
                processed, cmds, deferred_cmd = extract_and_execute_commands(processed, in_terminal=_in_terminal)
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
                if deferred_cmd:
                    time.sleep(0.05)  # let paste settle before suffix command
                    deferred_cmd()
                play_success_sound()

            # Save to history and stats
            try:
                save_transcription(processed, recording_mode, duration)
                app_name = ""
                prof_name = ""
                if profile_monitor:
                    try:
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
        total = time.perf_counter() - stage_start
        # Whisper stage dominating = CPU contention → tune process_priority / cpu_threads.
        logger.debug("Transcribe timings (s): total=%.2f %s",
                     total,
                     " ".join(f"{k}={v:.2f}" for k, v in timings.items()))
        if total > _SLOW_TRANSCRIPTION_WARN_SECS:
            logger.warning(
                "Slow transcription: %.1fs (stages: %s). "
                "Likely CPU-starved by other heavy processes — consider closing some, "
                "raising process_priority, or tuning cpu_threads in config.json.",
                total,
                ", ".join(f"{k}={v:.1f}s" for k, v in timings.items()),
            )
        update_tray("#2ecc71", "Koda: Ready")


# ============================================================
# CORRECTION MODE
# ============================================================

def undo_and_rerecord():
    """Undo the last paste and start a new recording."""
    logger.info("undo_and_rerecord: last_transcription=%r recording_mode=%r", last_transcription, recording_mode)
    if last_transcription:
        try:
            proc_name, win_title = get_active_window_info()
            in_terminal = is_terminal_app(proc_name, win_title)
        except Exception:
            in_terminal = False
        if in_terminal:
            # Escape = PSReadLine RevertLine — clears current input line.
            # Ctrl+Z does nothing to synthetic pastes in terminal.
            keyboard.send("escape")
        else:
            keyboard.send("ctrl+z")
        time.sleep(0.2)
    # Start recording in the same mode as last time.
    # force_vad=True so VAD auto-stops the recording in hold mode —
    # correction mode has no hotkey release to stop it otherwise.
    start_recording(recording_mode, force_vad=True)


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
    """Warm-start TTS in a background thread so the first hotkey press doesn't
    pay the ~300-800ms cold-start cost. Safe to fail — _get_tts() will retry
    lazily on first real use."""
    def _warm():
        try:
            _get_tts()
            logger.info("TTS engine warmed")
        except Exception as e:
            logger.warning("TTS warm-start failed (will retry on use): %s", e)
    threading.Thread(target=_warm, daemon=True).start()


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
        except Exception as e:
            global _tts_warned
            if not _tts_warned:
                logger.error("TTS init failed: %s", e, exc_info=True)
                error_notify("Read-back voice unavailable. Check debug.log.")
                _tts_warned = True
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
        except Exception as err:
            logger.error("TTS speak failed: %s", err, exc_info=True)
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

    if not text or text == original:
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
        except Exception as err:
            logger.error("TTS speak failed: %s", err, exc_info=True)
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
                _hotkey_pong.set()  # Signal watchdog that service is responsive (legacy plain string)
            elif isinstance(event, tuple) and len(event) == 2 and event[0] == "pong":
                _hotkey_pong.set()
                global _last_key_event_mono
                _last_key_event_mono = event[1]  # monotonic time of last actual key delivery
            elif event == "hooks_dead":
                logger.warning("Hotkey service reports hooks are dead — triggering restart")
                threading.Thread(target=setup_hotkeys, daemon=True).start()
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
                if config.get("prompt_assist", {}).get("conversational", True):
                    from prompt_conversation import run_conversation
                    threading.Thread(target=run_conversation, args=(config,), daemon=True).start()
                else:
                    start_recording("prompt")
            elif event == "prompt_release":
                if recording:
                    threading.Thread(target=stop_recording, daemon=True).start()
            elif event == "prompt_toggle":
                if config.get("prompt_assist", {}).get("conversational", True):
                    from prompt_conversation import run_conversation
                    threading.Thread(target=run_conversation, args=(config,), daemon=True).start()
                elif recording:
                    threading.Thread(target=stop_recording, daemon=True).start()
                else:
                    start_recording("prompt")
            elif event == "correction":
                logger.info("Correction mode triggered")
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
    log_path = os.path.join(_DATA_DIR, "debug.log")
    return {
        "hotkey_dictation": config.get("hotkey_dictation", "ctrl+space"),
        "hotkey_command": config.get("hotkey_command", "f8"),
        "hotkey_prompt": config.get("hotkey_prompt", "ctrl+f9"),
        "hotkey_correction": config.get("hotkey_correction", "f7"),
        "hotkey_readback": config.get("hotkey_readback", "f6"),
        "hotkey_readback_selected": config.get("hotkey_readback_selected", "f5"),
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
    global _hotkey_proc, _hotkey_conn, _hotkey_listener, _hotkeys_registered, _last_key_event_mono
    _last_key_event_mono = time.monotonic()  # reset on restart — give new service grace period

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
_mic_disconnected = False  # True while mic is known-dead; prevents repeated notifications
_input_device_count = 0   # Baseline input device count; drop = physical disconnect
_screen_was_locked = False


def _is_screen_locked():
    """Return True if the Windows session is currently locked.

    When locked, the input desktop switches to Winlogon and is inaccessible
    from the user session — OpenInputDesktop returns 0 or a non-Default desktop.
    """
    try:
        hdesk = ctypes.windll.user32.OpenInputDesktop(0, False, 0x0001)
        if not hdesk:
            return True  # Can't open input desktop — session is locked
        buf = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetUserObjectInformationW(hdesk, 2, buf, ctypes.sizeof(buf), None)
        ctypes.windll.user32.CloseDesktop(hdesk)
        return buf.value.lower() != "default"
    except Exception:
        return False


def _restart_audio_stream():
    """Fully tear down and recreate the audio stream. Retries 3x for USB re-enumeration."""
    global stream
    try:
        if stream:
            stream.stop()
            stream.close()
    except Exception:
        pass
    mic_device = config.get("mic_device")
    last_err = None
    for attempt in range(3):
        try:
            stream = sd.InputStream(
                samplerate=16000,
                channels=1,
                dtype="float32",
                device=mic_device,
                callback=audio_callback,
            )
            stream.start()
            logger.info("Audio stream restarted successfully (attempt %d)", attempt + 1)
            return True
        except Exception as e:
            last_err = e
            logger.warning("Audio stream restart attempt %d failed: %s", attempt + 1, e)
            if attempt < 2:
                time.sleep(2)
    logger.error("Audio stream restart failed after 3 attempts: %s", last_err)
    return False


def _full_recovery(reason):
    """Force-restart audio stream + hotkey service after sleep/wake or lock/unlock."""
    logger.warning("Full recovery triggered: %s", reason)
    update_tray("gray", "Koda: Recovering...")

    # Restart audio — devices reset after sleep
    try:
        ok = _restart_audio_stream()
    except Exception as e:
        ok = False
        logger.error("Audio recovery failed: %s", e)
    if not ok:
        error_notify("Microphone error after wake. Check your mic.")
        update_tray("#e74c3c", "Koda: Mic error")
        return

    # Restart hotkey service — hooks die after sleep/lock
    try:
        setup_hotkeys()
    except Exception as e:
        logger.error("Hotkey recovery failed: %s", e)

    update_tray("#2ecc71", "Koda: Ready")
    logger.info("Full recovery complete (%s)", reason)


def _count_input_devices():
    """Return current number of audio input devices via Windows API (no PortAudio disruption)."""
    try:
        import ctypes
        return ctypes.windll.winmm.waveInGetNumDevs()
    except Exception:
        return 0


def _watchdog_thread():
    """Monitor Koda's health and auto-recover from failures.

    Stream health checked every 3 seconds for fast mic disconnect detection.
    Sleep/wake detection and hotkey health checked every 15 seconds.
    Heartbeat logged every 5 minutes.
    """
    global _watchdog_running, _input_device_count
    _watchdog_running = True
    check_count = 0
    last_15s_time = time.monotonic()
    last_heartbeat_time = time.monotonic()
    _input_device_count = _count_input_devices()
    logger.info("Watchdog started (input devices: %d)", _input_device_count)

    while _watchdog_running:
        time.sleep(3)

        now = time.monotonic()

        try:
            # --- Fast path: stream health every 3s ---
            # Covers both startup failure (stream is None — mic unavailable at launch)
            # and mid-session death (stream.active == False). A null stream at launch
            # used to leave Koda permanently dead: the watchdog required `stream` to be
            # truthy to even consider a restart. Now any state where the stream can't
            # produce audio triggers the same recovery path.
            if stream is None or not stream.active:
                global _mic_disconnected
                current_count = _count_input_devices()
                count_changed = current_count != _input_device_count
                if current_count < _input_device_count:
                    # Physical device removed — don't restart on wrong device
                    logger.warning("Input device count dropped %d→%d — physical disconnect",
                                   _input_device_count, current_count)
                    if not _mic_disconnected:
                        error_notify("Microphone disconnected. Plug it back in — Koda will recover.")
                        update_tray("#e74c3c", "Koda: Mic error")
                    _mic_disconnected = True
                    _input_device_count = current_count
                elif not _mic_disconnected or count_changed:
                    # Either the first time we've seen the stream dead (initial retry
                    # after startup failure) or the device count changed upward (mic
                    # plugged in after launch). Avoid hammering _restart_audio_stream
                    # every 3s once we've settled into the "no mic" steady state.
                    if stream is None:
                        logger.info("Audio stream not open — attempting to start (devices=%d)", current_count)
                    else:
                        logger.warning("Audio stream died — restarting")
                    ok = False
                    try:
                        ok = _restart_audio_stream()
                    except Exception as e:
                        logger.error("Failed to restart audio stream: %s", e)
                    if ok:
                        if _mic_disconnected:
                            error_notify("Microphone recovered automatically.")
                        _mic_disconnected = False
                        update_tray("#2ecc71", "Koda: Ready")
                    else:
                        if not _mic_disconnected:
                            error_notify("Microphone unavailable. Plug one in and set it as your default input — Koda will recover automatically.")
                            update_tray("#e74c3c", "Koda: Mic error")
                        _mic_disconnected = True
                    _input_device_count = current_count

            # --- Slow path: every ~15s ---
            elapsed_15 = now - last_15s_time
            if elapsed_15 < 15:
                continue
            check_count += 1
            last_15s_time = now

            # Detect sleep/wake: expected ~15s, >30s means system was asleep
            if elapsed_15 > 30:
                logger.warning("Sleep/wake detected (expected 15s, got %.0fs) — full recovery", elapsed_15)
                time.sleep(2)  # Brief pause for hardware to stabilize
                _full_recovery(f"sleep/wake, gap={elapsed_15:.0f}s")
                last_15s_time = time.monotonic()
                continue

            # Detect screen lock/unlock — Windows corrupts keyboard modifier state
            # on lock, breaking hotkey combinations even though the hook stays alive.
            # Restart hotkeys immediately on unlock so state is clean.
            global _screen_was_locked
            locked_now = _is_screen_locked()
            if _screen_was_locked and not locked_now:
                logger.info("Screen unlock detected — restarting hotkeys to restore hook state")
                setup_hotkeys()
                update_tray("#2ecc71", "Koda: Ready")
            _screen_was_locked = locked_now

            # Heartbeat every 5 minutes
            if now - last_heartbeat_time >= 300:
                last_heartbeat_time = now
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

            # Check hotkey service subprocess is alive
            if _hotkeys_registered and _hotkey_proc is not None:
                try:
                    if not _hotkey_proc.is_alive():
                        logger.warning("Hotkey service process died (exitcode=%s) — restarting",
                                       _hotkey_proc.exitcode)
                        setup_hotkeys()
                        error_notify("Hotkeys recovered automatically. You're good to go.")
                        update_tray("#2ecc71", "Koda: Ready (recovered)")
                    elif check_count % 2 == 0 and _hotkey_conn is not None:
                        # Ping the service every ~30s to verify hooks are alive
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

                    # Check for key-event staleness: process alive and pinging back,
                    # but no WM_HOTKEY messages delivered for a long time. Likely the
                    # RegisterHotKey registrations were silently dropped. _last_key_event_mono
                    # is updated on every WM_HOTKEY receipt in hotkey_service (via pong tuple).
                    secs_since_key = now - _last_key_event_mono
                    if secs_since_key > 900:  # 15 min — almost certainly a dead hook
                        logger.warning(
                            "No key events for %.0fs — silent hook death detected, restarting hotkey service",
                            secs_since_key,
                        )
                        setup_hotkeys()
                        error_notify("Hotkeys recovered automatically. You're good to go.")
                    elif secs_since_key > 600:  # 10 min — warn but don't restart yet
                        logger.warning(
                            "No key events for %.0fs — hook may be dead (will restart at 15 min)",
                            secs_since_key,
                        )
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
    hotkey_cmd  = config.get("hotkey_command", "f8").upper()
    mode        = config.get("hotkey_mode", "hold")
    mode_label  = "Hold-to-talk" if mode == "hold" else "Toggle"
    output_mode = config.get("output_mode", "auto_paste")

    tools_menu = pystray.Menu(
        pystray.MenuItem("Transcribe audio file",           lambda icon, item: _open_transcribe_file()),
        pystray.MenuItem("Install Explorer right-click",    lambda icon, item: _install_context_menu()),
        pystray.MenuItem("Usage stats",                     lambda icon, item: _open_stats()),
    )

    voice_menu       = pystray.Menu(*_build_voice_menu_items())
    speed_menu       = pystray.Menu(*_build_speed_menu_items())
    translation_menu = pystray.Menu(*_build_translation_menu_items())

    return pystray.Menu(
        pystray.MenuItem(f"Koda v{VERSION}  —  {hotkey_dict} dictation  |  {hotkey_cmd} command  |  {mode_label}", None, enabled=False),
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
            "Switch to Toggle mode" if mode == "hold" else "Switch to Hold mode",
            switch_mode,
        ),
        pystray.MenuItem(
            "Paste into active window" if output_mode == "auto_paste" else "Clipboard only (no paste)",
            toggle_output_mode,
            checked=lambda item: config.get("output_mode", "auto_paste") == "auto_paste",
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Read-back voice",  voice_menu),
        pystray.MenuItem("Read-back speed",  speed_menu),
        pystray.MenuItem("Translation",      translation_menu),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Settings",    lambda icon, item: _open_settings_gui()),
        pystray.MenuItem("Tools",       tools_menu),
        # Plugin menu items
        *[pystray.MenuItem(label, lambda icon, item, cb=cb: cb())
          for label, cb in plugins.get_all_menu_items()],
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            f"Update available: v{_update_available[0]}" if _update_available else "Check for updates",
            _on_update_menu_click,
        ),
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


def _open_settings_standalone():
    """In-process path used by --settings: opens the Settings window and blocks.

    Called from the frozen exe's CLI handler — the tray app cannot share a Tk
    mainloop with pystray, so frozen-mode Settings launches a separate Koda.exe
    process via --settings and that process ends when the window closes.
    """
    from settings_gui import KodaSettings
    app = KodaSettings()
    app.mainloop()


def _open_settings_gui():
    """Launch the settings GUI in a separate process."""
    import subprocess
    if getattr(sys, "frozen", False):
        # In the packaged exe, sys.executable is Koda.exe — spawn it with --settings
        # so a fresh Koda.exe process opens the Settings window standalone.
        subprocess.Popen([sys.executable, "--settings"])
    else:
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
    """Install the 'Transcribe with Koda' right-click context menu.

    Calls context_menu.install() in-process — works identically in dev (venv)
    and frozen (Koda.exe) modes. context_menu._build_command() detects sys.frozen
    and registers the appropriate launch command.
    """
    try:
        import context_menu
        context_menu.install()
        notify("Context menu installed! Right-click audio files to transcribe.")
    except Exception as e:
        notify(f"Failed: {str(e)[:100]}")


def switch_mode(icon, item):
    current = config.get("hotkey_mode", "hold")
    config["hotkey_mode"] = "toggle" if current == "hold" else "hold"
    save_config(config)
    setup_hotkeys()  # restarts the hotkey service subprocess with new mode
    icon.menu = build_menu()


def _on_update_menu_click(icon, item):
    """Handle 'Check for updates' / 'Download update' tray menu click."""
    if _update_available:
        # Open download URL in browser
        import webbrowser
        webbrowser.open(_update_available[1])
    else:
        # Trigger a manual check
        def _manual_check_cb(version, url):
            global _update_available
            if version:
                _update_available = (version, url)
                icon.menu = build_menu()
                if tray_icon:
                    try:
                        tray_icon.notify(
                            f"Koda v{version} is available! Click 'Update available' in the tray menu.",
                            "Koda Update",
                        )
                    except Exception:
                        pass
            else:
                if tray_icon:
                    try:
                        tray_icon.notify(f"You're running the latest version (v{VERSION}).", "Koda")
                    except Exception:
                        pass

        check_for_update(VERSION, callback=_manual_check_cb)


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


def _on_update_check_result(latest_version, download_url):
    """Called from background thread when update check completes."""
    global _update_available
    if latest_version:
        _update_available = (latest_version, download_url)
        if tray_icon:
            try:
                tray_icon.notify(
                    f"Koda v{latest_version} is available (you have v{VERSION}).\n"
                    f"Right-click tray icon → Check for updates.",
                    "Koda Update Available",
                )
            except Exception:
                pass
        logger.info("Update available: v%s (download: %s)", latest_version, download_url)


def run_setup():
    global stream, overlay, profile_monitor, base_config

    update_tray("gray", "Koda: Loading model...")

    # Start floating overlay (if enabled — default on)
    if config.get("overlay_enabled", False):
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
    try:
        stream = sd.InputStream(
            samplerate=16000,
            channels=1,
            dtype="float32",
            device=mic_device,
            callback=audio_callback,
        )
        stream.start()
    except Exception as e:
        logger.error("Failed to open audio stream at startup: %s", e)
        error_notify("Microphone unavailable. Check your mic — Koda will retry automatically.")

    setup_hotkeys()
    start_wake_word_listener()

    # Start health watchdog
    threading.Thread(target=_watchdog_thread, daemon=True).start()

    update_tray("#2ecc71", "Koda: Ready")
    logger.info("Koda v%s fully initialized", VERSION)

    # "Koda is ready" toast — always fires regardless of config.notifications
    # (direct tray_icon.notify bypasses the gate in notify()). Also flushes any
    # startup-time error_notify calls that were queued before the tray went live.
    if tray_icon:
        try:
            tray_icon.notify(f"Koda v{VERSION} is ready — hold Ctrl+Space to dictate.", "Koda")
        except Exception:
            pass
    flush_pending_error_notifications()

    # First-run welcome — show hotkey cheat sheet on first launch
    _first_run_path = os.path.join(_DATA_DIR, ".koda_initialized")
    if not os.path.exists(_first_run_path):
        try:
            with open(_first_run_path, "w") as f:
                f.write(VERSION)
            hk_dict = config.get("hotkey_dictation", "ctrl+space").upper()
            hk_cmd = config.get("hotkey_command", "f8").upper()
            hk_prompt = config.get("hotkey_prompt", "ctrl+f9").upper()
            welcome_msg = (
                f"Welcome to Koda!\n"
                f"{hk_dict} = Dictation (hold to talk)\n"
                f"{hk_cmd} = Command mode\n"
                f"{hk_prompt} = Prompt Assist\n"
                f"Right-click tray icon for settings."
            )
            if tray_icon:
                tray_icon.notify(welcome_msg, "Koda — Voice Input Ready")
            logger.info("First-run welcome shown")
        except Exception as e:
            logger.debug("First-run welcome failed: %s", e)

    # Check for updates (background, non-blocking)
    check_for_update(VERSION, callback=_on_update_check_result)


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
    config["custom_vocabulary"] = _load_custom_words()

    # Raise scheduling priority before any CPU-heavy work (model load, inference).
    # Keeps Koda responsive when the user also has many Node/Electron sessions open.
    set_process_priority(config.get("process_priority", "above_normal"))

    tray_icon = pystray.Icon(
        "koda",
        create_icon("gray"),
        "Koda: Loading...",
        build_menu(),
    )

    threading.Thread(target=run_setup, daemon=True).start()
    tray_icon.run()


def _handle_cli_args():
    """Handle one-shot CLI flags that exit without launching the tray app.

    --transcribe <file>          open the minimal transcribe window for <file>
    --install-context-menu       register the right-click "Transcribe with Koda" entry
    --uninstall-context-menu     remove the right-click entry

    Returns True if a flag was handled (caller should exit), False otherwise.
    """
    if len(sys.argv) < 2:
        return False
    flag = sys.argv[1]
    if flag == "--transcribe" and len(sys.argv) >= 3:
        import context_menu
        context_menu.transcribe(sys.argv[2])
        return True
    if flag == "--install-context-menu":
        import context_menu
        context_menu.install()
        return True
    if flag == "--uninstall-context-menu":
        import context_menu
        context_menu.uninstall()
        return True
    if flag == "--settings":
        _open_settings_standalone()
        return True
    return False


if __name__ == "__main__":
    multiprocessing.freeze_support()
    if _handle_cli_args():
        sys.exit(0)
    main()
