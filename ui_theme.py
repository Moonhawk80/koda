"""
Shared dark-theme setup for Koda's tkinter GUIs.

Consolidates the Catppuccin-palette boilerplate that was previously
repeated verbatim across stats_gui.py, transcribe_file.py, and
context_menu.py (forge-clean Track 3 M1).
"""

from tkinter import ttk

# --- Catppuccin palette ---
BG = "#1e1e2e"
BG_ALT = "#313244"
FG_PRIMARY = "#cdd6f4"
FG_ACCENT = "#89b4fa"
FG_GREEN = "#a6e3a1"
FG_MUTED = "#a6adc8"
UI_FONT = ("Segoe UI", 10)


def apply_dark_theme(root, *, header_size=12):
    """Configure the dark theme on `root` and return the `ttk.Style` object.

    Callers that need additional styles (e.g. stats_gui's Big/Unit/Stat.TLabel)
    receive the Style instance back so they can extend it without re-doing setup.

    Args:
        root: a tk.Tk or tk.Toplevel
        header_size: point size for the Header.TLabel. Default 12; stats_gui uses 14.

    Returns:
        ttk.Style — extendable by the caller.
    """
    root.configure(bg=BG)

    style = ttk.Style()
    style.theme_use("clam")
    style.configure("TLabel", background=BG, foreground=FG_PRIMARY, font=UI_FONT)
    style.configure("Header.TLabel", background=BG, foreground=FG_ACCENT,
                    font=("Segoe UI", header_size, "bold"))
    style.configure("TButton", font=UI_FONT)

    return style
