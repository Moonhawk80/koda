"""
Active-window detection for prompt-assist platform routing.

At hotkey press we capture (hwnd, exe, title) of the user's foreground
window so we can:
  1. Pick a platform-specific prompt template (Claude / ChatGPT / Gemini /
     Cursor / generic).
  2. Re-focus the same window before pasting — TTS and the overlay may
     steal focus during the conversation.

Design: docs/prompt-assist-v2-design.md §"Platform detection".
"""

import logging
import os

logger = logging.getLogger("koda")

PLATFORM_CLAUDE = "claude"
PLATFORM_CHATGPT = "chatgpt"
PLATFORM_GEMINI = "gemini"
PLATFORM_CURSOR = "cursor"
PLATFORM_VSCODE = "vscode"
PLATFORM_GENERIC = "generic"


def _get_window_info(hwnd) -> dict:
    """Return {hwnd, title, exe} for a window handle. Empty fields on failure."""
    info = {"hwnd": hwnd, "title": "", "exe": ""}
    try:
        import win32api
        import win32con
        import win32gui
        import win32process

        info["title"] = win32gui.GetWindowText(hwnd) or ""
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if pid:
            hproc = win32api.OpenProcess(
                win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid
            )
            try:
                info["exe"] = os.path.basename(
                    win32process.GetModuleFileNameEx(hproc, 0)
                ).lower()
            finally:
                win32api.CloseHandle(hproc)
    except Exception as e:
        logger.warning("active_window: get_window_info failed for hwnd=%s: %s", hwnd, e)
    return info


def get_foreground_window_info() -> dict:
    """Snapshot the current foreground window. Returns {hwnd, title, exe}."""
    try:
        import win32gui
        hwnd = win32gui.GetForegroundWindow()
    except Exception as e:
        logger.warning("active_window: GetForegroundWindow failed: %s", e)
        return {"hwnd": 0, "title": "", "exe": ""}
    return _get_window_info(hwnd)


def classify_platform(exe: str, title: str) -> str:
    """Map (exe, title) -> a platform identifier. Used to pick a template.

    Browser tabs surface in the window title (e.g. 'ChatGPT - Google Chrome').
    Native desktop apps show up by exe alone.
    """
    exe_l = (exe or "").lower()
    title_l = (title or "").lower()

    if exe_l == "claude.exe":
        return PLATFORM_CLAUDE

    if exe_l in ("chrome.exe", "msedge.exe", "brave.exe", "firefox.exe", "opera.exe"):
        if "chatgpt" in title_l or "openai" in title_l:
            return PLATFORM_CHATGPT
        if "gemini" in title_l or "bard" in title_l:
            return PLATFORM_GEMINI
        if "claude" in title_l:
            return PLATFORM_CLAUDE

    if exe_l == "cursor.exe":
        return PLATFORM_CURSOR
    if exe_l == "code.exe":
        return PLATFORM_VSCODE

    return PLATFORM_GENERIC


def detect_platform() -> dict:
    """Snapshot foreground window and classify the platform in one call.

    Returns: {hwnd, title, exe, platform}
    """
    info = get_foreground_window_info()
    info["platform"] = classify_platform(info["exe"], info["title"])
    return info


def refocus_window(hwnd) -> bool:
    """Bring the given window back to the foreground. Returns True on success.

    Used right before paste — TTS engine and overlay window can steal focus
    during the conversation. SetForegroundWindow has to be coaxed: we
    minimize-then-restore as a fallback path on failure.
    """
    if not hwnd:
        return False
    try:
        import win32con
        import win32gui

        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(hwnd)
        return True
    except Exception as e:
        logger.warning("active_window: refocus failed for hwnd=%s: %s", hwnd, e)
        return False
