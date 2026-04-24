"""
Koda Floating Status Overlay — branded K icon floating on desktop.

Same branded icon as the tray (dark square, white K, colored dot),
displayed as a draggable floating widget. Right-click to hide.

Also hosts show_prompt_preview() — the larger window the prompt-assist v2
flow uses to confirm an assembled prompt before paste.
"""

import ctypes
import ctypes.wintypes
import logging
import tkinter as tk
from PIL import ImageTk
import threading

logger = logging.getLogger("koda")


def _is_on_screen(x, y, size):
    """Return True if the centre of the overlay at (x, y) falls on any connected monitor."""
    pt = ctypes.wintypes.POINT(x + size // 2, y + size // 2)
    # MONITOR_DEFAULTTONULL returns NULL when the point is off all monitors
    return ctypes.windll.user32.MonitorFromPoint(pt, 0) != 0


def _default_position(size):
    """Return (x, y) for bottom-right of the primary monitor work area (excludes taskbar)."""
    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]
    work = RECT()
    # SPI_GETWORKAREA = 0x0030
    ctypes.windll.user32.SystemParametersInfoW(0x0030, 0, ctypes.byref(work), 0)
    x = work.right - size - 20
    y = work.bottom - size - 20
    return x, y


class KodaOverlay:
    """Floating branded K icon with status dot."""

    COLORS = {
        "ready": "#2ecc71",
        "recording": "#e74c3c",
        "transcribing": "#f39c12",
        "reading": "#9b59b6",
        "listening": "#3498db",
    }

    def __init__(self):
        self._root = None
        self._label = None
        self._state = "ready"
        self._preview_text = ""
        self._visible = True
        self._drag_data = {"x": 0, "y": 0}
        self._thread = None
        self._running = False
        self._position = None
        self._photo = None  # Keep reference to prevent GC
        self._prev_state = None
        self._icon_size = 48

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._root:
            try:
                self._root.after(0, self._root.destroy)
            except Exception:
                pass

    def _run(self):
        self._root = tk.Tk()
        root = self._root

        SIZE = self._icon_size

        KEY = "#010101"  # Transparent key color
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-toolwindow", True)
        root.attributes("-alpha", 0.85)
        root.configure(bg=KEY)
        root.attributes("-transparentcolor", KEY)

        # Label with transparent bg so rounded corners show through
        self._label = tk.Label(root, bg=KEY, bd=0, highlightthickness=0)
        self._label.pack()

        # Render initial icon
        self._update_icon()

        # Position bottom-right of primary monitor work area (excludes taskbar)
        root.update_idletasks()
        if self._position and _is_on_screen(*self._position, SIZE):
            x, y = self._position
        else:
            x, y = _default_position(SIZE)
        root.geometry(f"{SIZE}x{SIZE}+{x}+{y}")

        # Drag and hide
        root.bind("<Button-1>", self._on_drag_start)
        root.bind("<B1-Motion>", self._on_drag_motion)
        root.bind("<Button-3>", lambda e: self.toggle_visible())
        self._label.bind("<Button-1>", self._on_drag_start)
        self._label.bind("<B1-Motion>", self._on_drag_motion)
        self._label.bind("<Button-3>", lambda e: self.toggle_visible())

        self._poll()

        try:
            root.mainloop()
        except Exception:
            pass

    def _update_icon(self):
        """Re-render the branded icon with current state dot."""
        from voice import create_branded_icon
        dot_color = self.COLORS.get(self._state, "#2ecc71")
        img = create_branded_icon(self._icon_size, dot_color=dot_color)
        self._photo = ImageTk.PhotoImage(img)
        self._label.config(image=self._photo)

    def _poll(self):
        if not self._running or not self._root:
            return
        try:
            if self._state != self._prev_state:
                self._update_icon()
                self._prev_state = self._state
            self._root.after(300, self._poll)
        except Exception:
            pass

    def _on_drag_start(self, event):
        self._drag_data["x"] = event.x_root - self._root.winfo_x()
        self._drag_data["y"] = event.y_root - self._root.winfo_y()

    def _on_drag_motion(self, event):
        x = event.x_root - self._drag_data["x"]
        y = event.y_root - self._drag_data["y"]
        self._root.geometry(f"+{x}+{y}")
        self._position = (x, y)

    def set_state(self, state, preview=""):
        self._state = state
        self._preview_text = preview

    def set_preview(self, text):
        self._preview_text = text

    def toggle_visible(self):
        if not self._root:
            return
        try:
            if self._visible:
                self._root.withdraw()
                self._visible = False
            else:
                self._root.deiconify()
                self._visible = True
        except Exception:
            pass

    def show(self):
        if self._root and not self._visible:
            try:
                self._root.deiconify()
                self._visible = True
            except Exception:
                pass

    def hide(self):
        if self._root and self._visible:
            try:
                self._root.withdraw()
                self._visible = False
            except Exception:
                pass

    @property
    def is_visible(self):
        return self._visible


# ============================================================
# Prompt-assist v2 — confirmation preview window
# ============================================================

def show_prompt_preview(text, callbacks):
    """Open a topmost preview window showing the assembled prompt + 4 actions.

    Args:
        text: assembled prompt to display.
        callbacks: dict with keys 'on_confirm', 'on_refine', 'on_add',
                   'on_cancel'. Exactly one fires; the window then closes.

    Spawns its own thread + Tk root. Returns immediately.
    """
    def _run():
        decided = {"v": False}
        root_holder = {"r": None}

        def _fire(key, *args):
            if decided["v"]:
                return
            decided["v"] = True
            try:
                cb = callbacks.get(key)
                if cb:
                    cb(*args)
            except Exception as e:
                logger.error("prompt_preview callback %s failed: %s", key, e, exc_info=True)
            try:
                if root_holder["r"]:
                    root_holder["r"].destroy()
            except Exception:
                pass

        root = tk.Tk()
        root_holder["r"] = root
        root.title("Koda - Prompt Preview")
        root.attributes("-topmost", True)
        BG, FG, BTN_BG = "#1e1e1e", "#e8e8e8", "#2a2a2a"
        root.configure(bg=BG)
        W, H = 680, 460
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        root.geometry(f"{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}")

        body = tk.Frame(root, bg=BG)
        body.pack(fill="both", expand=True, padx=14, pady=(14, 8))
        txt = tk.Text(
            body, wrap="word", bg=BG, fg=FG, bd=0, highlightthickness=0,
            font=("Consolas", 11), padx=10, pady=10,
            insertbackground=FG, selectbackground="#264f78",
        )
        txt.insert("1.0", text or "")
        txt.config(state="disabled")
        scroll = tk.Scrollbar(body, command=txt.yview, bg=BG)
        txt.config(yscrollcommand=scroll.set)
        txt.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        btn_row = tk.Frame(root, bg=BG)
        btn_row.pack(fill="x", padx=14, pady=(0, 14))

        add_holder = {"frame": None}

        def _show_add_inline():
            if add_holder["frame"]:
                return
            af = tk.Frame(root, bg=BG)
            af.pack(fill="x", padx=14, pady=(0, 14))
            tk.Label(af, text="Append:", bg=BG, fg=FG, font=("Segoe UI", 10)).pack(side="left", padx=(0, 8))
            entry = tk.Entry(af, bg=BTN_BG, fg=FG, insertbackground=FG, bd=0,
                             font=("Segoe UI", 10), relief="flat")
            entry.pack(side="left", fill="x", expand=True, ipady=4)
            entry.focus_set()
            def _confirm_add(_=None):
                _fire("on_add", entry.get().strip())
            entry.bind("<Return>", _confirm_add)
            entry.bind("<Escape>", lambda e: _fire("on_cancel"))
            tk.Button(af, text="OK", command=_confirm_add, bg=BTN_BG, fg="#2ecc71",
                      bd=0, padx=12, pady=4, font=("Segoe UI", 10, "bold"),
                      activebackground="#3a3a3a", cursor="hand2").pack(side="left", padx=(8, 0))
            add_holder["frame"] = af

        for label, accent, action in [
            ("Send",   "#2ecc71", lambda: _fire("on_confirm")),
            ("Refine", "#3498db", lambda: _fire("on_refine")),
            ("Add",    "#f39c12", _show_add_inline),
            ("Cancel", "#e74c3c", lambda: _fire("on_cancel")),
        ]:
            tk.Button(
                btn_row, text=label, command=action,
                bg=BTN_BG, fg=accent, bd=0, padx=18, pady=8,
                activebackground="#3a3a3a", activeforeground=accent,
                font=("Segoe UI", 10, "bold"), cursor="hand2",
            ).pack(side="left", padx=4)

        root.bind("<Escape>", lambda e: _fire("on_cancel"))
        root.bind("<Return>", lambda e: _fire("on_confirm"))
        root.protocol("WM_DELETE_WINDOW", lambda: _fire("on_cancel"))

        root.lift()
        try:
            root.focus_force()
        except Exception:
            pass

        try:
            root.mainloop()
        except Exception as e:
            logger.error("prompt_preview mainloop crashed: %s", e, exc_info=True)
        finally:
            if not decided["v"]:
                # Window closed without firing — treat as cancel
                try:
                    cb = callbacks.get("on_cancel")
                    if cb:
                        cb()
                except Exception:
                    pass

    threading.Thread(target=_run, daemon=True).start()
