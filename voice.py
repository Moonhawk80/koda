"""
Voice-to-Claude: Push-to-talk voice input for Claude Code.

Runs in the system tray. Hold F9 to record, release to transcribe and paste.
Right-click the tray icon to quit.
"""

import sys
import time
import threading
import numpy as np
import sounddevice as sd
import keyboard
import pyperclip
import pyautogui
import pystray
from PIL import Image, ImageDraw

# --- Config ---
MODEL_SIZE = "base"  # Options: tiny, base, small, medium, large-v3
SAMPLE_RATE = 16000
HOTKEY_RECORD = "f9"

# --- Globals ---
recording = False
audio_chunks = []
model = None
tray_icon = None
stream = None


def create_icon(color="gray"):
    """Create a simple mic icon for the tray."""
    img = Image.new("RGBA", (64, 64))
    draw = ImageDraw.Draw(img)
    # Background circle
    draw.ellipse([4, 4, 60, 60], fill=color)
    # Mic shape (white)
    draw.rounded_rectangle([22, 10, 42, 38], radius=10, fill="white")
    draw.arc([16, 28, 48, 52], start=0, end=180, fill="white", width=3)
    draw.line([32, 52, 32, 58], fill="white", width=3)
    draw.line([24, 58, 40, 58], fill="white", width=3)
    return img


def load_model():
    global model
    from faster_whisper import WhisperModel
    model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")


def audio_callback(indata, frames, time_info, status):
    if recording:
        audio_chunks.append(indata.copy())


def update_tray(color, tooltip):
    if tray_icon:
        tray_icon.icon = create_icon(color)
        tray_icon.title = tooltip


def start_recording():
    global recording, audio_chunks
    if recording:
        return
    audio_chunks = []
    recording = True
    update_tray("#e74c3c", "Voice-to-Claude: Recording...")


def stop_recording():
    global recording
    if not recording:
        return
    recording = False
    update_tray("#f39c12", "Voice-to-Claude: Transcribing...")

    if not audio_chunks:
        update_tray("#2ecc71", "Voice-to-Claude: Ready (F9)")
        return

    audio = np.concatenate(audio_chunks, axis=0).flatten()
    segments, info = model.transcribe(audio, beam_size=5, language="en")
    text = " ".join(seg.text for seg in segments).strip()

    if text:
        pyperclip.copy(text)
        time.sleep(0.15)
        pyautogui.hotkey("ctrl", "v")

    update_tray("#2ecc71", "Voice-to-Claude: Ready (F9)")


def on_quit(icon, item):
    """Clean up and exit."""
    global stream
    keyboard.unhook_all()
    if stream:
        stream.stop()
        stream.close()
    icon.stop()


def setup_hotkeys():
    keyboard.on_press_key(
        HOTKEY_RECORD,
        lambda e: start_recording(),
    )
    keyboard.on_release_key(
        HOTKEY_RECORD,
        lambda e: threading.Thread(target=stop_recording, daemon=True).start(),
    )


def run_tray():
    global tray_icon, stream

    # Load model before showing "ready"
    update_tray("gray", "Voice-to-Claude: Loading model...")
    load_model()

    # Start audio stream
    stream = sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype="float32",
        callback=audio_callback,
    )
    stream.start()

    # Register hotkeys
    setup_hotkeys()

    update_tray("#2ecc71", "Voice-to-Claude: Ready (F9)")


def main():
    global tray_icon

    menu = pystray.Menu(
        pystray.MenuItem("Voice-to-Claude", None, enabled=False),
        pystray.MenuItem("Hold F9 to talk", None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", on_quit),
    )

    tray_icon = pystray.Icon(
        "voice-to-claude",
        create_icon("gray"),
        "Voice-to-Claude: Loading...",
        menu,
    )

    # Run setup in background thread so tray appears immediately
    threading.Thread(target=run_tray, daemon=True).start()

    # This blocks — runs the tray icon event loop
    tray_icon.run()


if __name__ == "__main__":
    main()
