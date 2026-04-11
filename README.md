# Koda

Push-to-talk voice input for any app. Speak into your microphone and your words get transcribed and pasted directly into Claude, ChatGPT, Slack, email — any active window.

Three modes: **Dictation** (raw text), **Command** (cleaned up), and **Prompt Assist** (structures your speech into effective LLM prompts).

Runs locally using [Whisper](https://github.com/openai/whisper) — no cloud API, no cost, fully offline after initial setup.

---

## Hotkeys

| Key | Action |
|---|---|
| **Ctrl+Space** | Dictation — hold to talk, release to paste |
| **F8** | Command mode — cleaned up text with code vocabulary |
| **F9** | Prompt Assist — structures speech into LLM prompts |
| **F7** | Correction — undo last paste and re-record |
| **F6** | Read back — reads last transcription aloud |
| **F5** | Read selected — reads highlighted text aloud |

All hotkeys are configurable in `config.json`.

---

## Installation

### Option A: Windows Installer (recommended)

1. Download `KodaSetup-4.2.0.exe` from [Releases](https://github.com/Moonhawk80/koda/releases)
2. Double-click to install
3. Launch Koda from the Start Menu or desktop shortcut

### Option B: From Source

**Requirements:** Windows 10/11, Python 3.10+, a microphone, ~500MB disk space.

```
git clone https://github.com/Moonhawk80/koda.git
cd koda
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

Run the setup wizard:
```
python configure.py
```

Start Koda:
```
pythonw voice.py
```

A branded K icon appears in your system tray. Green dot = ready.

---

## Features

### Prompt Assist (F9)

Hold F9, describe what you need, release. Koda detects your intent and structures it into an effective prompt:

- **Code requests** — adds language, requirements, best practices
- **Debug requests** — structures as problem/cause/fix format
- **Explanations** — asks for examples, pitfalls, alternatives
- **Code review** — adds severity priorities and review criteria
- **Writing** — adds tone, structure, clarity guidelines

Works with Claude, ChatGPT, Gemini, or any LLM input.

### Text Processing
- **Filler word removal** — strips "um", "uh", "you know", "basically"
- **Auto-formatting** — spoken numbers, dates, emails, punctuation
  - "one hundred twenty three" -> "123"
  - "alex at gmail dot com" -> "alex@gmail.com"
  - "january fifth twenty twenty six" -> "January 5, 2026"
- **Code vocabulary** (Command mode) — "open paren" -> `(`, "camel case user name" -> `userName`
- **Custom vocabulary** — add domain-specific words to `custom_words.json`
- **Smart capitalization** — sentence-start caps, standalone "I" correction

### Voice Editing
- **30+ voice commands** — "select all", "undo", "new line", "delete word", "go to end", etc.
- Commands are detected and executed as keyboard actions, stripped from text output
- "hello world new line" types "hello world" then presses Enter

### Productivity
- **Per-app profiles** — auto-switch settings by active window (code vocab ON in VS Code, OFF in Slack)
- **Floating overlay** — draggable K icon showing recording state
- **Audio file transcription** — GUI for transcribing audio files with timestamps
- **Explorer context menu** — right-click audio files to transcribe
- **Usage stats dashboard** — words dictated, time saved, top apps, 7-day chart
- **Translation** — Whisper native (any -> English) or Ollama LLM (any -> any)

### Read-back
- **F6** reads last transcription aloud
- **F5** reads highlighted text aloud
- Speed: Slow (120 wpm), Normal (160 wpm), Fast (220 wpm)
- Change voice and speed from the tray menu

### LLM Polish (Optional)
Command mode can use a local AI via [Ollama](https://ollama.com) to clean up speech:
- You say: "uh can you like go into the database and um fix that thing where the dates are wrong"
- Pasted: "Fix the date formatting issue in the database"

Setup: `ollama pull phi3:mini`, then enable in config.

### Plugin System
Drop `.py` files in the `plugins/` folder to extend Koda with custom text processors, voice commands, and tray menu items. See `plugins/example_plugin.py.disabled`.

---

## Configuration

All settings in `config.json` (created on first run). Edit directly or use the tray menu.

| Setting | Default | Description |
|---|---|---|
| `model_size` | `"small"` | Whisper model: `tiny`, `base`, `small`, `medium`, `large-v3` |
| `language` | `"en"` | Speech language, or `"auto"` for detection |
| `hotkey_dictation` | `"ctrl+space"` | Dictation hotkey |
| `hotkey_command` | `"f8"` | Command mode hotkey |
| `hotkey_prompt` | `"f9"` | Prompt Assist hotkey |
| `hotkey_correction` | `"f7"` | Correction hotkey |
| `hotkey_readback` | `"f6"` | Read-back hotkey |
| `hotkey_readback_selected` | `"f5"` | Read selected hotkey |
| `hotkey_mode` | `"hold"` | `"hold"` or `"toggle"` (auto-stops on silence) |
| `sound_effects` | `true` | Audio chimes for record/stop/paste |
| `noise_reduction` | `false` | Filter background noise |
| `voice_commands` | `true` | Voice editing commands |
| `overlay_enabled` | `true` | Floating status overlay |
| `profiles_enabled` | `true` | Per-app profile switching |

### Whisper Models

| Model | Size | Speed | Accuracy |
|---|---|---|---|
| `tiny` | ~75MB | 0.06x RT | Lower |
| `base` | ~150MB | 0.19x RT | Good |
| **`small`** | ~500MB | **0.34x RT** | **Better (recommended)** |
| `medium` | ~1.5GB | Slower | High |
| `large-v3` | ~3GB | Slowest | Highest (needs GPU) |

---

## Tray Icon

| Color | Status |
|---|---|
| Gray | Loading model |
| Green | Ready |
| Red | Recording |
| Orange | Transcribing |
| Purple | Reading aloud |
| Blue | Listening (wake word) |

Right-click the tray icon to toggle features, open stats, change settings, and quit.

---

## Building

### Build Koda.exe (standalone, no Python needed)

```
venv\Scripts\activate
python build_exe.py
```

Output: `dist\Koda.exe` (~526MB with small model).

### Build Windows Installer

Requires [Inno Setup 6](https://jrsoftware.org/isdl.php).

```
python installer\build_installer.py
```

Output: `dist\KodaSetup-4.2.0.exe`.

---

## Architecture

- `voice.py` — main app: tray, recording, transcription, paste
- `hotkey_service.py` — keyboard hooks in a separate process (immune to GIL during transcription)
- `prompt_assist.py` — intent detection and prompt structuring for LLM use
- `text_processing.py` — auto-formatting, filler removal, code vocab
- `voice_commands.py` — 30+ voice editing commands
- `plugin_manager.py` — plugin discovery and lifecycle
- `overlay.py` — floating status overlay
- `profiles.py` — per-app profile switching
- `stats.py` / `stats_gui.py` — usage statistics and dashboard
- `config.py` — configuration management
- `history.py` — transcript history (SQLite)

---

## Troubleshooting

**Short phrases not transcribing** — hold the key a beat longer. Whisper needs ~1 second minimum.

**Transcription is slow** — use `tiny` or `base` model. Close CPU-heavy apps.

**Wrong microphone** — set `mic_device` to `null` in config (system default), or change your default mic in Windows Sound settings.

**Hotkeys not working** — check `debug.log` for errors. The hotkey service runs in a separate process; if it crashes, the watchdog auto-restarts it within 15 seconds.

**Double paste** — check Task Manager for stale pythonw.exe processes and kill them.

---

## License

MIT
