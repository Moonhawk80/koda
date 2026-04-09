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
    """Play a .wav file through the system default output device."""
    filepath = os.path.join(SOUNDS_DIR, filename)
    if not os.path.exists(filepath):
        return

    def _play():
        try:
            import wave
            with wave.open(filepath, 'r') as wf:
                rate = wf.getframerate()
                frames = wf.readframes(wf.getnframes())
                audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32767
            sd.play(audio, samplerate=rate)
        except Exception:
            # Fallback to winsound
            winsound.PlaySound(filepath, winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)

    threading.Thread(target=_play, daemon=True).start()


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

def load_whisper_model():
    global model
    from faster_whisper import WhisperModel
    model_size = config.get("model_size", "base")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")


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
            segments, _ = model.transcribe(
                audio, beam_size=1, language=config.get("language", "en"),
                vad_filter=False,
            )
            text = " ".join(seg.text for seg in segments).strip()
            if text:
                streaming_text = text
                # Show partial text in tray tooltip
                preview = text[:80] + "..." if len(text) > 80 else text
                update_tray("#e74c3c", f"Koda: {preview}")
        except Exception:
            pass


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
    label = "Dictation" if mode == "dictation" else "Command"
    update_tray("#e74c3c", f"Koda: Recording ({label})...")

    # Start streaming transcription in background
    if config.get("streaming", True):
        threading.Thread(target=_streaming_thread, daemon=True).start()

    # Use VAD auto-stop in toggle mode OR when triggered by wake word
    if force_vad or config.get("hotkey_mode", "hold") == "toggle":
        threading.Thread(target=vad_monitor_thread, args=(vad_timeout_ms,), daemon=True).start()


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

        # Transcribe — vad_filter OFF for short phrases, beam_size 3 for speed
        language = config.get("language", "en")
        segments, info = model.transcribe(
            audio,
            beam_size=3,
            language=language,
            vad_filter=False,
        )
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
# READ-BACK (Text-to-Speech)
# ============================================================

tts_engine = None
tts_speaking = False


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
            rate = config.get("tts", {}).get("rate", 160)
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

    # Read-back hotkeys
    hotkey_read = config.get("hotkey_readback", "ctrl+shift+r")
    hotkey_read_sel = config.get("hotkey_readback_selected", "ctrl+shift+t")
    _register_hotkey(hotkey_read, on_press=lambda: threading.Thread(
        target=read_back, daemon=True).start())
    _register_hotkey(hotkey_read_sel, on_press=lambda: threading.Thread(
        target=read_selected, daemon=True).start())


# ============================================================
# TRAY MENU
# ============================================================

def build_menu():
    hotkey_dict = config.get("hotkey_dictation", "ctrl+space").upper()
    hotkey_cmd = config.get("hotkey_command", "ctrl+shift+.").upper()
    hotkey_corr = config.get("hotkey_correction", "ctrl+shift+z").upper()
    hotkey_read = config.get("hotkey_readback", "ctrl+shift+r").upper()
    hotkey_read_sel = config.get("hotkey_readback_selected", "ctrl+shift+t").upper()
    mode = config.get("hotkey_mode", "hold")
    mode_label = "Hold-to-talk" if mode == "hold" else "Toggle (auto-stop)"
    wake_enabled = config.get("wake_word", {}).get("enabled", False)

    return pystray.Menu(
        pystray.MenuItem(f"Koda v{VERSION}", None, enabled=False),
        pystray.MenuItem(f"{hotkey_dict} = Dictation  |  {hotkey_cmd} = Command", None, enabled=False),
        pystray.MenuItem(f"{hotkey_corr} = Redo  |  {hotkey_read} = Read back", None, enabled=False),
        pystray.MenuItem(f"{hotkey_read_sel} = Read selected  |  Mode: {mode_label}", None, enabled=False),
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
        pystray.MenuItem(
            "Read-back voice",
            pystray.Menu(*_build_voice_menu_items()),
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
    init_tts()

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
