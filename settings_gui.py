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
        self.configure(bg="#1e1e2e")

        self.config_data = load_config()
        self._custom_words = self._load_custom_words_data()
        self._profiles_data = self._load_profiles_data()
        self._filler_words = self._load_filler_words_data()
        self._snippets = dict(self.config_data.get("snippets", {}))

        # Style
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TLabel", background="#1e1e2e", foreground="#cdd6f4", font=("Segoe UI", 10))
        style.configure("Header.TLabel", background="#1e1e2e", foreground="#89b4fa", font=("Segoe UI", 12, "bold"))
        style.configure("TCheckbutton", background="#1e1e2e", foreground="#cdd6f4", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10))
        style.configure("TCombobox", font=("Segoe UI", 10))
        style.configure("TEntry", font=("Segoe UI", 10))

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        # Size window to fit screen height with some padding
        self.update_idletasks()
        screen_h = self.winfo_screenheight()
        win_h = min(screen_h - 80, 900)
        self.geometry(f"540x{win_h}")

    def _build_ui(self):
        # Outer frame holds canvas + scrollbar
        outer = tk.Frame(self, bg="#1e1e2e")
        outer.pack(fill="both", expand=True)

        canvas = tk.Canvas(outer, bg="#1e1e2e", highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        main = ttk.Frame(canvas, padding=20)
        canvas_window = canvas.create_window((0, 0), window=main, anchor="nw")

        def _on_frame_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)

        main.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        # Mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Title
        ttk.Label(main, text="Koda Settings", style="Header.TLabel").pack(anchor="w", pady=(0, 15))

        # --- Hotkeys ---
        ttk.Label(main, text="HOTKEYS", style="Header.TLabel").pack(anchor="w", pady=(10, 5))

        hk_frame = ttk.Frame(main)
        hk_frame.pack(fill="x", pady=2)

        # Safe hotkey options: F-keys and ctrl+space (proven to work without conflicts)
        FKEY_OPTIONS = ["f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12"]
        DICTATION_OPTIONS = ["ctrl+space", "ctrl+alt+d"] + FKEY_OPTIONS

        ttk.Label(hk_frame, text="Dictation:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.hk_dict_var = tk.StringVar(value=self.config_data.get("hotkey_dictation", "ctrl+space"))
        ttk.Combobox(hk_frame, textvariable=self.hk_dict_var, width=22,
                     values=DICTATION_OPTIONS, state="readonly").grid(row=0, column=1, sticky="w")

        ttk.Label(hk_frame, text="Command:").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=3)
        self.hk_cmd_var = tk.StringVar(value=self.config_data.get("hotkey_command", "f8"))
        ttk.Combobox(hk_frame, textvariable=self.hk_cmd_var, width=22,
                     values=FKEY_OPTIONS, state="readonly").grid(row=1, column=1, sticky="w")

        ttk.Label(hk_frame, text="Prompt Assist:").grid(row=2, column=0, sticky="w", padx=(0, 10), pady=3)
        self.hk_prompt_var = tk.StringVar(value=self.config_data.get("hotkey_prompt", "f9"))
        ttk.Combobox(hk_frame, textvariable=self.hk_prompt_var, width=22,
                     values=FKEY_OPTIONS, state="readonly").grid(row=2, column=1, sticky="w")

        ttk.Label(hk_frame, text="Correction:").grid(row=3, column=0, sticky="w", padx=(0, 10), pady=3)
        self.hk_corr_var = tk.StringVar(value=self.config_data.get("hotkey_correction", "f7"))
        ttk.Combobox(hk_frame, textvariable=self.hk_corr_var, width=22,
                     values=FKEY_OPTIONS, state="readonly").grid(row=3, column=1, sticky="w")

        ttk.Label(hk_frame, text="Read back:").grid(row=4, column=0, sticky="w", padx=(0, 10), pady=3)
        self.hk_read_var = tk.StringVar(value=self.config_data.get("hotkey_readback", "f6"))
        ttk.Combobox(hk_frame, textvariable=self.hk_read_var, width=22,
                     values=FKEY_OPTIONS, state="readonly").grid(row=4, column=1, sticky="w")

        ttk.Label(hk_frame, text="Read selected:").grid(row=5, column=0, sticky="w", padx=(0, 10), pady=3)
        self.hk_readsel_var = tk.StringVar(value=self.config_data.get("hotkey_readback_selected", "f5"))
        ttk.Combobox(hk_frame, textvariable=self.hk_readsel_var, width=22,
                     values=FKEY_OPTIONS, state="readonly").grid(row=5, column=1, sticky="w")

        # --- Model ---
        ttk.Label(main, text="SPEECH MODEL", style="Header.TLabel").pack(anchor="w", pady=(15, 5))

        model_frame = ttk.Frame(main)
        model_frame.pack(fill="x", pady=2)

        ttk.Label(model_frame, text="Model size:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.model_var = tk.StringVar(value=self.config_data.get("model_size", "base"))
        model_combo = ttk.Combobox(model_frame, textvariable=self.model_var, width=22,
                                   values=["tiny", "base", "small", "medium", "large-v2", "large-v3",
                                           "large-v3-turbo", "distil-large-v3", "distil-medium.en"],
                                   state="readonly")
        model_combo.grid(row=0, column=1, sticky="w")

        ttk.Label(model_frame, text="Language:").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=3)
        self.lang_var = tk.StringVar(value=self.config_data.get("language", "en"))
        lang_combo = ttk.Combobox(model_frame, textvariable=self.lang_var, width=22,
                                  values=["en", "es", "fr", "de", "pt", "zh", "ja", "ko",
                                          "ar", "hi", "ru", "it", "nl", "pl", "tr", "auto"],
                                  state="readonly")
        lang_combo.grid(row=1, column=1, sticky="w")

        # --- Mode ---
        ttk.Label(main, text="RECORDING MODE", style="Header.TLabel").pack(anchor="w", pady=(15, 5))

        self.mode_var = tk.StringVar(value=self.config_data.get("hotkey_mode", "hold"))
        mode_frame = ttk.Frame(main)
        mode_frame.pack(fill="x", pady=2)
        ttk.Radiobutton(mode_frame, text="Hold-to-talk (hold key while speaking)", variable=self.mode_var, value="hold").pack(anchor="w")
        ttk.Radiobutton(mode_frame, text="Toggle (press once, auto-stops on silence)", variable=self.mode_var, value="toggle").pack(anchor="w")

        # --- Output Mode ---
        ttk.Label(main, text="OUTPUT MODE", style="Header.TLabel").pack(anchor="w", pady=(15, 5))

        self.output_var = tk.StringVar(value=self.config_data.get("output_mode", "auto_paste"))
        output_frame = ttk.Frame(main)
        output_frame.pack(fill="x", pady=2)
        ttk.Radiobutton(output_frame, text="Auto-paste (copy + Ctrl+V into active window)", variable=self.output_var, value="auto_paste").pack(anchor="w")
        ttk.Radiobutton(output_frame, text="Clipboard only (copy to clipboard, no paste)", variable=self.output_var, value="clipboard").pack(anchor="w")

        # --- Custom Words ---
        ttk.Label(main, text="CUSTOM WORDS", style="Header.TLabel").pack(anchor="w", pady=(15, 5))

        cw_frame = ttk.Frame(main)
        cw_frame.pack(fill="x", pady=2)
        ttk.Label(cw_frame, text="Replace misheard words with correct versions:").pack(anchor="w")

        tree_frame = ttk.Frame(cw_frame)
        tree_frame.pack(fill="x", pady=(5, 0))

        self._vocab_tree = ttk.Treeview(
            tree_frame, columns=("misheard", "correct"), show="headings", height=5,
            selectmode="browse",
        )
        self._vocab_tree.heading("misheard", text="Misheard")
        self._vocab_tree.heading("correct", text="Correct")
        self._vocab_tree.column("misheard", width=230, anchor="w")
        self._vocab_tree.column("correct", width=230, anchor="w")
        self._vocab_tree.pack(side="left", fill="x", expand=True)

        vocab_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self._vocab_tree.yview)
        self._vocab_tree.configure(yscrollcommand=vocab_scroll.set)
        vocab_scroll.pack(side="left", fill="y")

        self._refresh_vocab_tree()

        vocab_btn_row = ttk.Frame(cw_frame)
        vocab_btn_row.pack(anchor="w", pady=(4, 0))
        ttk.Button(vocab_btn_row, text="Add", command=self._add_vocab_entry).pack(side="left", padx=(0, 4))
        ttk.Button(vocab_btn_row, text="Edit", command=self._edit_vocab_entry).pack(side="left", padx=(0, 4))
        ttk.Button(vocab_btn_row, text="Remove", command=self._remove_vocab_entry).pack(side="left", padx=(0, 12))
        ttk.Button(vocab_btn_row, text="Import", command=self._import_vocab).pack(side="left", padx=(0, 4))
        ttk.Button(vocab_btn_row, text="Export", command=self._export_vocab).pack(side="left")

        # --- Per-App Profiles ---
        ttk.Label(main, text="PER-APP PROFILES", style="Header.TLabel").pack(anchor="w", pady=(15, 5))
        ttk.Label(main, text="Auto-switch settings based on the active window:").pack(anchor="w")

        prof_frame = ttk.Frame(main)
        prof_frame.pack(fill="x", pady=(5, 0))

        self._profile_tree = ttk.Treeview(
            prof_frame, columns=("name", "match", "overrides"), show="headings", height=4,
            selectmode="browse",
        )
        self._profile_tree.heading("name", text="Profile")
        self._profile_tree.heading("match", text="Matches")
        self._profile_tree.heading("overrides", text="Overrides")
        self._profile_tree.column("name", width=110, anchor="w")
        self._profile_tree.column("match", width=175, anchor="w")
        self._profile_tree.column("overrides", width=175, anchor="w")
        self._profile_tree.pack(side="left", fill="x", expand=True)

        prof_scroll = ttk.Scrollbar(prof_frame, orient="vertical", command=self._profile_tree.yview)
        self._profile_tree.configure(yscrollcommand=prof_scroll.set)
        prof_scroll.pack(side="left", fill="y")

        self._refresh_profile_tree()

        prof_btn_row = ttk.Frame(main)
        prof_btn_row.pack(anchor="w", pady=(4, 0))
        ttk.Button(prof_btn_row, text="Add", command=self._add_profile).pack(side="left", padx=(0, 4))
        ttk.Button(prof_btn_row, text="Edit", command=self._edit_profile).pack(side="left", padx=(0, 4))
        ttk.Button(prof_btn_row, text="Remove", command=self._remove_profile).pack(side="left", padx=(0, 12))
        ttk.Button(prof_btn_row, text="Edit profiles.json", command=self._open_profiles).pack(side="left")

        # --- Filler Words ---
        ttk.Label(main, text="FILLER WORDS", style="Header.TLabel").pack(anchor="w", pady=(15, 5))
        ttk.Label(main, text="Words and phrases removed from speech (when filler removal is on):").pack(anchor="w")

        fw_frame = ttk.Frame(main)
        fw_frame.pack(fill="x", pady=(5, 0))

        self._filler_tree = ttk.Treeview(
            fw_frame, columns=("word",), show="headings", height=5,
            selectmode="browse",
        )
        self._filler_tree.heading("word", text="Word / Phrase")
        self._filler_tree.column("word", width=450, anchor="w")
        self._filler_tree.pack(side="left", fill="x", expand=True)

        fw_scroll = ttk.Scrollbar(fw_frame, orient="vertical", command=self._filler_tree.yview)
        self._filler_tree.configure(yscrollcommand=fw_scroll.set)
        fw_scroll.pack(side="left", fill="y")

        self._refresh_filler_tree()

        fw_btn_row = ttk.Frame(main)
        fw_btn_row.pack(anchor="w", pady=(4, 0))
        ttk.Button(fw_btn_row, text="Add", command=self._add_filler_word).pack(side="left", padx=(0, 4))
        ttk.Button(fw_btn_row, text="Remove", command=self._remove_filler_word).pack(side="left", padx=(0, 12))
        ttk.Button(fw_btn_row, text="Restore defaults", command=self._restore_filler_defaults).pack(side="left")

        # --- Snippets ---
        ttk.Label(main, text="SNIPPETS", style="Header.TLabel").pack(anchor="w", pady=(15, 5))
        ttk.Label(main, text="Speak the trigger alone to paste the expansion:").pack(anchor="w")

        sn_frame = ttk.Frame(main)
        sn_frame.pack(fill="x", pady=(5, 0))

        self._snippets_tree = ttk.Treeview(
            sn_frame, columns=("trigger", "expansion"), show="headings", height=4,
            selectmode="browse",
        )
        self._snippets_tree.heading("trigger", text="Trigger")
        self._snippets_tree.heading("expansion", text="Expansion")
        self._snippets_tree.column("trigger", width=150, anchor="w")
        self._snippets_tree.column("expansion", width=300, anchor="w")
        self._snippets_tree.pack(side="left", fill="x", expand=True)

        sn_scroll = ttk.Scrollbar(sn_frame, orient="vertical", command=self._snippets_tree.yview)
        self._snippets_tree.configure(yscrollcommand=sn_scroll.set)
        sn_scroll.pack(side="left", fill="y")

        self._refresh_snippets_tree()

        sn_btn_row = ttk.Frame(main)
        sn_btn_row.pack(anchor="w", pady=(4, 0))
        ttk.Button(sn_btn_row, text="Add", command=self._add_snippet).pack(side="left", padx=(0, 4))
        ttk.Button(sn_btn_row, text="Edit", command=self._edit_snippet).pack(side="left", padx=(0, 4))
        ttk.Button(sn_btn_row, text="Remove", command=self._remove_snippet).pack(side="left")

        # --- Toggles ---
        ttk.Label(main, text="FEATURES", style="Header.TLabel").pack(anchor="w", pady=(15, 5))

        self.sound_var = tk.BooleanVar(value=self.config_data.get("sound_effects", True))
        ttk.Checkbutton(main, text="Sound effects", variable=self.sound_var).pack(anchor="w")

        self.filler_var = tk.BooleanVar(value=self.config_data.get("post_processing", {}).get("remove_filler_words", True))
        ttk.Checkbutton(main, text="Remove filler words (um, uh, you know)", variable=self.filler_var).pack(anchor="w")

        self.noise_var = tk.BooleanVar(value=self.config_data.get("noise_reduction", False))
        ttk.Checkbutton(main, text="Noise reduction (slower, for noisy environments)", variable=self.noise_var).pack(anchor="w")

        self.stream_var = tk.BooleanVar(value=self.config_data.get("streaming", True))
        ttk.Checkbutton(main, text="Streaming transcription (live preview while speaking)", variable=self.stream_var).pack(anchor="w")

        self.code_var = tk.BooleanVar(value=self.config_data.get("post_processing", {}).get("code_vocabulary", False))
        ttk.Checkbutton(main, text="Code vocabulary (open paren → ( in command mode)", variable=self.code_var).pack(anchor="w")

        self.autoformat_var = tk.BooleanVar(value=self.config_data.get("post_processing", {}).get("auto_format", True))
        ttk.Checkbutton(main, text="Auto-format (numbers, dates, smart punctuation)", variable=self.autoformat_var).pack(anchor="w")

        self.overlay_var = tk.BooleanVar(value=self.config_data.get("overlay_enabled", True))
        ttk.Checkbutton(main, text="Floating status overlay (live recording preview)", variable=self.overlay_var).pack(anchor="w")

        self.voicecmds_var = tk.BooleanVar(value=self.config_data.get("voice_commands", True))
        ttk.Checkbutton(main, text="Voice commands (say 'select all', 'undo', 'new line')", variable=self.voicecmds_var).pack(anchor="w")

        self.profiles_var = tk.BooleanVar(value=self.config_data.get("profiles_enabled", True))
        ttk.Checkbutton(main, text="Per-app profiles (auto-switch settings by active window)", variable=self.profiles_var).pack(anchor="w")

        # --- Translation ---
        ttk.Label(main, text="TRANSLATION", style="Header.TLabel").pack(anchor="w", pady=(15, 5))

        trans_frame = ttk.Frame(main)
        trans_frame.pack(fill="x", pady=2)

        self.trans_var = tk.BooleanVar(value=self.config_data.get("translation", {}).get("enabled", False))
        ttk.Checkbutton(trans_frame, text="Enable translation (speak one language, type another)",
                         variable=self.trans_var).pack(anchor="w")

        target_frame = ttk.Frame(main)
        target_frame.pack(fill="x", pady=2)
        ttk.Label(target_frame, text="Target language:").pack(side="left", padx=(0, 10))
        self.trans_lang_var = tk.StringVar(value=self.config_data.get("translation", {}).get("target_language", "English"))
        trans_combo = ttk.Combobox(target_frame, textvariable=self.trans_lang_var, width=22,
                                   values=["English", "Spanish", "French", "German", "Portuguese",
                                           "Japanese", "Korean", "Chinese", "Italian", "Russian"],
                                   state="readonly")
        trans_combo.pack(side="left")
        ttk.Label(target_frame, text="(English uses Whisper; others need Ollama)").pack(side="left", padx=(10, 0))

        # --- Read-back voice ---
        ttk.Label(main, text="READ-BACK", style="Header.TLabel").pack(anchor="w", pady=(15, 5))

        voice_frame = ttk.Frame(main)
        voice_frame.pack(fill="x", pady=2)

        self.voices = self._get_voices()
        voice_names = [name for name, _ in self.voices]
        current_voice = self.config_data.get("tts", {}).get("voice", voice_names[0] if voice_names else "")

        ttk.Label(voice_frame, text="Voice:").grid(row=0, column=0, sticky="w", padx=(0, 10))
        self.voice_var = tk.StringVar(value=current_voice)
        if voice_names:
            voice_combo = ttk.Combobox(voice_frame, textvariable=self.voice_var, width=35,
                                       values=voice_names, state="readonly")
            voice_combo.grid(row=0, column=1, sticky="w")

        ttk.Label(voice_frame, text="Speed:").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=3)
        current_speed = self.config_data.get("tts", {}).get("rate", "normal")
        self.speed_var = tk.StringVar(value=current_speed)
        speed_combo = ttk.Combobox(voice_frame, textvariable=self.speed_var, width=35,
                                   values=["slow", "normal", "fast"], state="readonly")
        speed_combo.grid(row=1, column=1, sticky="w")

        # --- Performance ---
        ttk.Label(main, text="PERFORMANCE", style="Header.TLabel").pack(anchor="w", pady=(15, 5))

        perf_frame = ttk.Frame(main)
        perf_frame.pack(fill="x", pady=2)

        current_compute = self.config_data.get("compute_type", "int8")
        mode_label = "Power Mode (NVIDIA GPU)" if current_compute == "float16" else "Standard Mode (CPU)"
        ttk.Label(perf_frame, text=f"Current mode:  {mode_label}").pack(anchor="w")

        self._perf_status_var = tk.StringVar(value="")
        ttk.Label(perf_frame, textvariable=self._perf_status_var,
                  foreground="#a6e3a1").pack(anchor="w", pady=(2, 0))

        perf_btn_row = ttk.Frame(perf_frame)
        perf_btn_row.pack(anchor="w", pady=(6, 0))
        ttk.Button(perf_btn_row, text="Check GPU", command=self._check_gpu).pack(side="left", padx=(0, 8))
        if current_compute != "float16":
            ttk.Button(perf_btn_row, text="Enable Power Mode",
                       command=self._enable_power_mode).pack(side="left", padx=(0, 8))
        else:
            ttk.Button(perf_btn_row, text="Switch to Standard Mode",
                       command=self._disable_power_mode).pack(side="left", padx=(0, 8))
        ttk.Button(perf_btn_row, text="Learn more",
                   command=self._open_cuda_url).pack(side="left")

        # --- History ---
        ttk.Label(main, text="HISTORY", style="Header.TLabel").pack(anchor="w", pady=(15, 5))

        hist_frame = ttk.Frame(main)
        hist_frame.pack(fill="x", pady=2)
        ttk.Button(hist_frame, text="View transcript history", command=self._open_history).pack(side="left", padx=(0, 10))
        ttk.Button(hist_frame, text="Export history", command=self._export_history).pack(side="left")

        # --- Buttons ---
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill="x", pady=(20, 0))

        ttk.Button(btn_frame, text="Save & Restart Koda", command=self.save_and_restart).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="Save", command=self.save).pack(side="left", padx=(0, 10))
        ttk.Button(btn_frame, text="Cancel", command=self.on_close).pack(side="left")

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
        # Kill only the main Koda process (pythonw.exe).
        # Do NOT kill python.exe — that's this settings GUI process.
        subprocess.run(["powershell", "-Command",
                        "Get-Process pythonw -ErrorAction SilentlyContinue | Stop-Process -Force"],
                       capture_output=True)
        time.sleep(0.5)
        # Restart
        start_bat = os.path.join(SCRIPT_DIR, "start.bat")
        subprocess.Popen(["cmd", "/c", start_bat], cwd=SCRIPT_DIR,
                         creationflags=subprocess.CREATE_NO_WINDOW)
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
