"""
Koda Floating Status Overlay — cute mascot widget.

A small round character that reacts to Koda's state:
  Ready: green face, happy smile, headset
  Recording: red, open mouth listening
  Transcribing: orange, thinking dots
  Reading: purple, speaking
  Listening: blue, alert ears

Draggable, semi-transparent. Right-click to hide.
"""

import tkinter as tk
import threading
import time

_KEY_COLOR = "#010101"


class KodaOverlay:
    """Koda mascot overlay — small animated character."""

    COLORS = {
        "ready": "#2ecc71",
        "recording": "#e74c3c",
        "transcribing": "#f39c12",
        "reading": "#9b59b6",
        "listening": "#3498db",
    }

    def __init__(self):
        self._root = None
        self._canvas = None
        self._state = "ready"
        self._preview_text = ""
        self._visible = True
        self._drag_data = {"x": 0, "y": 0}
        self._thread = None
        self._running = False
        self._opacity = 0.88
        self._position = None
        self._anim_frame = 0

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

        SIZE = 56

        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", self._opacity)
        root.attributes("-toolwindow", True)
        root.configure(bg=_KEY_COLOR)
        root.attributes("-transparentcolor", _KEY_COLOR)

        self._canvas = tk.Canvas(root, width=SIZE, height=SIZE + 16, bg=_KEY_COLOR,
                                 highlightthickness=0, bd=0)
        self._canvas.pack()

        self._SIZE = SIZE

        # Position: bottom-right corner
        root.update_idletasks()
        if self._position:
            x, y = self._position
        else:
            screen_w = root.winfo_screenwidth()
            screen_h = root.winfo_screenheight()
            x = screen_w - SIZE - 24
            y = screen_h - SIZE - 100
        root.geometry(f"{SIZE}x{SIZE + 16}+{x}+{y}")

        self._canvas.bind("<Button-1>", self._on_drag_start)
        self._canvas.bind("<B1-Motion>", self._on_drag_motion)
        self._canvas.bind("<Button-3>", lambda e: self.toggle_visible())

        self._draw_character()
        self._poll()

        try:
            root.mainloop()
        except Exception:
            pass

    def _draw_character(self):
        """Draw the Koda mascot based on current state."""
        c = self._canvas
        c.delete("all")
        S = self._SIZE
        cx, cy = S // 2, S // 2
        r = S // 2 - 2  # radius

        state = self._state
        color = self.COLORS.get(state, "#2ecc71")

        # --- Shadow ---
        c.create_oval(cx - r + 2, cy - r + 3, cx + r + 2, cy + r + 3,
                       fill="#0a0a14", outline="")

        # --- Body (circle) ---
        c.create_oval(cx - r, cy - r, cx + r, cy + r,
                       fill=color, outline="")

        # --- Lighter highlight on top ---
        hi_r = r - 4
        c.create_arc(cx - hi_r, cy - r + 2, cx + hi_r, cy,
                      start=0, extent=180, fill=self._lighten(color), outline="")

        # --- Eyes ---
        eye_y = cy - 4
        eye_spread = 8

        if state == "recording":
            # Big open eyes — listening intently
            c.create_oval(cx - eye_spread - 5, eye_y - 5, cx - eye_spread + 5, eye_y + 5,
                           fill="white", outline="")
            c.create_oval(cx + eye_spread - 5, eye_y - 5, cx + eye_spread + 5, eye_y + 5,
                           fill="white", outline="")
            # Pupils (looking at you)
            c.create_oval(cx - eye_spread - 2, eye_y - 2, cx - eye_spread + 2, eye_y + 2,
                           fill="#1e1e2e", outline="")
            c.create_oval(cx + eye_spread - 2, eye_y - 2, cx + eye_spread + 2, eye_y + 2,
                           fill="#1e1e2e", outline="")
        elif state == "transcribing":
            # Squinting eyes — thinking
            c.create_line(cx - eye_spread - 4, eye_y, cx - eye_spread + 4, eye_y,
                           fill="#1e1e2e", width=2)
            c.create_line(cx + eye_spread - 4, eye_y, cx + eye_spread + 4, eye_y,
                           fill="#1e1e2e", width=2)
        else:
            # Normal happy eyes
            c.create_oval(cx - eye_spread - 3, eye_y - 3, cx - eye_spread + 3, eye_y + 3,
                           fill="white", outline="")
            c.create_oval(cx + eye_spread - 3, eye_y - 3, cx + eye_spread + 3, eye_y + 3,
                           fill="white", outline="")
            c.create_oval(cx - eye_spread - 1.5, eye_y - 1.5, cx - eye_spread + 1.5, eye_y + 1.5,
                           fill="#1e1e2e", outline="")
            c.create_oval(cx + eye_spread - 1.5, eye_y - 1.5, cx + eye_spread + 1.5, eye_y + 1.5,
                           fill="#1e1e2e", outline="")

        # --- Mouth ---
        mouth_y = cy + 7

        if state == "recording":
            # Open circle mouth — "listening"
            c.create_oval(cx - 4, mouth_y - 4, cx + 4, mouth_y + 4,
                           fill="#1e1e2e", outline="")
        elif state == "transcribing":
            # Thinking dots
            frame = self._anim_frame % 3
            for i in range(3):
                dot_x = cx - 6 + i * 6
                dot_fill = "#1e1e2e" if i <= frame else self._darken(color)
                c.create_oval(dot_x - 1.5, mouth_y - 1.5, dot_x + 1.5, mouth_y + 1.5,
                               fill=dot_fill, outline="")
        elif state == "reading":
            # Speaking — wavy mouth
            frame = self._anim_frame % 2
            w = 4 if frame == 0 else 6
            c.create_oval(cx - w, mouth_y - 3, cx + w, mouth_y + 3,
                           fill="#1e1e2e", outline="")
        else:
            # Happy smile
            c.create_arc(cx - 6, mouth_y - 6, cx + 6, mouth_y + 2,
                          start=200, extent=140, fill="#1e1e2e", outline="")

        # --- Headset (small arc on top) ---
        c.create_arc(cx - r + 4, cy - r - 2, cx + r - 4, cy + 4,
                      start=30, extent=120, outline="white", width=2, style="arc")
        # Ear pads
        c.create_oval(cx - r + 2, cy - 4, cx - r + 8, cy + 4,
                       fill="white", outline="")
        c.create_oval(cx + r - 8, cy - 4, cx + r - 2, cy + 4,
                       fill="white", outline="")

        # --- Status text below ---
        labels = {
            "ready": "Ready",
            "recording": "Listening...",
            "transcribing": "Thinking...",
            "reading": "Speaking...",
            "listening": "Hey Koda?",
        }
        c.create_text(cx, S + 8, text=labels.get(state, ""),
                       fill="#cdd6f4", font=("Segoe UI", 7), anchor="center")

    @staticmethod
    def _lighten(color):
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        return f"#{min(255,int(r*1.3)):02x}{min(255,int(g*1.3)):02x}{min(255,int(b*1.3)):02x}"

    @staticmethod
    def _darken(color):
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        return f"#{int(r*0.7):02x}{int(g*0.7):02x}{int(b*0.7):02x}"

    def _poll(self):
        if not self._running or not self._root:
            return
        try:
            old_state = getattr(self, "_prev_state", None)
            old_frame = getattr(self, "_prev_frame", None)

            if self._state != old_state or (self._state in ("transcribing", "reading") and self._anim_frame != old_frame):
                self._draw_character()
                self._prev_state = self._state
                self._prev_frame = self._anim_frame

            # Animate thinking/speaking
            if self._state in ("transcribing", "reading"):
                self._anim_frame += 1

            # Dimmer when idle
            if self._state == "ready":
                self._root.attributes("-alpha", self._opacity * 0.8)
            else:
                self._root.attributes("-alpha", self._opacity)

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

    # --- Public API ---

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
