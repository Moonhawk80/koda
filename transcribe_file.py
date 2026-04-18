"""
Audio file transcription for Koda.

Transcribes .wav, .mp3, .m4a, .flac, .ogg, .webm files using the loaded Whisper model.
Shows results in a window with copy/save buttons.
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import time


class TranscribeFileWindow:
    """Window for drag-and-drop / file-pick audio transcription."""

    def __init__(self, model, config):
        self._model = model
        self._config = config
        self._root = None
        self._thread = None

    def show(self):
        """Open the transcription window in its own thread."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        self._root = tk.Tk()
        root = self._root

        from ui_theme import apply_dark_theme

        root.title("Koda — Transcribe Audio File")
        root.geometry("650x500")
        root.attributes("-topmost", True)

        apply_dark_theme(root)

        main = ttk.Frame(root, padding=20)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="Transcribe Audio File", style="Header.TLabel").pack(anchor="w", pady=(0, 10))

        # File selection
        file_frame = ttk.Frame(main)
        file_frame.pack(fill="x", pady=(0, 10))

        self._file_var = tk.StringVar()
        file_entry = ttk.Entry(file_frame, textvariable=self._file_var, width=55)
        file_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))

        ttk.Button(file_frame, text="Browse...", command=self._browse).pack(side="left")

        # Options row
        opt_frame = ttk.Frame(main)
        opt_frame.pack(fill="x", pady=(0, 10))

        ttk.Label(opt_frame, text="Language:").pack(side="left", padx=(0, 5))
        self._lang_var = tk.StringVar(value=self._config.get("language", "en"))
        lang_combo = ttk.Combobox(opt_frame, textvariable=self._lang_var, width=8,
                                  values=["auto", "en", "es", "fr", "de", "pt", "zh", "ja", "ko",
                                          "ar", "hi", "ru", "it", "nl", "pl", "tr"],
                                  state="readonly")
        lang_combo.pack(side="left", padx=(0, 15))

        self._timestamps_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(opt_frame, text="Include timestamps", variable=self._timestamps_var).pack(side="left")

        # Transcribe button
        btn_frame = ttk.Frame(main)
        btn_frame.pack(fill="x", pady=(0, 10))

        self._transcribe_btn = ttk.Button(btn_frame, text="Transcribe", command=self._transcribe)
        self._transcribe_btn.pack(side="left", padx=(0, 10))

        self._status_label = ttk.Label(btn_frame, text="")
        self._status_label.pack(side="left")

        # Results text area
        self._text = tk.Text(main, bg="#313244", fg="#cdd6f4", font=("Consolas", 10),
                             wrap="word", state="disabled")
        self._text.pack(fill="both", expand=True, pady=(0, 10))

        # Bottom buttons
        bottom = ttk.Frame(main)
        bottom.pack(fill="x")

        ttk.Button(bottom, text="Copy to clipboard", command=self._copy).pack(side="left", padx=(0, 10))
        ttk.Button(bottom, text="Save as .txt", command=self._save).pack(side="left", padx=(0, 10))
        ttk.Button(bottom, text="Close", command=root.destroy).pack(side="right")

        # Support file drop via command line args or drag
        root.drop_target_register = None  # tkdnd not available by default

        root.mainloop()

    def _browse(self):
        filepath = filedialog.askopenfilename(
            title="Select Audio File",
            filetypes=[
                ("Audio files", "*.wav *.mp3 *.m4a *.flac *.ogg *.webm *.wma"),
                ("All files", "*.*"),
            ],
        )
        if filepath:
            self._file_var.set(filepath)

    def _transcribe(self):
        filepath = self._file_var.get().strip()
        if not filepath or not os.path.exists(filepath):
            messagebox.showerror("Koda", "Please select a valid audio file.")
            return

        if self._model is None:
            messagebox.showerror("Koda", "Whisper model not loaded. Start Koda first.")
            return

        self._transcribe_btn.config(state="disabled")
        self._status_label.config(text="Transcribing...")
        self._set_text("Transcribing... please wait.")

        threading.Thread(target=self._do_transcribe, args=(filepath,), daemon=True).start()

    def _do_transcribe(self, filepath):
        try:
            start = time.time()

            # Build kwargs
            kwargs = {"beam_size": 5, "vad_filter": True}
            lang = self._lang_var.get()
            if lang != "auto":
                kwargs["language"] = lang

            segments, info = self._model.transcribe(filepath, **kwargs)

            include_timestamps = self._timestamps_var.get()
            lines = []
            full_text = []

            for seg in segments:
                if include_timestamps:
                    start_ts = _format_timestamp(seg.start)
                    end_ts = _format_timestamp(seg.end)
                    lines.append(f"[{start_ts} → {end_ts}]  {seg.text.strip()}")
                else:
                    full_text.append(seg.text.strip())

            if include_timestamps:
                result = "\n".join(lines)
            else:
                result = " ".join(full_text)

            duration = time.time() - start
            detected_lang = getattr(info, 'language', lang)

            header = f"File: {os.path.basename(filepath)}\n"
            header += f"Language: {detected_lang} | Duration: {duration:.1f}s to transcribe\n"
            header += "─" * 50 + "\n\n"

            self._set_text(header + result)
            self._root.after(0, lambda: self._status_label.config(text=f"Done in {duration:.1f}s"))

        except Exception as e:
            self._set_text(f"Error: {e}")
            self._root.after(0, lambda: self._status_label.config(text="Error"))

        finally:
            self._root.after(0, lambda: self._transcribe_btn.config(state="normal"))

    def _set_text(self, text):
        def _update():
            self._text.config(state="normal")
            self._text.delete("1.0", "end")
            self._text.insert("1.0", text)
            self._text.config(state="disabled")
        self._root.after(0, _update)

    def _copy(self):
        content = self._text.get("1.0", "end").strip()
        if content:
            self._root.clipboard_clear()
            self._root.clipboard_append(content)
            self._status_label.config(text="Copied!")

    def _save(self):
        content = self._text.get("1.0", "end").strip()
        if not content:
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Save Transcription",
        )
        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            self._status_label.config(text=f"Saved to {os.path.basename(filepath)}")


def _format_timestamp(seconds):
    """Format seconds as HH:MM:SS.sss."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:05.2f}"
    return f"{m:02d}:{s:05.2f}"
