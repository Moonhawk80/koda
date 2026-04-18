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

    # Open transcription window with file pre-selected (minimal mode —
    # auto-starts transcription, no file picker / options / save button).
    from transcribe_file import TranscribeFileWindow
    TranscribeFileWindow(model, config, preload_filepath=filepath, minimal=True).show(blocking=True)


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
