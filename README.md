# Voice-to-Claude

Push-to-talk voice input for [Claude Code](https://claude.ai/claude-code). Speak into your microphone and your words get transcribed and pasted directly into Claude Code (or any active window).

Runs locally using [OpenAI Whisper](https://github.com/openai/whisper) — no cloud API, no cost, fully offline after initial setup.

---

## Features

- **Push-to-talk** — Hold `F9` to record, release to transcribe and paste
- **System tray app** — Runs silently in the background with a status icon
- **Color-coded status** — Green (ready), Red (recording), Orange (transcribing)
- **Offline** — All processing happens locally on your machine
- **Auto-start** — Optional Windows startup integration
- **Lightweight** — Uses `faster-whisper` with int8 quantization for fast CPU inference

---

## Requirements

- **Windows 10 or 11**
- **Python 3.10 or newer** — [Download here](https://www.python.org/downloads/)
  - During installation, **check "Add Python to PATH"**
- **A microphone** (built-in, USB, or headset)
- **~500MB disk space** (for Python packages + Whisper model)

---

## Installation

### Step 1: Download

Clone this repository or download and extract the ZIP:

```
git clone https://github.com/YOUR_ORG/voice-to-claude.git
cd voice-to-claude
```

Or click the green **Code** button on GitHub → **Download ZIP** → extract to a folder like `C:\voice-to-claude`.

### Step 2: Run the installer

1. Open the folder in File Explorer
2. **Double-click `install.bat`**
3. Wait for it to finish (installs dependencies + downloads the Whisper model)

That's it. You'll see "Installation complete!" when done.

### Step 3: Verify (optional)

Double-click **`test.bat`** to run the stress test. It checks your mic, audio capture, Whisper model, clipboard, keyboard hooks, and runs a full end-to-end test. All tests should show `[PASS]`.

---

## Usage

### Starting Voice-to-Claude

**Double-click `start.bat`**

A microphone icon will appear in your system tray (bottom-right of your screen, near the clock). You may need to click the **^** arrow to see it.

| Icon Color | Status |
|---|---|
| Gray | Loading model (wait ~10 seconds) |
| Green | Ready — hold F9 to talk |
| Red | Recording your voice |
| Orange | Transcribing your speech |

### Speaking a command

1. Open Claude Code (or any terminal/app where you want the text)
2. Make sure the target window is focused
3. **Hold `F9`** and speak your message
4. **Release `F9`** — your speech is transcribed and pasted into the active window

### Stopping Voice-to-Claude

Right-click the tray icon → **Quit**

---

## Hotkey Reference

| Key | Action |
|---|---|
| **Hold F9** | Push-to-talk (record while held) |
| **Right-click tray icon → Quit** | Stop Voice-to-Claude |

### Changing the hotkey

Open `voice.py` in a text editor and change this line:

```python
HOTKEY_RECORD = "f9"
```

You can use any key or combination, for example:
- `"f8"` — F8 key
- `"scroll lock"` — Scroll Lock key
- `"ctrl+shift+space"` — Ctrl+Shift+Space

Save the file and restart Voice-to-Claude.

---

## Auto-Start with Windows

To launch Voice-to-Claude automatically when you log in:

1. Double-click **`install_startup.bat`**

To remove it from startup:

1. Double-click **`uninstall_startup.bat`**

---

## Changing the Whisper Model

Open `voice.py` and change `MODEL_SIZE`:

```python
MODEL_SIZE = "base"  # Options: tiny, base, small, medium, large-v3
```

| Model | Size | Speed | Accuracy | Best for |
|---|---|---|---|---|
| `tiny` | ~75MB | Fastest | Lower | Quick commands, fast machine |
| `base` | ~150MB | Fast | Good | **Recommended default** |
| `small` | ~500MB | Medium | Better | Detailed dictation |
| `medium` | ~1.5GB | Slower | High | Long-form speech |
| `large-v3` | ~3GB | Slowest | Highest | Maximum accuracy (needs good CPU/GPU) |

Save and restart Voice-to-Claude after changing.

---

## Troubleshooting

### "No speech detected"
- Check your microphone is set as the default input device in Windows Sound Settings
- Speak closer to the mic or louder
- Run `test.bat` to verify your mic is capturing audio

### Tray icon doesn't appear
- Check the **^** arrow in the system tray for hidden icons
- Make sure no error window popped up behind other windows
- Try running from a terminal to see errors:
  ```
  cd C:\voice-to-claude
  venv\Scripts\activate
  python voice.py
  ```

### F9 doesn't trigger recording
- Some apps may intercept F9 — try a different hotkey (see Hotkey Reference above)
- The `keyboard` library may need Administrator privileges on some systems. Try right-clicking `start.bat` → **Run as administrator**

### Transcription is slow
- Switch to the `tiny` model for faster results
- Close other CPU-heavy applications
- The first transcription after startup is always slower (model warm-up)

### Wrong microphone is being used
- Open Windows **Settings → System → Sound → Input** and set your preferred microphone as default
- Restart Voice-to-Claude after changing

---

## Files

| File | Purpose |
|---|---|
| `voice.py` | Main application |
| `install.bat` | One-time installer (sets up environment + model) |
| `start.bat` | Launches Voice-to-Claude |
| `test.bat` | Runs the stress test suite |
| `test_stress.py` | Stress test script |
| `install_startup.bat` | Adds Voice-to-Claude to Windows startup |
| `uninstall_startup.bat` | Removes Voice-to-Claude from Windows startup |
| `requirements.txt` | Python package list |

---

## License

MIT
