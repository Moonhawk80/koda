"""
Voice-to-Claude: Push-to-talk voice input for Claude Code.

System tray app with two modes:
  F9  = Dictation mode (raw transcription, light cleanup)
  F10 = Command mode (full cleanup: filler removal, code vocab, formatting)

Supports hold-to-talk and toggle mode (with VAD auto-stop).
Right-click the tray icon to access settings or quit.
"""

import sys
import os
import time
import threading
import winsound
import numpy as np
import sounddevice as sd
import keyboard
import pyperclip
import pyautogui
import pystray
from PIL import Image, ImageDraw

from config import load_config, save_config, open_config_file
from text_processing import process_text

# --- Version ---
VERSION = "1.1.0"

# --- Globals ---
recording = False
audio_chunks = []
model = None
tray_icon = None
stream = None
config = {}
vad_model = None
last_speech_time = 0
recording_mode = "dictation"  # "dictation" or "command"


# ============================================================
# ICON
# ============================================================

def create_icon(color="gray"):
    """Create a mic icon for the system tray."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 60, 60], fill=color)
    draw.rounded_rectangle([22, 10, 42, 38], radius=10, fill="white")
    draw.arc([16, 28, 48, 52], start=0, end=180, fill="white", width=3)
    draw.line([32, 52, 32, 58], fill="white", width=3)
    draw.line([24, 58, 40, 58], fill="white", width=3)
    return img


# ============================================================
# SOUND EFFECTS
# ============================================================

SOUNDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")


def _play_wav(filename):
    """Play a .wav file asynchronously."""
    filepath = os.path.join(SOUNDS_DIR, filename)
    if os.path.exists(filepath):
        winsound.PlaySound(filepath, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)


def play_start_sound():
    """Rising chime — recording started."""
    if config.get("sound_effects", True):
        _play_wav("start.wav")


def play_stop_sound():
    """Soft note — recording stopped, processing."""
    if config.get("sound_effects", True):
        _play_wav("stop.wav")


def play_success_sound():
    """Ascending chime — text pasted."""
    if config.get("sound_effects", True):
        _play_wav("success.wav")


# ============================================================
# TRAY
# ============================================================

def update_tray(color, tooltip):
    """Update tray icon color and hover text."""
    if tray_icon:
        tray_icon.icon = create_icon(color)
        tray_icon.title = tooltip


def notify(message, title="Voice-to-Claude"):
    """Show a Windows toast notification."""
    if config.get("notifications", True) and tray_icon:
        try:
            tray_icon.notify(message[:200], title)
        except Exception:
            pass


# ============================================================
# MODEL
# ============================================================

def load_whisper_model():
    """Load the faster-whisper model."""
    global model
    from faster_whisper import WhisperModel
    model_size = config.get("model_size", "base")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")


# ============================================================
# VAD (Voice Activity Detection)
# ============================================================

def init_vad():
    """Initialize Silero VAD for auto-stop detection."""
    global vad_model
    if not config.get("vad", {}).get("enabled", True):
        return
    try:
        from faster_whisper.vad import SileroVADModel
        vad_model = SileroVADModel()
    except Exception:
        # Fall back to energy-based VAD if Silero fails
        vad_model = None


def check_vad_silence(audio_chunk):
    """Check if an audio chunk contains speech. Returns True if speech detected."""
    if vad_model is not None:
        try:
            # Silero VAD expects 512-sample chunks at 16kHz
            chunk_size = 512
            if len(audio_chunk) >= chunk_size:
                segment = audio_chunk[:chunk_size].astype(np.float32)
                result = vad_model({"speech_prob": 0.5}, segment)
                if hasattr(result, 'get'):
                    return result.get("speech_prob", 0) > 0.5
        except Exception:
            pass

    # Fallback: energy-based detection
    rms = np.sqrt(np.mean(audio_chunk ** 2))
    return rms > 0.01


def vad_monitor_thread():
    """Monitor audio for silence and auto-stop recording in toggle mode."""
    global recording, last_speech_time

    silence_timeout = config.get("vad", {}).get("silence_timeout_ms", 1500) / 1000.0

    while recording:
        time.sleep(0.1)
        if not audio_chunks:
            continue

        # Check the most recent chunk
        latest = audio_chunks[-1].flatten()
        if check_vad_silence(latest):
            last_speech_time = time.time()
        elif time.time() - last_speech_time > silence_timeout:
            # Silence exceeded timeout — auto-stop
            stop_recording()
            return


# ============================================================
# RECORDING
# ============================================================

def audio_callback(indata, frames, time_info, status):
    """Sounddevice callback — collects audio chunks while recording."""
    if recording:
        audio_chunks.append(indata.copy())


def start_recording(mode="dictation"):
    """Begin recording audio from the microphone."""
    global recording, audio_chunks, last_speech_time, recording_mode
    if recording:
        return
    audio_chunks = []
    recording_mode = mode
    last_speech_time = time.time()
    recording = True

    play_start_sound()
    label = "Dictation" if mode == "dictation" else "Command"
    update_tray("#e74c3c", f"Voice-to-Claude: Recording ({label})...")

    # In toggle mode, start VAD monitor to auto-stop
    if config.get("hotkey_mode", "hold") == "toggle":
        threading.Thread(target=vad_monitor_thread, daemon=True).start()


def stop_recording():
    """Stop recording and process the audio."""
    global recording
    if not recording:
        return
    recording = False

    play_stop_sound()
    update_tray("#f39c12", "Voice-to-Claude: Transcribing...")

    if not audio_chunks:
        update_tray("#2ecc71", "Voice-to-Claude: Ready")
        return

    # Process in a thread to avoid blocking
    threading.Thread(target=_transcribe_and_paste, daemon=True).start()


def _transcribe_and_paste():
    """Transcribe audio, apply post-processing, and paste."""
    try:
        audio = np.concatenate(audio_chunks, axis=0).flatten()

        # Noise reduction (optional)
        if config.get("noise_reduction", False):
            try:
                import noisereduce as nr
                audio = nr.reduce_noise(y=audio, sr=16000, stationary=True)
            except Exception:
                pass

        # Transcribe with Whisper
        language = config.get("language", "en")
        transcribe_opts = {
            "beam_size": 5,
            "language": language,
            "vad_filter": config.get("vad", {}).get("enabled", True),
        }

        segments, info = model.transcribe(audio, **transcribe_opts)
        text = " ".join(seg.text for seg in segments).strip()

        if not text:
            update_tray("#2ecc71", "Voice-to-Claude: Ready")
            notify("No speech detected")
            return

        # Apply post-processing based on mode
        if recording_mode == "command":
            # Full processing pipeline
            processed = process_text(text, config)
        else:
            # Dictation: light cleanup only (fillers + capitalize)
            light_config = {
                "post_processing": {
                    "remove_filler_words": config.get("post_processing", {}).get("remove_filler_words", True),
                    "code_vocabulary": False,
                    "auto_capitalize": config.get("post_processing", {}).get("auto_capitalize", True),
                }
            }
            processed = process_text(text, light_config)

        if processed:
            pyperclip.copy(processed)
            time.sleep(0.15)
            pyautogui.hotkey("ctrl", "v")
            play_success_sound()
            notify(processed)

    except Exception as e:
        notify(f"Error: {e}")
    finally:
        update_tray("#2ecc71", "Voice-to-Claude: Ready")


# ============================================================
# HOTKEYS
# ============================================================

def _get_trigger_key(hotkey_str):
    """Get the last key in a combo for release detection. e.g. 'ctrl+space' -> 'space'."""
    return hotkey_str.split("+")[-1].strip()


def _register_hotkey(hotkey_str, on_press, on_release=None):
    """Register a hotkey that works for both single keys and combos."""
    parts = [p.strip() for p in hotkey_str.split("+")]
    trigger_key = parts[-1]
    modifiers = parts[:-1]

    if modifiers:
        # Combo key: use add_hotkey for press, on_release_key for the trigger key
        keyboard.add_hotkey(hotkey_str, on_press, suppress=False)
        if on_release:
            keyboard.on_release_key(trigger_key, lambda e: on_release())
    else:
        # Single key
        keyboard.on_press_key(trigger_key, lambda e: on_press())
        if on_release:
            keyboard.on_release_key(trigger_key, lambda e: on_release())


def setup_hotkeys():
    """Register global hotkeys based on config."""
    hotkey_dict = config.get("hotkey_dictation", "ctrl+space")
    hotkey_cmd = config.get("hotkey_command", "ctrl+shift+.")
    mode = config.get("hotkey_mode", "hold")

    if mode == "hold":
        _register_hotkey(
            hotkey_dict,
            on_press=lambda: start_recording("dictation"),
            on_release=lambda: threading.Thread(target=stop_recording, daemon=True).start(),
        )
        _register_hotkey(
            hotkey_cmd,
            on_press=lambda: start_recording("command"),
            on_release=lambda: threading.Thread(target=stop_recording, daemon=True).start(),
        )
    else:
        def toggle_dictation():
            if recording:
                threading.Thread(target=stop_recording, daemon=True).start()
            else:
                start_recording("dictation")

        def toggle_command():
            if recording:
                threading.Thread(target=stop_recording, daemon=True).start()
            else:
                start_recording("command")

        _register_hotkey(hotkey_dict, on_press=toggle_dictation)
        _register_hotkey(hotkey_cmd, on_press=toggle_command)


# ============================================================
# TRAY MENU
# ============================================================

def build_menu():
    """Build the system tray right-click menu."""
    hotkey_dict = config.get("hotkey_dictation", "F9").upper()
    hotkey_cmd = config.get("hotkey_command", "F10").upper()
    mode = config.get("hotkey_mode", "hold")
    mode_label = "Hold-to-talk" if mode == "hold" else "Toggle (auto-stop)"

    return pystray.Menu(
        pystray.MenuItem(f"Voice-to-Claude v{VERSION}", None, enabled=False),
        pystray.MenuItem(f"{hotkey_dict} = Dictation  |  {hotkey_cmd} = Command", None, enabled=False),
        pystray.MenuItem(f"Mode: {mode_label}", None, enabled=False),
        pystray.Menu.SEPARATOR,
        # --- Toggles ---
        pystray.MenuItem(
            "Sound effects",
            toggle_setting("sound_effects"),
            checked=lambda item: config.get("sound_effects", True),
        ),
        pystray.MenuItem(
            "Notifications",
            toggle_setting("notifications"),
            checked=lambda item: config.get("notifications", True),
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
            "Noise reduction",
            toggle_setting("noise_reduction"),
            checked=lambda item: config.get("noise_reduction", False),
        ),
        pystray.Menu.SEPARATOR,
        # --- Mode switch ---
        pystray.MenuItem(
            "Switch to Toggle mode" if mode == "hold" else "Switch to Hold mode",
            switch_mode,
        ),
        pystray.MenuItem("Open settings file", lambda icon, item: open_config_file()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", on_quit),
    )


def toggle_setting(key):
    """Create a toggle handler for a top-level config boolean."""
    def handler(icon, item):
        config[key] = not config.get(key, True)
        save_config(config)
        icon.menu = build_menu()
    return handler


def toggle_post_processing(key):
    """Create a toggle handler for a post_processing config boolean."""
    def handler(icon, item):
        pp = config.setdefault("post_processing", {})
        pp[key] = not pp.get(key, False)
        save_config(config)
        icon.menu = build_menu()
    return handler


def switch_mode(icon, item):
    """Switch between hold and toggle hotkey mode."""
    keyboard.unhook_all()
    current = config.get("hotkey_mode", "hold")
    config["hotkey_mode"] = "toggle" if current == "hold" else "hold"
    save_config(config)
    setup_hotkeys()
    icon.menu = build_menu()
    new_mode = "Toggle (auto-stop)" if config["hotkey_mode"] == "toggle" else "Hold-to-talk"
    notify(f"Switched to {new_mode}")


# ============================================================
# LIFECYCLE
# ============================================================

def on_quit(icon, item):
    """Clean up and exit."""
    global stream
    keyboard.unhook_all()
    if stream:
        stream.stop()
        stream.close()
    icon.stop()


def run_setup():
    """Background thread: load model, start audio, register hotkeys."""
    global stream

    # Load Whisper model
    update_tray("gray", "Voice-to-Claude: Loading model...")
    load_whisper_model()

    # Initialize VAD
    init_vad()

    # Start audio stream
    mic_device = config.get("mic_device")
    stream = sd.InputStream(
        samplerate=16000,
        channels=1,
        dtype="float32",
        device=mic_device,
        callback=audio_callback,
    )
    stream.start()

    # Register hotkeys
    setup_hotkeys()

    update_tray("#2ecc71", "Voice-to-Claude: Ready")
    notify("Voice-to-Claude is ready!")


def main():
    global tray_icon, config

    # Load config
    config = load_config()

    # Create tray icon
    tray_icon = pystray.Icon(
        "voice-to-claude",
        create_icon("gray"),
        "Voice-to-Claude: Loading...",
        build_menu(),
    )

    # Run setup in background so tray appears immediately
    threading.Thread(target=run_setup, daemon=True).start()

    # Blocks — runs the tray event loop
    tray_icon.run()


if __name__ == "__main__":
    main()
