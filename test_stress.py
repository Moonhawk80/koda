"""
Stress Test Suite for Voice-to-Claude

Tests each component individually, then end-to-end.
Run with: python test_stress.py
"""

import sys
import time
import os
import numpy as np

PASS = "[PASS]"
FAIL = "[FAIL]"
WARN = "[WARN]"
results = []


def test(name, fn):
    try:
        result = fn()
        if result is True:
            print(f"  {PASS} {name}")
            results.append((name, True, None))
        elif isinstance(result, str):
            print(f"  {WARN} {name} — {result}")
            results.append((name, True, result))
        else:
            print(f"  {FAIL} {name} — returned {result}")
            results.append((name, False, str(result)))
    except Exception as e:
        print(f"  {FAIL} {name} — {e}")
        results.append((name, False, str(e)))


# ============================================================
# 1. DEPENDENCY TESTS
# ============================================================
print("\n=== 1. Dependencies ===")


def test_imports():
    import faster_whisper, sounddevice, keyboard, pyperclip, pyautogui, pystray, PIL
    return True


def test_numpy():
    arr = np.zeros(16000, dtype=np.float32)
    assert arr.shape == (16000,)
    return True


test("Import all packages", test_imports)
test("NumPy array operations", test_numpy)


# ============================================================
# 2. AUDIO DEVICE TESTS
# ============================================================
print("\n=== 2. Audio Devices ===")


def test_audio_devices():
    import sounddevice as sd
    devices = sd.query_devices()
    input_devices = [d for d in devices if d["max_input_channels"] > 0]
    if not input_devices:
        return "No input devices found"
    return True


def test_default_input():
    import sounddevice as sd
    idx = sd.default.device[0]
    dev = sd.query_devices(idx)
    name = dev["name"]
    channels = dev["max_input_channels"]
    if channels == 0:
        return f"Default device '{name}' has no input channels"
    print(f"         Default input: {name} ({channels}ch)")
    return True


def test_audio_capture():
    """Record 1 second of audio and verify we get data."""
    import sounddevice as sd
    duration = 1.0
    sample_rate = 16000
    print(f"         Recording {duration}s of audio...", end=" ", flush=True)
    audio = sd.rec(int(duration * sample_rate), samplerate=sample_rate, channels=1, dtype="float32")
    sd.wait()
    print("done.")
    if audio is None or len(audio) == 0:
        return "No audio data captured"
    peak = np.max(np.abs(audio))
    print(f"         Peak amplitude: {peak:.4f}")
    if peak < 0.001:
        return f"Audio captured but very quiet (peak={peak:.6f}) — check mic is active"
    return True


def test_audio_capture_callback():
    """Test the callback-based recording (same method as voice.py)."""
    import sounddevice as sd
    chunks = []

    def callback(indata, frames, time_info, status):
        chunks.append(indata.copy())

    stream = sd.InputStream(samplerate=16000, channels=1, dtype="float32", callback=callback)
    stream.start()
    time.sleep(1.0)
    stream.stop()
    stream.close()

    if not chunks:
        return "Callback received no audio chunks"
    audio = np.concatenate(chunks, axis=0).flatten()
    print(f"         Callback captured {len(audio)} samples ({len(audio)/16000:.1f}s)")
    return True


test("Audio devices available", test_audio_devices)
test("Default input device", test_default_input)
test("Audio capture (direct)", test_audio_capture)
test("Audio capture (callback)", test_audio_capture_callback)


# ============================================================
# 3. WHISPER MODEL TESTS
# ============================================================
print("\n=== 3. Whisper Model ===")


def test_model_load():
    from faster_whisper import WhisperModel
    print("         Loading 'base' model (int8, CPU)...", end=" ", flush=True)
    start = time.time()
    model = WhisperModel("base", device="cpu", compute_type="int8")
    elapsed = time.time() - start
    print(f"done in {elapsed:.1f}s")
    test_model_load.model = model
    return True


def test_transcribe_silence():
    """Whisper should handle silence gracefully."""
    model = test_model_load.model
    silence = np.zeros(16000 * 2, dtype=np.float32)  # 2s silence
    segments, info = model.transcribe(silence, beam_size=5, language="en")
    text = " ".join(seg.text for seg in segments).strip()
    print(f"         Silence transcription: '{text}'")
    return True  # Pass regardless — some models produce filler text for silence


def test_transcribe_tone():
    """Generate a tone and verify model doesn't crash on non-speech audio."""
    model = test_model_load.model
    t = np.linspace(0, 2, 16000 * 2, dtype=np.float32)
    tone = (0.3 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    segments, info = model.transcribe(tone, beam_size=5, language="en")
    text = " ".join(seg.text for seg in segments).strip()
    print(f"         Tone transcription: '{text}'")
    return True


def test_transcribe_speech():
    """Record real speech and transcribe it."""
    import sounddevice as sd
    model = test_model_load.model
    print('         Say something into your mic (3 seconds)...', end=" ", flush=True)
    audio = sd.rec(int(3 * 16000), samplerate=16000, channels=1, dtype="float32")
    sd.wait()
    audio = audio.flatten()
    print("transcribing...", end=" ", flush=True)

    start = time.time()
    segments, info = model.transcribe(audio, beam_size=5, language="en")
    text = " ".join(seg.text for seg in segments).strip()
    elapsed = time.time() - start

    print(f"done in {elapsed:.1f}s")
    print(f'         You said: "{text}"')
    if not text:
        return "No speech detected — try speaking louder or closer to mic"
    return True


def test_transcribe_speed():
    """Benchmark: transcribe 10s of audio, measure time."""
    model = test_model_load.model
    # Generate 10s of random noise (worst case for Whisper)
    audio = np.random.randn(16000 * 10).astype(np.float32) * 0.1
    print("         Benchmarking 10s of audio...", end=" ", flush=True)
    start = time.time()
    segments, info = model.transcribe(audio, beam_size=5, language="en")
    # Consume the generator
    for seg in segments:
        pass
    elapsed = time.time() - start
    ratio = 10.0 / elapsed
    print(f"done in {elapsed:.1f}s (speed: {ratio:.1f}x realtime)")
    if ratio < 1.0:
        return f"Transcription slower than realtime ({ratio:.1f}x) — consider 'tiny' model"
    return True


test("Model load", test_model_load)
test("Transcribe silence", test_transcribe_silence)
test("Transcribe tone (non-speech)", test_transcribe_tone)
test("Transcribe live speech (3s)", test_transcribe_speech)
test("Transcription speed benchmark", test_transcribe_speed)


# ============================================================
# 4. SYSTEM INTEGRATION TESTS
# ============================================================
print("\n=== 4. System Integration ===")


def test_clipboard():
    import pyperclip
    original = pyperclip.paste()
    pyperclip.copy("voice-to-claude-test-12345")
    result = pyperclip.paste()
    pyperclip.copy(original)  # restore
    if result != "voice-to-claude-test-12345":
        return f"Clipboard mismatch: got '{result}'"
    return True


def test_keyboard_hook():
    import keyboard
    triggered = []
    keyboard.on_press_key("f9", lambda e: triggered.append(True))
    # Simulate a press
    keyboard.press("f9")
    keyboard.release("f9")
    time.sleep(0.1)
    keyboard.unhook_all()
    if not triggered:
        return "Keyboard hook did not trigger — may need admin rights"
    return True


def test_tray_icon_create():
    import pystray
    from PIL import Image, ImageDraw
    img = Image.new("RGBA", (64, 64))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 60, 60], fill="green")
    icon = pystray.Icon("test", img, "Test")
    # Don't run the icon, just verify creation
    return True


test("Clipboard read/write", test_clipboard)
test("Keyboard hook (F9)", test_keyboard_hook)
test("System tray icon creation", test_tray_icon_create)


# ============================================================
# 5. END-TO-END SIMULATION
# ============================================================
print("\n=== 5. End-to-End Simulation ===")


def test_full_pipeline():
    """Simulate the full voice.py pipeline without pasting."""
    import sounddevice as sd
    import pyperclip
    model = test_model_load.model

    # Step 1: Record
    print("         Step 1: Recording 3s — SPEAK NOW...", end=" ", flush=True)
    chunks = []

    def callback(indata, frames, time_info, status):
        chunks.append(indata.copy())

    stream = sd.InputStream(samplerate=16000, channels=1, dtype="float32", callback=callback)
    stream.start()
    time.sleep(3.0)
    stream.stop()
    stream.close()
    print(f"got {len(chunks)} chunks")

    # Step 2: Transcribe
    print("         Step 2: Transcribing...", end=" ", flush=True)
    audio = np.concatenate(chunks, axis=0).flatten()
    start = time.time()
    segments, info = model.transcribe(audio, beam_size=5, language="en")
    text = " ".join(seg.text for seg in segments).strip()
    elapsed = time.time() - start
    print(f"done in {elapsed:.1f}s")

    # Step 3: Clipboard
    print(f"         Step 3: Copying to clipboard...", end=" ", flush=True)
    if text:
        pyperclip.copy(text)
        verify = pyperclip.paste()
        if verify == text:
            print("verified")
        else:
            return "Clipboard verification failed"
    else:
        print("(no speech detected, skipping clipboard)")

    print(f'         Result: "{text}"')
    return True


test("Full pipeline (record -> transcribe -> clipboard)", test_full_pipeline)


# ============================================================
# SUMMARY
# ============================================================
print("\n" + "=" * 50)
passed = sum(1 for _, ok, _ in results if ok)
failed = sum(1 for _, ok, _ in results if not ok)
warnings = sum(1 for _, ok, msg in results if ok and msg)
total = len(results)

print(f"Results: {passed}/{total} passed", end="")
if warnings:
    print(f", {warnings} warnings", end="")
if failed:
    print(f", {failed} FAILED", end="")
print()

if failed:
    print("\nFailed tests:")
    for name, ok, msg in results:
        if not ok:
            print(f"  - {name}: {msg}")
    print("\nFix the failures above before going live.")
    sys.exit(1)
else:
    print("\nAll tests passed! Voice-to-Claude is ready to go.")
    sys.exit(0)
