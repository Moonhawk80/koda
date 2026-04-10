# Koda

Push-to-talk voice input for any app. Speak into your microphone and your words get transcribed and pasted directly into Claude Code, ChatGPT, Google Chat, Slack, email — any active window.

Runs locally using [Whisper](https://github.com/openai/whisper) — no cloud API, no cost, fully offline after initial setup.

---

## Features

### Core
- **Push-to-talk** — Hold a hotkey to record, release to transcribe and paste
- **Two modes** — Dictation (light cleanup) and Command (full cleanup for coding)
- **Streaming transcription** — Live preview of what you're saying while recording
- **Hold-to-talk or Toggle** — Hold the key, or press once and it auto-stops via VAD
- **Sound effects** — Audio chimes for recording start/stop/success
- **System tray app** — Branded K icon with color-coded status dot
- **Single-instance** — Prevents duplicate processes via Windows mutex
- **Offline** — All processing happens locally

### Text Processing
- **Filler word removal** — Strips "um", "uh", "you know", "basically"
- **Auto-formatting** — Spoken numbers, dates, emails, and punctuation converted automatically
  - "one hundred twenty three" → "123"
  - "january fifth twenty twenty six" → "January 5, 2026"
  - "alex at gmail dot com" → "alex@gmail.com"
  - "em dash" → "—", "dot dot dot" → "..."
- **Code vocabulary** — Say "open paren" and get `(`, "camel case user name" → `userName`
- **Custom vocabulary** — Add domain-specific words to `custom_words.json`
- **Smart capitalization** — Sentence-start caps, standalone "I" correction

### Voice Editing
- **30+ voice commands** — "select all", "undo", "new line", "delete word", "go to end", etc.
- Commands are detected and executed as keyboard actions, stripped from text output
- Works alongside regular dictation — say "hello world new line" to type and press Enter

### Productivity
- **Per-app profiles** — Auto-switch settings by active window (e.g., code vocab ON in VS Code, OFF in Slack)
- **Floating overlay** — Draggable branded K icon showing recording state
- **Audio file transcription** — GUI for transcribing audio files with timestamps
- **Context menu** — Right-click audio files in Explorer to transcribe
- **Usage stats dashboard** — Words dictated, time saved, top apps, 7-day chart
- **Real-time translation** — Whisper native (any → English) or Ollama LLM (any → any language)

### Polish
- **Read-back** — Reads last transcription or selected text aloud with speed control
- **Correction mode** — Undo last paste and re-record
- **LLM polish** — Optional local AI cleanup via Ollama (free, no API costs)
- **Settings GUI** — Graphical settings window for easy configuration
- **Noise reduction** — Optional background noise filtering
- **Auto-start** — Optional Windows startup integration

---

## Requirements

- **Windows 10 or 11**
- **Python 3.10 or newer** — [Download here](https://www.python.org/downloads/)
  - During installation, **check "Add Python to PATH"**
- **A microphone** (USB, headset, or built-in)
- **~500MB disk space** (for packages + Whisper model)
- **Ollama** (optional, for LLM polish/translation) — [Download here](https://ollama.com/download)

---

## Installation

### Step 1: Download

```
git clone https://github.com/Alex-Alternative/koda.git
cd koda
```

Or click **Code → Download ZIP** on GitHub, extract to a folder like `C:\koda`.

### Step 2: Run the installer

1. Open the folder in File Explorer
2. **Double-click `install.bat`**
3. Follow the setup wizard (picks your mic, hotkeys, preferences)

### Step 3: Verify (optional)

Double-click **`test.bat`** to run the stress test.

---

## Usage

### Starting Koda

**Double-click `start.bat`**

A branded K icon appears in your system tray (bottom-right, near the clock). Click the **^** arrow if hidden.

| Icon Color | Status |
|---|---|
| Gray | Loading model (~10 seconds) |
| Green | Ready |
| Red | Recording |
| Orange | Transcribing |
| Purple | Reading aloud |
| Blue | Listening (wake word) |

### Hotkey Reference

| Hotkey | Action |
|---|---|
| **Ctrl+Space** | Dictation — hold to talk, release to paste (light cleanup) |
| **Ctrl+Shift+Period** | Command mode — hold to talk (full cleanup + code vocab) |
| **Ctrl+Shift+Z** | Correction — undo last paste and re-record |
| **Ctrl+Alt+R** | Read back — reads last transcription aloud |
| **Ctrl+Alt+T** | Read selected — reads highlighted text aloud |

All hotkeys are configurable in `config.json` or via the setup wizard (`configure.bat`).

### Right-click tray menu

- Toggle sound effects, filler removal, code vocabulary, auto-formatting, noise reduction, LLM polish
- Toggle floating overlay, per-app profiles, voice commands
- Open usage stats dashboard
- Choose read-back voice and speed (Slow / Normal / Fast)
- Switch between Hold and Toggle mode
- Open Settings GUI or config file directly
- Install/uninstall Explorer context menu
- Quit

---

## Auto-Formatting

When enabled (on by default), Koda automatically converts spoken patterns:

### Numbers
Converts when a scale word (hundred, thousand, million) is present:
- "one hundred twenty three" → "123"
- "two thousand and five" → "2,005"
- "three million" → "3,000,000"
- "five hundred dollars" → "$500"
- "one hundred percent" → "100%"

### Dates
- "january fifth twenty twenty six" → "January 5, 2026"
- "march 3rd" → "March 3"
- "december twenty fifth" → "December 25"

### Emails
- "alex at gmail dot com" → "alex@gmail.com"
- "john dot doe at company dot co dot uk" → "john.doe@company.co.uk"

### Punctuation
- "em dash" or "dash dash" → "—"
- "dot dot dot" or "ellipsis" → "..."
- "exclamation point" → "!"

---

## Voice Editing Commands

Speak these phrases during dictation and Koda executes them as keyboard actions:

| You say | Action |
|---|---|
| "select all" | Ctrl+A |
| "copy" / "cut" / "paste" | Ctrl+C / X / V |
| "undo" / "redo" | Ctrl+Z / Y |
| "delete that" | Backspace |
| "delete word" | Ctrl+Backspace |
| "delete line" | Select and delete current line |
| "new line" / "new paragraph" | Enter / Double Enter |
| "go to top" / "go to end" | Ctrl+Home / Ctrl+End |
| "select line" / "select word" | Select current line / previous word |
| "bold" / "italic" / "underline" | Ctrl+B / I / U |
| "save" / "find" | Ctrl+S / F |
| "tab" / "escape" | Tab / Escape |

Commands can appear at the start or end of text: "hello world new line" types "hello world" then presses Enter.

---

## Per-App Profiles

Koda automatically switches settings based on the active window. Edit `profiles.json` to customize.

**Default profiles:**
- **VS Code** / **Terminal** — Code vocabulary ON, auto-formatting OFF
- **Slack** — Code vocabulary OFF, filler removal ON
- **Outlook** — Code vocabulary OFF, auto-capitalize ON

**Custom profile example:**
```json
{
  "My App": {
    "match": {"process": "myapp.exe"},
    "settings": {
      "post_processing": {
        "code_vocabulary": true,
        "auto_format": false
      }
    }
  }
}
```

Match by process name or window title regex: `{"title": "Chrome|Firefox"}`.

---

## Floating Overlay

A small branded K icon floats on your desktop showing Koda's status:
- **Green dot** — Ready
- **Red dot** — Recording
- **Orange dot** — Transcribing
- **Drag** to reposition, **right-click** to hide/show

Toggle in the tray menu or set `"overlay_enabled": true/false` in config.

---

## Usage Stats Dashboard

Track your voice productivity. Open from the tray menu.

- **Words dictated** — total and per-day chart
- **Time saved** — compared to typing at 40 WPM
- **Commands used** — most frequent voice commands
- **Per-app breakdown** — which apps you dictate in most
- **7-day chart** — daily word count trend

---

## Audio File Transcription

Transcribe audio files with a GUI:
- **Tray menu** → Transcribe Audio File
- **Right-click** an audio file in Explorer → Transcribe with Koda

Supports: WAV, MP3, FLAC, M4A, OGG, and more. Shows timestamps and allows saving the transcript.

---

## Settings GUI

Koda includes a graphical settings window for easy configuration without editing JSON files.

**How to open:**
- Right-click the Koda tray icon and select **Settings window**
- Double-click **`settings.bat`** in the Koda folder
- Or use the desktop shortcut (created during install)

Changes take effect after restarting Koda. The Settings GUI includes a **Save & Restart** button.

---

## Streaming Transcription

When enabled (on by default), Koda shows a live preview of your speech while you're still recording.

- The tray icon tooltip and floating overlay update every 2 seconds
- The final transcription uses a higher-quality pass
- Toggle in the Settings GUI or `config.json` (`"streaming": true`)

---

## Read-back Speed Control

| Speed | Words per minute | Best for |
|---|---|---|
| Slow | 120 | Careful review, accessibility |
| Normal | 160 | General use (default) |
| Fast | 220 | Quick playback |

Change via tray menu > **Read-back speed**, Settings GUI, or `config.json`: `"tts": {"rate": "normal"}`.

---

## Configuration

All settings are in `config.json` (created on first run). Edit directly or use the tray menu.

### Key settings

| Setting | Default | Description |
|---|---|---|
| `model_size` | `"small"` | `tiny`, `base`, `small`, `medium`, `large-v3` |
| `language` | `"en"` | Speech language, or `"auto"` for detection |
| `hotkey_dictation` | `"ctrl+space"` | Dictation mode hotkey |
| `hotkey_command` | `"ctrl+shift+."` | Command mode hotkey |
| `hotkey_correction` | `"ctrl+shift+z"` | Undo and re-record |
| `hotkey_readback` | `"ctrl+alt+r"` | Read last transcription aloud |
| `hotkey_readback_selected` | `"ctrl+alt+t"` | Read selected text aloud |
| `hotkey_mode` | `"hold"` | `"hold"` or `"toggle"` (auto-stops on silence) |
| `mic_device` | `null` | Mic device index or `null` for system default |
| `sound_effects` | `true` | Play chimes on record/stop/paste |
| `overlay_enabled` | `true` | Floating status overlay |
| `profiles_enabled` | `true` | Per-app profile switching |
| `voice_commands` | `true` | Voice editing commands |
| `auto_format` | `true` | Auto-format numbers, dates, emails |
| `noise_reduction` | `false` | Filter background noise (slower) |
| `streaming` | `true` | Live transcription preview |
| `llm_polish.enabled` | `false` | AI cleanup via Ollama |
| `llm_polish.model` | `"phi3:mini"` | Ollama model to use |
| `translation.enabled` | `false` | Real-time translation |
| `translation.target_language` | `"English"` | Target language for translation |
| `tts.rate` | `"normal"` | Read-back speed |

### Whisper model sizes

| Model | Download | Speed | Accuracy | Notes |
|---|---|---|---|---|
| `tiny` | ~75MB | Fastest | Lower | Quick drafts |
| `base` | ~150MB | Fast | Good | Lightweight |
| `small` | ~500MB | Medium | Better | **Recommended** |
| `medium` | ~1.5GB | Slower | High | |
| `large-v3` | ~3GB | Slowest | Highest | Best with GPU |

---

## LLM Prompt Polish (Optional)

Command mode can use a local AI model to clean up your speech into clear instructions.

**Setup:**
1. Install Ollama: https://ollama.com/download
2. Open a terminal and run: `ollama pull phi3:mini`
3. Enable in config: set `"llm_polish": {"enabled": true, "model": "phi3:mini"}`
4. Make sure Ollama is running before using command mode

**Example:**
- You say: *"uh can you like go into the database and um fix that thing where the dates are wrong"*
- Pasted: *"Fix the date formatting issue in the database"*

---

## Code Vocabulary (Command Mode)

When enabled, these spoken words expand in command mode:

| You say | You get |
|---|---|
| "open paren" / "close paren" | `(` / `)` |
| "open bracket" / "close bracket" | `[` / `]` |
| "open brace" / "close brace" | `{` / `}` |
| "semicolon" | `;` |
| "equals" / "double equals" | `=` / `==` |
| "arrow" / "fat arrow" | `->` / `=>` |
| "new line" | actual line break |
| "hash" | `#` |
| "pipe" | `\|` |

### Case formatting

| You say | You get |
|---|---|
| "camel case user name" | `userName` |
| "snake case get user data" | `get_user_data` |
| "pascal case my component" | `MyComponent` |
| "kebab case page title" | `page-title` |
| "screaming snake max retries" | `MAX_RETRIES` |

---

## Auto-Start with Windows

Double-click **`install_startup.bat`** to start Koda on login.

Double-click **`uninstall_startup.bat`** to remove.

---

## Troubleshooting

### Short phrases not transcribing
- Hold the key a beat longer before and after speaking
- The Whisper model needs at least ~1 second of audio

### No sound effects
- Check your Windows audio output device
- Sounds play through the system default output

### Transcription is slow
- Use the `tiny` or `base` model in config
- Close CPU-heavy applications
- If you have an NVIDIA GPU, update CUDA drivers for much faster transcription

### Wrong microphone
- Set `mic_device` to `null` in config (uses system default)
- Or change your default mic in Windows: Settings > System > Sound > Input

### LLM polish not working
- Make sure Ollama is running: open a terminal, run `ollama serve`
- Make sure the model is downloaded: `ollama pull phi3:mini`

### Double paste or extra characters
- Make sure only one Koda instance is running (check Task Manager for pythonw.exe)
- Koda uses a mutex to prevent duplicates, but stale processes from debug runs can persist

### Overlay not draggable
- Click on the icon itself (the dark square), not the tiny transparent corners

---

## Files

| File | Purpose |
|---|---|
| `voice.py` | Main application — tray icon, recording, transcription, paste |
| `config.py` | Configuration management |
| `text_processing.py` | Auto-formatting, filler removal, code vocab, case formatting |
| `voice_commands.py` | 30+ voice editing commands |
| `overlay.py` | Floating status overlay |
| `profiles.py` | Per-app profile matching and switching |
| `stats.py` | Usage statistics (SQLite) |
| `stats_gui.py` | Stats dashboard GUI |
| `transcribe_file.py` | Audio file transcription GUI |
| `context_menu.py` | Windows Explorer right-click integration |
| `history.py` | Transcript history (SQLite) |
| `config.json` | Your settings (auto-created) |
| `profiles.json` | Per-app profile definitions |
| `custom_words.json` | Custom vocabulary replacements |
| `configure.py` | Interactive setup wizard |
| `settings_gui.py` | Graphical settings window |
| `build_exe.py` | Build standalone Koda.exe |
| `test_features.py` | Test suite for Phase 2-4 features |

---

## Building the .exe (for distribution without Python)

```
cd koda
venv\Scripts\activate
python build_exe.py
```

Output: `dist\Koda.exe` (~400MB+ with small model). No Python installation required for recipients.

---

## License

MIT
