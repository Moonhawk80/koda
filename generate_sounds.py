"""Generate pleasant sound effect .wav files for Voice-to-Claude."""

import wave
import struct
import math
import os

SAMPLE_RATE = 44100
SOUNDS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sounds")


def generate_tone(freq, duration, volume=0.5, fade_ms=20):
    """Generate a sine wave with smooth fade in/out."""
    n_samples = int(SAMPLE_RATE * duration)
    fade_samples = int(SAMPLE_RATE * fade_ms / 1000)
    samples = []
    for i in range(n_samples):
        t = i / SAMPLE_RATE
        val = volume * math.sin(2 * math.pi * freq * t)
        # Fade in
        if i < fade_samples:
            val *= i / fade_samples
        # Fade out
        if i > n_samples - fade_samples:
            val *= (n_samples - i) / fade_samples
        samples.append(val)
    return samples


def mix(samples_list):
    """Mix multiple sample arrays together."""
    max_len = max(len(s) for s in samples_list)
    result = [0.0] * max_len
    for samples in samples_list:
        for i, val in enumerate(samples):
            result[i] += val
    # Normalize
    peak = max(abs(v) for v in result) or 1
    return [v / peak * 0.7 for v in result]


def save_wav(filename, samples):
    """Save samples as a 16-bit mono WAV file."""
    os.makedirs(SOUNDS_DIR, exist_ok=True)
    filepath = os.path.join(SOUNDS_DIR, filename)
    with wave.open(filepath, "w") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SAMPLE_RATE)
        for s in samples:
            f.writeframes(struct.pack("<h", int(s * 32767)))
    print(f"  Created {filepath}")


def make_start_sound():
    """Soft rising two-note chime — 'listening'."""
    note1 = generate_tone(523, 0.08, 0.4)   # C5
    gap = [0.0] * int(SAMPLE_RATE * 0.02)
    note2 = generate_tone(659, 0.12, 0.5)   # E5
    samples = note1 + gap + note2
    save_wav("start.wav", samples)


def make_stop_sound():
    """Soft single low note — 'processing'."""
    note = generate_tone(440, 0.10, 0.35)   # A4
    save_wav("stop.wav", note)


def make_success_sound():
    """Pleasant ascending three-note chime — 'done'."""
    note1 = generate_tone(523, 0.07, 0.3)   # C5
    gap = [0.0] * int(SAMPLE_RATE * 0.015)
    note2 = generate_tone(659, 0.07, 0.35)  # E5
    note3 = generate_tone(784, 0.12, 0.4)   # G5
    samples = note1 + gap + note2 + gap + note3
    save_wav("success.wav", samples)


def make_error_sound():
    """Two descending notes — 'error'."""
    note1 = generate_tone(440, 0.10, 0.35)  # A4
    gap = [0.0] * int(SAMPLE_RATE * 0.02)
    note2 = generate_tone(330, 0.15, 0.3)   # E4
    samples = note1 + gap + note2
    save_wav("error.wav", samples)


if __name__ == "__main__":
    print("Generating sound effects...")
    make_start_sound()
    make_stop_sound()
    make_success_sound()
    make_error_sound()
    print("Done!")
