"""
Koda Hotkey Service — RegisterHotKey implementation.

Uses Windows RegisterHotKey API instead of WH_KEYBOARD_LL hooks.
RegisterHotKey registers directly with the OS Window Manager and
survives screen lock, sleep/wake, UAC, and fast-user-switching —
conditions that silently kill WH_KEYBOARD_LL hooks.

For hold-mode releases, a background thread polls GetAsyncKeyState
on the trigger key. This installs zero system hooks and therefore
cannot block keyboard input under any circumstances.

Protocol (over multiprocessing.Pipe): identical to previous version.
    Child → Parent:
        "ready"                 — service is live
        ("pong", float)         — reply to "ping"; float = monotonic time of last key event
        "dictation_press"       — hold mode: hotkey pressed
        "dictation_release"     — hold mode: trigger key released
        "command_press"         — hold mode
        "command_release"       — hold mode
        "prompt_press"          — hold mode
        "prompt_release"        — hold mode
        "dictation_toggle"      — toggle mode
        "command_toggle"        — toggle mode
        "prompt_toggle"         — toggle mode
        "correction"            — correction hotkey
        "readback"              — read-back hotkey
        "readback_selected"     — read-selected hotkey

    Parent → Child:
        "ping"                  — health check (expects ("pong", float) back)
        "quit"                  — graceful shutdown
"""

import ctypes
import ctypes.wintypes
import os
import logging
import threading
import time
import queue

logger = logging.getLogger("koda.hotkey")

# ── Win32 constants ──────────────────────────────────────────────────────────
MOD_ALT        = 0x0001
MOD_CONTROL    = 0x0002
MOD_SHIFT      = 0x0004
MOD_WIN        = 0x0008
MOD_NOREPEAT   = 0x4000  # suppress WM_HOTKEY repeat while key is held

WM_HOTKEY      = 0x0312

# Custom thread message used by the pipe-reader thread to wake the GetMessage loop
WM_APP_PIPE    = 0x8001

user32   = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# ── VK code table ────────────────────────────────────────────────────────────
_VK_MAP = {
    'space': 0x20,
    'f1':  0x70, 'f2':  0x71, 'f3':  0x72, 'f4':  0x73,
    'f5':  0x74, 'f6':  0x75, 'f7':  0x76, 'f8':  0x77,
    'f9':  0x78, 'f10': 0x79, 'f11': 0x7A, 'f12': 0x7B,
    # Numpad
    'num0': 0x60, 'num1': 0x61, 'num2': 0x62, 'num3': 0x63,
    'num4': 0x64, 'num5': 0x65, 'num6': 0x66, 'num7': 0x67,
    'num8': 0x68, 'num9': 0x69,
    # Navigation / editing
    'insert':   0x2D, 'delete': 0x2E,
    'home':     0x24, 'end':    0x23,
    'pageup':   0x21, 'pagedown': 0x22,
    'up':       0x26, 'down':   0x28, 'left': 0x25, 'right': 0x27,
    'tab':      0x09, 'enter':  0x0D, 'esc':  0x1B, 'backspace': 0x08,
    # OEM punctuation (US layout)
    ';':  0xBA, '=':  0xBB, ',':  0xBC, '-':  0xBD,
    '.':  0xBE, '/':  0xBF, '`':  0xC0, '[':  0xDB,
    '\\': 0xDC, ']':  0xDD, "'":  0xDE,
}


def _parse_hotkey(hotkey_str):
    """Convert 'ctrl+space' / 'f8' / 'ctrl+alt+a' → (modifiers, vk_code).

    Returns (mods, vk) where mods always includes MOD_NOREPEAT.
    Returns (MOD_NOREPEAT, 0) if the key portion could not be parsed.
    """
    parts = [p.strip().lower() for p in hotkey_str.split('+')]
    mods = MOD_NOREPEAT
    vk = 0
    for p in parts:
        if p == 'ctrl':
            mods |= MOD_CONTROL
        elif p == 'alt':
            mods |= MOD_ALT
        elif p == 'shift':
            mods |= MOD_SHIFT
        elif p == 'win':
            mods |= MOD_WIN
        elif p in _VK_MAP:
            vk = _VK_MAP[p]
        elif len(p) == 1 and p.isalpha():
            vk = ord(p.upper())
    return mods, vk


def _trigger_vk(hotkey_str):
    """Return the VK code of the trigger key (last token in the hotkey string)."""
    trigger = hotkey_str.split('+')[-1].strip().lower()
    if trigger in _VK_MAP:
        return _VK_MAP[trigger]
    if len(trigger) == 1 and trigger.isalpha():
        return ord(trigger.upper())
    return 0


# ── Win32 structures ─────────────────────────────────────────────────────────
class _MSG(ctypes.Structure):
    _fields_ = [
        ("hwnd",    ctypes.wintypes.HWND),
        ("message", ctypes.wintypes.UINT),
        ("wParam",  ctypes.wintypes.WPARAM),
        ("lParam",  ctypes.wintypes.LPARAM),
        ("time",    ctypes.wintypes.DWORD),
        ("pt",      ctypes.wintypes.POINT),
    ]



# ── Service entry point ──────────────────────────────────────────────────────
def service_main(conn, hotkey_config):
    """Entry point for the hotkey service process."""
    log_path = hotkey_config.get("_log_path", "debug.log")
    logging.basicConfig(
        filename=log_path,
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )
    logger.setLevel(logging.DEBUG)
    logger.info("Hotkey service starting (RegisterHotKey, pid=%d)", os.getpid())

    # ── Parse config ─────────────────────────────────────────────────────────
    hotkey_dict    = hotkey_config.get("hotkey_dictation",         "ctrl+space")
    hotkey_cmd     = hotkey_config.get("hotkey_command",            "f8")
    hotkey_prompt  = hotkey_config.get("hotkey_prompt",             "f9")
    hotkey_correct = hotkey_config.get("hotkey_correction",         "f7")
    hotkey_read    = hotkey_config.get("hotkey_readback",           "f6")
    hotkey_read_sel= hotkey_config.get("hotkey_readback_selected",  "f5")
    mode = hotkey_config.get("hotkey_mode", "hold")

    # ── Shared state ─────────────────────────────────────────────────────────
    _last_key = [time.monotonic()]   # list-cell for nonlocal mutation from closures
    _last_key_lock = threading.Lock()
    _quit = threading.Event()
    _thread_id = kernel32.GetCurrentThreadId()
    _cmd_queue: queue.Queue = queue.Queue()

    def _touch():
        with _last_key_lock:
            _last_key[0] = time.monotonic()

    def _send(evt):
        try:
            conn.send(evt)
        except Exception as e:
            logger.error("send(%s) failed: %s", evt, e)

    # ── RegisterHotKey ───────────────────────────────────────────────────────
    _id_to_event: dict[int, str] = {}
    _registered_ids: list[int] = []

    def _reg(hk_str, hk_id, event_name):
        mods, vk = _parse_hotkey(hk_str)
        if vk == 0:
            logger.error("Cannot parse hotkey '%s' — skipping", hk_str)
            return
        ok = user32.RegisterHotKey(None, hk_id, mods, vk)
        if ok:
            _id_to_event[hk_id] = event_name
            _registered_ids.append(hk_id)
            logger.debug("RegisterHotKey OK  id=%-2d  %-20s → %s", hk_id, hk_str, event_name)
        else:
            err = kernel32.GetLastError()
            logger.error("RegisterHotKey FAIL id=%-2d  %-20s  err=%d", hk_id, hk_str, err)

    if mode == "hold":
        _reg(hotkey_dict,    1, "dictation_press")
        _reg(hotkey_cmd,     2, "command_press")
        _reg(hotkey_prompt,  3, "prompt_press")
    else:
        _reg(hotkey_dict,    1, "dictation_toggle")
        _reg(hotkey_cmd,     2, "command_toggle")
        _reg(hotkey_prompt,  3, "prompt_toggle")

    _reg(hotkey_correct,   4, "correction")
    _reg(hotkey_read,      5, "readback")
    _reg(hotkey_read_sel,  6, "readback_selected")

    # ── GetAsyncKeyState polling for hold-mode key-up events ────────────────
    # RegisterHotKey fires on key-down only. For hold mode we need the key-up
    # to send _release events. We use GetAsyncKeyState polling instead of a
    # WH_KEYBOARD_LL hook — polling installs zero system hooks and therefore
    # cannot block keyboard input if the message loop is slow to start.
    # Poll interval 10ms gives ≤10ms release latency, fine for voice recording.

    if mode == "hold":
        _release_vks: dict[int, str] = {}
        for hk_str, evt in [
            (hotkey_dict,   "dictation_release"),
            (hotkey_cmd,    "command_release"),
            (hotkey_prompt, "prompt_release"),
        ]:
            vk = _trigger_vk(hk_str)
            if vk:
                _release_vks[vk] = evt

        _active_press_vks: set[int] = set()
        _active_press_lock = threading.Lock()

        def _poll_key_release():
            """Background thread: poll GetAsyncKeyState for tracked key releases."""
            while not _quit.is_set():
                with _active_press_lock:
                    tracked = list(_active_press_vks)
                for vk in tracked:
                    # Bit 15 = key is currently down
                    if not (user32.GetAsyncKeyState(vk) & 0x8000):
                        evt = _release_vks.get(vk)
                        if evt:
                            _touch()
                            _send(evt)
                        with _active_press_lock:
                            _active_press_vks.discard(vk)
                time.sleep(0.01)

        threading.Thread(target=_poll_key_release, daemon=True).start()
    else:
        _active_press_vks = None
        _active_press_lock = None

    # ── Pipe-reader thread ───────────────────────────────────────────────────
    # Runs on a daemon thread. Puts commands in _cmd_queue and posts
    # WM_APP_PIPE to the message loop thread to process them.
    def _pipe_reader():
        while not _quit.is_set():
            try:
                if conn.poll(1.0):
                    cmd = conn.recv()
                    _cmd_queue.put(cmd)
                    user32.PostThreadMessageW(_thread_id, WM_APP_PIPE, 0, 0)
            except EOFError:
                logger.warning("Parent pipe closed — exiting")
                _quit.set()
                user32.PostThreadMessageW(_thread_id, WM_APP_PIPE, 0, 0)
                break
            except Exception as e:
                logger.error("Pipe reader error: %s", e)

    threading.Thread(target=_pipe_reader, daemon=True).start()

    # ── Ready ────────────────────────────────────────────────────────────────
    logger.info("Hotkey service ready (RegisterHotKey, mode=%s, pid=%d)", mode, os.getpid())
    _send("ready")

    # ── Message loop ─────────────────────────────────────────────────────────
    msg = _MSG()
    try:
        while not _quit.is_set():
            ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if ret == 0 or ret == -1:
                break

            if msg.message == WM_HOTKEY:
                evt = _id_to_event.get(msg.wParam)
                if evt:
                    _touch()
                    _send(evt)
                    # For hold mode, track the trigger key so the poller
                    # can detect its release and send the _release event.
                    if _active_press_vks is not None and evt.endswith("_press"):
                        hk_str_map = {
                            "dictation_press": hotkey_dict,
                            "command_press":   hotkey_cmd,
                            "prompt_press":    hotkey_prompt,
                        }
                        hk_str = hk_str_map.get(evt)
                        if hk_str:
                            vk = _trigger_vk(hk_str)
                            if vk:
                                with _active_press_lock:
                                    _active_press_vks.add(vk)

            elif msg.message == WM_APP_PIPE:
                while not _cmd_queue.empty():
                    try:
                        cmd = _cmd_queue.get_nowait()
                    except queue.Empty:
                        break
                    if cmd == "quit":
                        logger.info("Quit received")
                        _quit.set()
                        break
                    elif cmd == "ping":
                        _touch()   # prove message loop is alive; pong carries a fresh timestamp
                        with _last_key_lock:
                            last_t = _last_key[0]
                        _send(("pong", last_t))

            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    finally:
        for hk_id in _registered_ids:
            user32.UnregisterHotKey(None, hk_id)
        logger.info("Hotkey service stopped (pid=%d)", os.getpid())
