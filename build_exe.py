"""Build Koda as a single .exe using PyInstaller, with bundled Whisper model."""
import PyInstaller.__main__
import os
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.expanduser("~/.cache/huggingface/hub/models--Systran--faster-whisper-small/snapshots/536b0662742c02347bc0e980a01041f333bce120")

# Copy model to a local dir for bundling
bundle_model = os.path.join(SCRIPT_DIR, "_model_small")
if os.path.exists(MODEL_DIR):
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
    "custom_words.json",
    "profiles.json",
]

args = [
    os.path.join(SCRIPT_DIR, "voice.py"),
    "--name=Koda",
    "--onefile",
    "--windowed",
    "--icon=NONE",
    # Bundle all module files
    *[f"--add-data={os.path.join(SCRIPT_DIR, f)};." for f in DATA_FILES if os.path.exists(os.path.join(SCRIPT_DIR, f))],
    # Bundle sounds directory and plugins
    f"--add-data={os.path.join(SCRIPT_DIR, 'sounds')};sounds",
    f"--add-data={os.path.join(SCRIPT_DIR, 'plugins')};plugins",
    # Hidden imports for pystray, PIL, pyttsx3
    "--hidden-import=pystray._win32",
    "--hidden-import=PIL._tkinter_finder",
    "--hidden-import=comtypes.stream",
    "--hidden-import=pyttsx3.drivers",
    "--hidden-import=pyttsx3.drivers.sapi5",
    # Output paths
    f"--distpath={os.path.join(SCRIPT_DIR, 'dist')}",
    f"--workpath={os.path.join(SCRIPT_DIR, 'build')}",
    f"--specpath={SCRIPT_DIR}",
    "--clean",
]

if bundle_model:
    args.append(f"--add-data={bundle_model};_model_small")

print("Building Koda.exe with all Phase 1-4 features + small model...")
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
