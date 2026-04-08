"""
Voice-to-Claude Setup Wizard
Interactive configuration for first-time setup or reconfiguration.
"""

import json
import os
import sys
import time
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def banner():
    print()
    print("  ╔══════════════════════════════════════════╗")
    print("  ║        Voice-to-Claude Setup Wizard      ║")
    print("  ╚══════════════════════════════════════════╝")
    print()


def ask_choice(prompt, options, default=0):
    """Ask the user to pick from a numbered list. Returns the selected value."""
    print(f"  {prompt}\n")
    for i, (label, value) in enumerate(options):
        marker = " (recommended)" if i == default else ""
        print(f"    [{i + 1}] {label}{marker}")
    print()
    while True:
        raw = input(f"  Enter choice [1-{len(options)}] (default: {default + 1}): ").strip()
        if raw == "":
            return options[default][1]
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return options[idx][1]
        except ValueError:
            pass
        print(f"  Please enter a number between 1 and {len(options)}.")


def ask_yes_no(prompt, default=True):
    """Ask a yes/no question."""
    hint = "Y/n" if default else "y/N"
    raw = input(f"  {prompt} [{hint}]: ").strip().lower()
    if raw == "":
        return default
    return raw in ("y", "yes")


# ============================================================
# STEP 1: MICROPHONE
# ============================================================

def setup_microphone():
    clear()
    banner()
    print("  STEP 1 of 6: MICROPHONE\n")
    print("  ─────────────────────────────────────────\n")

    import sounddevice as sd
    devices = sd.query_devices()
    input_devices = [(i, d) for i, d in enumerate(devices) if d["max_input_channels"] > 0]

    if not input_devices:
        print("  [!] No microphones detected. Check your audio settings.")
        print("      Proceeding with system default.\n")
        input("  Press Enter to continue...")
        return None

    default_idx = sd.default.device[0]

    print("  Available microphones:\n")
    option_list = []
    default_choice = 0
    for pos, (idx, dev) in enumerate(input_devices):
        tag = " << DEFAULT" if idx == default_idx else ""
        name = dev["name"]
        print(f"    [{pos + 1}] {name}{tag}")
        option_list.append((name, idx))
        if idx == default_idx:
            default_choice = pos

    print()
    while True:
        raw = input(f"  Pick your microphone [1-{len(option_list)}] (default: {default_choice + 1}): ").strip()
        if raw == "":
            chosen_idx = option_list[default_choice][1]
            break
        try:
            pos = int(raw) - 1
            if 0 <= pos < len(option_list):
                chosen_idx = option_list[pos][1]
                break
        except ValueError:
            pass
        print(f"  Please enter a number between 1 and {len(option_list)}.")

    chosen_name = sd.query_devices(chosen_idx)["name"]
    print(f"\n  Selected: {chosen_name}\n")

    # Mic test
    if ask_yes_no("Test your microphone now?", default=True):
        print("\n  Recording 3 seconds — say something into your mic...\n")
        audio = sd.rec(int(3 * 16000), samplerate=16000, channels=1, dtype="float32", device=chosen_idx)
        sd.wait()
        peak = np.max(np.abs(audio))
        bar_len = int(min(peak * 100, 30))
        bar = "█" * bar_len + "░" * (30 - bar_len)

        print(f"  Volume: [{bar}] {peak:.3f}\n")
        if peak < 0.005:
            print("  [!] Very quiet — your mic might be muted or too far away.")
            print("      Check Windows Sound Settings and try again.\n")
        elif peak < 0.02:
            print("  [~] A bit quiet — try speaking louder or moving closer.\n")
        else:
            print("  [OK] Sounds good!\n")

        # Playback option
        if ask_yes_no("Play it back to hear yourself?", default=False):
            print("  Playing back...")
            sd.play(audio, samplerate=16000)
            sd.wait()
            print()

    input("  Press Enter to continue...")
    return chosen_idx if chosen_idx != default_idx else None


# ============================================================
# STEP 2: HOTKEYS
# ============================================================

HOTKEY_OPTIONS = [
    ("Ctrl + Space", "ctrl+space"),
    ("Ctrl + Period (.)", "ctrl+."),
    ("Ctrl + Semicolon (;)", "ctrl+;"),
    ("Ctrl + Shift + Space", "ctrl+shift+space"),
    ("Alt + Space", "alt+space"),
    ("F9", "f9"),
    ("F8", "f8"),
    ("Scroll Lock", "scroll lock"),
]

COMMAND_HOTKEY_OPTIONS = [
    ("Ctrl + Shift + Period (.)", "ctrl+shift+."),
    ("Ctrl + Shift + Semicolon (;)", "ctrl+shift+;"),
    ("Ctrl + Alt + Space", "ctrl+alt+space"),
    ("Alt + Period (.)", "alt+."),
    ("F10", "f10"),
    ("F7", "f7"),
]


def setup_hotkeys():
    clear()
    banner()
    print("  STEP 2 of 6: HOTKEYS\n")
    print("  ─────────────────────────────────────────\n")
    print("  Voice-to-Claude has two modes:\n")
    print("    Dictation — pastes what you say (light cleanup)")
    print("    Command   — cleans up speech for coding (removes fillers, etc.)\n")
    print("  Each mode needs its own hotkey.\n")

    print("  ── Dictation hotkey (main one you'll use) ──\n")
    dictation = ask_choice(
        "Pick your dictation hotkey:",
        HOTKEY_OPTIONS,
        default=0,  # Ctrl+Space
    )

    print(f"\n  Dictation: {dictation}\n")

    print("  ── Command hotkey (for coding tasks) ──\n")
    command = ask_choice(
        "Pick your command hotkey:",
        COMMAND_HOTKEY_OPTIONS,
        default=0,  # Ctrl+Shift+Period
    )

    print(f"\n  Command: {command}\n")
    input("  Press Enter to continue...")
    return dictation, command


# ============================================================
# STEP 3: HOTKEY MODE
# ============================================================

def setup_mode():
    clear()
    banner()
    print("  STEP 3 of 6: RECORDING MODE\n")
    print("  ─────────────────────────────────────────\n")

    mode = ask_choice(
        "How do you want recording to work?",
        [
            ("Hold-to-talk — hold the key while speaking, release to stop", "hold"),
            ("Toggle — press once to start, auto-stops when you stop talking", "toggle"),
        ],
        default=0,
    )

    print()
    input("  Press Enter to continue...")
    return mode


# ============================================================
# STEP 4: WHISPER MODEL
# ============================================================

def setup_model():
    clear()
    banner()
    print("  STEP 4 of 6: SPEECH MODEL\n")
    print("  ─────────────────────────────────────────\n")
    print("  Larger models are more accurate but slower.\n")

    model = ask_choice(
        "Pick a model size:",
        [
            ("Tiny    (~75MB)  — Fastest, less accurate", "tiny"),
            ("Base    (~150MB) — Good balance of speed and accuracy", "base"),
            ("Small   (~500MB) — Better accuracy, moderate speed", "small"),
            ("Medium  (~1.5GB) — High accuracy, slower", "medium"),
            ("Large   (~3GB)   — Best accuracy, slowest (needs fast CPU)", "large-v3"),
        ],
        default=1,  # base
    )

    print()
    input("  Press Enter to continue...")
    return model


# ============================================================
# STEP 5: LANGUAGE
# ============================================================

def setup_language():
    clear()
    banner()
    print("  STEP 5 of 6: LANGUAGE\n")
    print("  ─────────────────────────────────────────\n")

    lang = ask_choice(
        "What language will you be speaking?",
        [
            ("English", "en"),
            ("Spanish", "es"),
            ("French", "fr"),
            ("German", "de"),
            ("Portuguese", "pt"),
            ("Chinese", "zh"),
            ("Japanese", "ja"),
            ("Korean", "ko"),
            ("Other (set manually in config.json)", "en"),
        ],
        default=0,
    )

    print()
    input("  Press Enter to continue...")
    return lang


# ============================================================
# STEP 6: PREFERENCES
# ============================================================

def setup_preferences():
    clear()
    banner()
    print("  STEP 6 of 6: PREFERENCES\n")
    print("  ─────────────────────────────────────────\n")

    sound = ask_yes_no("Enable sound effects? (beeps when recording starts/stops)", default=True)
    fillers = ask_yes_no('Remove filler words? ("um", "uh", "you know")', default=True)
    noise = ask_yes_no("Enable noise reduction? (slower, useful in noisy offices)", default=False)
    auto_start = ask_yes_no("Start Voice-to-Claude when Windows starts?", default=False)
    print()
    input("  Press Enter to continue...")
    return sound, fillers, noise, auto_start


# ============================================================
# SUMMARY & SAVE
# ============================================================

def show_summary_and_save(config):
    clear()
    banner()
    print("  SETUP COMPLETE!\n")
    print("  ─────────────────────────────────────────\n")
    print("  Your settings:\n")
    print(f"    Microphone:       {'System default' if config['mic_device'] is None else 'Device #' + str(config['mic_device'])}")
    print(f"    Dictation hotkey: {config['hotkey_dictation']}")
    print(f"    Command hotkey:   {config['hotkey_command']}")
    print(f"    Recording mode:   {config['hotkey_mode']}")
    print(f"    Speech model:     {config['model_size']}")
    print(f"    Language:         {config['language']}")
    print(f"    Sound effects:    {'On' if config['sound_effects'] else 'Off'}")
    print(f"    Filler removal:   {'On' if config['post_processing']['remove_filler_words'] else 'Off'}")
    print(f"    Noise reduction:  {'On' if config['noise_reduction'] else 'Off'}")
    print()

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print(f"  Settings saved to: {CONFIG_PATH}\n")

    return config.get("_auto_start", False)


# ============================================================
# MAIN
# ============================================================

def main():
    clear()
    banner()
    print("  Welcome! This wizard will help you set up Voice-to-Claude.\n")
    print("  You'll pick your microphone, hotkeys, and preferences.")
    print("  It takes about 1 minute.\n")
    input("  Press Enter to begin...")

    # Run each step
    mic_device = setup_microphone()
    hotkey_dict, hotkey_cmd = setup_hotkeys()
    mode = setup_mode()
    model_size = setup_model()
    language = setup_language()
    sound, fillers, noise, auto_start = setup_preferences()

    # Build config
    config = {
        "model_size": model_size,
        "language": language,
        "hotkey_dictation": hotkey_dict,
        "hotkey_command": hotkey_cmd,
        "hotkey_mode": mode,
        "mic_device": mic_device,
        "sound_effects": sound,
        "notifications": False,
        "noise_reduction": noise,
        "post_processing": {
            "remove_filler_words": fillers,
            "code_vocabulary": False,
            "auto_capitalize": True,
        },
        "vad": {
            "enabled": True,
            "silence_timeout_ms": 1500,
        },
        "_auto_start": auto_start,
    }

    wants_startup = show_summary_and_save(config)

    # Handle auto-start
    if wants_startup:
        import subprocess
        startup_bat = os.path.join(SCRIPT_DIR, "install_startup.bat")
        if os.path.exists(startup_bat):
            subprocess.run(["cmd", "/c", startup_bat], cwd=SCRIPT_DIR)

    # Remove internal key
    config.pop("_auto_start", None)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    print("  ─────────────────────────────────────────\n")
    print("  To start Voice-to-Claude, double-click start.bat")
    print("  To re-run this setup, double-click configure.bat\n")
    print("  You can also change settings anytime by right-clicking")
    print("  the tray icon or editing config.json directly.\n")
    input("  Press Enter to exit setup...")


if __name__ == "__main__":
    main()
