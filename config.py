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
    "language": "en",
    "output_mode": "auto_paste",
    "hotkey_dictation": "ctrl+space",
    "hotkey_command": "ctrl+shift+.",
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
    "tts": {
        "rate": "normal",
        "voice": "",
    },
    "overlay_enabled": False,
    "profiles_enabled": True,
    "voice_commands": True,
    "snippets": {},
    "translation": {
        "enabled": False,
        "target_language": "English",
    },
}


def _deep_merge(base, override):
    merged = base.copy()
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            user_config = json.load(f)
        return _deep_merge(DEFAULT_CONFIG, user_config)
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
