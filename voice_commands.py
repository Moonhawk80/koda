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
import pyautogui


# --- Command definitions ---

# Each command: (pattern, action_function, description)
# Patterns are matched case-insensitively against the full transcription.
# If the ENTIRE transcription is a command (or starts/ends with one),
# the command is executed and stripped from the text output.

def _action_select_all():
    pyautogui.hotkey("ctrl", "a")

def _action_copy():
    pyautogui.hotkey("ctrl", "c")

def _action_cut():
    pyautogui.hotkey("ctrl", "x")

def _action_paste():
    pyautogui.hotkey("ctrl", "v")

def _action_undo():
    pyautogui.hotkey("ctrl", "z")

def _action_redo():
    pyautogui.hotkey("ctrl", "y")

def _action_delete():
    pyautogui.press("delete")

def _action_backspace():
    pyautogui.press("backspace")

def _action_delete_word():
    pyautogui.hotkey("ctrl", "backspace")

def _action_delete_line():
    pyautogui.hotkey("home")
    pyautogui.hotkey("shift", "end")
    pyautogui.press("delete")

def _action_enter():
    pyautogui.press("enter")

def _action_double_enter():
    pyautogui.press("enter")
    pyautogui.press("enter")

def _action_tab():
    pyautogui.press("tab")

def _action_escape():
    pyautogui.press("escape")

def _action_home():
    pyautogui.press("home")

def _action_end():
    pyautogui.press("end")

def _action_go_top():
    pyautogui.hotkey("ctrl", "home")

def _action_go_bottom():
    pyautogui.hotkey("ctrl", "end")

def _action_select_word():
    pyautogui.hotkey("ctrl", "shift", "left")

def _action_select_line():
    pyautogui.press("home")
    pyautogui.hotkey("shift", "end")

def _action_select_to_end():
    pyautogui.hotkey("shift", "end")

def _action_select_to_start():
    pyautogui.hotkey("shift", "home")

def _action_move_word_left():
    pyautogui.hotkey("ctrl", "left")

def _action_move_word_right():
    pyautogui.hotkey("ctrl", "right")

def _action_save():
    pyautogui.hotkey("ctrl", "s")

def _action_find():
    pyautogui.hotkey("ctrl", "f")

def _action_bold():
    pyautogui.hotkey("ctrl", "b")

def _action_italic():
    pyautogui.hotkey("ctrl", "i")

def _action_underline():
    pyautogui.hotkey("ctrl", "u")


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
    (r"select all", _action_select_all, "Select all text"),
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

# Compile patterns
_COMPILED_COMMANDS = [
    (re.compile(r"^\s*" + pattern + r"\s*[.!?]?\s*$", re.IGNORECASE), action, desc)
    for pattern, action, desc in VOICE_COMMANDS
]

# Also compile for prefix/suffix extraction (command at start or end of text)
_PREFIX_COMMANDS = [
    (re.compile(r"^\s*" + pattern + r"[\s,.!?]+", re.IGNORECASE), action, desc)
    for pattern, action, desc in VOICE_COMMANDS
]
_SUFFIX_COMMANDS = [
    (re.compile(r"[\s,.!?]+" + pattern + r"\s*[.!?]?\s*$", re.IGNORECASE), action, desc)
    for pattern, action, desc in VOICE_COMMANDS
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


def extract_and_execute_commands(text):
    """Check if text contains voice commands. Execute them and return remaining text.

    Returns:
        (remaining_text, commands_executed) — remaining_text is empty string if the
        entire transcription was a command.
    """
    if not text:
        return text, []

    executed = []
    original = text.strip()

    # Check if the ENTIRE text is a single command
    for pattern, action, desc in _COMPILED_COMMANDS:
        if pattern.match(original):
            time.sleep(0.1)  # Small delay for focus
            action()
            executed.append(desc)
            return "", executed

    # Check for command at the START of text
    for pattern, action, desc in _PREFIX_COMMANDS:
        match = pattern.match(text)
        if match:
            action()
            executed.append(desc)
            text = text[match.end():].strip()
            break

    # Check for command at the END of text
    for pattern, action, desc in _SUFFIX_COMMANDS:
        match = pattern.search(text)
        if match:
            action()
            executed.append(desc)
            text = text[:match.start()].strip()
            break

    return text, executed


def get_command_list():
    """Return a list of (pattern_description, description) for all available commands."""
    return [(desc, desc) for _, _, desc in VOICE_COMMANDS]
