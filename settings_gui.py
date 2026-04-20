"""
Koda Settings — GUI for configuring Koda.
Opens from the tray menu or desktop shortcut.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import logging
import os
import sys
import time

from config import CONFIG_PATH, CUSTOM_WORDS_PATH, DEFAULT_CUSTOM_WORDS, load_config, save_config

logger = logging.getLogger("koda")

# Windows DPI awareness. Without this, PyInstaller-frozen tkinter apps render
# at legacy 96 DPI and Windows bitmap-upscales them — producing a tiny blurry
# window on any display scaled above 100%. Must be set before Tk() is created.
if sys.platform == "win32":
    try:
        import ctypes
        # 2 = PROCESS_PER_MONITOR_DPI_AWARE (preferred); fall back to 1 on older Windows.
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# Directory containing this file — used for in-source (non-frozen) subprocess
# launch of voice.py. Intentionally NOT derived from config.CONFIG_DIR because
# in a frozen exe, CONFIG_DIR points at %APPDATA%\Koda while voice.py lives
# wherever the source tree is; these paths only coincide in dev mode.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ICO_PATH = os.path.join(SCRIPT_DIR, "koda.ico")


# Settings whose changes only take effect after Koda is relaunched.
# Theme and most UI toggles apply live — these don't (hotkey_service needs
# re-registration, Whisper model needs reload, audio stream needs re-open).
RESTART_REQUIRED_KEYS = (
    "model_size",
    "compute_type",
    "hotkey_dictation",
    "hotkey_command",
    "hotkey_prompt",
    "hotkey_correction",
    "hotkey_readback",
    "hotkey_readback_selected",
    "hotkey_mode",
    "mic_device",
    "streaming",
)


def _restart_required_changes(before, after):
    """Return the subset of RESTART_REQUIRED_KEYS whose values differ."""
    return [k for k in RESTART_REQUIRED_KEYS if before.get(k) != after.get(k)]


def _detect_system_theme():
    """Read Windows apps-theme preference. Returns 'light' or 'dark'.

    Falls back to 'light' on any registry / non-Windows failure.
    """
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            # AppsUseLightTheme: 0 = dark, 1 = light
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return "light" if value else "dark"
    except Exception:
        return "light"


# Fluent-lite palette. `window` = outer chrome, `content` = tab-body panels.
# Dark accent is brighter than light to keep contrast on dark bg.
THEMES = {
    "light": {
        "window":    "#f5f5f5",
        "content":   "#ffffff",
        "border":    "#e5e7eb",
        "text":      "#1f2937",
        "text_dim":  "#6b7280",
        "accent":    "#2563eb",
        "accent_hv": "#1d4ed8",
        "accent_fg": "#ffffff",
        "success":   "#059669",
        "hover":     "#eeeeee",
        "tree_sel":  "#dbeafe",
    },
    "dark": {
        "window":    "#1f1f1f",
        "content":   "#2b2b2b",
        "border":    "#404040",
        "text":      "#e5e7eb",
        "text_dim":  "#9ca3af",
        "accent":    "#3b82f6",
        "accent_hv": "#60a5fa",
        "accent_fg": "#ffffff",
        "success":   "#10b981",
        "hover":     "#333333",
        "tree_sel":  "#1e3a8a",
    },
}


class RoundedButton(tk.Canvas):
    """Canvas-drawn button with truly rounded corners.

    ttk.Button (clam theme) draws a flat rectangle with no corner-radius
    control, so we bypass ttk for the two hero actions (Save / Cancel) and
    paint a PIL-rendered rounded rectangle with text on top. Re-themes live
    via re_theme(palette).
    """

    def __init__(self, parent, text, command, *, primary, palette,
                 width=112, height=36, radius=8, font=("Segoe UI", 10, "bold")):
        super().__init__(parent, width=width, height=height,
                         bg=palette["window"], highlightthickness=0, bd=0)
        self._text = text
        self._cmd = command
        self._primary = primary
        self._palette = palette
        # Note: self._w is used by tkinter internally as the widget path name,
        # so use _btn_w / _btn_h / _btn_r for our geometry.
        self._btn_w, self._btn_h, self._btn_r = width, height, radius
        self._font = font
        self._hover = False
        self._bg_img = None  # must retain reference or PhotoImage gets GC'd
        self._redraw()
        self.bind("<Button-1>", lambda e: self._cmd() if self._cmd else None)
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))

    def _set_hover(self, on):
        self._hover = on
        self._redraw()

    def _redraw(self):
        from PIL import Image, ImageDraw, ImageTk
        p = self._palette
        if self._primary:
            fill = p["accent_hv"] if self._hover else p["accent"]
            text_fg = p["accent_fg"]
            outline = fill
        else:
            fill = p["hover"] if self._hover else p["window"]
            text_fg = p["text"]
            outline = p["border"]
        # Supersample for anti-aliased edges.
        scale = 3
        W, H, R = self._btn_w * scale, self._btn_h * scale, self._btn_r * scale
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        draw.rounded_rectangle([0, 0, W - 1, H - 1], radius=R,
                               fill=fill, outline=outline, width=scale)
        img = img.resize((self._btn_w, self._btn_h), Image.LANCZOS)
        self._bg_img = ImageTk.PhotoImage(img)
        self.delete("all")
        self.configure(bg=p["window"])
        self.create_image(0, 0, image=self._bg_img, anchor="nw")
        self.create_text(self._btn_w // 2, self._btn_h // 2, text=self._text,
                         fill=text_fg, font=self._font)

    def re_theme(self, palette):
        self._palette = palette
        self._redraw()


def _make_scrollable(parent, palette):
    """Wrap a tab frame with a vertical-scrolling canvas. Returns the inner
    frame callers should pack their widgets into."""
    container = ttk.Frame(parent, style="Content.TFrame")
    container.pack(fill="both", expand=True)

    canvas = tk.Canvas(container, highlightthickness=0, bd=0,
                       bg=palette["content"])
    vsb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=vsb.set)
    canvas.pack(side="left", fill="both", expand=True)
    vsb.pack(side="right", fill="y")

    inner = ttk.Frame(canvas, padding=20)
    inner_id = canvas.create_window((0, 0), window=inner, anchor="nw")

    def _on_inner_configure(_event):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def _on_canvas_configure(event):
        canvas.itemconfigure(inner_id, width=event.width)

    inner.bind("<Configure>", _on_inner_configure)
    canvas.bind("<Configure>", _on_canvas_configure)

    # Mousewheel only while the pointer is over this canvas — otherwise
    # every tab's canvas would fight for wheel events.
    def _on_wheel(event):
        canvas.yview_scroll(int(-event.delta / 120), "units")

    def _bind_wheel(_e):
        canvas.bind_all("<MouseWheel>", _on_wheel)

    def _unbind_wheel(_e):
        canvas.unbind_all("<MouseWheel>")

    canvas.bind("<Enter>", _bind_wheel)
    canvas.bind("<Leave>", _unbind_wheel)
    return inner, canvas


class KodaSettings(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Koda Settings")
        self.resizable(True, True)

        self.config_data = load_config()
        # First launch: follow the OS apps-theme pref. Once the user clicks the
        # toggle, we persist their explicit choice and stop auto-following.
        self._theme_name = self.config_data.get("ui_theme") or _detect_system_theme()
        self._custom_words = self._load_custom_words_data()
        self._profiles_data = self._load_profiles_data()
        self._filler_words = self._load_filler_words_data()
        self._snippets = dict(self.config_data.get("snippets", {}))

        # Track dialog toplevels + rounded buttons + scroll canvases so the
        # theme toggle can restyle all of them on switch.
        self._open_dialogs = []
        self._rounded_buttons = []
        self._scroll_canvases = []

        self._style = ttk.Style()
        self._style.theme_use("clam")

        # Window titlebar / taskbar icon.
        try:
            self.iconbitmap(ICO_PATH)
        except tk.TclError:
            pass

        # Apply theme BEFORE building UI — RoundedButton and _make_scrollable
        # read the palette at construction time.
        self._apply_theme(self._theme_name)
        self._build_ui()

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.update_idletasks()
        self.geometry("680x640")
        self.minsize(620, 540)

    # ---------- Theme plumbing ----------

    def _palette(self):
        return THEMES[self._theme_name]

    def _apply_theme(self, name):
        self._theme_name = name
        t = THEMES[name]
        self.configure(bg=t["window"])

        s = self._style
        s.configure(".",               background=t["window"],  foreground=t["text"],     font=("Segoe UI", 10))
        s.configure("TFrame",          background=t["content"])
        s.configure("Chrome.TFrame",   background=t["window"])
        s.configure("TLabel",          background=t["content"], foreground=t["text"],     font=("Segoe UI", 10))
        s.configure("Chrome.TLabel",   background=t["window"],  foreground=t["text"],     font=("Segoe UI", 10))
        s.configure("Title.TLabel",    background=t["window"],  foreground=t["text"],     font=("Segoe UI", 13, "bold"))
        s.configure("Header.TLabel",   background=t["content"], foreground=t["text"],     font=("Segoe UI", 11, "bold"))
        s.configure("Dim.TLabel",      background=t["content"], foreground=t["text_dim"], font=("Segoe UI", 9))
        s.configure("Success.TLabel",  background=t["content"], foreground=t["success"],  font=("Segoe UI", 10))

        s.configure("TCheckbutton",    background=t["content"], foreground=t["text"],     font=("Segoe UI", 10))
        s.map("TCheckbutton",          background=[("active", t["content"])])
        s.configure("TRadiobutton",    background=t["content"], foreground=t["text"],     font=("Segoe UI", 10))
        s.map("TRadiobutton",          background=[("active", t["content"])])

        # Default button — used for the tray-style secondary actions inside tabs.
        s.configure("TButton",
                    background=t["content"], foreground=t["text"],
                    bordercolor=t["border"], lightcolor=t["border"], darkcolor=t["border"],
                    focusthickness=0, padding=(12, 6), font=("Segoe UI", 10))
        s.map("TButton",
              background=[("active", t["hover"]), ("pressed", t["hover"])],
              bordercolor=[("active", t["border"])])

        s.configure("Primary.TButton",
                    background=t["accent"], foreground=t["accent_fg"],
                    bordercolor=t["accent"], lightcolor=t["accent"], darkcolor=t["accent"],
                    focusthickness=0, padding=(18, 8), font=("Segoe UI", 10, "bold"))
        s.map("Primary.TButton",
              background=[("active", t["accent_hv"]), ("pressed", t["accent_hv"])],
              foreground=[("active", t["accent_fg"])],
              bordercolor=[("active", t["accent_hv"])])

        s.configure("Secondary.TButton",
                    background=t["window"], foreground=t["text"],
                    bordercolor=t["border"], lightcolor=t["border"], darkcolor=t["border"],
                    focusthickness=0, padding=(18, 8), font=("Segoe UI", 10))
        s.map("Secondary.TButton",
              background=[("active", t["hover"]), ("pressed", t["hover"])])

        # Toggle pill for the theme switch.
        s.configure("Toggle.TButton",
                    background=t["window"], foreground=t["text_dim"],
                    bordercolor=t["border"], lightcolor=t["border"], darkcolor=t["border"],
                    focusthickness=0, padding=(10, 4), font=("Segoe UI", 9))
        s.map("Toggle.TButton",
              background=[("active", t["hover"]), ("pressed", t["hover"])],
              foreground=[("active", t["text"])])

        s.configure("TCombobox",
                    fieldbackground=t["content"], background=t["content"],
                    foreground=t["text"], bordercolor=t["border"],
                    lightcolor=t["border"], darkcolor=t["border"],
                    arrowcolor=t["text"], selectbackground=t["accent"],
                    selectforeground=t["accent_fg"], font=("Segoe UI", 10))
        s.map("TCombobox",
              fieldbackground=[("readonly", t["content"])],
              foreground=[("readonly", t["text"])],
              selectbackground=[("readonly", t["content"])],
              selectforeground=[("readonly", t["text"])])

        s.configure("TEntry",
                    fieldbackground=t["content"], foreground=t["text"],
                    bordercolor=t["border"], lightcolor=t["border"], darkcolor=t["border"],
                    insertcolor=t["text"], font=("Segoe UI", 10))

        s.configure("TSeparator", background=t["border"])

        s.configure("TNotebook", background=t["window"], borderwidth=0, tabmargins=(2, 6, 2, 0))
        s.configure("TNotebook.Tab",
                    background=t["window"], foreground=t["text_dim"],
                    bordercolor=t["border"], lightcolor=t["window"], darkcolor=t["window"],
                    padding=(12, 8), font=("Segoe UI", 10))
        s.map("TNotebook.Tab",
              background=[("selected", t["content"]), ("active", t["hover"])],
              foreground=[("selected", t["text"]), ("active", t["text"])],
              lightcolor=[("selected", t["content"])],
              darkcolor=[("selected", t["content"])])
        # Nested notebook (inside Words tab) uses tighter tabs since it lives
        # inside the already-padded outer tab content.
        s.configure("Sub.TNotebook", background=t["content"], borderwidth=0, tabmargins=(0, 4, 0, 0))
        s.configure("Sub.TNotebook.Tab",
                    background=t["content"], foreground=t["text_dim"],
                    bordercolor=t["border"], lightcolor=t["content"], darkcolor=t["content"],
                    padding=(10, 6), font=("Segoe UI", 9))
        s.map("Sub.TNotebook.Tab",
              background=[("selected", t["window"]), ("active", t["hover"])],
              foreground=[("selected", t["text"]), ("active", t["text"])],
              lightcolor=[("selected", t["window"])],
              darkcolor=[("selected", t["window"])])

        s.configure("Treeview",
                    background=t["content"], foreground=t["text"],
                    fieldbackground=t["content"], bordercolor=t["border"],
                    font=("Segoe UI", 10))
        s.map("Treeview",
              background=[("selected", t["tree_sel"])],
              foreground=[("selected", t["text"])])
        s.configure("Treeview.Heading",
                    background=t["window"], foreground=t["text"],
                    bordercolor=t["border"], font=("Segoe UI", 10, "bold"))
        s.map("Treeview.Heading",
              background=[("active", t["hover"])])

        s.configure("Vertical.TScrollbar",
                    background=t["window"], troughcolor=t["window"],
                    bordercolor=t["border"], arrowcolor=t["text"])

        # Re-theme any open Toplevel dialogs.
        for dlg in list(self._open_dialogs):
            try:
                dlg.configure(bg=t["window"])
            except tk.TclError:
                self._open_dialogs.remove(dlg)

        # Refresh theme toggle label.
        if hasattr(self, "_theme_btn"):
            self._theme_btn.configure(text=self._theme_toggle_label())

        # Repaint canvas-based rounded buttons.
        for btn in getattr(self, "_rounded_buttons", []):
            try:
                btn.re_theme(t)
            except tk.TclError:
                pass

        # Update scroll canvas backgrounds.
        for canvas in getattr(self, "_scroll_canvases", []):
            try:
                canvas.configure(bg=t["content"])
            except tk.TclError:
                pass

    def _theme_toggle_label(self):
        return "\u2600 Light" if self._theme_name == "dark" else "\U0001F319 Dark"

    def _toggle_theme(self):
        new_name = "dark" if self._theme_name == "light" else "light"
        self._apply_theme(new_name)
        self.config_data["ui_theme"] = new_name
        save_config(self.config_data)

    def _register_dialog(self, dlg):
        """Apply current window bg to a Toplevel and track it for theme toggles."""
        dlg.configure(bg=self._palette()["window"])
        self._open_dialogs.append(dlg)
        dlg.bind("<Destroy>", lambda e, d=dlg: self._open_dialogs.remove(d) if e.widget is d and d in self._open_dialogs else None)

    # ---------- Layout ----------

    def _build_ui(self):
        # Bottom action bar — packed first so tall tabs can't push it off-screen.
        btn_frame = ttk.Frame(self, style="Chrome.TFrame")
        btn_frame.pack(side="bottom", fill="x", padx=16, pady=(8, 14))
        save_btn = RoundedButton(btn_frame, "Save", self.save_and_close,
                                 primary=True, palette=self._palette())
        save_btn.pack(side="right")
        cancel_btn = RoundedButton(btn_frame, "Cancel", self.on_close,
                                   primary=False, palette=self._palette())
        cancel_btn.pack(side="right", padx=(0, 10))
        self._rounded_buttons.extend([save_btn, cancel_btn])

        sep = ttk.Separator(self, orient="horizontal")
        sep.pack(side="bottom", fill="x", padx=16)

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=16, pady=(14, 0))

        # Only wrap the long tabs (General, Advanced) in a scroll canvas.
        # Hotkeys, Speech, and Words fit on-screen and a scroll wrapper would
        # leave blank space + a pointless scrollbar.
        gen_tab = ttk.Frame(notebook)
        hk_tab  = ttk.Frame(notebook, padding=20)
        sp_tab  = ttk.Frame(notebook, padding=20)
        wd_tab  = ttk.Frame(notebook, padding=20)
        adv_tab = ttk.Frame(notebook)

        notebook.add(gen_tab,  text="  General  ")
        notebook.add(hk_tab,   text="  Hotkeys  ")
        notebook.add(sp_tab,   text="  Speech  ")
        notebook.add(wd_tab,   text="  Words  ")
        notebook.add(adv_tab,  text="  Advanced  ")

        gen_inner, gen_canvas = _make_scrollable(gen_tab, self._palette())
        adv_inner, adv_canvas = _make_scrollable(adv_tab, self._palette())
        self._scroll_canvases.extend([gen_canvas, adv_canvas])

        self._build_general_tab(gen_inner)
        self._build_hotkeys_tab(hk_tab)
        self._build_speech_tab(sp_tab)
        self._build_words_tab(wd_tab)
        self._build_advanced_tab(adv_inner)

    def _section_header(self, parent, text, first=False):
        ttk.Label(parent, text=text, style="Header.TLabel").pack(
            anchor="w", pady=(0 if first else 16, 6))

    def _build_general_tab(self, parent):
        self._section_header(parent, "Recording Mode", first=True)
        self.mode_var = tk.StringVar(value=self.config_data.get("hotkey_mode", "hold"))
        ttk.Radiobutton(parent, text="Hold-to-talk  (hold key while speaking)",
                        variable=self.mode_var, value="hold").pack(anchor="w", pady=1)
        ttk.Radiobutton(parent, text="Toggle  (press once, auto-stops on silence)",
                        variable=self.mode_var, value="toggle").pack(anchor="w", pady=1)

        self._section_header(parent, "Output")
        self.output_var = tk.StringVar(value=self.config_data.get("output_mode", "auto_paste"))
        ttk.Radiobutton(parent, text="Auto-paste  (types into the active window)",
                        variable=self.output_var, value="auto_paste").pack(anchor="w", pady=1)
        ttk.Radiobutton(parent, text="Clipboard only  (no paste)",
                        variable=self.output_var, value="clipboard").pack(anchor="w", pady=1)

        self._section_header(parent, "Features")
        checks = [
            ("sound_effects",                       "sound_var",       "Sound effects",                              True,  None),
            ("post_processing.remove_filler_words", "filler_var",      "Remove filler words  (um, uh, you know)",    True,  "post_processing"),
            ("streaming",                           "stream_var",      "Streaming transcription  (live preview)",    True,  None),
            ("post_processing.auto_format",         "autoformat_var",  "Auto-format  (numbers, dates, punctuation)", True,  "post_processing"),
            ("voice_commands",                      "voicecmds_var",   "Voice commands  (select all, undo, new line)", True, None),
        ]
        for cfg_key, attr, label, default, section in checks:
            if section:
                sub_key = cfg_key.split(".")[1]
                val = self.config_data.get(section, {}).get(sub_key, default)
            else:
                val = self.config_data.get(cfg_key, default)
            var = tk.BooleanVar(value=val)
            setattr(self, attr, var)
            ttk.Checkbutton(parent, text=label, variable=var).pack(anchor="w", pady=2)

    def _build_hotkeys_tab(self, parent):
        FKEY_OPTIONS = ["f1","f2","f3","f4","f5","f6","f7","f8","f9","f10","f11","f12"]
        DICT_OPTIONS = ["ctrl+space", "ctrl+alt+d"] + FKEY_OPTIONS
        PROMPT_OPTIONS = [f"ctrl+f{n}" for n in range(1, 13)] + FKEY_OPTIONS

        self._section_header(parent, "Hotkey Assignments", first=True)

        self.hk_dict_var    = tk.StringVar(value=self.config_data.get("hotkey_dictation",          "ctrl+space"))
        self.hk_cmd_var     = tk.StringVar(value=self.config_data.get("hotkey_command",             "f8"))
        self.hk_prompt_var  = tk.StringVar(value=self.config_data.get("hotkey_prompt",              "ctrl+f9"))
        self.hk_corr_var    = tk.StringVar(value=self.config_data.get("hotkey_correction",          "f7"))
        self.hk_read_var    = tk.StringVar(value=self.config_data.get("hotkey_readback",            "f6"))
        self.hk_readsel_var = tk.StringVar(value=self.config_data.get("hotkey_readback_selected",   "f5"))

        rows = [
            ("Dictation",     self.hk_dict_var,    DICT_OPTIONS),
            ("Command",       self.hk_cmd_var,      FKEY_OPTIONS),
            ("Prompt Assist", self.hk_prompt_var,   PROMPT_OPTIONS),
            ("Correction",    self.hk_corr_var,     FKEY_OPTIONS),
            ("Read back",     self.hk_read_var,     FKEY_OPTIONS),
            ("Read selected", self.hk_readsel_var,  FKEY_OPTIONS),
        ]
        f = ttk.Frame(parent)
        f.pack(fill="x", pady=(4, 0))
        for i, (label, var, opts) in enumerate(rows):
            ttk.Label(f, text=label).grid(row=i, column=0, sticky="w", padx=(0, 18), pady=6)
            ttk.Combobox(f, textvariable=var, values=opts, width=18, state="readonly").grid(row=i, column=1, sticky="w", pady=6)

    def _build_speech_tab(self, parent):
        self._section_header(parent, "Whisper Model", first=True)

        f = ttk.Frame(parent)
        f.pack(fill="x")

        ttk.Label(f, text="Model size").grid(row=0, column=0, sticky="w", padx=(0, 18), pady=6)
        self.model_var = tk.StringVar(value=self.config_data.get("model_size", "base"))
        ttk.Combobox(f, textvariable=self.model_var, width=24,
                     values=["tiny", "base", "small", "medium", "large-v2", "large-v3",
                             "large-v3-turbo", "distil-large-v3", "distil-medium.en"],
                     state="readonly").grid(row=0, column=1, sticky="w", pady=6)

        ttk.Label(f, text="Language").grid(row=1, column=0, sticky="w", padx=(0, 18), pady=6)
        self.lang_var = tk.StringVar(value=self.config_data.get("language", "en"))
        ttk.Combobox(f, textvariable=self.lang_var, width=24,
                     values=["en","es","fr","de","pt","zh","ja","ko","ar","hi","ru","it","nl","pl","tr","auto"],
                     state="readonly").grid(row=1, column=1, sticky="w", pady=6)

        ttk.Label(parent,
                  text="Larger models are more accurate but slower to load.\n"
                       "tiny/base = fastest  ·  small = best balance  ·  large = highest accuracy",
                  style="Dim.TLabel").pack(anchor="w", pady=(14, 0))

    def _build_words_tab(self, parent):
        sub = ttk.Notebook(parent, style="Sub.TNotebook")
        sub.pack(fill="both", expand=True)

        cw_tab = ttk.Frame(sub, padding=10)
        fw_tab = ttk.Frame(sub, padding=10)
        sn_tab = ttk.Frame(sub, padding=10)
        pr_tab = ttk.Frame(sub, padding=10)

        sub.add(cw_tab, text="Custom")
        sub.add(fw_tab, text="Fillers")
        sub.add(sn_tab, text="Snippets")
        sub.add(pr_tab, text="Profiles")

        # Custom Words
        ttk.Label(cw_tab, text="Replace misheard words with the correct version:",
                  style="Dim.TLabel").pack(anchor="w", pady=(0, 8))
        tf = ttk.Frame(cw_tab); tf.pack(fill="both", expand=True)
        self._vocab_tree = ttk.Treeview(tf, columns=("misheard","correct"), show="headings", height=6, selectmode="browse")
        self._vocab_tree.heading("misheard", text="Misheard"); self._vocab_tree.heading("correct", text="Replace with")
        self._vocab_tree.column("misheard", width=140, minwidth=80, anchor="w", stretch=True)
        self._vocab_tree.column("correct",  width=180, minwidth=100, anchor="w", stretch=True)
        self._vocab_tree.pack(side="left", fill="both", expand=True)
        s = ttk.Scrollbar(tf, orient="vertical", command=self._vocab_tree.yview)
        self._vocab_tree.configure(yscrollcommand=s.set); s.pack(side="left", fill="y")
        self._refresh_vocab_tree()
        # Two rows: CRUD on top, I/O on bottom. Always fits regardless of
        # window width / DPI scaling.
        br1 = ttk.Frame(cw_tab); br1.pack(anchor="w", pady=(10, 0))
        for lbl, cmd in [("Add", self._add_vocab_entry),
                         ("Edit", self._edit_vocab_entry),
                         ("Remove", self._remove_vocab_entry)]:
            ttk.Button(br1, text=lbl, command=cmd).pack(side="left", padx=(0, 6))
        br2 = ttk.Frame(cw_tab); br2.pack(anchor="w", pady=(6, 0))
        for lbl, cmd in [("Import", self._import_vocab),
                         ("Export", self._export_vocab)]:
            ttk.Button(br2, text=lbl, command=cmd).pack(side="left", padx=(0, 6))

        # Filler Words
        ttk.Label(fw_tab, text="Removed from speech when filler removal is enabled:",
                  style="Dim.TLabel").pack(anchor="w", pady=(0, 8))
        ff = ttk.Frame(fw_tab); ff.pack(fill="both", expand=True)
        self._filler_tree = ttk.Treeview(ff, columns=("word",), show="headings", height=6, selectmode="browse")
        self._filler_tree.heading("word", text="Word / Phrase")
        self._filler_tree.column("word", width=320, minwidth=160, anchor="w", stretch=True)
        self._filler_tree.pack(side="left", fill="both", expand=True)
        fs = ttk.Scrollbar(ff, orient="vertical", command=self._filler_tree.yview)
        self._filler_tree.configure(yscrollcommand=fs.set); fs.pack(side="left", fill="y")
        self._refresh_filler_tree()
        fbr = ttk.Frame(fw_tab); fbr.pack(anchor="w", pady=(10, 0))
        for lbl, cmd in [("Add", self._add_filler_word), ("Remove", self._remove_filler_word), ("Restore defaults", self._restore_filler_defaults)]:
            ttk.Button(fbr, text=lbl, command=cmd).pack(side="left", padx=(0, 6))

        # Snippets
        ttk.Label(sn_tab, text="Say the trigger word alone to paste the full expansion:",
                  style="Dim.TLabel").pack(anchor="w", pady=(0, 8))
        sf = ttk.Frame(sn_tab); sf.pack(fill="both", expand=True)
        self._snippets_tree = ttk.Treeview(sf, columns=("trigger","expansion"), show="headings", height=6, selectmode="browse")
        self._snippets_tree.heading("trigger", text="Trigger"); self._snippets_tree.heading("expansion", text="Expansion")
        self._snippets_tree.column("trigger",   width=110, minwidth=70,  anchor="w", stretch=False)
        self._snippets_tree.column("expansion", width=220, minwidth=120, anchor="w", stretch=True)
        self._snippets_tree.pack(side="left", fill="both", expand=True)
        ss = ttk.Scrollbar(sf, orient="vertical", command=self._snippets_tree.yview)
        self._snippets_tree.configure(yscrollcommand=ss.set); ss.pack(side="left", fill="y")
        self._refresh_snippets_tree()
        sbr = ttk.Frame(sn_tab); sbr.pack(anchor="w", pady=(10, 0))
        for lbl, cmd in [("Add", self._add_snippet), ("Edit", self._edit_snippet), ("Remove", self._remove_snippet)]:
            ttk.Button(sbr, text=lbl, command=cmd).pack(side="left", padx=(0, 6))

        # App Profiles
        ttk.Label(pr_tab, text="Auto-switch settings based on the active window:",
                  style="Dim.TLabel").pack(anchor="w", pady=(0, 8))
        pf = ttk.Frame(pr_tab); pf.pack(fill="both", expand=True)
        self._profile_tree = ttk.Treeview(pf, columns=("name","match","overrides"), show="headings", height=6, selectmode="browse")
        self._profile_tree.heading("name", text="Profile"); self._profile_tree.heading("match", text="Matches"); self._profile_tree.heading("overrides", text="Overrides")
        self._profile_tree.column("name",      width=90,  minwidth=70,  anchor="w", stretch=False)
        self._profile_tree.column("match",     width=130, minwidth=100, anchor="w", stretch=True)
        self._profile_tree.column("overrides", width=120, minwidth=90,  anchor="w", stretch=True)
        self._profile_tree.pack(side="left", fill="both", expand=True)
        ps = ttk.Scrollbar(pf, orient="vertical", command=self._profile_tree.yview)
        self._profile_tree.configure(yscrollcommand=ps.set); ps.pack(side="left", fill="y")
        self._refresh_profile_tree()
        pbr = ttk.Frame(pr_tab); pbr.pack(anchor="w", pady=(10, 0))
        for lbl, cmd in [("Add", self._add_profile), ("Edit", self._edit_profile), ("Remove", self._remove_profile), ("Edit JSON", self._open_profiles)]:
            ttk.Button(pbr, text=lbl, command=cmd).pack(side="left", padx=(0, 6))

    def _build_advanced_tab(self, parent):
        self._section_header(parent, "Appearance", first=True)
        ar = ttk.Frame(parent); ar.pack(fill="x", pady=(0, 4))
        ttk.Label(ar, text="Theme").pack(side="left", padx=(0, 12))
        self._theme_btn = ttk.Button(ar, text=self._theme_toggle_label(),
                                     style="Toggle.TButton", command=self._toggle_theme)
        self._theme_btn.pack(side="left")
        ttk.Label(ar, text="  (follows system on first launch)",
                  style="Dim.TLabel").pack(side="left", padx=(10, 0))

        self._section_header(parent, "Behavior")

        behavior_checks = [
            ("overlay_enabled",                 "overlay_var",   "Floating status overlay",                   False, None),
            ("profiles_enabled",                "profiles_var",  "Per-app profiles  (auto-switch by window)", True,  None),
            ("noise_reduction",                 "noise_var",     "Noise reduction  (for noisy environments)", False, None),
            ("post_processing.code_vocabulary", "code_var",      "Code vocabulary  (command mode symbols)",   False, "post_processing"),
        ]
        for cfg_key, attr, label, default, section in behavior_checks:
            if section:
                sub_key = cfg_key.split(".")[1]
                val = self.config_data.get(section, {}).get(sub_key, default)
            else:
                val = self.config_data.get(cfg_key, default)
            var = tk.BooleanVar(value=val)
            setattr(self, attr, var)
            ttk.Checkbutton(parent, text=label, variable=var).pack(anchor="w", pady=2)

        self._section_header(parent, "Translation")
        self.trans_var = tk.BooleanVar(value=self.config_data.get("translation", {}).get("enabled", False))
        ttk.Checkbutton(parent, text="Enable translation  (speak one language, output another)",
                        variable=self.trans_var).pack(anchor="w", pady=2)
        lf = ttk.Frame(parent); lf.pack(fill="x", pady=(6, 0))
        ttk.Label(lf, text="Target language").pack(side="left", padx=(0, 12))
        self.trans_lang_var = tk.StringVar(value=self.config_data.get("translation", {}).get("target_language", "English"))
        ttk.Combobox(lf, textvariable=self.trans_lang_var, width=18,
                     values=["English","Spanish","French","German","Portuguese","Japanese","Korean","Chinese","Italian","Russian"],
                     state="readonly").pack(side="left")
        ttk.Label(lf, text="English = Whisper  ·  Others = Ollama",
                  style="Dim.TLabel").pack(side="left", padx=(12, 0))

        self._section_header(parent, "Read-back Voice")
        self.voices = self._get_voices()
        voice_names = [name for name, _ in self.voices]
        current_voice = self.config_data.get("tts", {}).get("voice", voice_names[0] if voice_names else "")
        rf = ttk.Frame(parent); rf.pack(fill="x")
        ttk.Label(rf, text="Voice").grid(row=0, column=0, sticky="w", padx=(0, 14), pady=5)
        self.voice_var = tk.StringVar(value=current_voice)
        if voice_names:
            ttk.Combobox(rf, textvariable=self.voice_var, width=30, values=voice_names, state="readonly").grid(row=0, column=1, sticky="w", pady=5)
        ttk.Label(rf, text="Speed").grid(row=1, column=0, sticky="w", padx=(0, 14), pady=5)
        self.speed_var = tk.StringVar(value=self.config_data.get("tts", {}).get("rate", "normal"))
        ttk.Combobox(rf, textvariable=self.speed_var, width=30, values=["slow","normal","fast"], state="readonly").grid(row=1, column=1, sticky="w", pady=5)

        self._section_header(parent, "Performance")
        current_compute = self.config_data.get("compute_type", "int8")
        mode_text = "Power Mode  (NVIDIA GPU)" if current_compute == "float16" else "Standard Mode  (CPU)"
        ttk.Label(parent, text=f"Current: {mode_text}").pack(anchor="w")
        self._perf_status_var = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self._perf_status_var, style="Success.TLabel").pack(anchor="w", pady=(2, 0))
        pbr = ttk.Frame(parent); pbr.pack(anchor="w", pady=(8, 0))
        ttk.Button(pbr, text="Check GPU", command=self._check_gpu).pack(side="left", padx=(0, 6))
        if current_compute != "float16":
            ttk.Button(pbr, text="Enable Power Mode", command=self._enable_power_mode).pack(side="left", padx=(0, 6))
        else:
            ttk.Button(pbr, text="Switch to Standard Mode", command=self._disable_power_mode).pack(side="left", padx=(0, 6))
        ttk.Button(pbr, text="Learn more", command=self._open_cuda_url).pack(side="left")

        self._section_header(parent, "History")
        hbr = ttk.Frame(parent); hbr.pack(anchor="w")
        ttk.Button(hbr, text="View transcript history", command=self._open_history).pack(side="left", padx=(0, 8))
        ttk.Button(hbr, text="Export history", command=self._export_history).pack(side="left")

    def _get_voices(self):
        try:
            import pyttsx3
            engine = pyttsx3.init()
            return [(v.name, v.id) for v in engine.getProperty('voices')]
        except Exception:
            return []

    def save(self):
        cfg = self.config_data

        cfg["hotkey_dictation"] = self.hk_dict_var.get()
        cfg["hotkey_command"] = self.hk_cmd_var.get()
        cfg["hotkey_prompt"] = self.hk_prompt_var.get()
        cfg["hotkey_correction"] = self.hk_corr_var.get()
        cfg["hotkey_readback"] = self.hk_read_var.get()
        cfg["hotkey_readback_selected"] = self.hk_readsel_var.get()
        cfg["model_size"] = self.model_var.get()
        cfg["language"] = self.lang_var.get()
        cfg["hotkey_mode"] = self.mode_var.get()
        cfg["output_mode"] = self.output_var.get()
        cfg["sound_effects"] = self.sound_var.get()
        cfg["noise_reduction"] = self.noise_var.get()
        cfg["streaming"] = self.stream_var.get()
        cfg["overlay_enabled"] = self.overlay_var.get()
        cfg["profiles_enabled"] = self.profiles_var.get()
        cfg["voice_commands"] = self.voicecmds_var.get()
        cfg["ui_theme"] = self._theme_name

        trans = cfg.setdefault("translation", {})
        trans["enabled"] = self.trans_var.get()
        trans["target_language"] = self.trans_lang_var.get()

        pp = cfg.setdefault("post_processing", {})
        pp["remove_filler_words"] = self.filler_var.get()
        pp["code_vocabulary"] = self.code_var.get()
        pp["auto_format"] = self.autoformat_var.get()

        tts = cfg.setdefault("tts", {})
        tts["voice"] = self.voice_var.get()
        tts["rate"] = self.speed_var.get()

        cfg["snippets"] = self._snippets
        save_config(cfg)
        self._save_custom_words_data()
        self._save_profiles_data()
        self._save_filler_words_data()

    def save_and_close(self):
        before = {k: self.config_data.get(k) for k in RESTART_REQUIRED_KEYS}
        self.save()
        changed = _restart_required_changes(before, self.config_data)
        if changed:
            messagebox.showinfo(
                "Restart Koda to apply changes",
                "These settings take effect after you quit Koda from the tray and relaunch:\n\n"
                + "\n".join(f"  \u2022 {k}" for k in changed),
            )
        self.destroy()

    def _open_custom_words(self):
        """Open custom_words.json in the default editor."""
        from config import open_custom_words_file
        open_custom_words_file()

    def _open_profiles(self):
        """Open profiles.json in the default editor."""
        profiles_path = os.path.join(SCRIPT_DIR, "profiles.json")
        if not os.path.exists(profiles_path):
            from profiles import load_profiles
            load_profiles()  # Creates default file
        os.startfile(profiles_path)

    # --- Per-App Profile CRUD ---

    def _load_profiles_data(self):
        from profiles import load_profiles
        return load_profiles()

    def _save_profiles_data(self):
        from profiles import save_profiles
        save_profiles(self._profiles_data)

    def _profile_summary(self, profile):
        """Return (match_str, overrides_str) for Treeview display."""
        match_rules = profile.get("match", {})
        parts = []
        if "process" in match_rules:
            parts.append(match_rules["process"])
        if "title" in match_rules:
            t = match_rules["title"]
            parts.append(f"title:{t[:18]}" if len(t) > 18 else f"title:{t}")
        match_str = ", ".join(parts) if parts else "(none)"

        pp = profile.get("settings", {}).get("post_processing", {})
        overrides = []
        for key, label in [("code_vocabulary", "code"), ("remove_filler_words", "filler"),
                            ("auto_capitalize", "capitalize"), ("auto_format", "format")]:
            if key in pp:
                overrides.append(f"{label}={'on' if pp[key] else 'off'}")
        override_str = ", ".join(overrides) if overrides else "inherit all"
        return match_str, override_str

    def _refresh_profile_tree(self):
        self._profile_tree.delete(*self._profile_tree.get_children())
        for name, profile in self._profiles_data.items():
            if name.startswith("_") or not isinstance(profile, dict):
                continue
            match_str, override_str = self._profile_summary(profile)
            self._profile_tree.insert("", "end", iid=name, values=(name, match_str, override_str))

    def _profile_dialog(self, title, name="", profile=None):
        """Add/Edit dialog. Returns (name, profile_dict) or None."""
        if profile is None:
            profile = {}
        match_rules = profile.get("match", {})
        pp_overrides = profile.get("settings", {}).get("post_processing", {})

        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.geometry("460x320")
        dlg.resizable(False, False)
        self._register_dialog(dlg)
        dlg.grab_set()

        result = [None]

        ttk.Label(dlg, text="Profile name").grid(row=0, column=0, sticky="w", padx=14, pady=(16, 4))
        name_var = tk.StringVar(value=name)
        ttk.Entry(dlg, textvariable=name_var, width=28).grid(row=0, column=1, padx=(0, 14), pady=(16, 4))

        ttk.Label(dlg, text="Match process (e.g. code.exe)").grid(row=1, column=0, sticky="w", padx=14, pady=4)
        proc_var = tk.StringVar(value=match_rules.get("process", ""))
        ttk.Entry(dlg, textvariable=proc_var, width=28).grid(row=1, column=1, padx=(0, 14), pady=4)

        ttk.Label(dlg, text="Match title regex (optional)").grid(row=2, column=0, sticky="w", padx=14, pady=4)
        title_var = tk.StringVar(value=match_rules.get("title", ""))
        ttk.Entry(dlg, textvariable=title_var, width=28).grid(row=2, column=1, padx=(0, 14), pady=4)

        ttk.Label(dlg, text="Overrides (inherit = base config)",
                  style="Dim.TLabel").grid(row=3, column=0, columnspan=2, sticky="w", padx=14, pady=(12, 4))

        override_vars = {}
        override_row = 4
        for key, label in [
            ("code_vocabulary", "Code vocabulary"),
            ("remove_filler_words", "Remove filler words"),
            ("auto_capitalize", "Auto-capitalize"),
            ("auto_format", "Auto-format"),
        ]:
            val = "on" if pp_overrides.get(key) is True else ("off" if pp_overrides.get(key) is False else "inherit")
            var = tk.StringVar(value=val)
            override_vars[key] = var
            ttk.Label(dlg, text=f"  {label}").grid(row=override_row, column=0, sticky="w", padx=14, pady=2)
            ttk.Combobox(dlg, textvariable=var, values=["inherit", "on", "off"],
                         state="readonly", width=10).grid(row=override_row, column=1, sticky="w",
                                                          padx=(0, 14), pady=2)
            override_row += 1

        def on_ok(*_):
            n = name_var.get().strip()
            if not n or n.startswith("_"):
                messagebox.showwarning("Koda", "Name required; cannot start with '_'.", parent=dlg)
                return
            proc = proc_var.get().strip().lower()
            ttl = title_var.get().strip()
            if not proc and not ttl:
                messagebox.showwarning("Koda", "At least one match rule (process or title) is required.", parent=dlg)
                return
            match = {}
            if proc:
                match["process"] = proc
            if ttl:
                match["title"] = ttl
            pp = {}
            for key, var in override_vars.items():
                if var.get() == "on":
                    pp[key] = True
                elif var.get() == "off":
                    pp[key] = False
            new_profile = {"match": match, "settings": {"post_processing": pp} if pp else {}}
            result[0] = (n, new_profile)
            dlg.destroy()

        btn_row = ttk.Frame(dlg)
        btn_row.grid(row=override_row, column=0, columnspan=2, pady=(14, 0))
        ttk.Button(btn_row, text="OK", style="Primary.TButton", command=on_ok).pack(side="left", padx=6)
        ttk.Button(btn_row, text="Cancel", style="Secondary.TButton", command=dlg.destroy).pack(side="left")

        dlg.wait_window()
        return result[0]

    def _add_profile(self):
        pair = self._profile_dialog("Add Profile")
        if pair:
            name, profile = pair
            self._profiles_data[name] = profile
            self._refresh_profile_tree()

    def _edit_profile(self):
        sel = self._profile_tree.selection()
        if not sel:
            messagebox.showinfo("Koda", "Select a profile to edit.", parent=self)
            return
        old_name = sel[0]
        old_profile = self._profiles_data.get(old_name, {})
        pair = self._profile_dialog("Edit Profile", old_name, old_profile)
        if pair:
            new_name, new_profile = pair
            if old_name != new_name:
                del self._profiles_data[old_name]
            self._profiles_data[new_name] = new_profile
            self._refresh_profile_tree()

    def _remove_profile(self):
        sel = self._profile_tree.selection()
        if not sel:
            messagebox.showinfo("Koda", "Select a profile to remove.", parent=self)
            return
        self._profiles_data.pop(sel[0], None)
        self._refresh_profile_tree()

    # --- Filler Words CRUD ---

    def _load_filler_words_data(self):
        from text_processing import load_filler_words
        return load_filler_words()

    def _save_filler_words_data(self):
        from text_processing import save_filler_words
        save_filler_words(self._filler_words)

    def _refresh_filler_tree(self):
        self._filler_tree.delete(*self._filler_tree.get_children())
        for word in self._filler_words:
            self._filler_tree.insert("", "end", values=(word,))

    def _add_filler_word(self):
        dlg = tk.Toplevel(self)
        dlg.title("Add Filler Word")
        dlg.geometry("360x120")
        dlg.resizable(False, False)
        self._register_dialog(dlg)
        dlg.grab_set()
        result = [None]
        ttk.Label(dlg, text="Word or phrase to remove").grid(row=0, column=0, sticky="w", padx=14, pady=(16, 4))
        word_var = tk.StringVar()
        entry = ttk.Entry(dlg, textvariable=word_var, width=28)
        entry.grid(row=0, column=1, padx=(0, 14), pady=(16, 4))
        def on_ok(*_):
            w = word_var.get().strip().lower()
            if not w:
                messagebox.showwarning("Koda", "Enter a word or phrase.", parent=dlg)
                return
            result[0] = w
            dlg.destroy()
        btn_row = ttk.Frame(dlg)
        btn_row.grid(row=1, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn_row, text="OK", style="Primary.TButton", command=on_ok).pack(side="left", padx=6)
        ttk.Button(btn_row, text="Cancel", style="Secondary.TButton", command=dlg.destroy).pack(side="left")
        entry.focus_set()
        entry.bind("<Return>", on_ok)
        dlg.wait_window()
        if result[0] and result[0] not in self._filler_words:
            self._filler_words.append(result[0])
            self._refresh_filler_tree()

    def _remove_filler_word(self):
        sel = self._filler_tree.selection()
        if not sel:
            messagebox.showinfo("Koda", "Select a word to remove.", parent=self)
            return
        word = self._filler_tree.item(sel[0], "values")[0]
        if word in self._filler_words:
            self._filler_words.remove(word)
        self._refresh_filler_tree()

    def _restore_filler_defaults(self):
        from text_processing import DEFAULT_FILLER_WORDS
        self._filler_words = list(DEFAULT_FILLER_WORDS)
        self._refresh_filler_tree()

    # --- Snippets CRUD ---

    def _refresh_snippets_tree(self):
        self._snippets_tree.delete(*self._snippets_tree.get_children())
        for trigger, expansion in self._snippets.items():
            display = expansion if len(expansion) <= 40 else expansion[:37] + "..."
            self._snippets_tree.insert("", "end", iid=trigger, values=(trigger, display))

    def _snippet_dialog(self, title, trigger="", expansion=""):
        """Add/Edit dialog. Returns (trigger, expansion) or None."""
        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.geometry("460x170")
        dlg.resizable(False, False)
        self._register_dialog(dlg)
        dlg.grab_set()
        result = [None]
        ttk.Label(dlg, text="Trigger phrase (say this alone)").grid(row=0, column=0, sticky="w", padx=14, pady=(16, 4))
        trig_var = tk.StringVar(value=trigger)
        trig_entry = ttk.Entry(dlg, textvariable=trig_var, width=30)
        trig_entry.grid(row=0, column=1, padx=(0, 14), pady=(16, 4))
        ttk.Label(dlg, text="Expansion (text to paste)").grid(row=1, column=0, sticky="w", padx=14, pady=4)
        exp_var = tk.StringVar(value=expansion)
        exp_entry = ttk.Entry(dlg, textvariable=exp_var, width=30)
        exp_entry.grid(row=1, column=1, padx=(0, 14), pady=4)
        def on_ok(*_):
            t = trig_var.get().strip().lower()
            e = exp_var.get().strip()
            if not t or not e:
                messagebox.showwarning("Koda", "Both fields are required.", parent=dlg)
                return
            result[0] = (t, e)
            dlg.destroy()
        btn_row = ttk.Frame(dlg)
        btn_row.grid(row=2, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(btn_row, text="OK", style="Primary.TButton", command=on_ok).pack(side="left", padx=6)
        ttk.Button(btn_row, text="Cancel", style="Secondary.TButton", command=dlg.destroy).pack(side="left")
        trig_entry.focus_set()
        trig_entry.bind("<Return>", lambda e: exp_entry.focus_set())
        exp_entry.bind("<Return>", on_ok)
        dlg.wait_window()
        return result[0]

    def _add_snippet(self):
        pair = self._snippet_dialog("Add Snippet")
        if pair:
            trigger, expansion = pair
            self._snippets[trigger] = expansion
            self._refresh_snippets_tree()

    def _edit_snippet(self):
        sel = self._snippets_tree.selection()
        if not sel:
            messagebox.showinfo("Koda", "Select a snippet to edit.", parent=self)
            return
        old_trigger = sel[0]
        old_expansion = self._snippets.get(old_trigger, "")
        pair = self._snippet_dialog("Edit Snippet", old_trigger, old_expansion)
        if pair:
            new_trigger, new_expansion = pair
            if old_trigger != new_trigger:
                del self._snippets[old_trigger]
            self._snippets[new_trigger] = new_expansion
            self._refresh_snippets_tree()

    def _remove_snippet(self):
        sel = self._snippets_tree.selection()
        if not sel:
            messagebox.showinfo("Koda", "Select a snippet to remove.", parent=self)
            return
        self._snippets.pop(sel[0], None)
        self._refresh_snippets_tree()

    # --- Custom Vocabulary CRUD ---

    def _load_custom_words_data(self):
        """Load custom_words.json into an ordered dict.

        On corruption: preserve the broken file as custom_words.json.corrupt.<ts>
        before returning defaults — so a subsequent Save cannot destroy the
        user's tuned vocabulary. Mirrors the profiles.load_profiles pattern.
        """
        if os.path.exists(CUSTOM_WORDS_PATH):
            try:
                with open(CUSTOM_WORDS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return dict(data) if isinstance(data, dict) else {}
            except (json.JSONDecodeError, OSError) as e:
                backup = f"{CUSTOM_WORDS_PATH}.corrupt.{int(time.time())}"
                try:
                    os.replace(CUSTOM_WORDS_PATH, backup)
                    logger.warning("custom_words.json corrupt (%s) — backed up to %s", e, backup)
                except OSError:
                    logger.error("custom_words.json corrupt (%s) and could not be backed up", e)
        return dict(DEFAULT_CUSTOM_WORDS)

    def _save_custom_words_data(self):
        """Write _custom_words back to custom_words.json."""
        with open(CUSTOM_WORDS_PATH, "w", encoding="utf-8") as f:
            json.dump(self._custom_words, f, indent=2)

    def _refresh_vocab_tree(self):
        """Repopulate the Treeview from _custom_words."""
        self._vocab_tree.delete(*self._vocab_tree.get_children())
        for misheard, correct in self._custom_words.items():
            self._vocab_tree.insert("", "end", values=(misheard, correct))

    def _vocab_dialog(self, title, misheard="", correct=""):
        """Show a small dialog for Add/Edit. Returns (misheard, correct) or None."""
        dlg = tk.Toplevel(self)
        dlg.title(title)
        dlg.geometry("380x150")
        dlg.resizable(False, False)
        self._register_dialog(dlg)
        dlg.grab_set()

        result = [None]

        ttk.Label(dlg, text="Misheard word/phrase").grid(row=0, column=0, sticky="w", padx=14, pady=(16, 4))
        mis_var = tk.StringVar(value=misheard)
        mis_entry = ttk.Entry(dlg, textvariable=mis_var, width=28)
        mis_entry.grid(row=0, column=1, padx=(0, 14), pady=(16, 4))

        ttk.Label(dlg, text="Replace with").grid(row=1, column=0, sticky="w", padx=14, pady=4)
        cor_var = tk.StringVar(value=correct)
        cor_entry = ttk.Entry(dlg, textvariable=cor_var, width=28)
        cor_entry.grid(row=1, column=1, padx=(0, 14), pady=4)

        def on_ok(*_):
            m = mis_var.get().strip().lower()
            c = cor_var.get().strip()
            if not m or not c:
                messagebox.showwarning("Koda", "Both fields are required.", parent=dlg)
                return
            result[0] = (m, c)
            dlg.destroy()

        btn_row = ttk.Frame(dlg)
        btn_row.grid(row=2, column=0, columnspan=2, pady=(12, 0))
        ttk.Button(btn_row, text="OK", style="Primary.TButton", command=on_ok).pack(side="left", padx=6)
        ttk.Button(btn_row, text="Cancel", style="Secondary.TButton", command=dlg.destroy).pack(side="left")

        mis_entry.focus_set()
        cor_entry.bind("<Return>", on_ok)
        mis_entry.bind("<Return>", lambda e: cor_entry.focus_set())

        dlg.wait_window()
        return result[0]

    def _add_vocab_entry(self):
        pair = self._vocab_dialog("Add Custom Word")
        if pair:
            misheard, correct = pair
            self._custom_words[misheard] = correct
            self._refresh_vocab_tree()

    def _edit_vocab_entry(self):
        sel = self._vocab_tree.selection()
        if not sel:
            messagebox.showinfo("Koda", "Select an entry to edit.", parent=self)
            return
        old_mis, old_cor = self._vocab_tree.item(sel[0], "values")
        pair = self._vocab_dialog("Edit Custom Word", old_mis, old_cor)
        if pair:
            new_mis, new_cor = pair
            if old_mis != new_mis:
                del self._custom_words[old_mis]
            self._custom_words[new_mis] = new_cor
            self._refresh_vocab_tree()

    def _remove_vocab_entry(self):
        sel = self._vocab_tree.selection()
        if not sel:
            messagebox.showinfo("Koda", "Select an entry to remove.", parent=self)
            return
        misheard, _ = self._vocab_tree.item(sel[0], "values")
        self._custom_words.pop(misheard, None)
        self._refresh_vocab_tree()

    def _import_vocab(self):
        filepath = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Import Custom Words",
            parent=self,
        )
        if not filepath:
            return
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("Expected a JSON object")
            self._custom_words.update({k.lower(): v for k, v in data.items()})
            self._refresh_vocab_tree()
            messagebox.showinfo("Koda", f"Imported {len(data)} entries.", parent=self)
        except Exception as e:
            messagebox.showerror("Koda", f"Import failed: {e}", parent=self)

    def _export_vocab(self):
        filepath = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            title="Export Custom Words",
            parent=self,
        )
        if not filepath:
            return
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(self._custom_words, f, indent=2)
            messagebox.showinfo("Koda", f"Exported to:\n{filepath}", parent=self)
        except Exception as e:
            messagebox.showerror("Koda", f"Export failed: {e}", parent=self)

    def _open_history(self):
        """Open a simple history viewer window."""
        try:
            from history import get_recent, search_history
        except ImportError:
            messagebox.showerror("Koda", "History module not found.")
            return

        t = self._palette()
        hist_win = tk.Toplevel(self)
        hist_win.title("Koda - Transcript History")
        hist_win.geometry("620x460")
        self._register_dialog(hist_win)

        top_frame = ttk.Frame(hist_win)
        top_frame.pack(fill="x", padx=12, pady=(12, 6))

        ttk.Label(top_frame, text="Search").pack(side="left", padx=(0, 8))
        search_var = tk.StringVar()
        search_entry = ttk.Entry(top_frame, textvariable=search_var, width=40)
        search_entry.pack(side="left", padx=(0, 6))

        text_widget = tk.Text(hist_win, bg=t["content"], fg=t["text"],
                              insertbackground=t["text"], selectbackground=t["accent"],
                              selectforeground=t["accent_fg"], relief="flat",
                              font=("Consolas", 10), wrap="word", state="disabled")
        text_widget.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        def refresh(query=None):
            if query:
                rows = search_history(query, limit=50)
            else:
                rows = get_recent(limit=50)
            text_widget.config(state="normal")
            text_widget.delete("1.0", "end")
            if not rows:
                text_widget.insert("end", "No transcriptions found.")
            else:
                for row in rows:
                    _id, ts, text, mode, dur = row
                    ts_short = ts[:19].replace("T", " ") if ts else ""
                    text_widget.insert("end", f"[{ts_short}] ({mode}, {dur:.1f}s)\n")
                    text_widget.insert("end", f"  {text}\n\n")
            text_widget.config(state="disabled")

        def on_search(*args):
            query = search_var.get().strip()
            refresh(query if query else None)

        ttk.Button(top_frame, text="Search", command=on_search).pack(side="left")
        search_entry.bind("<Return>", on_search)

        refresh()

    def _export_history(self):
        """Export transcript history to a text file."""
        try:
            from history import export_history
        except ImportError:
            messagebox.showerror("Koda", "History module not found.")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Export Transcript History",
        )
        if filepath:
            try:
                export_history(filepath)
                messagebox.showinfo("Koda", f"History exported to:\n{filepath}")
            except Exception as e:
                messagebox.showerror("Koda", f"Export failed: {e}")

    def _check_gpu(self):
        """Run GPU detection and report result in the UI."""
        self._perf_status_var.set("Checking...")
        self.update_idletasks()
        try:
            from hardware import detect_gpu, get_nvidia_gpu_name
            status = detect_gpu()
            if status == "cuda_ready":
                gpu = get_nvidia_gpu_name() or "NVIDIA GPU"
                self._perf_status_var.set(f"Power Mode available — {gpu} detected with CUDA ready.")
            elif status == "nvidia_no_cuda":
                gpu = get_nvidia_gpu_name() or "NVIDIA GPU"
                self._perf_status_var.set(f"{gpu} found but CUDA not set up. Click 'Enable Power Mode' to try.")
            else:
                self._perf_status_var.set("No NVIDIA GPU detected — Standard Mode is the right choice.")
        except Exception as e:
            self._perf_status_var.set(f"Detection error: {e}")

    def _enable_power_mode(self):
        """Attempt to install CUDA packages and switch to Power Mode."""
        from tkinter import messagebox
        self._perf_status_var.set("Installing GPU support — this may take a few minutes...")
        self.update_idletasks()
        try:
            from hardware import detect_gpu, try_install_cuda_packages
            status = detect_gpu()
            if status == "cuda_ready":
                self.config_data["compute_type"] = "float16"
                self.config_data["model_size"] = "large-v3-turbo"
                save_config(self.config_data)
                self._perf_status_var.set("Power Mode enabled! Restart Koda to apply.")
                messagebox.showinfo("Koda", "Power Mode enabled!\n\nRestart Koda to use your GPU.")
            elif status == "nvidia_no_cuda":
                success = try_install_cuda_packages()
                if success:
                    self.config_data["compute_type"] = "float16"
                    self.config_data["model_size"] = "large-v3-turbo"
                    save_config(self.config_data)
                    self._perf_status_var.set("Power Mode enabled! Restart Koda to apply.")
                    messagebox.showinfo("Koda", "Power Mode enabled!\n\nRestart Koda to use your GPU.")
                else:
                    self._perf_status_var.set("Automatic setup failed. See 'Learn more' for manual steps.")
                    messagebox.showwarning(
                        "Koda",
                        "Automatic GPU setup didn't work on this system.\n\n"
                        "Click 'Learn more' to download the NVIDIA CUDA Toolkit manually.\n"
                        "After installing it, come back here and click 'Enable Power Mode' again."
                    )
            else:
                self._perf_status_var.set("No NVIDIA GPU found — Power Mode is not available on this machine.")
        except Exception as e:
            self._perf_status_var.set(f"Error: {e}")

    def _disable_power_mode(self):
        """Switch back to Standard Mode (CPU)."""
        self.config_data["compute_type"] = "int8"
        self.config_data["model_size"] = "small"
        save_config(self.config_data)
        self._perf_status_var.set("Switched to Standard Mode. Restart Koda to apply.")

    def _open_cuda_url(self):
        """Open the NVIDIA CUDA download page in the browser."""
        import webbrowser
        webbrowser.open("https://developer.nvidia.com/cuda-downloads")

    def on_close(self):
        self.destroy()


if __name__ == "__main__":
    app = KodaSettings()
    app.mainloop()
