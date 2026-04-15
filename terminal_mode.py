"""
Terminal mode for Koda — normalizes spoken shell syntax for terminal windows.

When Ctrl+Space is used in a terminal (Windows Terminal, PowerShell, cmd, bash, WSL),
spoken symbols and path separators are automatically converted to their shell equivalents.
No hotkey change needed — activates automatically when the active window is a terminal.

Examples:
  "cd slash users slash alex slash projects"   → "cd /users/alex/projects"
  "tilde slash projects slash koda"            → "~/projects/koda"
  "git dash dash version"                      → "git --version"
  "npm install dash dash save dev"             → "npm install --save dev"
  "ls dash l"                                  → "ls -l"
  "dot dot slash src"                          → "../src"
  "cat file dot txt greater than output dot txt" → "cat file.txt > output.txt"
  "echo hello pipe grep world"                 → "echo hello | grep world"
"""

import re
import logging

logger = logging.getLogger("koda")

# ---------------------------------------------------------------------------
# Terminal app detection
# ---------------------------------------------------------------------------

TERMINAL_PROCESSES = {
    "windowsterminal.exe",
    "powershell.exe",
    "pwsh.exe",       # PowerShell Core
    "cmd.exe",
    "bash.exe",       # Git Bash / WSL bash
    "wsl.exe",
    "mintty.exe",     # MSYS2 / Cygwin / Git Bash
    "hyper.exe",
    "alacritty.exe",
    "wezterm.exe",
    "conemu64.exe",
    "cmder.exe",
}

TERMINAL_WINDOW_PATTERNS = [
    re.compile(r"powershell", re.IGNORECASE),
    re.compile(r"command prompt", re.IGNORECASE),
    re.compile(r"windows terminal", re.IGNORECASE),
    re.compile(r"git bash", re.IGNORECASE),
    re.compile(r"\bwsl\b", re.IGNORECASE),
    re.compile(r"\bterminal\b", re.IGNORECASE),
    re.compile(r"administrator:.*prompt", re.IGNORECASE),
    re.compile(r"\bpwsh\b", re.IGNORECASE),
]


def is_terminal_app(process_name: str, window_title: str) -> bool:
    """Return True if the active window is a terminal or shell."""
    if process_name.lower() in TERMINAL_PROCESSES:
        return True
    for pat in TERMINAL_WINDOW_PATTERNS:
        if pat.search(window_title):
            return True
    return False


# ---------------------------------------------------------------------------
# Symbol substitution rules
# Order matters — longer/more specific phrases must come before shorter ones
# ---------------------------------------------------------------------------

_SUBSTITUTIONS = [
    # Path shorthand (multi-word, before single slash rule)
    (re.compile(r'\bdot\s+dot\s+slash\b', re.IGNORECASE),      '../'),
    (re.compile(r'\bdot\s+slash\b',        re.IGNORECASE),      './'),
    (re.compile(r'\bdot\s+dot\b',          re.IGNORECASE),      '..'),

    # Slash variants
    (re.compile(r'\bforward\s+slash\b',    re.IGNORECASE),      '/'),
    (re.compile(r'\bback\s+slash\b',       re.IGNORECASE),      '\\\\'),
    (re.compile(r'\bbackslash\b',          re.IGNORECASE),      '\\\\'),

    # Double operators (before single versions)
    (re.compile(r'\bdash\s+dash\b',        re.IGNORECASE),      '--'),
    (re.compile(r'\bdouble\s+dash\b',      re.IGNORECASE),      '--'),
    (re.compile(r'\bdouble\s+ampersand\b', re.IGNORECASE),      '&&'),
    (re.compile(r'\band\s+and\b',          re.IGNORECASE),      '&&'),
    (re.compile(r'\bdouble\s+greater\s+than\b', re.IGNORECASE), '>>'),
    (re.compile(r'\bdouble\s+pipe\b',      re.IGNORECASE),      '||'),
    (re.compile(r'\bor\s+or\b',            re.IGNORECASE),      '||'),

    # Comparison / redirect
    (re.compile(r'\bgreater\s+than\b',     re.IGNORECASE),      '>'),
    (re.compile(r'\bless\s+than\b',        re.IGNORECASE),      '<'),

    # Misc symbols
    (re.compile(r'\bdollar\s+sign\b',      re.IGNORECASE),      '$'),
    (re.compile(r'\bat\s+sign\b',          re.IGNORECASE),      '@'),
    (re.compile(r'\bslash\b',              re.IGNORECASE),      '/'),
    (re.compile(r'\btilde\b',              re.IGNORECASE),      '~'),
    (re.compile(r'\bpipe\b',               re.IGNORECASE),      '|'),
    (re.compile(r'\bampersand\b',          re.IGNORECASE),      '&'),
    (re.compile(r'\basterisk\b',           re.IGNORECASE),      '*'),
    (re.compile(r'\bstar\b',               re.IGNORECASE),      '*'),
    (re.compile(r'\bdollar\b',             re.IGNORECASE),      '$'),
    (re.compile(r'\bsemicolon\b',          re.IGNORECASE),      ';'),
    (re.compile(r'\bcolon\b',              re.IGNORECASE),      ':'),
]

# File extension dot — applied AFTER other substitutions so "dot dash" doesn't
# greedily match before "dash" has been converted to "-".
# Restricts to known extensions to avoid false positives.
_KNOWN_EXTENSIONS = re.compile(
    r'\s+dot\s+(txt|py|js|ts|jsx|tsx|json|md|yaml|yml|html|css|csv|log|sh|bat|'
    r'ps1|sql|xml|env|toml|ini|cfg|conf|go|rs|java|cpp|c|h|rb|php|vue|pdf|'
    r'png|jpg|jpeg|gif|svg|zip|tar|gz|exe|dll|lock|gitignore|dockerignore)\b',
    re.IGNORECASE,
)

# "dash <letter>" → "-<letter>" for single-letter flags: "dash v" → "-v"
_DASH_FLAG = re.compile(r'\bdash\s+([a-zA-Z])\b', re.IGNORECASE)


def normalize_for_terminal(text: str) -> str:
    """
    Convert spoken terminal syntax to shell-ready symbols.
    Called after process_text() (with auto_capitalize disabled) when the
    active window is a terminal application.
    """
    t = text.strip()

    # Apply symbol substitutions
    for pattern, replacement in _SUBSTITUTIONS:
        t = pattern.sub(replacement, t)

    # "dash <letter>" → "-<letter>" for single-letter flags (ls -l, git -v, etc.)
    # Run before extension dot so "dot dash" doesn't eat the "-"
    t = _DASH_FLAG.sub(lambda m: f"-{m.group(1).lower()}", t)

    # File extension dot — applied after dash conversion so "dot dash" is safe
    # "file dot txt" → "file.txt" (space before dot consumed, space after dot consumed)
    t = _KNOWN_EXTENSIONS.sub(lambda m: f".{m.group(1).lower()}", t)

    # Collapse spaces around path slashes: "users / alex" → "users/alex"
    t = re.sub(r'\s*/\s*', '/', t)

    # Re-add space between first command word and its path argument:
    # "cd/users/alex" → "cd /users/alex"
    t = re.sub(r'^([a-zA-Z][\w]*)/([^/])', r'\1 /\2', t)

    # Collapse spaces after double-dash flags: "-- verbose" → "--verbose"
    t = re.sub(r'--\s+(\w)', r'--\1', t)

    logger.debug("Terminal mode: %r -> %r", text, t)
    return t
