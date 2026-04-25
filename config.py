"""
Configuration management for Koda.
Loads/saves config.json with sensible defaults.
"""

import json
import os
import sys


def _resolve_config_dir():
    if getattr(sys, "frozen", False):
        # Running as PyInstaller --onefile exe — store config in APPDATA\Koda
        # (the exe extracts to a temp _MEIPASS dir, which is wrong for persistent data)
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        d = os.path.join(base, "Koda")
        os.makedirs(d, exist_ok=True)
        return d
    # Running from source — config lives in the project root next to this file
    return os.path.dirname(os.path.abspath(__file__))


CONFIG_DIR = _resolve_config_dir()
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG = {
    "model_size": "small",
    "compute_type": "int8",
    # Windows process priority class for the Koda tray process. Higher values let
    # Windows preempt other normal-priority processes (e.g. many Node/Electron
    # sessions) so transcription stays responsive under system load. Values:
    # "normal" | "above_normal" | "high". "above_normal" is the polite default.
    "process_priority": "above_normal",
    # Number of CPU threads faster-whisper/CTranslate2 uses for inference. 0 =
    # all cores (OpenMP default), which contends badly when many other heavy
    # processes are running. 4 is a deliberate under-allocation that plays nice
    # with a busy system; raise on an otherwise-idle box if you want peak speed.
    "cpu_threads": 4,
    "language": "en",
    "output_mode": "auto_paste",
    "hotkey_dictation": "ctrl+space",
    "hotkey_command": "ctrl+shift+.",
    "hotkey_prompt": "ctrl+f9",
    "hotkey_correction": "ctrl+shift+z",
    "hotkey_readback": "ctrl+alt+r",
    "hotkey_readback_selected": "ctrl+alt+t",
    "hotkey_mode": "hold",
    "mic_device": None,
    "sound_effects": True,
    "notifications": False,
    "noise_reduction": False,
    "streaming": True,
    "post_processing": {
        "remove_filler_words": True,
        "code_vocabulary": False,
        "auto_capitalize": True,
        "auto_format": True,
    },
    "vad": {
        "enabled": True,
        "silence_timeout_ms": 1500,
    },
    "wake_word": {
        "enabled": False,
        "phrase": "hey koda",
    },
    "llm_polish": {
        "enabled": False,
        "model": "phi3:mini",
    },
    "prompt_assist": {
        "conversational": True,
        "refine_backend": "none",
        "api_provider": None,
        "opener": "What are we working on with AI today?",
    },
    "tts": {
        "rate": "normal",
        "voice": "",
    },
    "overlay_enabled": False,
    "profiles_enabled": True,
    "voice_commands": True,
    "app_launch_enabled": True,  # "open word" / "launch chrome" / "start powershell"
    "snippets": {},
    "translation": {
        "enabled": False,
        "target_language": "English",
    },
    "formula_mode": {
        "enabled": False,
        "auto_detect_apps": True,
    },
}


def deep_merge(base, override):
    """Recursively merge override into base (returns new dict)."""
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            user_config = json.load(f)
        return deep_merge(DEFAULT_CONFIG, user_config)
    else:
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()


def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)


def open_config_file():
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG)
    os.startfile(CONFIG_PATH)


CUSTOM_WORDS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "custom_words.json"
)
DEFAULT_CUSTOM_WORDS = {"coda": "Koda", "claude code": "Claude Code"}


def open_custom_words_file():
    if not os.path.exists(CUSTOM_WORDS_PATH):
        with open(CUSTOM_WORDS_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CUSTOM_WORDS, f, indent=2)
    os.startfile(CUSTOM_WORDS_PATH)
