"""
Voice editing commands for Koda.

Detects spoken commands in transcribed text and executes them as keyboard actions.
Commands are stripped from the final output — they control the editor, not the text.

Usage: speak naturally during dictation. When Koda detects a command phrase,
it executes the action instead of typing the phrase.

Examples:
  "select all" → Ctrl+A
  "delete that" → Backspace (deletes last paste)
  "undo" → Ctrl+Z
  "new line" → Enter
  "go to end" → Ctrl+End
"""

import re
import time
import logging
import ctypes
import ctypes.wintypes
import keyboard

logger = logging.getLogger("koda")


def _focused_window():
    """Return (hwnd, title) of the currently focused window for debug logging."""
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        buf = ctypes.create_unicode_buffer(256)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, 256)
        return hwnd, buf.value
    except Exception:
        return 0, "unknown"


# --- Command definitions ---

# Each command: (pattern, action_function, description)
# Patterns are matched case-insensitively against the full transcription.
# If the ENTIRE transcription is a command (or starts/ends with one),
# the command is executed and stripped from the text output.
#
# Uses keyboard.send() throughout — pyautogui's synthetic Ctrl conflicts
# with the keyboard library's hooks and causes commands like undo to silently fail.

def _action_select_all():
    keyboard.send("ctrl+a")

def _action_copy():
    keyboard.send("ctrl+c")

def _action_cut():
    keyboard.send("ctrl+x")

def _action_paste():
    keyboard.send("ctrl+v")

def _action_undo():
    keyboard.send("ctrl+z")

def _action_redo():
    keyboard.send("ctrl+y")

def _action_delete():
    keyboard.send("delete")

def _action_backspace():
    keyboard.send("backspace")

def _action_delete_word():
    keyboard.send("ctrl+backspace")

def _action_delete_line():
    keyboard.send("home")
    keyboard.send("shift+end")
    keyboard.send("delete")


# --- Terminal-mode overrides ---
# Readline/shell shortcuts replace GUI equivalents when active window is a terminal.
# "select all" → Ctrl+A in GUI means select all; in terminals it means BOL. Clear
# the whole command line instead (Ctrl+E to EOL, then Ctrl+U to kill to BOL).
# "delete" → Forward-Delete does nothing in terminal without a selection. Ctrl+K
# kills from cursor to end of line, which is the most useful equivalent.

def _action_terminal_select_all():
    """Select all text in the terminal viewport (Windows Terminal Ctrl+Shift+A).
    Ctrl+A + Shift+End fires in PSReadLine but produces no visible highlight.
    Ctrl+Shift+A is Windows Terminal's native select-all and creates a real visual selection.
    """
    keyboard.send("ctrl+shift+a")

def _action_terminal_clear_line():
    """Clear entire command line via PSReadLine RevertLine (Escape).
    Works in Windows mode (default) and Vi mode. Clears current input back to empty.
    """
    keyboard.send("escape")

def _action_terminal_kill_end():
    """Kill from cursor to end of line (readline Ctrl+K)."""
    keyboard.send("ctrl+k")

def _action_terminal_kill_bol():
    """Clear the current input line via PSReadLine RevertLine (Escape).
    Escape = RevertLine in PSReadLine Windows mode (the default).
    Ctrl+U only works in Emacs mode — not reliable cross-machine.
    Used for both 'delete' and 'undo' in terminal mode.
    """
    keyboard.send("escape")

def _action_terminal_delete_word():
    """Delete word before cursor (readline Ctrl+W)."""
    keyboard.send("ctrl+w")


# Maps command description → terminal override action.
# Only commands that behave differently in a terminal need an entry here.
TERMINAL_OVERRIDES = {
    # "Select all text" removed — no reliable keystroke selects just the current
    # input line in PSReadLine: Ctrl+A+Shift+End produces no visual highlight,
    # Ctrl+Shift+A selects the entire viewport. Fall back to GUI default (Ctrl+A).
    "Delete selection/last text": _action_terminal_kill_bol,   # Ctrl+U: cursor at EOL after paste, kill to BOL
    "Delete forward":             _action_terminal_kill_bol,   # Ctrl+U: same reason — Ctrl+K (EOL) kills nothing
    "Delete current line":        _action_terminal_clear_line,
    "Delete previous word":       _action_terminal_delete_word,
    "Undo":                       _action_terminal_kill_bol,   # Ctrl+U: Ctrl+Z doesn't undo synthetic paste in PSReadLine
}

def _action_enter():
    keyboard.send("enter")

def _action_double_enter():
    keyboard.send("enter")
    keyboard.send("enter")

def _action_tab():
    keyboard.send("tab")

def _action_escape():
    keyboard.send("escape")

def _action_home():
    keyboard.send("home")

def _action_end():
    keyboard.send("end")

def _action_go_top():
    keyboard.send("ctrl+home")

def _action_go_bottom():
    keyboard.send("ctrl+end")

def _action_select_word():
    keyboard.send("ctrl+shift+left")

def _action_select_line():
    keyboard.send("home")
    keyboard.send("shift+end")

def _action_select_to_end():
    keyboard.send("shift+end")

def _action_select_to_start():
    keyboard.send("shift+home")

def _action_move_word_left():
    keyboard.send("ctrl+left")

def _action_move_word_right():
    keyboard.send("ctrl+right")

def _action_save():
    keyboard.send("ctrl+s")

def _action_find():
    keyboard.send("ctrl+f")

def _action_bold():
    keyboard.send("ctrl+b")

def _action_italic():
    keyboard.send("ctrl+i")

def _action_underline():
    keyboard.send("ctrl+u")


# Command registry: (regex_pattern, action, description)
# Ordered by specificity — longer/more specific patterns first
VOICE_COMMANDS = [
    # Navigation
    (r"go to (?:the )?(?:beginning|start|top)", _action_go_top, "Go to document start"),
    (r"go to (?:the )?(?:end|bottom)", _action_go_bottom, "Go to document end"),
    (r"go to (?:line )?(?:start|beginning)", _action_home, "Go to line start"),
    (r"go to (?:line )?end", _action_end, "Go to line end"),
    (r"move word left", _action_move_word_left, "Move cursor one word left"),
    (r"move word right", _action_move_word_right, "Move cursor one word right"),

    # Selection
    (r"select (?:all|alt|ole|hall|everything)", _action_select_all, "Select all text"),
    (r"select (?:the )?(?:whole )?line", _action_select_line, "Select current line"),
    (r"select (?:the )?(?:last )?word", _action_select_word, "Select previous word"),
    (r"select to (?:the )?end", _action_select_to_end, "Select to end of line"),
    (r"select to (?:the )?(?:start|beginning)", _action_select_to_start, "Select to start of line"),

    # Deletion
    (r"delete (?:that|this|it|selection)", _action_backspace, "Delete selection/last text"),
    (r"delete (?:the )?(?:last )?word", _action_delete_word, "Delete previous word"),
    (r"delete (?:the )?(?:whole )?line", _action_delete_line, "Delete current line"),
    (r"(?:backspace|back space)", _action_backspace, "Backspace"),
    (r"delete", _action_delete, "Delete forward"),

    # Editing
    (r"undo(?: that)?", _action_undo, "Undo"),
    (r"redo(?: that)?", _action_redo, "Redo"),
    (r"copy(?: that| this| it| selection)?", _action_copy, "Copy"),
    (r"cut(?: that| this| it| selection)?", _action_cut, "Cut"),
    (r"paste(?: that| this| it)?", _action_paste, "Paste"),
    (r"save(?: file| document| it)?", _action_save, "Save"),
    (r"find(?: and replace)?", _action_find, "Find"),

    # Formatting
    (r"(?:make (?:it |that )?)?bold", _action_bold, "Bold"),
    (r"(?:make (?:it |that )?)?italic(?:s)?", _action_italic, "Italic"),
    (r"(?:make (?:it |that )?)?underline(?:d)?", _action_underline, "Underline"),

    # Whitespace
    (r"new paragraph", _action_double_enter, "New paragraph (double enter)"),
    (r"(?:new line|next line|press enter)", _action_enter, "New line"),
    (r"(?:press )?tab", _action_tab, "Tab"),
    (r"(?:press )?escape", _action_escape, "Escape"),
]

# Commands that only trigger when the ENTIRE utterance is the command.
# Excluded from suffix matching to prevent false positives when these words
# appear naturally at the end of a dictated sentence.
# (Prefix matching is disabled entirely — see extract_and_execute_commands.)
_WHOLE_UTTERANCE_ONLY = {
    "Delete forward",    # "I need to delete" should not fire forward-delete
    "Select all text",   # "I need to select all" should not fire Ctrl+A
    "Undo",              # "I said undo" should not fire Ctrl+Z
    "Redo",              # "I said redo" should not fire Ctrl+Y
    "Copy",              # "I need to copy" should not fire Ctrl+C
    "Cut",               # "I want to cut" should not fire Ctrl+X
    "Paste",             # "I need to paste" should not fire Ctrl+V
    "Save",              # "I want to save" should not fire Ctrl+S
    "Find",              # "I need to find" should not fire Ctrl+F
}

# Compile patterns
_COMPILED_COMMANDS = [
    (re.compile(r"^\s*" + pattern + r"\s*[.!?]?\s*$", re.IGNORECASE), action, desc)
    for pattern, action, desc in VOICE_COMMANDS
]

# Also compile for prefix/suffix extraction (command at start or end of text)
_PREFIX_COMMANDS = [
    (re.compile(r"^\s*" + pattern + r"[\s,.!?]+", re.IGNORECASE), action, desc)
    for pattern, action, desc in VOICE_COMMANDS
    if desc not in _WHOLE_UTTERANCE_ONLY
]
_SUFFIX_COMMANDS = [
    (re.compile(r"[\s,.!?]+" + pattern + r"\s*[.!?]?\s*$", re.IGNORECASE), action, desc)
    for pattern, action, desc in VOICE_COMMANDS
    if desc not in _WHOLE_UTTERANCE_ONLY
]


def register_extra_commands(commands):
    """Register additional voice commands from plugins.

    Args:
        commands: list of (regex_pattern, action_function, description)
    """
    for pattern, action, desc in commands:
        _COMPILED_COMMANDS.append(
            (re.compile(r"^\s*" + pattern + r"\s*[.!?]?\s*$", re.IGNORECASE), action, desc)
        )
        _PREFIX_COMMANDS.append(
            (re.compile(r"^\s*" + pattern + r"[\s,.!?]+", re.IGNORECASE), action, desc)
        )
        _SUFFIX_COMMANDS.append(
            (re.compile(r"[\s,.!?]+" + pattern + r"\s*[.!?]?\s*$", re.IGNORECASE), action, desc)
        )


def extract_and_execute_commands(text, in_terminal=False):
    """Check if text contains voice commands. Execute them and return remaining text.

    Args:
        text: transcribed text to scan for commands
        in_terminal: if True, use terminal-appropriate key actions (readline shortcuts)
                     instead of GUI shortcuts for commands that differ in a terminal.

    Returns:
        (remaining_text, commands_executed) — remaining_text is empty string if the
        entire transcription was a command.
    """
    if not text:
        return text, [], None

    def _run(action, desc):
        hwnd, title = _focused_window()
        if in_terminal and desc in TERMINAL_OVERRIDES:
            fn = TERMINAL_OVERRIDES[desc]
            logger.debug("Voice cmd [terminal]: %r -> %s | focus: hwnd=%s %r", desc, fn.__name__, hwnd, title)
            try:
                fn()
                logger.debug("Voice cmd [terminal]: %r done", desc)
            except Exception as e:
                logger.error("Voice cmd [terminal] error for %r: %s", desc, e)
        else:
            logger.debug("Voice cmd: %r -> %s | focus: hwnd=%s %r", desc, action.__name__, hwnd, title)
            try:
                action()
                logger.debug("Voice cmd: %r done", desc)
            except Exception as e:
                logger.error("Voice cmd error for %r: %s", desc, e)

    executed = []
    original = text.strip()

    # Check if the ENTIRE text is a single command
    for pattern, action, desc in _COMPILED_COMMANDS:
        if pattern.match(original):
            time.sleep(0.1)  # Small delay for focus
            _run(action, desc)
            executed.append(desc)
            return "", executed, None

    # Check for command at the END of text only.
    # Prefix matching (command at start) was removed — it caused too many false
    # positives when command words appeared naturally at the start of a sentence
    # (e.g. "select all the files" firing Ctrl+A and dropping "the files").
    # Users can say command words alone as a standalone utterance, or append them
    # at the end of dictation ("write this text new line").
    for pattern, action, desc in _SUFFIX_COMMANDS:
        match = pattern.search(text)
        if match:
            text = text[:match.start()].strip()
            executed.append(desc)
            # Return as deferred — caller must paste text FIRST, then fire this.
            # Firing here would send Enter before the text is pasted.
            def _deferred(a=action, d=desc):
                _run(a, d)
            return text, executed, _deferred

    return text, executed, None


def get_command_list():
    """Return a list of (pattern_description, description) for all available commands."""
    return [(desc, desc) for _, _, desc in VOICE_COMMANDS]
