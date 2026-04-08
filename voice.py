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
VERSION = "2.0.0"

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
    if config.get("sound_effects", True):
        _play_wav("start.wav")


# ============================================================
# TRAY
# ============================================================

def update_tray(color, tooltip):
    if tray_icon:
        tray_icon.icon = create_icon(color)
        tray_icon.title = tooltip


def notify(message, title="Koda"):
    if config.get("notifications", False) and tray_icon:
        try:
            tray_icon.notify(message[:200], title)
        except Exception:
            pass


# ============================================================
# MODEL
# ============================================================

wake_model = None  # Separate tiny model for wake word detection


def load_whisper_model():
    global model, wake_model
    from faster_whisper import WhisperModel
    model_size = config.get("model_size", "base")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    # Load tiny model for fast wake word detection
    if config.get("wake_word", {}).get("enabled", False):
        wake_model = WhisperModel("tiny", device="cpu", compute_type="int8")


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


def vad_monitor_thread():
    global recording, last_speech_time
    silence_timeout = config.get("vad", {}).get("silence_timeout_ms", 1500) / 1000.0
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
# WAKE WORD ("Hey Koda")
# ============================================================

def start_wake_word_listener():
    """Start background thread that listens for 'Hey Koda'."""
    global wake_word_active, wake_word_thread
    if not config.get("wake_word", {}).get("enabled", False):
        return
    wake_word_active = True
    wake_word_thread = threading.Thread(target=_wake_word_loop, daemon=True)
    wake_word_thread.start()


def stop_wake_word_listener():
    global wake_word_active
    wake_word_active = False


def _wake_word_loop():
    """Continuously listen for the wake word using the shared audio buffer."""
    global wake_word_active
    wake_phrase = config.get("wake_word", {}).get("phrase", "hey koda").lower()
    energy_threshold = 0.008

    while wake_word_active:
        if recording:
            time.sleep(0.5)
            continue

        # Wait for audio to accumulate
        time.sleep(1.5)

        if not wake_word_active or recording:
            continue

        # Grab audio from the shared buffer
        with wake_buffer_lock:
            if not wake_buffer:
                continue
            audio = np.concatenate(wake_buffer, axis=0).flatten()
            wake_buffer.clear()

        # Skip if too quiet
        rms = np.sqrt(np.mean(audio ** 2))
        if rms < energy_threshold:
            continue

        # Quick transcription with tiny model + prompt hint
        try:
            wm = wake_model if wake_model else model
            segments, _ = wm.transcribe(
                audio, beam_size=5, language=config.get("language", "en"),
                vad_filter=False, initial_prompt="Hey Koda",
            )
            text = " ".join(seg.text for seg in segments).strip().lower()

            if _matches_wake_phrase(text, wake_phrase):
                play_wakeword_sound()
                update_tray("#3498db", "Koda: Listening...")
                time.sleep(0.5)
                # Clear buffer before recording so old audio doesn't re-trigger
                with wake_buffer_lock:
                    wake_buffer.clear()
                start_recording("dictation", force_vad=True)
                # Wait for recording to finish
                while recording:
                    time.sleep(0.1)
                # Cooldown after recording to prevent re-trigger
                with wake_buffer_lock:
                    wake_buffer.clear()
                time.sleep(2)
        except Exception:
            pass


def _matches_wake_phrase(text, phrase):
    """Fuzzy match for wake word. Handles common Whisper mishearings."""
    text = text.lower().strip().rstrip(".,!?")
    phrase = phrase.lower().strip()

    # Direct match
    if phrase in text:
        return True

    # Common Whisper mishearings of "hey koda"
    variants = [
        "hey koda", "hey coda", "hey coder", "hey kota",
        "a koda", "a coda", "hey koba", "hey coba",
        "hey code a", "hey ko da",
    ]
    for variant in variants:
        if variant in text:
            return True

    return False


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


def start_recording(mode="dictation", force_vad=False):
    global recording, audio_chunks, last_speech_time, recording_mode
    if recording:
        return
    audio_chunks = []
    recording_mode = mode
    last_speech_time = time.time()
    recording = True

    play_start_sound()
    label = "Dictation" if mode == "dictation" else "Command"
    update_tray("#e74c3c", f"Koda: Recording ({label})...")

    # Use VAD auto-stop in toggle mode OR when triggered by wake word
    if force_vad or config.get("hotkey_mode", "hold") == "toggle":
        threading.Thread(target=vad_monitor_thread, daemon=True).start()


def stop_recording():
    global recording
    if not recording:
        return
    recording = False
    play_stop_sound()
    update_tray("#f39c12", "Koda: Transcribing...")

    if not audio_chunks:
        update_tray("#2ecc71", "Koda: Ready")
        return

    threading.Thread(target=_transcribe_and_paste, daemon=True).start()


def _transcribe_and_paste():
    global last_transcription
    try:
        audio = np.concatenate(audio_chunks, axis=0).flatten()

        # Noise reduction
        if config.get("noise_reduction", False):
            try:
                import noisereduce as nr
                audio = nr.reduce_noise(y=audio, sr=16000, stationary=True)
            except Exception:
                pass

        # Transcribe
        language = config.get("language", "en")
        transcribe_opts = {
            "beam_size": 5,
            "language": language,
            "vad_filter": config.get("vad", {}).get("enabled", True),
        }
        segments, info = model.transcribe(audio, **transcribe_opts)
        text = " ".join(seg.text for seg in segments).strip()

        if not text:
            update_tray("#2ecc71", "Koda: Ready")
            return

        # Post-processing
        if recording_mode == "command":
            processed = process_text(text, config)
            # LLM polish for command mode
            processed = polish_with_llm(processed)
        else:
            light_config = {
                "post_processing": {
                    "remove_filler_words": config.get("post_processing", {}).get("remove_filler_words", True),
                    "code_vocabulary": False,
                    "auto_capitalize": config.get("post_processing", {}).get("auto_capitalize", True),
                }
            }
            processed = process_text(text, light_config)

        if processed:
            last_transcription = processed
            pyperclip.copy(processed)
            time.sleep(0.15)
            pyautogui.hotkey("ctrl", "v")
            play_success_sound()

    except Exception as e:
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
# HOTKEYS
# ============================================================

def _register_hotkey(hotkey_str, on_press, on_release=None):
    parts = [p.strip() for p in hotkey_str.split("+")]
    trigger_key = parts[-1]
    modifiers = parts[:-1]

    if modifiers:
        keyboard.add_hotkey(hotkey_str, on_press, suppress=False)
        if on_release:
            keyboard.on_release_key(trigger_key, lambda e: on_release())
    else:
        keyboard.on_press_key(trigger_key, lambda e: on_press())
        if on_release:
            keyboard.on_release_key(trigger_key, lambda e: on_release())


def setup_hotkeys():
    hotkey_dict = config.get("hotkey_dictation", "ctrl+space")
    hotkey_cmd = config.get("hotkey_command", "ctrl+shift+.")
    hotkey_correct = config.get("hotkey_correction", "ctrl+shift+z")
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

    # Correction hotkey (always available)
    _register_hotkey(hotkey_correct, on_press=lambda: threading.Thread(
        target=undo_and_rerecord, daemon=True).start())


# ============================================================
# TRAY MENU
# ============================================================

def build_menu():
    hotkey_dict = config.get("hotkey_dictation", "ctrl+space").upper()
    hotkey_cmd = config.get("hotkey_command", "ctrl+shift+.").upper()
    hotkey_corr = config.get("hotkey_correction", "ctrl+shift+z").upper()
    mode = config.get("hotkey_mode", "hold")
    mode_label = "Hold-to-talk" if mode == "hold" else "Toggle (auto-stop)"
    wake_enabled = config.get("wake_word", {}).get("enabled", False)

    return pystray.Menu(
        pystray.MenuItem(f"Koda v{VERSION}", None, enabled=False),
        pystray.MenuItem(f"{hotkey_dict} = Dictation  |  {hotkey_cmd} = Command", None, enabled=False),
        pystray.MenuItem(f"{hotkey_corr} = Redo  |  Mode: {mode_label}", None, enabled=False),
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
            f'Wake word ("Hey Koda")',
            toggle_wake_word,
            checked=lambda item: config.get("wake_word", {}).get("enabled", False),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            "Switch to Toggle mode" if mode == "hold" else "Switch to Hold mode",
            switch_mode,
        ),
        pystray.MenuItem("Open settings file", lambda icon, item: open_config_file()),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", on_quit),
    )


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


def switch_mode(icon, item):
    keyboard.unhook_all()
    current = config.get("hotkey_mode", "hold")
    config["hotkey_mode"] = "toggle" if current == "hold" else "hold"
    save_config(config)
    setup_hotkeys()
    icon.menu = build_menu()


# ============================================================
# LIFECYCLE
# ============================================================

def on_quit(icon, item):
    global stream, wake_word_active
    wake_word_active = False
    keyboard.unhook_all()
    if stream:
        stream.stop()
        stream.close()
    icon.stop()


def run_setup():
    global stream

    update_tray("gray", "Koda: Loading model...")
    load_whisper_model()
    init_vad()

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

    update_tray("#2ecc71", "Koda: Ready")


def main():
    global tray_icon, config

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
    main()
