"""
Koda Floating Status Overlay — branded K icon floating on desktop.

Same branded icon as the tray (dark square, white K, colored dot),
displayed as a draggable floating widget. Right-click to hide.
"""

import tkinter as tk
from PIL import ImageTk
import threading


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

        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-toolwindow", True)
        root.configure(bg="#1a1a2e")

        # Label to hold the icon image
        self._label = tk.Label(root, bg="#1a1a2e", bd=0, highlightthickness=0)
        self._label.pack()

        # Render initial icon
        self._update_icon()

        # Position bottom-right
        root.update_idletasks()
        if self._position:
            x, y = self._position
        else:
            screen_w = root.winfo_screenwidth()
            screen_h = root.winfo_screenheight()
            x = screen_w - SIZE - 20
            y = screen_h - SIZE - 120
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
