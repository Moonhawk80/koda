"""
App-launch voice commands for Koda.

Parses utterances like "open word" or "launch chrome" into a launch intent,
resolves the spoken app name against an alias map in apps.json, and launches
the resolved executable. Prefix-match only (verb must be at the start) — the
launch verbs open/launch/start are rarely first words of natural dictation,
unlike select/copy/save which were the reason prefix-matching was removed
from voice_commands.py in session 33.

MVP scope: launch only, no chained dictation (V2), no disambiguation picker.
"""

import json
import logging
import os
import re
import shutil
import subprocess
import sys
from difflib import get_close_matches

logger = logging.getLogger("koda")

APPS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "apps.json"
)

# open | launch | start + app token (greedy, stops at optional trailing noise word)
_LAUNCH_PATTERN = re.compile(
    r"^\s*(?:open|launch|start)\s+"
    r"(?P<app>[a-zA-Z][\w\s]*?)"
    r"(?:\s+(?:app|application|program|document))?"
    r"\s*[.!?]?\s*$",
    re.IGNORECASE,
)


def _load_app_aliases():
    """Load apps.json → dict[alias_lower, list[exe_candidates]]. Empty dict on error."""
    try:
        with open(APPS_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        logger.debug("apps.json not found at %s — using empty alias map", APPS_PATH)
        return {}
    except (ValueError, OSError) as e:
        logger.warning("Could not load apps.json: %s", e)
        return {}
    return {k.lower(): (v if isinstance(v, list) else [v]) for k, v in raw.items()}


def resolve_app(spoken):
    """Resolve a spoken app name to an executable path or None.

    Resolution order:
    1. Exact alias match (case-insensitive) in apps.json
    2. Fuzzy alias match (Levenshtein-ish via difflib) against apps.json keys
    3. shutil.which() on the raw token — catches anything on PATH
    4. None — caller should fall through to os.startfile() as last resort
    """
    if not spoken:
        return None
    token = spoken.strip().lower()
    aliases = _load_app_aliases()

    if token in aliases:
        for exe in aliases[token]:
            resolved = shutil.which(exe)
            if resolved:
                return resolved
        return aliases[token][0]  # not on PATH but let os.startfile try

    close = get_close_matches(token, aliases.keys(), n=1, cutoff=0.75)
    if close:
        logger.info("App alias fuzzy-matched: %r -> %r", spoken, close[0])
        for exe in aliases[close[0]]:
            resolved = shutil.which(exe)
            if resolved:
                return resolved
        return aliases[close[0]][0]

    on_path = shutil.which(token) or shutil.which(token + ".exe")
    if on_path:
        return on_path

    return None


def extract_launch_intent(text):
    """If text is a launch utterance, return (app_token, raw_match). Else (None, None).

    Intended to run BEFORE voice_commands.extract_and_execute_commands so a launch
    doesn't get partially matched by a text-editing command (e.g. "open word" could
    otherwise trigger nothing — or a future plugin command — by accident).
    """
    if not text:
        return None, None
    match = _LAUNCH_PATTERN.match(text.strip())
    if not match:
        return None, None
    app = match.group("app").strip()
    if not app:
        return None, None
    return app, text


def launch_app(spoken):
    """Resolve `spoken` and launch it. Returns (success: bool, resolved_path_or_name: str).

    Never raises — all failure paths return (False, reason_string) and log.
    """
    resolved = resolve_app(spoken)
    if resolved is None:
        logger.warning("App launch: no alias or PATH match for %r", spoken)
        return False, spoken

    try:
        if sys.platform == "win32":
            os.startfile(resolved)
        else:
            subprocess.Popen([resolved])
        logger.info("Launched app: %r -> %s", spoken, resolved)
        return True, resolved
    except Exception as e:
        logger.error("App launch failed for %r (resolved=%s): %s", spoken, resolved, e)
        return False, resolved
