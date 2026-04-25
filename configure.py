"""
Koda Setup Wizard
Interactive configuration for first-time setup or reconfiguration.
"""

import json
import os
import sys
import time
import webbrowser
import numpy as np

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(SCRIPT_DIR, "config.json")

CUDA_DOWNLOAD_URL = "https://developer.nvidia.com/cuda-downloads"


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def banner():
    print()
    print("  ╔══════════════════════════════════════════╗")
    print("  ║        Koda Setup Wizard      ║")
    print("  ╚══════════════════════════════════════════╝")
    print()


def ask_choice(prompt, options, default=0):
    """Ask the user to pick from a numbered list. Returns the selected value."""
    print(f"  {prompt}\n")
    for i, (label, value) in enumerate(options):
        marker = " (recommended)" if i == default else ""
        print(f"    [{i + 1}] {label}{marker}")
    print()
    while True:
        raw = input(f"  Enter choice [1-{len(options)}] (default: {default + 1}): ").strip()
        if raw == "":
            return options[default][1]
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return options[idx][1]
        except ValueError:
            pass
        print(f"  Please enter a number between 1 and {len(options)}.")


def ask_yes_no(prompt, default=True):
    """Ask a yes/no question."""
    hint = "Y/n" if default else "y/N"
    raw = input(f"  {prompt} [{hint}]: ").strip().lower()
    if raw == "":
        return default
    return raw in ("y", "yes")


# ============================================================
# STEP 1: PERFORMANCE (GPU detection)
# ============================================================

def setup_performance():
    """
    Detect GPU and offer Standard vs Power Mode.
    Returns (model_size, compute_type) or (None, "int8") to let setup_model() decide.
    Bucket A — CUDA ready:       offer Power Mode choice
    Bucket B — NVIDIA, no CUDA:  offer to auto-install or show download URL
    Bucket C — no GPU:           silent, return CPU defaults
    """
    from hardware import detect_gpu, get_nvidia_gpu_name, try_install_cuda_packages

    print("  Checking your hardware...", end="", flush=True)
    status = detect_gpu()
    print(" done.\n")

    # ── Bucket C: no GPU — silent ────────────────────────────
    if status == "none":
        return None, "int8"

    gpu_name = get_nvidia_gpu_name() or "NVIDIA GPU"

    # ── Bucket A: CUDA ready — offer Power Mode ──────────────
    if status == "cuda_ready":
        clear()
        banner()
        print("  STEP 1 of 9: PERFORMANCE\n")
        print("  ─────────────────────────────────────────\n")
        print(f"  Great news — your computer supports Power Mode!\n")
        print(f"  Detected: {gpu_name}\n")
        print("  Standard Mode          Power Mode")
        print("  ───────────────────    ──────────────────────")
        print("  Good accuracy          Excellent accuracy")
        print("  ~1-2 sec response      Near-instant response")
        print("  Works on any PC        Uses your NVIDIA GPU\n")

        choice = ask_choice(
            "Which mode would you like?",
            [
                ("Power Mode  — faster and smarter (recommended for your PC)", "power"),
                ("Standard Mode — works great on any computer", "standard"),
            ],
            default=0,
        )
        print()
        input("  Press Enter to continue...")

        if choice == "power":
            return "large-v3-turbo", "float16"
        return None, "int8"

    # ── Bucket B: NVIDIA present but CUDA not set up ─────────
    clear()
    banner()
    print("  STEP 1 of 9: PERFORMANCE\n")
    print("  ─────────────────────────────────────────\n")
    print(f"  We found an NVIDIA GPU on your machine ({gpu_name}).")
    print("  Power Mode needs one extra piece to work.\n")
    print("  Power Mode gives you:")
    print("    - Near-instant transcription (vs ~1-2 seconds)")
    print("    - Excellent accuracy with a larger speech model\n")

    choice = ask_choice(
        "What would you like to do?",
        [
            ("Try to set it up automatically  (downloads ~400MB)", "auto"),
            ("Skip for now — use Standard Mode", "skip"),
            ("Show me how to set it up myself", "manual"),
        ],
        default=0,
    )

    if choice == "auto":
        print("\n  Installing GPU support — this may take a few minutes...")
        print("  (downloading NVIDIA runtime packages)\n")
        success = try_install_cuda_packages()
        if success:
            print("  GPU support installed successfully!\n")
            print("  Standard Mode          Power Mode")
            print("  ───────────────────    ──────────────────────")
            print("  Good accuracy          Excellent accuracy")
            print("  ~1-2 sec response      Near-instant response\n")
            confirm = ask_choice(
                "Power Mode is ready. Which would you like?",
                [
                    ("Power Mode  — faster and smarter (recommended)", "power"),
                    ("Standard Mode", "standard"),
                ],
                default=0,
            )
            print()
            input("  Press Enter to continue...")
            if confirm == "power":
                return "large-v3-turbo", "float16"
            return None, "int8"
        else:
            print("  Automatic setup didn't work on this system.\n")
            print("  You can still enable Power Mode manually:")
            print(f"    1. Download and install the NVIDIA CUDA Toolkit from:")
            print(f"       {CUDA_DOWNLOAD_URL}")
            print("    2. Restart Koda")
            print("    3. Open Settings and switch to Power Mode\n")
            print("  Saving instructions to: ENABLE_POWER_MODE.txt\n")
            _save_power_mode_instructions(gpu_name)
            open_browser = ask_yes_no("Open the NVIDIA download page in your browser now?", default=True)
            if open_browser:
                webbrowser.open(CUDA_DOWNLOAD_URL)
            input("\n  Press Enter to continue with Standard Mode...")
            return None, "int8"

    elif choice == "manual":
        print()
        print("  To enable Power Mode:")
        print(f"    1. Download the NVIDIA CUDA Toolkit (free):")
        print(f"       {CUDA_DOWNLOAD_URL}")
        print("    2. Install it and restart your computer")
        print("    3. Open Koda Settings and click 'Enable Power Mode'\n")
        print("  Saving these instructions to: ENABLE_POWER_MODE.txt\n")
        _save_power_mode_instructions(gpu_name)
        open_browser = ask_yes_no("Open the NVIDIA download page now?", default=True)
        if open_browser:
            webbrowser.open(CUDA_DOWNLOAD_URL)
        input("\n  Press Enter to continue with Standard Mode...")
        return None, "int8"

    # choice == "skip"
    print()
    input("  Press Enter to continue with Standard Mode...")
    return None, "int8"


def _save_power_mode_instructions(gpu_name):
    """Write a plain-text reminder file to the koda folder."""
    path = os.path.join(SCRIPT_DIR, "ENABLE_POWER_MODE.txt")
    lines = [
        "Koda Power Mode — Setup Instructions",
        "=" * 40,
        "",
        f"Your GPU: {gpu_name}",
        "",
        "Power Mode gives Koda near-instant transcription and better accuracy.",
        "To enable it:",
        "",
        "  1. Download the NVIDIA CUDA Toolkit (free) from:",
        f"     {CUDA_DOWNLOAD_URL}",
        "",
        "  2. Install it and restart your computer.",
        "",
        "  3. Open Koda Settings (right-click the tray icon > Settings)",
        "     and click 'Enable Power Mode' in the Performance section.",
        "",
        "  That's it — Koda will switch to Power Mode automatically.",
        "",
    ]
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ============================================================
# STEP 2: MICROPHONE
# ============================================================

def setup_microphone():
    clear()
    banner()
    print("  STEP 2 of 9: MICROPHONE\n")
    print("  ─────────────────────────────────────────\n")

    import sounddevice as sd
    devices = sd.query_devices()
    input_devices = [(i, d) for i, d in enumerate(devices) if d["max_input_channels"] > 0]

    if not input_devices:
        print("  [!] No microphones detected. Check your audio settings.")
        print("      Proceeding with system default.\n")
        input("  Press Enter to continue...")
        return None

    default_idx = sd.default.device[0]

    print("  Available microphones:\n")
    option_list = []
    default_choice = 0
    for pos, (idx, dev) in enumerate(input_devices):
        tag = " << DEFAULT" if idx == default_idx else ""
        name = dev["name"]
        print(f"    [{pos + 1}] {name}{tag}")
        option_list.append((name, idx))
        if idx == default_idx:
            default_choice = pos

    print()
    while True:
        raw = input(f"  Pick your microphone [1-{len(option_list)}] (default: {default_choice + 1}): ").strip()
        if raw == "":
            chosen_idx = option_list[default_choice][1]
            break
        try:
            pos = int(raw) - 1
            if 0 <= pos < len(option_list):
                chosen_idx = option_list[pos][1]
                break
        except ValueError:
            pass
        print(f"  Please enter a number between 1 and {len(option_list)}.")

    chosen_name = sd.query_devices(chosen_idx)["name"]
    print(f"\n  Selected: {chosen_name}\n")

    # Mic test
    if ask_yes_no("Test your microphone now?", default=True):
        print("\n  Recording 3 seconds — say something into your mic...\n")
        audio = sd.rec(int(3 * 16000), samplerate=16000, channels=1, dtype="float32", device=chosen_idx)
        sd.wait()
        peak = np.max(np.abs(audio))
        bar_len = int(min(peak * 100, 30))
        bar = "█" * bar_len + "░" * (30 - bar_len)

        print(f"  Volume: [{bar}] {peak:.3f}\n")
        if peak < 0.005:
            print("  [!] Very quiet — your mic might be muted or too far away.")
            print("      Check Windows Sound Settings and try again.\n")
        elif peak < 0.02:
            print("  [~] A bit quiet — try speaking louder or moving closer.\n")
        else:
            print("  [OK] Sounds good!\n")

        # Playback option
        if ask_yes_no("Play it back to hear yourself?", default=False):
            print("  Playing back...")
            sd.play(audio, samplerate=16000)
            sd.wait()
            print()

    input("  Press Enter to continue...")
    return chosen_idx if chosen_idx != default_idx else None


# ============================================================
# STEP 2: HOTKEYS
# ============================================================

FKEY_OPTIONS = [
    ("F5", "f5"), ("F6", "f6"), ("F7", "f7"), ("F8", "f8"),
    ("F9", "f9"), ("F10", "f10"), ("F11", "f11"), ("F12", "f12"),
]

# Prompt Assist gets its own list: Ctrl+F* variants are offered first because
# bare F9 collides with Alienware Command Center / other OEM performance-mode
# toggles on many laptops (see commit a55a0e7). Bare F-keys remain available
# for users on non-conflicting hardware.
PROMPT_FKEY_OPTIONS = [
    ("Ctrl + F9", "ctrl+f9"),
    ("Ctrl + F8", "ctrl+f8"),
    ("Ctrl + F10", "ctrl+f10"),
    ("Ctrl + F11", "ctrl+f11"),
    ("Ctrl + F12", "ctrl+f12"),
    ("F9", "f9"),
    ("F10", "f10"),
    ("F11", "f11"),
    ("F12", "f12"),
]

DICTATION_OPTIONS = [
    ("Ctrl + Space", "ctrl+space"),
    ("F8", "f8"),
    ("F9", "f9"),
    ("F10", "f10"),
    ("Ctrl + Alt + D", "ctrl+alt+d"),
]


def setup_hotkeys():
    clear()
    banner()
    print("  STEP 3 of 9: HOTKEYS\n")
    print("  ─────────────────────────────────────────\n")
    print("  Koda uses hotkeys to control voice input.")
    print("  Ctrl+Space for main dictation, F-keys for the rest.\n")
    print("  Here's what each one does:\n")
    print("  VOICE MODES (hold key to talk, release to paste):")
    print("    Dictation    - Pastes exactly what you say with light cleanup")
    print("    Command      - Cleans up your speech (removes fillers, formats code)")
    print("    Prompt Assist- Turns your speech into a structured prompt for")
    print("                   ChatGPT, Claude, or any AI tool\n")
    print("  UTILITIES:")
    print("    Correction   - Made a mistake? Undoes the last paste and lets")
    print("                   you re-record immediately")
    print("    Read Back    - Reads your last transcription out loud so you")
    print("                   can hear what was typed")
    print("    Read Selected- Highlight any text on screen and have Koda")
    print("                   read it to you\n")
    print("  NOTE: Prompt Assist defaults to Ctrl+F9 because bare F9 collides")
    print("        with Alienware Command Center and other OEM performance")
    print("        toggles on many laptops.\n")

    # --- Dictation (main) ---
    print("  ── Dictation hotkey (your main key, used most often) ──\n")
    dictation = ask_choice(
        "Pick your dictation hotkey:",
        DICTATION_OPTIONS,
        default=0,  # Ctrl+Space
    )
    print(f"\n  Dictation: {dictation}\n")

    # --- Customize the rest? ---
    print("  ── Other hotkeys (defaults shown) ──\n")
    print("    F8      = Command         - Hold to talk, pastes cleaned-up text")
    print("    Ctrl+F9 = Prompt Assist   - Hold to talk, pastes a structured AI prompt")
    print("    F7      = Correction      - Undo last paste and re-record")
    print("    F6      = Read Back       - Reads last transcription aloud")
    print("    F5      = Read Selected   - Reads highlighted text aloud\n")

    customize = ask_yes_no("Customize these? (or keep defaults)", default=False)

    command = "f8"
    prompt = "ctrl+f9"
    correction = "f7"
    readback = "f6"
    readback_sel = "f5"

    if customize:
        print("\n  Pick an F-key for each function:\n")

        print("  ── Command ──")
        print("  Hold to talk. Cleans up your speech: removes filler words,")
        print("  formats code terms, and optionally polishes with AI.\n")
        command = ask_choice("Command hotkey:", FKEY_OPTIONS, default=3)  # F8
        print()

        print("  ── Prompt Assist ──")
        print("  Hold to talk. Turns your speech into a well-structured prompt")
        print("  for ChatGPT, Claude, or any AI assistant.\n")
        prompt = ask_choice("Prompt Assist hotkey:", PROMPT_FKEY_OPTIONS, default=0)  # Ctrl+F9
        print()

        print("  ── Correction ──")
        print("  Made a mistake? Press this to undo the last paste and")
        print("  immediately start re-recording.\n")
        correction = ask_choice("Correction hotkey:", FKEY_OPTIONS, default=2)  # F7
        print()

        print("  ── Read Back ──")
        print("  Reads your last transcription out loud through your speakers")
        print("  so you can hear what was typed without looking.\n")
        readback = ask_choice("Read back hotkey:", FKEY_OPTIONS, default=1)  # F6
        print()

        print("  ── Read Selected ──")
        print("  Highlight any text on screen, press this key, and Koda")
        print("  reads it aloud. Great for proofreading.\n")
        readback_sel = ask_choice("Read selected hotkey:", FKEY_OPTIONS, default=0)  # F5

    print()
    input("  Press Enter to continue...")
    return dictation, command, prompt, correction, readback, readback_sel


# ============================================================
# STEP 3: HOTKEY MODE
# ============================================================

def setup_mode():
    clear()
    banner()
    print("  STEP 4 of 9: RECORDING MODE\n")
    print("  ─────────────────────────────────────────\n")

    mode = ask_choice(
        "How do you want recording to work?",
        [
            ("Hold-to-talk — hold the key while speaking, release to stop", "hold"),
            ("Toggle — press once to start, auto-stops when you stop talking", "toggle"),
        ],
        default=0,
    )

    print()
    input("  Press Enter to continue...")
    return mode


# ============================================================
# STEP 4: WHISPER MODEL
# ============================================================

def setup_model():
    clear()
    banner()
    print("  STEP 5 of 9: SPEECH MODEL\n")
    print("  ─────────────────────────────────────────\n")
    print("  Larger models are more accurate but slower.\n")

    model = ask_choice(
        "Pick a model size:",
        [
            ("Tiny    (~75MB)  — Fastest, less accurate", "tiny"),
            ("Base    (~150MB) — Good balance of speed and accuracy", "base"),
            ("Small   (~500MB) — Better accuracy, moderate speed", "small"),
            ("Medium  (~1.5GB) — High accuracy, slower", "medium"),
            ("Large v2  (~3GB)   — High accuracy, slow", "large-v2"),
            ("Large v3  (~3GB)   — Best accuracy, slowest (needs fast CPU)", "large-v3"),
            ("Large v3 Turbo     — Near-best accuracy, faster than v3", "large-v3-turbo"),
            ("Distil Large v3    — Distilled, fast + accurate", "distil-large-v3"),
            ("Distil Medium (EN) — English-only, fast + good", "distil-medium.en"),
        ],
        default=1,  # base
    )

    print()
    input("  Press Enter to continue...")
    return model


# ============================================================
# STEP 5: LANGUAGE
# ============================================================

def setup_language():
    clear()
    banner()
    print("  STEP 6 of 9: LANGUAGE\n")
    print("  ─────────────────────────────────────────\n")

    lang = ask_choice(
        "What language will you be speaking?",
        [
            ("English", "en"),
            ("Spanish", "es"),
            ("French", "fr"),
            ("German", "de"),
            ("Portuguese", "pt"),
            ("Chinese", "zh"),
            ("Japanese", "ja"),
            ("Korean", "ko"),
            ("Arabic", "ar"),
            ("Hindi", "hi"),
            ("Russian", "ru"),
            ("Italian", "it"),
            ("Dutch", "nl"),
            ("Polish", "pl"),
            ("Turkish", "tr"),
            ("Auto-detect", "auto"),
        ],
        default=0,
    )

    print()
    input("  Press Enter to continue...")
    return lang


# ============================================================
# STEP 6: PREFERENCES
# ============================================================

def setup_preferences():
    clear()
    banner()
    print("  STEP 7 of 9: PREFERENCES\n")
    print("  ─────────────────────────────────────────\n")

    sound = ask_yes_no("Enable sound effects? (beeps when recording starts/stops)", default=True)
    fillers = ask_yes_no('Remove filler words? ("um", "uh", "you know")', default=True)
    noise = ask_yes_no("Enable noise reduction? (slower, useful in noisy offices)", default=False)
    auto_start = ask_yes_no("Start Koda when Windows starts?", default=False)
    print()
    input("  Press Enter to continue...")
    return sound, fillers, noise, auto_start


# ============================================================
# STEP 7: WAKE WORD
# ============================================================

def setup_wake_word():
    clear()
    banner()
    print("  STEP 8 of 9: WAKE WORD\n")
    print("  ─────────────────────────────────────────\n")
    print('  Say "Hey Koda" to start recording hands-free.')
    print("  No need to press any keys — just speak the wake word.\n")
    print("  Note: Wake word uses your mic continuously in the background.")
    print("  It uses minimal CPU but keeps the mic active.\n")

    enabled = ask_yes_no('Enable wake word ("Hey Koda")?', default=False)
    print()
    input("  Press Enter to continue...")
    return enabled


# ============================================================
# STEP 9: PROMPT-ASSIST VOICE
# ============================================================

def setup_prompt_voice():
    """Pick a TTS voice for the conversational prompt-assist flow."""
    clear()
    banner()
    print("  STEP 9 of 11: PROMPT ASSIST VOICE\n")
    print("  ─────────────────────────────────────────\n")
    print("  Press your prompt-assist hotkey (default Ctrl+F9) and Koda")
    print("  will speak a short question, then assemble your prompt.")
    print("  Pick the voice you want to hear.\n")

    try:
        import pyttsx3
        engine = pyttsx3.init()
        voices = engine.getProperty("voices") or []
    except Exception as e:
        print(f"  Voice list unavailable ({e}). Using system default.\n")
        input("  Press Enter to continue...")
        return ""

    if not voices:
        print("  No SAPI5 voices found. Using system default.\n")
        input("  Press Enter to continue...")
        return ""

    options = []
    for v in voices[:6]:  # cap so the list stays scannable
        options.append((v.name, v.name))

    print("  Available voices (sample plays after you choose):\n")
    selected_name = ask_choice(
        "Pick a voice:", options, default=0
    )

    try:
        for v in voices:
            if v.name == selected_name:
                engine.setProperty("voice", v.id)
                break
        engine.say("Hi, I'm Koda. What are we working on with AI today?")
        engine.runAndWait()
    except Exception as e:
        print(f"  (Couldn't preview the voice: {e})\n")

    print()
    input("  Press Enter to continue...")
    return selected_name


# ============================================================
# STEP 10: PROMPT-ASSIST REFINE BACKEND
# ============================================================

def setup_prompt_backend():
    """Pick the LLM backend that polishes assembled prompts."""
    clear()
    banner()
    print("  STEP 10 of 11: PROMPT POLISH BACKEND\n")
    print("  ─────────────────────────────────────────\n")
    print("  After Koda assembles your prompt, an optional AI step can")
    print("  polish it for clarity. Pick how that polish happens.\n")
    print("    1. None     — template only, zero setup, recommended")
    print("    2. Ollama   — local model, free, ~2GB download, install separately")
    print("    3. API key  — Claude or OpenAI, best quality, ~$0.01/prompt\n")

    backend = ask_choice(
        "Choose backend:",
        [
            ("None — template only", "none"),
            ("Local Ollama", "ollama"),
            ("Bring your own API key", "api"),
        ],
        default=0,
    )

    provider = None
    if backend == "api":
        print()
        provider = ask_choice(
            "Which API?",
            [("Anthropic Claude", "claude"), ("OpenAI", "openai")],
            default=0,
        )
        print()
        print(f"  Paste your {provider.title()} API key. It's stored in the")
        print("  Windows Credential Manager — never in config.json, never logged.\n")
        key = input("  API key: ").strip()
        if key:
            from prompt_assist_credentials import save_api_key
            if save_api_key(provider, key):
                print("\n  Key saved.\n")
            else:
                print("\n  Could not save key (Credential Manager error). Falling back to None.\n")
                backend = "none"
                provider = None
        else:
            print("\n  No key entered. Falling back to None.\n")
            backend = "none"
            provider = None

    print()
    input("  Press Enter to continue...")
    return backend, provider


# ============================================================
# STEP 11: LLM PROMPT POLISHING (legacy command-mode polish)
# ============================================================

def setup_llm():
    clear()
    banner()
    print("  STEP 11 of 11: COMMAND MODE AI POLISHING\n")
    print("  ─────────────────────────────────────────\n")
    print("  When enabled, Koda uses a local AI model (via Ollama) to")
    print("  clean up your speech into clear, concise instructions.\n")
    print("  Example:")
    print('    You say:  "uh can you like go into the database and um fix')
    print('              that thing where the dates are wrong"')
    print('    Becomes:  "Fix the date formatting issue in the database"\n')
    print("  Requires Ollama to be installed (free, runs locally).")
    print("  Download: https://ollama.com/download\n")

    enabled = ask_yes_no("Enable AI prompt polishing?", default=False)

    llm_model = "phi3:mini"
    if enabled:
        print()
        llm_model = ask_choice(
            "Pick an AI model (smaller = faster, larger = smarter):",
            [
                ("Phi-3 Mini (2.3GB) — Fast, good for cleanup", "phi3:mini"),
                ("Llama 3.2 (2GB) — Fast, general purpose", "llama3.2:1b"),
                ("Mistral (4.1GB) — Better quality, slower", "mistral"),
                ("Llama 3.2 3B (2GB) — Good balance", "llama3.2:3b"),
            ],
            default=0,
        )
        print(f"\n  After setup, run: ollama pull {llm_model}")
        print("  This downloads the model (one-time only).\n")

    input("  Press Enter to continue...")
    return enabled, llm_model


# ============================================================
# SUMMARY & SAVE
# ============================================================

def show_summary_and_save(config):
    clear()
    banner()
    print("  SETUP COMPLETE!\n")
    print("  ─────────────────────────────────────────\n")
    print("  Your settings:\n")
    print(f"    Microphone:       {'System default' if config['mic_device'] is None else 'Device #' + str(config['mic_device'])}")
    print(f"    Dictation:        {config['hotkey_dictation']}")
    print(f"    Command:          {config['hotkey_command']}")
    print(f"    Prompt Assist:    {config['hotkey_prompt']}")
    print(f"    Correction:       {config['hotkey_correction']}")
    print(f"    Read back:        {config['hotkey_readback']}")
    print(f"    Read selected:    {config['hotkey_readback_selected']}")
    print(f"    Recording mode:   {config['hotkey_mode']}")
    perf_label = "Power Mode (NVIDIA GPU)" if config.get("compute_type") == "float16" else "Standard Mode (CPU)"
    print(f"    Performance:      {perf_label}")
    print(f"    Speech model:     {config['model_size']}")
    print(f"    Language:         {config['language']}")
    print(f"    Sound effects:    {'On' if config['sound_effects'] else 'Off'}")
    print(f"    Filler removal:   {'On' if config['post_processing']['remove_filler_words'] else 'Off'}")
    print(f"    Noise reduction:  {'On' if config['noise_reduction'] else 'Off'}")
    print(f"    Wake word:        {'On (\"Hey Koda\")' if config['wake_word']['enabled'] else 'Off'}")
    print(f"    LLM polish:       {'On (' + config['llm_polish']['model'] + ')' if config['llm_polish']['enabled'] else 'Off'}")
    pa = config.get("prompt_assist", {})
    backend_label = {"none": "Template only", "ollama": "Local Ollama", "api": f"API ({pa.get('api_provider') or 'unset'})"}.get(pa.get("refine_backend", "none"), "Template only")
    voice_label = config.get("tts", {}).get("voice") or "System default"
    print(f"    Prompt voice:     {voice_label}")
    print(f"    Prompt polish:    {backend_label}")
    print()

    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print(f"  Settings saved to: {CONFIG_PATH}\n")

    return config.get("_auto_start", False)


# ============================================================
# MAIN
# ============================================================

def main():
    clear()
    banner()
    print("  Welcome! This wizard will help you set up Koda.\n")
    print("  You'll pick your microphone, hotkeys, and preferences.")
    print("  It takes about 1 minute.\n")
    input("  Press Enter to begin...")

    # Run each step
    perf_model, compute_type = setup_performance()  # Step 1 — silent for no-GPU users
    mic_device = setup_microphone()                 # Step 2
    hotkey_dict, hotkey_cmd, hotkey_prompt, hotkey_corr, hotkey_read, hotkey_read_sel = setup_hotkeys()  # Step 3
    mode = setup_mode()                             # Step 4
    # Step 5 — skip model picker if performance step already chose one (Power Mode)
    if perf_model is not None:
        model_size = perf_model
    else:
        model_size = setup_model()
    language = setup_language()                     # Step 6
    sound, fillers, noise, auto_start = setup_preferences()  # Step 7
    wake_word_enabled = setup_wake_word()           # Step 8
    prompt_voice = setup_prompt_voice()             # Step 9
    refine_backend, api_provider = setup_prompt_backend()  # Step 10
    llm_enabled, llm_model = setup_llm()            # Step 11

    # Build config
    config = {
        "model_size": model_size,
        "compute_type": compute_type,
        "language": language,
        "hotkey_dictation": hotkey_dict,
        "hotkey_command": hotkey_cmd,
        "hotkey_prompt": hotkey_prompt,
        "hotkey_correction": hotkey_corr,
        "hotkey_readback": hotkey_read,
        "hotkey_readback_selected": hotkey_read_sel,
        "hotkey_mode": mode,
        "mic_device": mic_device,
        "sound_effects": sound,
        "notifications": False,
        "noise_reduction": noise,
        "post_processing": {
            "remove_filler_words": fillers,
            "code_vocabulary": False,
            "auto_capitalize": True,
        },
        "vad": {
            "enabled": True,
            "silence_timeout_ms": 1500,
        },
        "wake_word": {
            "enabled": wake_word_enabled,
            "phrase": "hey koda",
        },
        "llm_polish": {
            "enabled": llm_enabled,
            "model": llm_model,
        },
        "tts": {
            "rate": "normal",
            "voice": prompt_voice,
        },
        "prompt_assist": {
            "conversational": True,
            "refine_backend": refine_backend,
            "api_provider": api_provider,
            "opener": "What are we working on with AI today?",
        },
        "_auto_start": auto_start,
    }

    wants_startup = show_summary_and_save(config)

    # Handle auto-start
    if wants_startup:
        import subprocess
        startup_bat = os.path.join(SCRIPT_DIR, "install_startup.bat")
        if os.path.exists(startup_bat):
            subprocess.run(["cmd", "/c", startup_bat], cwd=SCRIPT_DIR)

    # Remove internal key
    config.pop("_auto_start", None)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

    print("  ─────────────────────────────────────────\n")
    print("  To start Koda, double-click start.bat")
    print("  To re-run this setup, double-click configure.bat")
    print("  To open the settings GUI, double-click settings.bat\n")
    print("  You can also change settings anytime by right-clicking")
    print("  the Koda tray icon or editing config.json directly.\n")
    input("  Press Enter to exit setup...")


if __name__ == "__main__":
    main()
