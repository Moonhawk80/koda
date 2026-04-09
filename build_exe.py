"""Build Koda as a single .exe using PyInstaller, with bundled Whisper model."""
import PyInstaller.__main__
import os
import shutil

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.expanduser("~/.cache/huggingface/hub/models--Systran--faster-whisper-base/snapshots/ebe41f70d5b6dfa9166e2c581c45c9c0cfc57b66")

# Copy model to a local dir for bundling
bundle_model = os.path.join(SCRIPT_DIR, "_model_base")
if os.path.exists(MODEL_DIR):
    if os.path.exists(bundle_model):
        shutil.rmtree(bundle_model)
    shutil.copytree(MODEL_DIR, bundle_model)
    print(f"Copied Whisper model to {bundle_model}")
else:
    print(f"WARNING: Model not found at {MODEL_DIR}")
    bundle_model = None

args = [
    os.path.join(SCRIPT_DIR, "voice.py"),
    "--name=Koda",
    "--onefile",
    "--windowed",
    "--icon=NONE",
    f"--add-data={os.path.join(SCRIPT_DIR, 'config.py')};.",
    f"--add-data={os.path.join(SCRIPT_DIR, 'text_processing.py')};.",
    f"--add-data={os.path.join(SCRIPT_DIR, 'settings_gui.py')};.",
    f"--add-data={os.path.join(SCRIPT_DIR, 'sounds')};sounds",
    "--hidden-import=pystray._win32",
    "--hidden-import=PIL._tkinter_finder",
    "--hidden-import=comtypes.stream",
    "--hidden-import=pyttsx3.drivers",
    "--hidden-import=pyttsx3.drivers.sapi5",
    f"--distpath={os.path.join(SCRIPT_DIR, 'dist')}",
    f"--workpath={os.path.join(SCRIPT_DIR, 'build')}",
    f"--specpath={SCRIPT_DIR}",
    "--clean",
]

if bundle_model:
    args.append(f"--add-data={bundle_model};_model_base")

PyInstaller.__main__.run(args)

# Cleanup
if bundle_model and os.path.exists(bundle_model):
    shutil.rmtree(bundle_model)
    print("Cleaned up bundled model copy")

print()
print(f"Build complete! Output: {os.path.join(SCRIPT_DIR, 'dist', 'Koda.exe')}")
