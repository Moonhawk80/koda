"""
Per-app profiles for Koda.

Automatically switches settings based on the active window.
Each profile maps an app (by process name or window title pattern) to
config overrides that are merged on top of the base config.
"""

import ctypes
import ctypes.wintypes
import logging
import os
import re
import json
import threading
import time

from config import deep_merge

logger = logging.getLogger("koda")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROFILES_PATH = os.path.join(SCRIPT_DIR, "profiles.json")

# --- Window detection (ctypes, no extra deps) ---

_user32 = ctypes.windll.user32
_kernel32 = ctypes.windll.kernel32

# Constants
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


def get_active_window_info():
    """Return (process_name, window_title) of the foreground window."""
    hwnd = _user32.GetForegroundWindow()
    if not hwnd:
        return ("", "")

    # Window title
    length = _user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    _user32.GetWindowTextW(hwnd, buf, length + 1)
    title = buf.value

    # Process name from PID
    pid = ctypes.wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    process_name = ""
    handle = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if handle:
        buf = ctypes.create_unicode_buffer(260)
        size = ctypes.wintypes.DWORD(260)
        if _kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            process_name = os.path.basename(buf.value).lower()
        _kernel32.CloseHandle(handle)

    return (process_name, title)


# --- Profile matching ---

# Default profiles shipped with Koda
DEFAULT_PROFILES = {
    "_description": "Per-app profiles. Each key is a profile name. 'match' is a process name or regex for window title. 'settings' are config overrides merged on top of your base config.",
    "VS Code": {
        "match": {"process": "code.exe"},
        "settings": {
            "post_processing": {
                "code_vocabulary": True,
                "auto_format": False,
            }
        }
    },
    "Terminal": {
        "match": {"process": "windowsterminal.exe"},
        "settings": {
            "post_processing": {
                "code_vocabulary": True,
                "auto_format": False,
            }
        }
    },
    "Slack": {
        "match": {"process": "slack.exe"},
        "settings": {
            "post_processing": {
                "code_vocabulary": False,
                "remove_filler_words": True,
            }
        }
    },
    "Outlook": {
        "match": {"process": "outlook.exe"},
        "settings": {
            "post_processing": {
                "code_vocabulary": False,
                "auto_capitalize": True,
            }
        }
    },
    "Notepad": {
        "match": {"process": "notepad.exe"},
        "settings": {}
    },
}


def load_profiles():
    """Load profiles from profiles.json, creating default file if needed.

    On corruption: preserve the broken file as profiles.json.corrupt.<ts>
    and write defaults — so the user can recover their customizations.
    """
    if os.path.exists(PROFILES_PATH):
        try:
            with open(PROFILES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            backup = f"{PROFILES_PATH}.corrupt.{int(time.time())}"
            try:
                os.replace(PROFILES_PATH, backup)
                logger.warning("profiles.json corrupt (%s) — backed up to %s", e, backup)
            except OSError:
                logger.error("profiles.json corrupt (%s) and could not be backed up", e)
    # Create default profiles file
    save_profiles(DEFAULT_PROFILES)
    return DEFAULT_PROFILES.copy()


def save_profiles(profiles):
    """Save profiles to profiles.json."""
    with open(PROFILES_PATH, "w", encoding="utf-8") as f:
        json.dump(profiles, f, indent=2)


def match_profile(profiles, process_name, window_title):
    """Find the first matching profile for the given window.

    Returns (profile_name, settings_overrides) or (None, {}).
    """
    for name, profile in profiles.items():
        if name.startswith("_"):
            continue
        if not isinstance(profile, dict) or "match" not in profile:
            continue

        match_rules = profile["match"]
        matched = False

        # Match by process name
        if "process" in match_rules:
            if process_name == match_rules["process"].lower():
                matched = True

        # Match by window title regex
        if not matched and "title" in match_rules:
            try:
                if re.search(match_rules["title"], window_title, re.IGNORECASE):
                    matched = True
            except re.error:
                pass

        if matched:
            return (name, profile.get("settings", {}))

    return (None, {})


# --- Profile monitor thread ---

class ProfileMonitor:
    """Background thread that watches the active window and applies profile overrides."""

    def __init__(self, base_config, on_profile_change=None):
        """
        Args:
            base_config: The base config dict (will not be mutated).
            on_profile_change: Callback(profile_name, merged_config) called when profile changes.
        """
        self._base_config = base_config
        self._on_change = on_profile_change
        self._profiles = load_profiles()
        self._current_profile = None
        self._running = False
        self._thread = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def reload_profiles(self):
        """Reload profiles from disk."""
        self._profiles = load_profiles()

    @property
    def current_profile(self):
        return self._current_profile

    def _monitor_loop(self):
        while self._running:
            try:
                process_name, title = get_active_window_info()
                profile_name, overrides = match_profile(self._profiles, process_name, title)

                if profile_name != self._current_profile:
                    self._current_profile = profile_name
                    if self._on_change:
                        merged = deep_merge(self._base_config, overrides) if overrides else self._base_config
                        self._on_change(profile_name, merged)
            except Exception:
                pass

            time.sleep(1)  # Check every second
