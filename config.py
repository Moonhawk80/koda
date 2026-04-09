"""
Configuration management for Koda.
Loads/saves config.json with sensible defaults.
"""

import json
import os

CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULT_CONFIG = {
    "model_size": "base",
    "language": "en",
    "hotkey_dictation": "ctrl+space",
    "hotkey_command": "ctrl+shift+.",
    "hotkey_correction": "ctrl+shift+z",
    "hotkey_readback": "ctrl+shift+r",
    "hotkey_readback_selected": "ctrl+shift+t",
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
