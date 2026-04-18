"""
Windows context menu integration for Koda.

Adds "Transcribe with Koda" to right-click menu for audio files.
Registers/unregisters shell context menu entries in the Windows Registry.

Usage:
  python context_menu.py install    — Add context menu entry
  python context_menu.py uninstall  — Remove context menu entry
  python context_menu.py transcribe <filepath>  — Transcribe a file (called by context menu)
"""

import sys
import os
import winreg

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Audio file extensions to register
AUDIO_EXTENSIONS = [
    ".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm", ".wma", ".aac", ".opus",
]

# Registry key name
MENU_KEY_NAME = "KodaTranscribe"


def _get_python_exe():
    """Get the path to pythonw.exe (windowless) in the venv, or fall back to python.exe."""
    venv_pythonw = os.path.join(SCRIPT_DIR, "venv", "Scripts", "pythonw.exe")
    if os.path.exists(venv_pythonw):
        return venv_pythonw
    venv_python = os.path.join(SCRIPT_DIR, "venv", "Scripts", "python.exe")
    if os.path.exists(venv_python):
        return venv_python
    return sys.executable


def install():
    """Register 'Transcribe with Koda' in the Windows Explorer context menu."""
    python_exe = _get_python_exe()
    script_path = os.path.join(SCRIPT_DIR, "context_menu.py")
    command = f'"{python_exe}" "{script_path}" transcribe "%1"'

    registered = []
    failed = []

    for ext in AUDIO_EXTENSIONS:
        try:
            # Create/open the extension key
            ext_key = winreg.CreateKey(winreg.HKEY_CURRENT_USER,
                                       f"Software\\Classes\\SystemFileAssociations\\{ext}\\shell\\{MENU_KEY_NAME}")
            winreg.SetValueEx(ext_key, "", 0, winreg.REG_SZ, "Transcribe with Koda")
            winreg.SetValueEx(ext_key, "Icon", 0, winreg.REG_SZ, f"{python_exe},0")

            # Create command subkey
            cmd_key = winreg.CreateKey(ext_key, "command")
            winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, command)

            winreg.CloseKey(cmd_key)
            winreg.CloseKey(ext_key)
            registered.append(ext)
        except Exception as e:
            failed.append((ext, str(e)))

    print(f"Registered context menu for: {', '.join(registered)}")
    if failed:
        print(f"Failed: {failed}")
    print("\nRight-click any audio file -> 'Transcribe with Koda'")


def uninstall():
    """Remove 'Transcribe with Koda' from the context menu."""
    removed = []
    for ext in AUDIO_EXTENSIONS:
        try:
            # Delete the command subkey first, then the menu key
            key_path = f"Software\\Classes\\SystemFileAssociations\\{ext}\\shell\\{MENU_KEY_NAME}"
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path + "\\command")
            except FileNotFoundError:
                pass
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, key_path)
            removed.append(ext)
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"Error removing {ext}: {e}")

    if removed:
        print(f"Removed context menu for: {', '.join(removed)}")
    else:
        print("No context menu entries found to remove.")


def transcribe(filepath):
    """Open the transcription window with the given file pre-loaded."""
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return

    # Add the project dir to path so imports work
    sys.path.insert(0, SCRIPT_DIR)

    from config import load_config
    config = load_config()

    # Load whisper model
    from faster_whisper import WhisperModel
    model_size = config.get("model_size", "base")

    print(f"Loading Whisper model ({model_size})...")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    # Open transcription window with file pre-selected
    from transcribe_file import TranscribeFileWindow
    win = TranscribeFileWindow(model, config)
    win._preload_file = filepath
    _run_with_preload(win, filepath)


def _run_with_preload(win, filepath):
    """Run the transcription window with a file pre-loaded."""
    import tkinter as tk
    from tkinter import ttk
    import threading
    import time

    from ui_theme import apply_dark_theme

    root = tk.Tk()
    root.title("Koda — Transcribe Audio File")
    root.geometry("650x500")

    apply_dark_theme(root)

    main = ttk.Frame(root, padding=20)
    main.pack(fill="both", expand=True)

    ttk.Label(main, text="Transcribe Audio File", style="Header.TLabel").pack(anchor="w", pady=(0, 10))

    # File path display
    ttk.Label(main, text=f"File: {os.path.basename(filepath)}").pack(anchor="w", pady=(0, 5))
    ttk.Label(main, text=f"Path: {filepath}", wraplength=600).pack(anchor="w", pady=(0, 10))

    status_label = ttk.Label(main, text="Transcribing... please wait.")
    status_label.pack(anchor="w", pady=(0, 10))

    text_widget = tk.Text(main, bg="#313244", fg="#cdd6f4", font=("Consolas", 10),
                          wrap="word", state="disabled")
    text_widget.pack(fill="both", expand=True, pady=(0, 10))

    bottom = ttk.Frame(main)
    bottom.pack(fill="x")

    def copy_text():
        content = text_widget.get("1.0", "end").strip()
        if content:
            root.clipboard_clear()
            root.clipboard_append(content)
            status_label.config(text="Copied to clipboard!")

    ttk.Button(bottom, text="Copy to clipboard", command=copy_text).pack(side="left", padx=(0, 10))
    ttk.Button(bottom, text="Close", command=root.destroy).pack(side="right")

    def do_transcribe():
        try:
            start = time.time()
            kwargs = {"beam_size": 5, "vad_filter": True}
            lang = win._config.get("language", "en")
            if lang != "auto":
                kwargs["language"] = lang

            segments, info = win._model.transcribe(filepath, **kwargs)
            result_parts = []
            for seg in segments:
                result_parts.append(seg.text.strip())

            result = " ".join(result_parts)
            duration = time.time() - start
            detected_lang = getattr(info, 'language', lang)

            header = f"Language: {detected_lang} | Transcribed in {duration:.1f}s\n"
            header += "\u2500" * 50 + "\n\n"

            def update_ui():
                text_widget.config(state="normal")
                text_widget.delete("1.0", "end")
                text_widget.insert("1.0", header + result)
                text_widget.config(state="disabled")
                status_label.config(text=f"Done in {duration:.1f}s")

            root.after(0, update_ui)

        except Exception as e:
            def show_error():
                text_widget.config(state="normal")
                text_widget.delete("1.0", "end")
                text_widget.insert("1.0", f"Error: {e}")
                text_widget.config(state="disabled")
                status_label.config(text="Error")
            root.after(0, show_error)

    threading.Thread(target=do_transcribe, daemon=True).start()
    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python context_menu.py install      — Add right-click menu")
        print("  python context_menu.py uninstall    — Remove right-click menu")
        print("  python context_menu.py transcribe <file>  — Transcribe a file")
        sys.exit(1)

    action = sys.argv[1].lower()

    if action == "install":
        install()
    elif action == "uninstall":
        uninstall()
    elif action == "transcribe" and len(sys.argv) >= 3:
        transcribe(sys.argv[2])
    else:
        print(f"Unknown action: {action}")
        sys.exit(1)
