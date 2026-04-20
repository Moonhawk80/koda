"""Build Koda as a single .exe using PyInstaller, with bundled Whisper model."""
import PyInstaller.__main__
import importlib.util
import os
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def _find_faster_whisper_assets():
    """Locate faster_whisper/assets dynamically — works for venv AND CI."""
    spec = importlib.util.find_spec("faster_whisper")
    if spec is None or spec.origin is None:
        raise RuntimeError("faster_whisper not installed; run `pip install -r requirements.txt`")
    return os.path.join(os.path.dirname(spec.origin), "assets")


FASTER_WHISPER_ASSETS = _find_faster_whisper_assets()


def _find_whisper_model(model_name="small"):
    """Find the cached Whisper model snapshot directory dynamically.

    faster-whisper stores models at:
      ~/.cache/huggingface/hub/models--Systran--faster-whisper-{name}/snapshots/{hash}/

    The hash changes when Hugging Face updates the model. This finds whichever
    snapshot is present rather than requiring a hardcoded hash — important for
    CI builds where the model is freshly downloaded.
    """
    base = os.path.expanduser(
        f"~/.cache/huggingface/hub/models--Systran--faster-whisper-{model_name}/snapshots"
    )
    if not os.path.isdir(base):
        return None
    snapshots = sorted(os.listdir(base))
    return os.path.join(base, snapshots[-1]) if snapshots else None


MODEL_DIR = _find_whisper_model("small")

# Copy model to a local dir for bundling
bundle_model = os.path.join(SCRIPT_DIR, "_model_small")
if MODEL_DIR and os.path.exists(MODEL_DIR):
    if os.path.exists(bundle_model):
        shutil.rmtree(bundle_model)
    shutil.copytree(MODEL_DIR, bundle_model)
    print(f"Copied Whisper model to {bundle_model}")
else:
    print(f"WARNING: Model not found at {MODEL_DIR}")
    bundle_model = None

# All Python modules that voice.py imports
DATA_FILES = [
    "config.py",
    "text_processing.py",
    "settings_gui.py",
    "history.py",
    "overlay.py",
    "profiles.py",
    "transcribe_file.py",
    "voice_commands.py",
    "context_menu.py",
    "stats.py",
    "stats_gui.py",
    "plugin_manager.py",
    "hotkey_service.py",
    "prompt_assist.py",
    "updater.py",
    "formula_mode.py",
    "terminal_mode.py",
    "generate_icon.py",
    "custom_words.json",
    "profiles.json",
    "koda.ico",
]

args = [
    os.path.join(SCRIPT_DIR, "voice.py"),
    "--name=Koda",
    "--onefile",
    "--windowed",
    f"--icon={os.path.join(SCRIPT_DIR, 'koda.ico')}",
    # Bundle all module files
    *[f"--add-data={os.path.join(SCRIPT_DIR, f)};." for f in DATA_FILES if os.path.exists(os.path.join(SCRIPT_DIR, f))],
    # Bundle sounds directory and plugins
    f"--add-data={os.path.join(SCRIPT_DIR, 'sounds')};sounds",
    f"--add-data={os.path.join(SCRIPT_DIR, 'plugins')};plugins",
    # Bundle faster_whisper VAD model (required for transcription)
    f"--add-data={FASTER_WHISPER_ASSETS};faster_whisper/assets",
    # Hidden imports for pystray, PIL, pyttsx3, multiprocessing
    "--hidden-import=pystray._win32",
    "--hidden-import=PIL._tkinter_finder",
    "--hidden-import=comtypes.stream",
    "--hidden-import=pyttsx3.drivers",
    "--hidden-import=pyttsx3.drivers.sapi5",
    "--hidden-import=multiprocessing.popen_spawn_win32",
    # Exclude heavy optional dependencies not needed at runtime
    # scipy/sklearn/sympy: pulled by openwakeword/noisereduce (optional features)
    # matplotlib: pulled by noisereduce (optional)
    # pytest: dev dependency, not needed in exe
    # NOTE: tkinter is REQUIRED by overlay.py, settings_gui.py, stats_gui.py — do NOT exclude
    "--exclude-module=scipy",
    "--exclude-module=sklearn",
    "--exclude-module=scikit-learn",
    "--exclude-module=matplotlib",
    "--exclude-module=sympy",
    "--exclude-module=pytest",
    "--exclude-module=pygments",
    "--exclude-module=fontTools",
    "--exclude-module=setuptools",
    "--exclude-module=pip",
    # Hidden imports for tkinter (used by overlay/settings/stats GUIs)
    "--hidden-import=tkinter",
    "--hidden-import=tkinter.ttk",
    "--hidden-import=tkinter.messagebox",
    "--hidden-import=tkinter.filedialog",
    # Output paths
    f"--distpath={os.path.join(SCRIPT_DIR, 'dist')}",
    f"--workpath={os.path.join(SCRIPT_DIR, 'build')}",
    f"--specpath={SCRIPT_DIR}",
    "--clean",
]

if bundle_model:
    args.append(f"--add-data={bundle_model};_model_small")

print("Building Koda.exe with all features + small model...")
print(f"Bundling {len(DATA_FILES)} modules + sounds + Whisper model")
print()

PyInstaller.__main__.run(args)

# Cleanup
if bundle_model and os.path.exists(bundle_model):
    shutil.rmtree(bundle_model)
    print("Cleaned up bundled model copy")

exe_path = os.path.join(SCRIPT_DIR, 'dist', 'Koda.exe')
if os.path.exists(exe_path):
    size_mb = os.path.getsize(exe_path) / (1024 * 1024)
    print()
    print(f"Build complete! Output: {exe_path}")
    print(f"Size: {size_mb:.0f} MB")
else:
    print("ERROR: Build failed - Koda.exe not found")
