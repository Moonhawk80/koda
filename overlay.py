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
import os
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

def _lighten(hex_color, amount=0.15):
    """Lighten a hex color like '#3498db' toward white by amount (0..1).
    Used for button hover states — small lift on top of the accent color."""
    try:
        h = hex_color.lstrip("#")
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        r = min(255, int(r + (255 - r) * amount))
        g = min(255, int(g + (255 - g) * amount))
        b = min(255, int(b + (255 - b) * amount))
        return f"#{r:02x}{g:02x}{b:02x}"
    except Exception:
        return hex_color


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
        root.title("Koda — Prompt Preview")
        try:
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "koda.ico")
            if os.path.exists(icon_path):
                root.iconbitmap(icon_path)
        except Exception:
            pass
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.0)  # fade in on show

        # -------------------------------------------------------------
        # Koda Dark v2 — layered surfaces, semantic accents, type scale
        # -------------------------------------------------------------
        BG_BASE     = "#0e1013"   # window background (deepest)
        BG_SURFACE  = "#16191f"   # raised card (body)
        BG_ELEVATED = "#1e222a"   # hover / interactive surface
        HAIRLINE    = "#242932"   # 1px separators
        TEXT        = "#e6e8ec"
        TEXT_DIM    = "#a6adba"
        TEXT_MUTED  = "#6b7280"
        BRAND       = "#2ecc71"   # Koda green
        INFO        = "#60a5fa"   # refine
        WARN        = "#f59e0b"   # add
        DANGER      = "#f87171"   # cancel (softer than saturated red)

        # Intent-pill color map — lights up with detected intent.
        INTENT_COLORS = {
            "code":    BRAND,
            "debug":   WARN,
            "explain": INFO,
            "review":  "#c084fc",
            "write":   "#f472b6",
            "general": TEXT_MUTED,
        }

        root.configure(bg=BG_BASE)
        W, H = 760, 580
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        root.geometry(f"{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}")

        # =============== FOOTER (hints) — packed bottom first ===============
        footer = tk.Frame(root, bg=BG_BASE)
        footer.pack(side="bottom", fill="x", padx=28, pady=(0, 14))
        tk.Label(
            footer, text="⏎  Paste       Esc  Cancel",
            bg=BG_BASE, fg=TEXT_MUTED, font=("Segoe UI", 9),
        ).pack(side="right")

        # Hairline above footer (between buttons and hints)
        tk.Frame(root, bg=HAIRLINE, height=1).pack(
            side="bottom", fill="x", padx=28, pady=(12, 10),
        )

        # =============== BUTTON ROW ===============
        btn_row = tk.Frame(root, bg=BG_BASE)
        btn_row.pack(side="bottom", fill="x", padx=28)

        add_holder = {"frame": None}

        # =============== HEADER (brand lockup + intent pill) ===============
        header = tk.Frame(root, bg=BG_BASE)
        header.pack(side="top", fill="x", padx=28, pady=(22, 14))

        # Koda K mark at 40px with brand-green status dot
        try:
            from voice import create_branded_icon
            mark_img = create_branded_icon(40, dot_color=BRAND)
            mark_photo = ImageTk.PhotoImage(mark_img)
            mark_label = tk.Label(header, image=mark_photo, bg=BG_BASE, bd=0)
            mark_label.image = mark_photo  # prevent GC
            mark_label.pack(side="left", padx=(0, 14))
        except Exception as e:
            logger.debug("brand mark render failed: %s", e)

        title_col = tk.Frame(header, bg=BG_BASE)
        title_col.pack(side="left", fill="y")
        tk.Label(
            title_col, text="Koda", bg=BG_BASE, fg=TEXT,
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor="w")
        tk.Label(
            title_col, text="Prompt Preview  ·  Review before paste",
            bg=BG_BASE, fg=TEXT_DIM, font=("Segoe UI", 10),
        ).pack(anchor="w", pady=(2, 0))

        # Intent pill — right side, color per detected intent
        try:
            from prompt_assist import detect_intent
            intent = detect_intent(text or "")
            pill_color = INTENT_COLORS.get(intent, TEXT_MUTED)
            tk.Label(
                header, text=f"  {intent.upper()}  ",
                bg=BG_ELEVATED, fg=pill_color,
                font=("Segoe UI Semibold", 9),
                padx=12, pady=6,
            ).pack(side="right", pady=(8, 0))
        except Exception as e:
            logger.debug("intent pill render failed: %s", e)

        # Hairline under header
        tk.Frame(root, bg=HAIRLINE, height=1).pack(side="top", fill="x", padx=28)

        # =============== BODY (prompt card) ===============
        body_wrap = tk.Frame(root, bg=BG_BASE)
        body_wrap.pack(side="top", fill="both", expand=True, padx=28, pady=18)

        body = tk.Frame(body_wrap, bg=BG_SURFACE)
        body.pack(fill="both", expand=True)

        # 1px top-edge highlight — faked depth (lighter line = raised card feel)
        tk.Frame(body, bg=BG_ELEVATED, height=1).pack(side="top", fill="x")

        txt = tk.Text(
            body, wrap="word", bg=BG_SURFACE, fg=TEXT, bd=0,
            highlightthickness=0, font=("Segoe UI", 13),
            padx=24, pady=22, insertbackground=TEXT,
            selectbackground="#2a3550", spacing1=4, spacing3=4,
        )
        txt.insert("1.0", text or "")
        txt.config(state="disabled")
        scroll = tk.Scrollbar(
            body, command=txt.yview, bg=BG_SURFACE,
            troughcolor=BG_SURFACE, bd=0, highlightthickness=0,
            activebackground=BG_ELEVATED, width=10,
        )
        txt.config(yscrollcommand=scroll.set)
        txt.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # =============== BUTTON FACTORIES ===============
        # Three hierarchies — text (ghost), elevated (secondary prominent),
        # primary (solid CTA). No 1px borders anywhere; differentiation
        # comes from weight + background contrast, not chrome.
        def _make_text_btn(parent, label, color, action):
            btn = tk.Label(
                parent, text=label, bg=BG_BASE, fg=color,
                font=("Segoe UI Semibold", 10),
                padx=14, pady=11, cursor="hand2",
            )
            btn.bind("<Button-1>", lambda e: action())
            btn.bind("<Enter>", lambda e: btn.configure(fg=_lighten(color, 0.3)))
            btn.bind("<Leave>", lambda e: btn.configure(fg=color))
            return btn

        def _make_elevated_btn(parent, label, color, action):
            btn = tk.Label(
                parent, text=label, bg=BG_ELEVATED, fg=color,
                font=("Segoe UI Semibold", 10),
                padx=20, pady=11, cursor="hand2",
            )
            hover_bg = _lighten(BG_ELEVATED, 0.35)
            btn.bind("<Button-1>", lambda e: action())
            btn.bind("<Enter>", lambda e: btn.configure(bg=hover_bg))
            btn.bind("<Leave>", lambda e: btn.configure(bg=BG_ELEVATED))
            return btn

        def _make_primary_btn(parent, label, action):
            btn = tk.Label(
                parent, text=label, bg=BRAND, fg="#0a0c0f",
                font=("Segoe UI Semibold", 11),
                padx=26, pady=12, cursor="hand2",
            )
            hover_bg = _lighten(BRAND, 0.12)
            btn.bind("<Button-1>", lambda e: action())
            btn.bind("<Enter>", lambda e: btn.configure(bg=hover_bg))
            btn.bind("<Leave>", lambda e: btn.configure(bg=BRAND))
            return btn

        # =============== ADD-INLINE ===============
        def _show_add_inline():
            if add_holder["frame"]:
                return
            af = tk.Frame(root, bg=BG_BASE)
            af.pack(side="bottom", fill="x", padx=28, pady=(0, 10), before=btn_row)
            tk.Label(af, text="Append:", bg=BG_BASE, fg=TEXT_DIM,
                     font=("Segoe UI", 10)).pack(side="left", padx=(0, 10))
            entry = tk.Entry(
                af, bg=BG_SURFACE, fg=TEXT, insertbackground=TEXT, bd=0,
                font=("Segoe UI", 12), relief="flat",
                highlightbackground=HAIRLINE, highlightcolor=INFO,
                highlightthickness=1,
            )
            entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 10))
            entry.focus_set()
            def _confirm_add(_=None):
                _fire("on_add", entry.get().strip())
            entry.bind("<Return>", _confirm_add)
            entry.bind("<Escape>", lambda e: _fire("on_cancel"))
            _make_primary_btn(af, "OK", _confirm_add).pack(side="left")
            add_holder["frame"] = af

        # =============== BUTTON LAYOUT ===============
        # Left: ghost destructive + ghost secondary.
        # Right: elevated secondary + solid primary (modern OS convention).
        _make_text_btn(btn_row, "Cancel", DANGER,
                       lambda: _fire("on_cancel")).pack(side="left")
        _make_text_btn(btn_row, "＋  Add", WARN,
                       _show_add_inline).pack(side="left", padx=(2, 0))
        _make_primary_btn(btn_row, "Paste",
                          lambda: _fire("on_confirm")).pack(side="right")
        _make_elevated_btn(btn_row, "Refine", INFO,
                           lambda: _fire("on_refine")).pack(side="right", padx=(0, 10))

        # =============== BINDINGS ===============
        root.bind("<Escape>", lambda e: _fire("on_cancel"))
        root.bind("<Return>", lambda e: _fire("on_confirm"))
        root.protocol("WM_DELETE_WINDOW", lambda: _fire("on_cancel"))

        root.lift()
        try:
            root.focus_force()
        except Exception:
            pass

        # Fade in over ~150ms — softens modal appearance, no animation feels abrupt
        def _fade(alpha=0.0):
            alpha = min(1.0, alpha + 0.12)
            try:
                root.attributes("-alpha", alpha)
            except Exception:
                return
            if alpha < 1.0:
                root.after(15, _fade, alpha)
        _fade()

        try:
            root.mainloop()
        except Exception as e:
            logger.error("prompt_preview mainloop crashed: %s", e, exc_info=True)
        finally:
            if not decided["v"]:
                try:
                    cb = callbacks.get("on_cancel")
                    if cb:
                        cb()
                except Exception:
                    pass

    threading.Thread(target=_run, daemon=True).start()
