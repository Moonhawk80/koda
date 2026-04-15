"""
Koda Settings — Simple GUI for configuring Koda.
Opens from the tray menu or desktop shortcut.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)


class KodaSettings(tk.Tk):
    CUSTOM_WORDS_PATH = os.path.join(SCRIPT_DIR, "custom_words.json")

    def __init__(self):
        super().__init__()
        self.title("Koda Settings")
        self.resizable(True, True)
        BG = "#f4f4f4"
        FG = "#1a1a1a"
        ACCENT = "#1a56db"
        self.configure(bg=BG)

        self.config_data = load_config()
        self._custom_words = self._load_custom_words_data()
        self._profiles_data = self._load_profiles_data()
        self._filler_words = self._load_filler_words_data()
        self._snippets = dict(self.config_data.get("snippets", {}))

        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".",            background=BG,  foreground=FG,     font=("Segoe UI", 10))
        style.configure("TFrame",       background=BG)
        style.configure("TLabel",       background=BG,  foreground=FG,     font=("Segoe UI", 10))
        style.configure("Header.TLabel",background=BG,  foreground=ACCENT, font=("Segoe UI", 10, "bold"))
        style.configure("TCheckbutton", background=BG,  foreground=FG,     font=("Segoe UI", 10))
        style.configure("TRadiobutton", background=BG,  foreground=FG,     font=("Segoe UI", 10))
        style.configure("TButton",      font=("Segoe UI", 10))
        style.configure("TCombobox",    font=("Segoe UI", 10))
        style.configure("TEntry",       font=("Segoe UI", 10))
        style.configure("TSeparator",   background="#d0d0d0")
        style.configure("TNotebook",    background=BG, borderwidth=0)
        style.configure("TNotebook.Tab",font=("Segoe UI", 10), padding=(12, 5))

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.update_idletasks()
        self.geometry("620x680")

    def _build_ui(self):
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        gen_tab  = ttk.Frame(notebook, padding=15)
        hk_tab   = ttk.Frame(notebook, padding=15)
        sp_tab   = ttk.Frame(notebook, padding=15)
        wd_tab   = ttk.Frame(notebook, padding=15)
        adv_tab  = ttk.Frame(notebook, padding=15)

        notebook.add(gen_tab,  text="  General  ")
        notebook.add(hk_tab,   text="  Hotkeys  ")
        notebook.add(sp_tab,   text="  Speech  ")
        notebook.add(wd_tab,   text="  Words  ")
        notebook.add(adv_tab,  text="  Advanced  ")

        self._build_general_tab(gen_tab)
        self._build_hotkeys_tab(hk_tab)
        self._build_speech_tab(sp_tab)
        self._build_words_tab(wd_tab)
        self._build_advanced_tab(adv_tab)

        sep = ttk.Separator(self, orient="horizontal")
        sep.pack(fill="x", padx=10, pady=(8, 0))

        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=8)
        ttk.Button(btn_frame, text="Save & Restart Koda", command=self.save_and_restart).pack(side="left", padx=(0, 8))
        ttk.Button(btn_frame, text="Save", command=self.save).pack(side="left", padx=(0, 8))
        ttk.Button(btn_frame, text="Cancel", command=self.on_close).pack(side="left")

    def _build_general_tab(self, parent):
        ttk.Label(parent, text="Recording Mode", style="Header.TLabel").pack(anchor="w", pady=(0, 4))
        self.mode_var = tk.StringVar(value=self.config_data.get("hotkey_mode", "hold"))
        ttk.Radiobutton(parent, text="Hold-to-talk  (hold key while speaking)", variable=self.mode_var, value="hold").pack(anchor="w")
        ttk.Radiobutton(parent, text="Toggle  (press once, auto-stops on silence)", variable=self.mode_var, value="toggle").pack(anchor="w")

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=10)

        ttk.Label(parent, text="Output", style="Header.TLabel").pack(anchor="w", pady=(0, 4))
        self.output_var = tk.StringVar(value=self.config_data.get("output_mode", "auto_paste"))
        ttk.Radiobutton(parent, text="Auto-paste  (types into the active window)", variable=self.output_var, value="auto_paste").pack(anchor="w")
        ttk.Radiobutton(parent, text="Clipboard only  (no paste)", variable=self.output_var, value="clipboard").pack(anchor="w")

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=10)

        ttk.Label(parent, text="Features", style="Header.TLabel").pack(anchor="w", pady=(0, 4))

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
            ttk.Checkbutton(parent, text=label, variable=var).pack(anchor="w", pady=1)

    def _build_hotkeys_tab(self, parent):
        FKEY_OPTIONS = ["f1","f2","f3","f4","f5","f6","f7","f8","f9","f10","f11","f12"]
        DICT_OPTIONS = ["ctrl+space", "ctrl+alt+d"] + FKEY_OPTIONS

        ttk.Label(parent, text="Hotkey Assignments", style="Header.TLabel").pack(anchor="w", pady=(0, 10))

        self.hk_dict_var    = tk.StringVar(value=self.config_data.get("hotkey_dictation",          "ctrl+space"))
        self.hk_cmd_var     = tk.StringVar(value=self.config_data.get("hotkey_command",             "f8"))
        self.hk_prompt_var  = tk.StringVar(value=self.config_data.get("hotkey_prompt",              "f9"))
        self.hk_corr_var    = tk.StringVar(value=self.config_data.get("hotkey_correction",          "f7"))
        self.hk_read_var    = tk.StringVar(value=self.config_data.get("hotkey_readback",            "f6"))
        self.hk_readsel_var = tk.StringVar(value=self.config_data.get("hotkey_readback_selected",   "f5"))

        rows = [
            ("Dictation:",     self.hk_dict_var,    DICT_OPTIONS),
            ("Command:",       self.hk_cmd_var,      FKEY_OPTIONS),
            ("Prompt Assist:", self.hk_prompt_var,   FKEY_OPTIONS),
            ("Correction:",    self.hk_corr_var,     FKEY_OPTIONS),
            ("Read back:",     self.hk_read_var,     FKEY_OPTIONS),
            ("Read selected:", self.hk_readsel_var,  FKEY_OPTIONS),
        ]
        f = ttk.Frame(parent)
        f.pack(fill="x")
        for i, (label, var, opts) in enumerate(rows):
            ttk.Label(f, text=label).grid(row=i, column=0, sticky="w", padx=(0, 14), pady=4)
            ttk.Combobox(f, textvariable=var, values=opts, width=18, state="readonly").grid(row=i, column=1, sticky="w")

    def _build_speech_tab(self, parent):
        ttk.Label(parent, text="Whisper Model", style="Header.TLabel").pack(anchor="w", pady=(0, 8))

        f = ttk.Frame(parent)
        f.pack(fill="x")

        ttk.Label(f, text="Model size:").grid(row=0, column=0, sticky="w", padx=(0, 14), pady=4)
        self.model_var = tk.StringVar(value=self.config_data.get("model_size", "base"))
        ttk.Combobox(f, textvariable=self.model_var, width=24,
                     values=["tiny", "base", "small", "medium", "large-v2", "large-v3",
                             "large-v3-turbo", "distil-large-v3", "distil-medium.en"],
                     state="readonly").grid(row=0, column=1, sticky="w")

        ttk.Label(f, text="Language:").grid(row=1, column=0, sticky="w", padx=(0, 14), pady=4)
        self.lang_var = tk.StringVar(value=self.config_data.get("language", "en"))
        ttk.Combobox(f, textvariable=self.lang_var, width=24,
                     values=["en","es","fr","de","pt","zh","ja","ko","ar","hi","ru","it","nl","pl","tr","auto"],
                     state="readonly").grid(row=1, column=1, sticky="w")

        ttk.Label(parent, text="\nLarger models are more accurate but slower to load.\n"
                               "tiny/base = fastest  |  small = best balance  |  large = highest accuracy",
                  foreground="#888888").pack(anchor="w")

    def _build_words_tab(self, parent):
        sub = ttk.Notebook(parent)
        sub.pack(fill="both", expand=True)

        cw_tab = ttk.Frame(sub, padding=10)
        fw_tab = ttk.Frame(sub, padding=10)
        sn_tab = ttk.Frame(sub, padding=10)
        pr_tab = ttk.Frame(sub, padding=10)

        sub.add(cw_tab, text="  Custom Words  ")
        sub.add(fw_tab, text="  Filler Words  ")
        sub.add(sn_tab, text="  Snippets  ")
        sub.add(pr_tab, text="  App Profiles  ")

        # Custom Words
        ttk.Label(cw_tab, text="Replace misheard words with the correct version:").pack(anchor="w", pady=(0, 5))
        tf = ttk.Frame(cw_tab); tf.pack(fill="both", expand=True)
        self._vocab_tree = ttk.Treeview(tf, columns=("misheard","correct"), show="headings", height=8, selectmode="browse")
        self._vocab_tree.heading("misheard", text="Misheard"); self._vocab_tree.heading("correct", text="Replace with")
        self._vocab_tree.column("misheard", width=200, anchor="w"); self._vocab_tree.column("correct", width=200, anchor="w")
        self._vocab_tree.pack(side="left", fill="both", expand=True)
        s = ttk.Scrollbar(tf, orient="vertical", command=self._vocab_tree.yview)
        self._vocab_tree.configure(yscrollcommand=s.set); s.pack(side="left", fill="y")
        self._refresh_vocab_tree()
        br = ttk.Frame(cw_tab); br.pack(anchor="w", pady=(6,0))
        for lbl, cmd in [("Add", self._add_vocab_entry), ("Edit", self._edit_vocab_entry),
                         ("Remove", self._remove_vocab_entry), ("Import", self._import_vocab), ("Export", self._export_vocab)]:
            ttk.Button(br, text=lbl, command=cmd).pack(side="left", padx=(0, 4))

        # Filler Words
        ttk.Label(fw_tab, text="Removed from speech when filler removal is enabled:").pack(anchor="w", pady=(0, 5))
        ff = ttk.Frame(fw_tab); ff.pack(fill="both", expand=True)
        self._filler_tree = ttk.Treeview(ff, columns=("word",), show="headings", height=8, selectmode="browse")
        self._filler_tree.heading("word", text="Word / Phrase"); self._filler_tree.column("word", width=440, anchor="w")
        self._filler_tree.pack(side="left", fill="both", expand=True)
        fs = ttk.Scrollbar(ff, orient="vertical", command=self._filler_tree.yview)
        self._filler_tree.configure(yscrollcommand=fs.set); fs.pack(side="left", fill="y")
        self._refresh_filler_tree()
        fbr = ttk.Frame(fw_tab); fbr.pack(anchor="w", pady=(6,0))
        for lbl, cmd in [("Add", self._add_filler_word), ("Remove", self._remove_filler_word), ("Restore defaults", self._restore_filler_defaults)]:
            ttk.Button(fbr, text=lbl, command=cmd).pack(side="left", padx=(0, 4))

        # Snippets
        ttk.Label(sn_tab, text="Say the trigger word alone to paste the full expansion:").pack(anchor="w", pady=(0, 5))
        sf = ttk.Frame(sn_tab); sf.pack(fill="both", expand=True)
        self._snippets_tree = ttk.Treeview(sf, columns=("trigger","expansion"), show="headings", height=8, selectmode="browse")
        self._snippets_tree.heading("trigger", text="Trigger"); self._snippets_tree.heading("expansion", text="Expansion")
        self._snippets_tree.column("trigger", width=140, anchor="w"); self._snippets_tree.column("expansion", width=300, anchor="w")
        self._snippets_tree.pack(side="left", fill="both", expand=True)
        ss = ttk.Scrollbar(sf, orient="vertical", command=self._snippets_tree.yview)
        self._snippets_tree.configure(yscrollcommand=ss.set); ss.pack(side="left", fill="y")
        self._refresh_snippets_tree()
        sbr = ttk.Frame(sn_tab); sbr.pack(anchor="w", pady=(6,0))
        for lbl, cmd in [("Add", self._add_snippet), ("Edit", self._edit_snippet), ("Remove", self._remove_snippet)]:
            ttk.Button(sbr, text=lbl, command=cmd).pack(side="left", padx=(0, 4))

        # App Profiles
        ttk.Label(pr_tab, text="Auto-switch settings based on the active window:").pack(anchor="w", pady=(0, 5))
        pf = ttk.Frame(pr_tab); pf.pack(fill="both", expand=True)
        self._profile_tree = ttk.Treeview(pf, columns=("name","match","overrides"), show="headings", height=8, selectmode="browse")
        self._profile_tree.heading("name", text="Profile"); self._profile_tree.heading("match", text="Matches"); self._profile_tree.heading("overrides", text="Overrides")
        self._profile_tree.column("name", width=110, anchor="w"); self._profile_tree.column("match", width=170, anchor="w"); self._profile_tree.column("overrides", width=160, anchor="w")
        self._profile_tree.pack(side="left", fill="both", expand=True)
        ps = ttk.Scrollbar(pf, orient="vertical", command=self._profile_tree.yview)
        self._profile_tree.configure(yscrollcommand=ps.set); ps.pack(side="left", fill="y")
        self._refresh_profile_tree()
        pbr = ttk.Frame(pr_tab); pbr.pack(anchor="w", pady=(6,0))
        for lbl, cmd in [("Add", self._add_profile), ("Edit", self._edit_profile), ("Remove", self._remove_profile), ("Edit JSON", self._open_profiles)]:
            ttk.Button(pbr, text=lbl, command=cmd).pack(side="left", padx=(0, 4))

    def _build_advanced_tab(self, parent):
        ttk.Label(parent, text="Behavior", style="Header.TLabel").pack(anchor="w", pady=(0, 4))

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
            ttk.Checkbutton(parent, text=label, variable=var).pack(anchor="w", pady=1)

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=10)

        ttk.Label(parent, text="Translation", style="Header.TLabel").pack(anchor="w", pady=(0, 4))
        self.trans_var = tk.BooleanVar(value=self.config_data.get("translation", {}).get("enabled", False))
        ttk.Checkbutton(parent, text="Enable translation  (speak one language, output another)", variable=self.trans_var).pack(anchor="w")
        lf = ttk.Frame(parent); lf.pack(fill="x", pady=(4, 0))
        ttk.Label(lf, text="Target language:").pack(side="left", padx=(0, 10))
        self.trans_lang_var = tk.StringVar(value=self.config_data.get("translation", {}).get("target_language", "English"))
        ttk.Combobox(lf, textvariable=self.trans_lang_var, width=18,
                     values=["English","Spanish","French","German","Portuguese","Japanese","Korean","Chinese","Italian","Russian"],
                     state="readonly").pack(side="left")
        ttk.Label(lf, text="  English = Whisper  |  Others = Ollama", foreground="#888888").pack(side="left", padx=(10, 0))

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=10)

        ttk.Label(parent, text="Read-back Voice", style="Header.TLabel").pack(anchor="w", pady=(0, 4))
        self.voices = self._get_voices()
        voice_names = [name for name, _ in self.voices]
        current_voice = self.config_data.get("tts", {}).get("voice", voice_names[0] if voice_names else "")
        rf = ttk.Frame(parent); rf.pack(fill="x")
        ttk.Label(rf, text="Voice:").grid(row=0, column=0, sticky="w", padx=(0,12), pady=3)
        self.voice_var = tk.StringVar(value=current_voice)
        if voice_names:
            ttk.Combobox(rf, textvariable=self.voice_var, width=30, values=voice_names, state="readonly").grid(row=0, column=1, sticky="w")
        ttk.Label(rf, text="Speed:").grid(row=1, column=0, sticky="w", padx=(0,12), pady=3)
        self.speed_var = tk.StringVar(value=self.config_data.get("tts", {}).get("rate", "normal"))
        ttk.Combobox(rf, textvariable=self.speed_var, width=30, values=["slow","normal","fast"], state="readonly").grid(row=1, column=1, sticky="w")

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=10)

        ttk.Label(parent, text="Performance", style="Header.TLabel").pack(anchor="w", pady=(0, 4))
        current_compute = self.config_data.get("compute_type", "int8")
        mode_text = "Power Mode  (NVIDIA GPU)" if current_compute == "float16" else "Standard Mode  (CPU)"
        ttk.Label(parent, text=f"Current: {mode_text}").pack(anchor="w")
        self._perf_status_var = tk.StringVar(value="")
        ttk.Label(parent, textvariable=self._perf_status_var, foreground="#2e7d32").pack(anchor="w", pady=(2,0))
        pbr = ttk.Frame(parent); pbr.pack(anchor="w", pady=(6,0))
        ttk.Button(pbr, text="Check GPU", command=self._check_gpu).pack(side="left", padx=(0, 6))
        if current_compute != "float16":
            ttk.Button(pbr, text="Enable Power Mode", command=self._enable_power_mode).pack(side="left", padx=(0, 6))
        else:
            ttk.Button(pbr, text="Switch to Standard Mode", command=self._disable_power_mode).pack(side="left", padx=(0, 6))
        ttk.Button(pbr, text="Learn more", command=self._open_cuda_url).pack(side="left")

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=10)

        ttk.Label(parent, text="History", style="Header.TLabel").pack(anchor="w", pady=(0, 4))
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

    def save(self, notify=True):
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
        if notify:
            messagebox.showinfo("Koda", "Settings saved! Restart Koda for changes to take effect.")

    def save_and_restart(self):
        self.save(notify=False)
        import subprocess
        import time
        # Kill only the parent Koda process by PID — not all pythonw processes,
        # since settings_gui itself runs as pythonw and would be self-killed.
        parent_pid = os.getppid()
        subprocess.run(["taskkill", "/f", "/pid", str(parent_pid)], capture_output=True)
        time.sleep(0.5)
        # Restart — launch pythonw directly (bypasses start.bat activation quirks)
        pythonw = os.path.join(SCRIPT_DIR, "venv", "Scripts", "pythonw.exe")
        subprocess.Popen([pythonw, "voice.py"], cwd=SCRIPT_DIR,
                         creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
        self.destroy()

    def _open_custom_words(self):
        """Open custom_words.json in the default editor."""
        custom_words_path = os.path.join(SCRIPT_DIR, "custom_words.json")
        if not os.path.exists(custom_words_path):
            with open(custom_words_path, "w", encoding="utf-8") as f:
                json.dump({"coda": "Koda", "claude code": "Claude Code"}, f, indent=2)
        os.startfile(custom_words_path)

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
        dlg.geometry("440x300")
        dlg.resizable(False, False)
        dlg.configure(bg="#1e1e2e")
        dlg.grab_set()

        result = [None]

        ttk.Label(dlg, text="Profile name:").grid(row=0, column=0, sticky="w", padx=12, pady=(14, 4))
        name_var = tk.StringVar(value=name)
        ttk.Entry(dlg, textvariable=name_var, width=28).grid(row=0, column=1, padx=(0, 12), pady=(14, 4))

        ttk.Label(dlg, text="Match process (e.g. code.exe):").grid(row=1, column=0, sticky="w", padx=12, pady=4)
        proc_var = tk.StringVar(value=match_rules.get("process", ""))
        ttk.Entry(dlg, textvariable=proc_var, width=28).grid(row=1, column=1, padx=(0, 12), pady=4)

        ttk.Label(dlg, text="Match title regex (optional):").grid(row=2, column=0, sticky="w", padx=12, pady=4)
        title_var = tk.StringVar(value=match_rules.get("title", ""))
        ttk.Entry(dlg, textvariable=title_var, width=28).grid(row=2, column=1, padx=(0, 12), pady=4)

        ttk.Label(dlg, text="Overrides (inherit = base config):").grid(
            row=3, column=0, columnspan=2, sticky="w", padx=12, pady=(10, 2))

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
            ttk.Label(dlg, text=f"  {label}:").grid(row=override_row, column=0, sticky="w", padx=12, pady=2)
            ttk.Combobox(dlg, textvariable=var, values=["inherit", "on", "off"],
                         state="readonly", width=10).grid(row=override_row, column=1, sticky="w",
                                                          padx=(0, 12), pady=2)
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
        btn_row.grid(row=override_row, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn_row, text="OK", command=on_ok).pack(side="left", padx=6)
        ttk.Button(btn_row, text="Cancel", command=dlg.destroy).pack(side="left")

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
        dlg.geometry("340x110")
        dlg.resizable(False, False)
        dlg.configure(bg="#1e1e2e")
        dlg.grab_set()
        result = [None]
        ttk.Label(dlg, text="Word or phrase to remove:").grid(row=0, column=0, sticky="w", padx=12, pady=(14, 4))
        word_var = tk.StringVar()
        entry = ttk.Entry(dlg, textvariable=word_var, width=28)
        entry.grid(row=0, column=1, padx=(0, 12), pady=(14, 4))
        def on_ok(*_):
            w = word_var.get().strip().lower()
            if not w:
                messagebox.showwarning("Koda", "Enter a word or phrase.", parent=dlg)
                return
            result[0] = w
            dlg.destroy()
        btn_row = ttk.Frame(dlg)
        btn_row.grid(row=1, column=0, columnspan=2, pady=(6, 0))
        ttk.Button(btn_row, text="OK", command=on_ok).pack(side="left", padx=6)
        ttk.Button(btn_row, text="Cancel", command=dlg.destroy).pack(side="left")
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
        dlg.geometry("440x160")
        dlg.resizable(False, False)
        dlg.configure(bg="#1e1e2e")
        dlg.grab_set()
        result = [None]
        ttk.Label(dlg, text="Trigger phrase (say this alone):").grid(row=0, column=0, sticky="w", padx=12, pady=(14, 4))
        trig_var = tk.StringVar(value=trigger)
        trig_entry = ttk.Entry(dlg, textvariable=trig_var, width=30)
        trig_entry.grid(row=0, column=1, padx=(0, 12), pady=(14, 4))
        ttk.Label(dlg, text="Expansion (text to paste):").grid(row=1, column=0, sticky="w", padx=12, pady=4)
        exp_var = tk.StringVar(value=expansion)
        exp_entry = ttk.Entry(dlg, textvariable=exp_var, width=30)
        exp_entry.grid(row=1, column=1, padx=(0, 12), pady=4)
        def on_ok(*_):
            t = trig_var.get().strip().lower()
            e = exp_var.get().strip()
            if not t or not e:
                messagebox.showwarning("Koda", "Both fields are required.", parent=dlg)
                return
            result[0] = (t, e)
            dlg.destroy()
        btn_row = ttk.Frame(dlg)
        btn_row.grid(row=2, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn_row, text="OK", command=on_ok).pack(side="left", padx=6)
        ttk.Button(btn_row, text="Cancel", command=dlg.destroy).pack(side="left")
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
        """Load custom_words.json into an ordered dict."""
        if os.path.exists(self.CUSTOM_WORDS_PATH):
            try:
                with open(self.CUSTOM_WORDS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return dict(data) if isinstance(data, dict) else {}
            except Exception:
                pass
        return {"coda": "Koda", "claude code": "Claude Code"}

    def _save_custom_words_data(self):
        """Write _custom_words back to custom_words.json."""
        with open(self.CUSTOM_WORDS_PATH, "w", encoding="utf-8") as f:
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
        dlg.geometry("360x140")
        dlg.resizable(False, False)
        dlg.configure(bg="#1e1e2e")
        dlg.grab_set()

        result = [None]

        ttk.Label(dlg, text="Misheard word/phrase:").grid(row=0, column=0, sticky="w", padx=12, pady=(14, 4))
        mis_var = tk.StringVar(value=misheard)
        mis_entry = ttk.Entry(dlg, textvariable=mis_var, width=28)
        mis_entry.grid(row=0, column=1, padx=(0, 12), pady=(14, 4))

        ttk.Label(dlg, text="Replace with:").grid(row=1, column=0, sticky="w", padx=12, pady=4)
        cor_var = tk.StringVar(value=correct)
        cor_entry = ttk.Entry(dlg, textvariable=cor_var, width=28)
        cor_entry.grid(row=1, column=1, padx=(0, 12), pady=4)

        def on_ok(*_):
            m = mis_var.get().strip().lower()
            c = cor_var.get().strip()
            if not m or not c:
                messagebox.showwarning("Koda", "Both fields are required.", parent=dlg)
                return
            result[0] = (m, c)
            dlg.destroy()

        btn_row = ttk.Frame(dlg)
        btn_row.grid(row=2, column=0, columnspan=2, pady=(10, 0))
        ttk.Button(btn_row, text="OK", command=on_ok).pack(side="left", padx=6)
        ttk.Button(btn_row, text="Cancel", command=dlg.destroy).pack(side="left")

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

        hist_win = tk.Toplevel(self)
        hist_win.title("Koda - Transcript History")
        hist_win.geometry("600x450")
        hist_win.configure(bg="#1e1e2e")

        top_frame = ttk.Frame(hist_win)
        top_frame.pack(fill="x", padx=10, pady=(10, 5))

        ttk.Label(top_frame, text="Search:").pack(side="left", padx=(0, 5))
        search_var = tk.StringVar()
        search_entry = ttk.Entry(top_frame, textvariable=search_var, width=40)
        search_entry.pack(side="left", padx=(0, 5))

        text_widget = tk.Text(hist_win, bg="#313244", fg="#cdd6f4", font=("Consolas", 10),
                              wrap="word", state="disabled")
        text_widget.pack(fill="both", expand=True, padx=10, pady=(0, 10))

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
