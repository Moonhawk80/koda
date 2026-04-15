"""
Tests for Koda Phase 2-4 features.

Covers: text processing (auto-formatting, emails, numbers, dates, punctuation),
voice commands, profile matching, usage stats, and formula mode.
"""

import json
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from text_processing import (
    process_text,
    format_spoken_emails,
    format_spoken_numbers,
    format_spoken_dates,
    format_smart_punctuation,
    remove_filler_words,
    auto_capitalize,
    apply_custom_vocabulary,
    expand_code_vocabulary,
    apply_case_formatting,
    apply_snippets,
    load_filler_words,
    save_filler_words,
    DEFAULT_FILLER_WORDS,
    FILLER_WORDS_PATH,
)
from voice_commands import extract_and_execute_commands
from profiles import match_profile, deep_merge
from formula_mode import convert_to_formula, is_formula_app, execute_excel_action, _normalize, _try_navigate, _try_create_table
from terminal_mode import is_terminal_app, normalize_for_terminal


# ============================================================
# Email Formatting
# ============================================================

class TestEmailFormatting(unittest.TestCase):
    """Tests for format_spoken_emails — the most complex auto-formatter."""

    def test_basic_email(self):
        self.assertEqual(format_spoken_emails("alex at gmail dot com"), "alex@gmail.com")

    def test_capitalized_email(self):
        self.assertEqual(format_spoken_emails("Alex at Gmail dot com"), "Alex@Gmail.com")

    def test_trailing_period(self):
        self.assertEqual(format_spoken_emails("Alex at Gmail dot com."), "Alex@Gmail.com.")

    def test_whisper_comma_after_domain(self):
        """Bug fix: Whisper small model adds commas — 'dot,' must still match."""
        self.assertEqual(format_spoken_emails("Alex at Gmail, dot com"), "Alex@Gmail.com")

    def test_whisper_period_after_domain(self):
        """Whisper adds period mid-email — should still format."""
        self.assertEqual(format_spoken_emails("Alex at Gmail. Dot com."), "Alex@Gmail.com.")

    def test_multi_part_tld(self):
        self.assertEqual(
            format_spoken_emails("info at company dot co dot uk"),
            "info@company.co.uk",
        )

    def test_local_part_with_dots(self):
        self.assertEqual(
            format_spoken_emails("john dot doe at gmail dot com"),
            "john.doe@gmail.com",
        )

    def test_domain_with_real_dots(self):
        """Fallback regex: domain already has real dots."""
        self.assertEqual(format_spoken_emails("alex at gmail.com"), "alex@gmail.com")

    def test_email_in_sentence(self):
        self.assertEqual(
            format_spoken_emails("send it to alex at gmail dot com please"),
            "send it to alex@gmail.com please",
        )

    def test_not_email_verb_at(self):
        """'at' after a verb should NOT be converted."""
        self.assertEqual(
            format_spoken_emails("I looked at the results"),
            "I looked at the results",
        )

    def test_not_email_preposition(self):
        self.assertEqual(
            format_spoken_emails("we arrived at the office"),
            "we arrived at the office",
        )

    def test_unknown_tld_ignored(self):
        """'dot zzz' with unknown TLD should not be formatted."""
        self.assertEqual(
            format_spoken_emails("alex at company dot zzz"),
            "alex at company dot zzz",
        )

    def test_various_tlds(self):
        for tld in ["org", "net", "io", "dev", "ai"]:
            result = format_spoken_emails(f"hello at example dot {tld}")
            self.assertEqual(result, f"hello@example.{tld}", f"Failed for .{tld}")


# ============================================================
# Number Formatting
# ============================================================

class TestNumberFormatting(unittest.TestCase):

    def test_hundred(self):
        self.assertEqual(format_spoken_numbers("one hundred twenty three"), "123")

    def test_thousand(self):
        self.assertEqual(format_spoken_numbers("two thousand and five"), "2,005")

    def test_percent(self):
        """Percent only converts when a scale word is present."""
        self.assertEqual(format_spoken_numbers("one hundred percent"), "100%")

    def test_dollars(self):
        self.assertEqual(format_spoken_numbers("five hundred dollars"), "$500")

    def test_million(self):
        self.assertEqual(format_spoken_numbers("three million"), "3,000,000")

    def test_no_scale_word_unchanged(self):
        """Small numbers without scale words should NOT be converted (avoid mangling times)."""
        self.assertEqual(format_spoken_numbers("two thirty"), "two thirty")

    def test_in_sentence(self):
        result = format_spoken_numbers("we need one hundred twenty units")
        self.assertEqual(result, "we need 120 units")

    def test_trailing_punctuation(self):
        """Trailing period on last number word gets stripped by rstrip — number still converts."""
        result = format_spoken_numbers("about two hundred.")
        self.assertEqual(result, "about 200")


# ============================================================
# Date Formatting
# ============================================================

class TestDateFormatting(unittest.TestCase):

    def test_month_ordinal(self):
        self.assertEqual(format_spoken_dates("january fifth"), "January 5")

    def test_month_ordinal_year(self):
        self.assertEqual(
            format_spoken_dates("january fifth twenty twenty six"),
            "January 5, 2026",
        )

    def test_month_numeric_ordinal(self):
        self.assertEqual(format_spoken_dates("march 3rd"), "March 3")

    def test_december(self):
        self.assertEqual(format_spoken_dates("december twenty fifth"), "December 25")

    def test_non_date_unchanged(self):
        self.assertEqual(format_spoken_dates("hello world"), "hello world")


# ============================================================
# Smart Punctuation
# ============================================================

class TestSmartPunctuation(unittest.TestCase):

    def test_em_dash(self):
        """Em dash replaces words but spaces remain (cleaned by space-before-punct rule only for .,;:!?%)."""
        self.assertEqual(format_smart_punctuation("that em dash was good"), "that — was good")

    def test_dash_dash(self):
        self.assertEqual(format_smart_punctuation("well dash dash sort of"), "well — sort of")

    def test_ellipsis(self):
        self.assertEqual(format_smart_punctuation("well dot dot dot"), "well...")

    def test_ellipsis_word(self):
        self.assertEqual(format_smart_punctuation("well ellipsis"), "well...")

    def test_space_before_punctuation(self):
        self.assertEqual(
            format_smart_punctuation("hello , world . yes"),
            "hello, world. yes",
        )


# ============================================================
# Filler Word Removal
# ============================================================

class TestFillerRemoval(unittest.TestCase):

    def test_basic_fillers(self):
        self.assertEqual(remove_filler_words("um hello uh world"), "hello world")

    def test_discourse_markers(self):
        self.assertEqual(
            remove_filler_words("you know it was I mean good"),
            "it was good",
        )

    def test_stutter_removal(self):
        self.assertEqual(remove_filler_words("the the cat sat"), "the the cat sat")  # "the" is safe

    def test_stutter_unsafe(self):
        self.assertEqual(remove_filler_words("hello hello world"), "hello world")

    def test_number_repeats_preserved(self):
        """Number words should NOT be de-stuttered."""
        self.assertEqual(remove_filler_words("twenty twenty"), "twenty twenty")


# ============================================================
# Auto Capitalize
# ============================================================

class TestAutoCapitalize(unittest.TestCase):

    def test_first_letter(self):
        self.assertEqual(auto_capitalize("hello world"), "Hello world")

    def test_after_period(self):
        self.assertEqual(auto_capitalize("hello. world"), "Hello. World")

    def test_standalone_i(self):
        self.assertEqual(auto_capitalize("i think i can"), "I think I can")

    def test_empty(self):
        self.assertEqual(auto_capitalize(""), "")


# ============================================================
# Code Vocabulary
# ============================================================

class TestCodeVocabulary(unittest.TestCase):

    def test_brackets(self):
        self.assertEqual(expand_code_vocabulary("open paren close paren"), "( )")

    def test_operators(self):
        self.assertEqual(expand_code_vocabulary("equals equals"), "= =")

    def test_double_equals(self):
        self.assertEqual(expand_code_vocabulary("double equals"), "==")

    def test_arrow(self):
        self.assertEqual(expand_code_vocabulary("arrow"), "->")


# ============================================================
# Case Formatting
# ============================================================

class TestCaseFormatting(unittest.TestCase):

    def test_camel_case(self):
        self.assertEqual(apply_case_formatting("camel case foo bar"), "fooBar")

    def test_snake_case(self):
        self.assertEqual(apply_case_formatting("snake case hello world"), "hello_world")

    def test_pascal_case(self):
        self.assertEqual(apply_case_formatting("pascal case my function"), "MyFunction")

    def test_kebab_case(self):
        self.assertEqual(apply_case_formatting("kebab case my component"), "my-component")


# ============================================================
# Custom Vocabulary
# ============================================================

class TestCustomVocabulary(unittest.TestCase):

    def test_basic_replacement(self):
        words = {"coda": "Koda"}
        self.assertEqual(apply_custom_vocabulary("I love coda", words), "I love Koda")

    def test_case_insensitive(self):
        words = {"coda": "Koda"}
        self.assertEqual(apply_custom_vocabulary("CODA is great", words), "Koda is great")

    def test_word_boundary(self):
        words = {"at": "AT"}
        # Should NOT replace "at" inside "cat"
        self.assertEqual(apply_custom_vocabulary("the cat sat at the mat", words), "the cat sat AT the mat")


# ============================================================
# Full Pipeline
# ============================================================

class TestProcessTextPipeline(unittest.TestCase):
    """Test the full process_text pipeline with realistic config."""

    CONFIG = {
        "post_processing": {
            "remove_filler_words": True,
            "code_vocabulary": False,
            "auto_capitalize": True,
            "auto_format": True,
        }
    }

    def test_email_through_pipeline(self):
        result = process_text("alex at gmail dot com", self.CONFIG)
        self.assertEqual(result, "Alex@gmail.com")

    def test_email_with_comma_through_pipeline(self):
        result = process_text("Alex at Gmail, dot com", self.CONFIG)
        self.assertEqual(result, "Alex@Gmail.com")

    def test_number_and_capitalize(self):
        result = process_text("we sold one hundred units", self.CONFIG)
        self.assertEqual(result, "We sold 100 units")

    def test_fillers_removed_and_capitalized(self):
        result = process_text("um i think um we should go", self.CONFIG)
        self.assertEqual(result, "I think we should go")

    def test_empty_text(self):
        self.assertEqual(process_text("", self.CONFIG), "")

    def test_none_text(self):
        self.assertIsNone(process_text(None, self.CONFIG))

    def test_auto_format_disabled(self):
        config = {"post_processing": {"auto_format": False, "remove_filler_words": False, "auto_capitalize": False}}
        result = process_text("alex at gmail dot com", config)
        self.assertEqual(result, "alex at gmail dot com")


# ============================================================
# Voice Commands
# ============================================================

class TestVoiceCommands(unittest.TestCase):
    """Test command extraction (actions mocked to avoid keyboard input)."""

    @patch("voice_commands.pyautogui")
    def test_select_all(self, mock_pyautogui):
        text, cmds = extract_and_execute_commands("select all")
        self.assertEqual(text, "")
        self.assertEqual(len(cmds), 1)
        mock_pyautogui.hotkey.assert_called_with("ctrl", "a")

    @patch("voice_commands.pyautogui")
    def test_undo(self, mock_pyautogui):
        text, cmds = extract_and_execute_commands("undo")
        self.assertEqual(text, "")
        self.assertEqual(len(cmds), 1)

    @patch("voice_commands.pyautogui")
    def test_new_line(self, mock_pyautogui):
        text, cmds = extract_and_execute_commands("new line")
        self.assertEqual(text, "")
        self.assertEqual(len(cmds), 1)
        mock_pyautogui.press.assert_called_with("enter")

    @patch("voice_commands.pyautogui")
    def test_command_with_text(self, mock_pyautogui):
        """Command at start of text — command extracted, text preserved."""
        text, cmds = extract_and_execute_commands("new line hello world")
        self.assertEqual(text, "hello world")
        self.assertEqual(len(cmds), 1)

    @patch("voice_commands.pyautogui")
    def test_no_command(self, mock_pyautogui):
        text, cmds = extract_and_execute_commands("hello world")
        self.assertEqual(text, "hello world")
        self.assertEqual(cmds, [])

    @patch("voice_commands.pyautogui")
    def test_empty(self, mock_pyautogui):
        text, cmds = extract_and_execute_commands("")
        self.assertEqual(text, "")
        self.assertEqual(cmds, [])

    @patch("voice_commands.pyautogui")
    def test_command_with_period(self, mock_pyautogui):
        """Whisper often adds trailing period to commands."""
        text, cmds = extract_and_execute_commands("select all.")
        self.assertEqual(text, "")
        self.assertEqual(len(cmds), 1)


# ============================================================
# Profile Matching
# ============================================================

class TestProfileMatching(unittest.TestCase):

    PROFILES = {
        "_description": "test profiles",
        "VS Code": {
            "match": {"process": "code.exe"},
            "settings": {"post_processing": {"code_vocabulary": True}},
        },
        "Slack": {
            "match": {"process": "slack.exe"},
            "settings": {"post_processing": {"code_vocabulary": False}},
        },
        "Browser": {
            "match": {"title": "Chrome|Firefox|Edge"},
            "settings": {},
        },
    }

    def test_match_by_process(self):
        name, settings = match_profile(self.PROFILES, "code.exe", "voice.py - VS Code")
        self.assertEqual(name, "VS Code")
        self.assertTrue(settings["post_processing"]["code_vocabulary"])

    def test_match_by_title(self):
        name, _ = match_profile(self.PROFILES, "chrome.exe", "Google Chrome")
        self.assertEqual(name, "Browser")

    def test_no_match(self):
        name, settings = match_profile(self.PROFILES, "notepad.exe", "Untitled")
        self.assertIsNone(name)
        self.assertEqual(settings, {})

    def test_skip_description(self):
        """Keys starting with _ should be skipped."""
        name, _ = match_profile(self.PROFILES, "_description", "")
        self.assertIsNone(name)


class TestDeepMerge(unittest.TestCase):

    def test_basic_merge(self):
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}
        self.assertEqual(deep_merge(base, override), {"a": 1, "b": 3, "c": 4})

    def test_nested_merge(self):
        base = {"post_processing": {"filler": True, "code": False}}
        override = {"post_processing": {"code": True}}
        result = deep_merge(base, override)
        self.assertEqual(result["post_processing"]["filler"], True)
        self.assertEqual(result["post_processing"]["code"], True)

    def test_base_unchanged(self):
        base = {"a": 1}
        override = {"a": 2}
        deep_merge(base, override)
        self.assertEqual(base["a"], 1)  # Original not mutated

    def test_empty_override(self):
        base = {"a": 1, "b": 2}
        self.assertEqual(deep_merge(base, {}), {"a": 1, "b": 2})

    def test_empty_base(self):
        self.assertEqual(deep_merge({}, {"a": 1}), {"a": 1})

    def test_non_dict_override_replaces_dict(self):
        base = {"pp": {"filler": True}}
        override = {"pp": "disabled"}
        result = deep_merge(base, override)
        self.assertEqual(result["pp"], "disabled")

    def test_three_levels_deep(self):
        base = {"a": {"b": {"c": 1, "d": 2}}}
        override = {"a": {"b": {"d": 99}}}
        result = deep_merge(base, override)
        self.assertEqual(result["a"]["b"]["c"], 1)
        self.assertEqual(result["a"]["b"]["d"], 99)

    def test_new_key_added(self):
        base = {"existing": True}
        override = {"new_key": 42}
        result = deep_merge(base, override)
        self.assertIn("new_key", result)
        self.assertIn("existing", result)


class TestProfileMatchEdgeCases(unittest.TestCase):

    PROFILES = {
        "_description": "edge case profiles",
        "CaseTest": {
            "match": {"process": "CHROME.EXE"},
            "settings": {"post_processing": {"code_vocabulary": True}},
        },
        "TitleOnly": {
            "match": {"title": "My App"},
            "settings": {},
        },
        "ProcessAndTitle": {
            "match": {"process": "app.exe", "title": "Dashboard"},
            "settings": {"post_processing": {"auto_capitalize": False}},
        },
        "BadRegex": {
            "match": {"title": "[invalid(regex"},
            "settings": {},
        },
        "First": {
            "match": {"process": "shared.exe"},
            "settings": {"post_processing": {"code_vocabulary": True}},
        },
        "Second": {
            "match": {"process": "shared.exe"},
            "settings": {"post_processing": {"code_vocabulary": False}},
        },
    }

    def test_process_match_case_insensitive(self):
        """Profile stores 'CHROME.EXE' but match_profile lowercases the stored value."""
        # match_profile compares process_name == match_rules["process"].lower()
        name, _ = match_profile(self.PROFILES, "chrome.exe", "")
        self.assertEqual(name, "CaseTest")

    def test_title_only_match(self):
        name, _ = match_profile(self.PROFILES, "unknown.exe", "My App Window")
        self.assertEqual(name, "TitleOnly")

    def test_process_takes_priority_over_title(self):
        """When process matches, we don't need title to match too."""
        name, settings = match_profile(self.PROFILES, "app.exe", "Something Else")
        self.assertEqual(name, "ProcessAndTitle")
        self.assertFalse(settings["post_processing"]["auto_capitalize"])

    def test_title_match_with_process_rule_present(self):
        """Title regex matches even when profile also has a process rule."""
        name, _ = match_profile(self.PROFILES, "other.exe", "Dashboard")
        self.assertEqual(name, "ProcessAndTitle")

    def test_invalid_regex_does_not_crash(self):
        """Bad regex in title rule is caught; match returns None."""
        name, settings = match_profile(self.PROFILES, "notepad.exe", "anything")
        # BadRegex profile won't match, but should not raise
        self.assertIsNone(name)
        self.assertEqual(settings, {})

    def test_first_match_wins(self):
        """When two profiles match the same process, the first one listed wins."""
        name, settings = match_profile(self.PROFILES, "shared.exe", "")
        self.assertEqual(name, "First")
        self.assertTrue(settings["post_processing"]["code_vocabulary"])

    def test_empty_profiles_dict(self):
        name, settings = match_profile({}, "code.exe", "")
        self.assertIsNone(name)
        self.assertEqual(settings, {})

    def test_profile_missing_match_key_skipped(self):
        profiles = {"NoMatch": {"settings": {}}}
        name, settings = match_profile(profiles, "code.exe", "anything")
        self.assertIsNone(name)

    def test_match_returns_empty_settings_when_no_settings_key(self):
        profiles = {"NoSettings": {"match": {"process": "foo.exe"}}}
        name, settings = match_profile(profiles, "foo.exe", "")
        self.assertEqual(name, "NoSettings")
        self.assertEqual(settings, {})


class TestProfileLoadSave(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.profiles_path = os.path.join(self.tmp_dir, "profiles.json")

    def _write_profiles(self, data):
        with open(self.profiles_path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def test_save_writes_valid_json(self):
        from profiles import save_profiles, PROFILES_PATH
        import profiles
        orig = profiles.PROFILES_PATH
        profiles.PROFILES_PATH = self.profiles_path
        try:
            data = {"MyApp": {"match": {"process": "app.exe"}, "settings": {}}}
            save_profiles(data)
            with open(self.profiles_path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            self.assertEqual(loaded["MyApp"]["match"]["process"], "app.exe")
        finally:
            profiles.PROFILES_PATH = orig

    def test_load_reads_existing_file(self):
        from profiles import load_profiles, PROFILES_PATH
        import profiles
        orig = profiles.PROFILES_PATH
        profiles.PROFILES_PATH = self.profiles_path
        try:
            data = {"TestProfile": {"match": {"process": "test.exe"}, "settings": {}}}
            self._write_profiles(data)
            result = load_profiles()
            self.assertIn("TestProfile", result)
        finally:
            profiles.PROFILES_PATH = orig

    def test_load_creates_default_when_missing(self):
        from profiles import load_profiles, DEFAULT_PROFILES
        import profiles
        orig = profiles.PROFILES_PATH
        profiles.PROFILES_PATH = self.profiles_path
        try:
            self.assertFalse(os.path.exists(self.profiles_path))
            result = load_profiles()
            self.assertTrue(os.path.exists(self.profiles_path))
            self.assertIn("VS Code", result)
        finally:
            profiles.PROFILES_PATH = orig

    def test_round_trip(self):
        from profiles import save_profiles, load_profiles
        import profiles
        orig = profiles.PROFILES_PATH
        profiles.PROFILES_PATH = self.profiles_path
        try:
            data = {"Zoom": {"match": {"process": "zoom.exe"}, "settings": {}}}
            save_profiles(data)
            result = load_profiles()
            self.assertEqual(result["Zoom"]["match"]["process"], "zoom.exe")
        finally:
            profiles.PROFILES_PATH = orig

    def test_load_corrupt_json_falls_back_to_defaults(self):
        from profiles import load_profiles, DEFAULT_PROFILES
        import profiles
        orig = profiles.PROFILES_PATH
        profiles.PROFILES_PATH = self.profiles_path
        try:
            with open(self.profiles_path, "w", encoding="utf-8") as f:
                f.write("NOT_JSON{{{")
            result = load_profiles()
            # Falls back to defaults when file is corrupt
            self.assertIn("VS Code", result)
        finally:
            profiles.PROFILES_PATH = orig

    def test_default_profiles_has_expected_apps(self):
        from profiles import DEFAULT_PROFILES
        self.assertIn("VS Code", DEFAULT_PROFILES)
        self.assertIn("Slack", DEFAULT_PROFILES)
        self.assertIn("Outlook", DEFAULT_PROFILES)


# ============================================================
# Usage Stats
# ============================================================

class TestUsageStats(unittest.TestCase):
    """Stats with a temporary database."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self._orig_path = None
        import stats
        self._orig_path = stats.DB_PATH
        stats.DB_PATH = self.tmp.name
        stats.init_stats_db()

    def tearDown(self):
        import stats
        stats.DB_PATH = self._orig_path
        os.unlink(self.tmp.name)

    def test_log_transcription(self):
        import stats
        stats.log_transcription_stats("hello world", "dictation", 1.5, "notepad.exe", "")
        summary = stats.get_summary()
        self.assertEqual(summary["total_transcriptions"], 1)
        self.assertEqual(summary["total_words"], 2)

    def test_log_command(self):
        import stats
        stats.log_command_stats("Select all", "code.exe")
        summary = stats.get_summary()
        self.assertEqual(summary["total_commands"], 1)

    def test_today_summary(self):
        import stats
        stats.log_transcription_stats("test text here", "dictation", 2.0)
        today = stats.get_today_summary()
        self.assertEqual(today["transcriptions"], 1)
        self.assertEqual(today["words"], 3)

    def test_time_saved_positive(self):
        import stats
        # 100 words in 10 seconds of speaking. Typing 100 words at 40 WPM = 150s.
        stats.log_transcription_stats(" ".join(["word"] * 100), "dictation", 10.0)
        summary = stats.get_summary()
        self.assertGreater(summary["time_saved_seconds"], 0)

    def test_empty_summary(self):
        import stats
        summary = stats.get_summary()
        self.assertEqual(summary["total_transcriptions"], 0)
        self.assertEqual(summary["total_words"], 0)
        self.assertEqual(summary["total_commands"], 0)


class TestUpdater(unittest.TestCase):
    """Tests for auto-update version comparison."""

    def test_newer_version(self):
        from updater import _is_newer
        self.assertTrue(_is_newer("4.2.0", "4.1.0"))
        self.assertTrue(_is_newer("5.0.0", "4.2.0"))
        self.assertTrue(_is_newer("4.1.1", "4.1.0"))

    def test_same_version(self):
        from updater import _is_newer
        self.assertFalse(_is_newer("4.1.0", "4.1.0"))

    def test_older_version(self):
        from updater import _is_newer
        self.assertFalse(_is_newer("4.0.0", "4.1.0"))
        self.assertFalse(_is_newer("3.9.9", "4.1.0"))

    def test_icon_generation(self):
        from generate_icon import generate_icon_image
        img = generate_icon_image(64)
        self.assertEqual(img.size, (64, 64))
        self.assertEqual(img.mode, "RGBA")

    def test_icon_status_dot(self):
        from generate_icon import generate_status_icon
        img = generate_status_icon(64, dot_color="#2ecc71")
        self.assertEqual(img.size, (64, 64))


class TestPromptAssist(unittest.TestCase):
    """Tests for Prompt Assist intent detection and detail extraction."""

    def test_intent_code(self):
        from prompt_assist import detect_intent
        self.assertEqual(detect_intent("build me a React landing page"), "code")
        self.assertEqual(detect_intent("create a Python script to parse CSV"), "code")

    def test_intent_debug(self):
        from prompt_assist import detect_intent
        self.assertEqual(detect_intent("my script crashes with a KeyError"), "debug")
        self.assertEqual(detect_intent("this function is not working"), "debug")

    def test_intent_write(self):
        from prompt_assist import detect_intent
        self.assertEqual(detect_intent("write an email to our clients"), "write")
        self.assertEqual(detect_intent("draft a blog post about AI"), "write")

    def test_intent_explain(self):
        from prompt_assist import detect_intent
        self.assertEqual(detect_intent("explain how async await works"), "explain")
        self.assertEqual(detect_intent("what is a closure in JavaScript"), "explain")

    def test_intent_review(self):
        from prompt_assist import detect_intent
        self.assertEqual(detect_intent("review this code for security issues"), "review")

    def test_intent_general(self):
        from prompt_assist import detect_intent
        self.assertEqual(detect_intent("what should I have for lunch"), "general")

    def test_extract_colors(self):
        from prompt_assist import _extract_details
        d = _extract_details("Make it blue and green with a dark red header")
        self.assertIn("colors", d)
        self.assertIn("blue", d["colors"])
        self.assertIn("green", d["colors"])

    def test_extract_quantities(self):
        from prompt_assist import _extract_details
        d = _extract_details("We have 21 people and have been around for 10 years")
        self.assertIn("quantities", d)
        self.assertIn("21 people", d["quantities"])
        self.assertIn("10 years", d["quantities"])

    def test_extract_names(self):
        from prompt_assist import _extract_details
        d = _extract_details("Build a site for Alternative Funding Group")
        self.assertIn("names", d)
        self.assertIn("Alternative Funding Group", d["names"])

    def test_extract_technologies(self):
        from prompt_assist import _extract_details
        d = _extract_details("Use React and Tailwind with a Supabase backend")
        self.assertIn("technologies", d)
        self.assertIn("React", d["technologies"])
        self.assertIn("Tailwind CSS", d["technologies"])
        self.assertIn("Supabase", d["technologies"])

    def test_extract_files(self):
        from prompt_assist import _extract_details
        d = _extract_details("It crashes when reading config.json and writing output.csv")
        self.assertIn("files", d)
        self.assertIn("config.json", d["files"])
        self.assertIn("output.csv", d["files"])

    def test_details_in_output(self):
        from prompt_assist import refine_prompt
        result = refine_prompt(
            "Build a landing page for Alternative Funding Group with React and Tailwind, dark blue and gold, we have 500 customers",
            {}
        )
        self.assertIn("Alternative Funding Group", result)
        self.assertIn("500 customers", result)
        self.assertIn("dark blue", result)
        self.assertIn("React", result)

    def test_empty_input(self):
        from prompt_assist import refine_prompt
        self.assertEqual(refine_prompt("", {}), "")
        self.assertIsNone(refine_prompt(None, {}))

    def test_no_details_still_works(self):
        from prompt_assist import refine_prompt
        result = refine_prompt("What should I do next", {})
        self.assertIn("What should I do next", result)

    # ------------------------------------------------------------------
    # _clean_for_prompt
    # ------------------------------------------------------------------

    def test_clean_strips_leading_okay_so(self):
        from prompt_assist import _clean_for_prompt
        result = _clean_for_prompt("okay so help me write a function")
        self.assertFalse(result.lower().startswith("okay"))

    def test_clean_strips_leading_um(self):
        from prompt_assist import _clean_for_prompt
        result = _clean_for_prompt("um explain closures")
        self.assertFalse(result.lower().startswith("um"))

    def test_clean_strips_trailing_please(self):
        from prompt_assist import _clean_for_prompt
        result = _clean_for_prompt("fix this bug please")
        self.assertNotIn("please", result)

    def test_clean_strips_trailing_thank_you(self):
        from prompt_assist import _clean_for_prompt
        result = _clean_for_prompt("explain closures thank you")
        self.assertNotIn("thank you", result)

    def test_clean_adds_period_if_missing(self):
        from prompt_assist import _clean_for_prompt
        result = _clean_for_prompt("explain closures")
        self.assertTrue(result.endswith("."))

    def test_clean_preserves_question_mark(self):
        from prompt_assist import _clean_for_prompt
        result = _clean_for_prompt("what is a closure?")
        self.assertTrue(result.endswith("?"))

    def test_clean_preserves_exclamation(self):
        from prompt_assist import _clean_for_prompt
        result = _clean_for_prompt("this is broken!")
        self.assertTrue(result.endswith("!"))

    def test_clean_collapses_whitespace(self):
        from prompt_assist import _clean_for_prompt
        result = _clean_for_prompt("fix   this   bug")
        self.assertNotIn("  ", result)

    def test_clean_empty_string_returns_empty(self):
        from prompt_assist import _clean_for_prompt
        self.assertEqual(_clean_for_prompt(""), "")

    # ------------------------------------------------------------------
    # _extract_language
    # ------------------------------------------------------------------

    def test_extract_language_python(self):
        from prompt_assist import _extract_language
        self.assertEqual(_extract_language("write a Python script"), "Python")

    def test_extract_language_javascript(self):
        from prompt_assist import _extract_language
        self.assertEqual(_extract_language("build a javascript function"), "JavaScript")

    def test_extract_language_typescript(self):
        from prompt_assist import _extract_language
        self.assertEqual(_extract_language("TypeScript component for React"), "TypeScript")

    def test_extract_language_sql(self):
        from prompt_assist import _extract_language
        self.assertEqual(_extract_language("optimize this SQL query"), "SQL")

    def test_extract_language_none(self):
        from prompt_assist import _extract_language
        self.assertIsNone(_extract_language("help me write an email"))

    # ------------------------------------------------------------------
    # _format_details
    # ------------------------------------------------------------------

    def test_format_details_empty_returns_empty_string(self):
        from prompt_assist import _format_details
        self.assertEqual(_format_details({}), "")

    def test_format_details_includes_all_categories(self):
        from prompt_assist import _format_details
        details = {
            "names": ["Acme Corp"],
            "quantities": ["10 users"],
            "technologies": ["React"],
            "files": ["app.py"],
        }
        result = _format_details(details)
        self.assertIn("Acme Corp", result)
        self.assertIn("10 users", result)
        self.assertIn("React", result)
        self.assertIn("app.py", result)

    # ------------------------------------------------------------------
    # Intent priority ordering
    # ------------------------------------------------------------------

    def test_intent_debug_beats_code(self):
        # "fix" is a debug signal; should not fall through to code
        from prompt_assist import detect_intent
        self.assertEqual(detect_intent("fix this Python function that returns wrong value"), "debug")

    def test_intent_review_beats_code(self):
        from prompt_assist import detect_intent
        self.assertEqual(detect_intent("review this Python code for bugs"), "review")

    # ------------------------------------------------------------------
    # Template structure
    # ------------------------------------------------------------------

    def test_code_template_has_requirements(self):
        from prompt_assist import refine_prompt
        result = refine_prompt("build a Python script to read CSV files", {})
        self.assertIn("Requirements:", result)
        self.assertIn("best practices", result)

    def test_debug_template_mentions_root_cause(self):
        from prompt_assist import refine_prompt
        result = refine_prompt("my function crashes with a KeyError on startup", {})
        self.assertIn("root cause", result)

    def test_explain_template_asks_for_examples(self):
        from prompt_assist import refine_prompt
        result = refine_prompt("explain how closures work in JavaScript", {})
        self.assertIn("examples", result)

    def test_review_template_mentions_severity(self):
        from prompt_assist import refine_prompt
        result = refine_prompt("review this code for security issues", {})
        self.assertIn("severity", result)

    def test_write_template_mentions_tone(self):
        from prompt_assist import refine_prompt
        result = refine_prompt("draft an email to our clients about the update", {})
        self.assertIn("tone", result)

    # ------------------------------------------------------------------
    # Edge cases
    # ------------------------------------------------------------------

    def test_whitespace_only_returns_input(self):
        from prompt_assist import refine_prompt
        self.assertEqual(refine_prompt("   ", {}), "   ")

    def test_llm_refine_false_skips_ollama(self):
        from prompt_assist import refine_prompt
        config = {"prompt_assist": {"llm_refine": False}}
        result = refine_prompt("explain Python decorators", config)
        self.assertIsNotNone(result)
        self.assertIn("explain", result.lower())


# ============================================================
# Custom Vocabulary Pipeline Wiring
# ============================================================

class TestCustomVocabularyPipeline(unittest.TestCase):
    """Verify custom_vocabulary in config is applied by process_text()."""

    BASE_CONFIG = {
        "post_processing": {
            "remove_filler_words": True,
            "code_vocabulary": False,
            "auto_capitalize": True,
            "auto_format": True,
        },
        "custom_vocabulary": {"coda": "Koda"},
    }

    def _cfg(self, vocab):
        """Return a config with the given custom_vocabulary dict."""
        return {
            "post_processing": {
                "remove_filler_words": True,
                "code_vocabulary": False,
                "auto_capitalize": True,
                "auto_format": True,
            },
            "custom_vocabulary": vocab,
        }

    # --- Basic wiring ---

    def test_vocab_applied_via_process_text(self):
        result = process_text("I use coda every day", self._cfg({"coda": "Koda"}))
        self.assertEqual(result, "I use Koda every day")

    def test_vocab_applied_last_after_capitalize(self):
        # "coda" at sentence start gets capitalised to "Coda" then vocab corrects to "Koda"
        result = process_text("coda is the best tool", self._cfg({"coda": "Koda"}))
        self.assertEqual(result, "Koda is the best tool")

    def test_vocab_multi_word_key(self):
        result = process_text("I use claude code for everything", self._cfg({"claude code": "Claude Code"}))
        self.assertIn("Claude Code", result)

    def test_vocab_case_insensitive_in_pipeline(self):
        result = process_text("CODA is great", self._cfg({"coda": "Koda"}))
        self.assertEqual(result, "Koda is great")

    def test_vocab_word_boundary_in_pipeline(self):
        # "coda" inside "encodable" must NOT be replaced
        result = process_text("the encodable format is used", self._cfg({"coda": "Koda"}))
        self.assertNotIn("Koda", result)

    # --- Edge cases ---

    def test_vocab_empty_dict_no_change(self):
        text = "Hello world"
        result = process_text(text, self._cfg({}))
        self.assertEqual(result, "Hello world")

    def test_vocab_missing_key_no_error(self):
        config = {
            "post_processing": {
                "remove_filler_words": False,
                "auto_capitalize": False,
                "auto_format": False,
            }
        }
        result = process_text("hello world", config)
        self.assertEqual(result, "hello world")

    def test_vocab_no_match_text_unchanged(self):
        result = process_text("nothing to replace here", self._cfg({"coda": "Koda"}))
        self.assertEqual(result, "Nothing to replace here")

    def test_vocab_multiple_entries_same_sentence(self):
        vocab = {"coda": "Koda", "alt funding": "Alt Funding"}
        result = process_text("coda is made by alt funding", self._cfg(vocab))
        self.assertIn("Koda", result)
        self.assertIn("Alt Funding", result)

    # --- Pipeline interaction ---

    def test_vocab_with_filler_removal(self):
        result = process_text("um I love coda", self._cfg({"coda": "Koda"}))
        self.assertNotIn("um", result)
        self.assertIn("Koda", result)

    def test_vocab_with_number_formatting(self):
        result = process_text("we have one hundred coda users", self._cfg({"coda": "Koda"}))
        self.assertIn("100", result)
        self.assertIn("Koda", result)

    def test_vocab_in_light_config(self):
        # Dictation mode uses light_config — custom_vocabulary is a top-level key
        light_config = {
            "post_processing": {
                "remove_filler_words": True,
                "code_vocabulary": False,
                "auto_capitalize": True,
                "auto_format": False,
            },
            "custom_vocabulary": {"coda": "Koda"},
        }
        result = process_text("open coda please", light_config)
        self.assertIn("Koda", result)

    def test_vocab_no_post_processing_key(self):
        # Config with only custom_vocabulary — pipeline should not crash
        config = {"custom_vocabulary": {"coda": "Koda"}}
        result = process_text("I use coda", config)
        self.assertIn("Koda", result)

    def test_vocab_replacement_survives_full_pipeline(self):
        # Full pipeline: filler + capitalize + vocab
        vocab = {"altfunding": "AltFunding"}
        result = process_text("um we work at altfunding dot com", self._cfg(vocab))
        self.assertNotIn("um", result)
        self.assertIn("AltFunding", result)

    def test_vocab_empty_text_returns_empty(self):
        self.assertEqual(process_text("", self._cfg({"coda": "Koda"})), "")


# ============================================================
# Snippets
# ============================================================

class TestSnippets(unittest.TestCase):
    """Tests for apply_snippets and its integration into process_text."""

    SNIPS = {
        "my address": "123 Main St, Anytown CA 90210",
        "my sig": "Best regards, Alexi",
        "test snippet": "hello world",
    }

    def test_exact_trigger_match(self):
        text, matched = apply_snippets("my address", self.SNIPS)
        self.assertTrue(matched)
        self.assertEqual(text, "123 Main St, Anytown CA 90210")

    def test_case_insensitive_trigger(self):
        text, matched = apply_snippets("MY ADDRESS", self.SNIPS)
        self.assertTrue(matched)
        self.assertEqual(text, "123 Main St, Anytown CA 90210")

    def test_trailing_punct_stripped(self):
        # Whisper may append a period — should still match
        text, matched = apply_snippets("my address.", self.SNIPS)
        self.assertTrue(matched)
        self.assertEqual(text, "123 Main St, Anytown CA 90210")

    def test_no_match_returns_original(self):
        text, matched = apply_snippets("send email", self.SNIPS)
        self.assertFalse(matched)
        self.assertEqual(text, "send email")

    def test_empty_snippets_no_change(self):
        text, matched = apply_snippets("my address", {})
        self.assertFalse(matched)
        self.assertEqual(text, "my address")

    def test_empty_text_returns_empty(self):
        text, matched = apply_snippets("", self.SNIPS)
        self.assertFalse(matched)
        self.assertEqual(text, "")

    def test_not_inline_replacement(self):
        # Snippet trigger embedded mid-sentence must NOT expand
        text, matched = apply_snippets("please use my address for shipping", self.SNIPS)
        self.assertFalse(matched)

    def test_snippet_bypasses_pipeline(self):
        # Expansion is returned as-is, not run through auto-capitalize
        config = {
            "snippets": {"test snippet": "hello world"},
            "post_processing": {"auto_capitalize": True, "remove_filler_words": True, "auto_format": True},
        }
        result = process_text("test snippet", config)
        self.assertEqual(result, "hello world")  # NOT "Hello world"

    def test_via_process_text_wired(self):
        config = {
            "snippets": {"my sig": "Best regards, Alexi"},
            "post_processing": {},
        }
        result = process_text("my sig", config)
        self.assertEqual(result, "Best regards, Alexi")

    def test_multiple_snippets_selects_correct(self):
        text, matched = apply_snippets("my sig", self.SNIPS)
        self.assertTrue(matched)
        self.assertEqual(text, "Best regards, Alexi")


# ============================================================
# Filler Words Manager
# ============================================================

class TestFillerWordsManager(unittest.TestCase):
    """Tests for load_filler_words, save_filler_words, and remove_filler_words with custom lists."""

    def test_default_words_includes_common_fillers(self):
        self.assertIn("um", DEFAULT_FILLER_WORDS)
        self.assertIn("uh", DEFAULT_FILLER_WORDS)
        self.assertIn("you know", DEFAULT_FILLER_WORDS)
        self.assertIn("basically", DEFAULT_FILLER_WORDS)

    def test_load_returns_defaults_when_no_file(self):
        with patch("text_processing.FILLER_WORDS_PATH", "/nonexistent/path/filler_words.json"):
            words = load_filler_words()
        self.assertEqual(words, list(DEFAULT_FILLER_WORDS))

    def test_save_and_load_round_trip(self):
        custom = ["um", "uh", "like", "you know"]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            tmp_path = f.name
        try:
            with patch("text_processing.FILLER_WORDS_PATH", tmp_path):
                save_filler_words(custom)
                loaded = load_filler_words()
            self.assertEqual(loaded, custom)
        finally:
            os.unlink(tmp_path)

    def test_load_corrupt_falls_back_to_defaults(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json {{{{")
            tmp_path = f.name
        try:
            with patch("text_processing.FILLER_WORDS_PATH", tmp_path):
                words = load_filler_words()
            self.assertEqual(words, list(DEFAULT_FILLER_WORDS))
        finally:
            os.unlink(tmp_path)

    def test_load_empty_list_is_valid(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump([], f)
            tmp_path = f.name
        try:
            with patch("text_processing.FILLER_WORDS_PATH", tmp_path):
                words = load_filler_words()
            self.assertEqual(words, [])
        finally:
            os.unlink(tmp_path)

    def test_custom_word_removed(self):
        result = remove_filler_words("I like totally agree", words=["totally"])
        self.assertNotIn("totally", result)
        self.assertIn("agree", result)

    def test_custom_multi_word_phrase_removed(self):
        result = remove_filler_words("it was kind of interesting", words=["kind of"])
        self.assertNotIn("kind of", result)
        self.assertIn("interesting", result)

    def test_builtin_um_removed_with_defaults(self):
        result = remove_filler_words("um I think so", words=list(DEFAULT_FILLER_WORDS))
        self.assertNotIn("um", result)
        self.assertIn("think", result)

    def test_no_false_positive_word_boundary(self):
        # "um" inside "summer" must NOT be removed
        result = remove_filler_words("the summer heat", words=["um"])
        self.assertIn("summer", result)

    def test_empty_filler_list_leaves_text_unchanged(self):
        text = "um I basically agree"
        result = remove_filler_words(text, words=[])
        # Stutter removal still runs, but no filler removal — text nearly unchanged
        self.assertIn("um", result)
        self.assertIn("basically", result)


class TestHotkeyParser(unittest.TestCase):
    """Tests for hotkey_service._parse_hotkey and _trigger_vk."""

    def setUp(self):
        from hotkey_service import _parse_hotkey, _trigger_vk
        self._parse = _parse_hotkey
        self._trigger = _trigger_vk

    def test_ctrl_space(self):
        mods, vk = self._parse("ctrl+space")
        self.assertEqual(vk, 0x20)
        self.assertTrue(mods & 0x0002)  # MOD_CONTROL

    def test_f8(self):
        mods, vk = self._parse("f8")
        self.assertEqual(vk, 0x77)

    def test_ctrl_shift_period(self):
        """DEFAULT hotkey ctrl+shift+. must parse — was silently skipped before."""
        mods, vk = self._parse("ctrl+shift+.")
        self.assertEqual(vk, 0xBE)          # VK_OEM_PERIOD
        self.assertTrue(mods & 0x0002)       # MOD_CONTROL
        self.assertTrue(mods & 0x0004)       # MOD_SHIFT

    def test_ctrl_shift_z(self):
        mods, vk = self._parse("ctrl+shift+z")
        self.assertEqual(vk, ord('Z'))
        self.assertTrue(mods & 0x0002)

    def test_ctrl_alt_r(self):
        mods, vk = self._parse("ctrl+alt+r")
        self.assertEqual(vk, ord('R'))
        self.assertTrue(mods & 0x0001)   # MOD_ALT
        self.assertTrue(mods & 0x0002)   # MOD_CONTROL

    def test_trigger_vk_period(self):
        vk = self._trigger("ctrl+shift+.")
        self.assertEqual(vk, 0xBE)

    def test_trigger_vk_space(self):
        vk = self._trigger("ctrl+space")
        self.assertEqual(vk, 0x20)

    def test_trigger_vk_f9(self):
        vk = self._trigger("f9")
        self.assertEqual(vk, 0x78)

    def test_all_default_hotkeys_parseable(self):
        """Every key in DEFAULT_CONFIG hotkeys must produce a non-zero VK."""
        from config import DEFAULT_CONFIG
        keys = [
            DEFAULT_CONFIG["hotkey_dictation"],
            DEFAULT_CONFIG["hotkey_command"],
            DEFAULT_CONFIG.get("hotkey_correction", ""),
            DEFAULT_CONFIG.get("hotkey_readback", ""),
            DEFAULT_CONFIG.get("hotkey_readback_selected", ""),
        ]
        for hk in keys:
            if not hk:
                continue
            _, vk = self._parse(hk)
            self.assertNotEqual(vk, 0, f"hotkey '{hk}' failed to parse — VK=0")


class TestNoKeyboardHooks(unittest.TestCase):
    """Guard: ensure no WH_KEYBOARD_LL hooks are ever re-introduced.

    A WH_KEYBOARD_LL hook installed in a process that isn't pumping its message
    queue blocks all keyboard input system-wide until Windows times out the hook.
    Koda uses RegisterHotKey + GetAsyncKeyState instead — zero hooks, zero risk.
    This test fails if any source file calls SetWindowsHookEx with WH_KEYBOARD_LL (13).
    """

    _SOURCE_FILES = [
        "hotkey_service.py",
        "voice.py",
        "settings_gui.py",
        "overlay.py",
        "text_processing.py",
        "updater.py",
        "hardware.py",
        "stats.py",
        "history.py",
        "plugin_manager.py",
        "profiles.py",
    ]

    def _live_lines(self, path):
        """Return non-comment, non-blank lines from a Python source file."""
        lines = []
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped and not stripped.startswith("#"):
                        lines.append(stripped)
        except FileNotFoundError:
            pass
        return lines

    def test_no_set_windows_hook_ex_in_source(self):
        """SetWindowsHookExW/A must not appear in non-comment code."""
        offenders = []
        for fname in self._SOURCE_FILES:
            for line in self._live_lines(fname):
                if "SetWindowsHookEx" in line:
                    offenders.append(f"{fname}: {line[:80]}")
        self.assertEqual(
            offenders, [],
            "WH_KEYBOARD_LL hook detected — use GetAsyncKeyState instead:\n"
            + "\n".join(offenders),
        )

    def test_no_wh_keyboard_ll_assignment_in_source(self):
        """WH_KEYBOARD_LL must not be assigned as a hook type in non-comment code."""
        import re
        # Match: SetWindowsHookEx(WH_KEYBOARD_LL or the literal 13 in a hook call
        pattern = re.compile(r"SetWindowsHookEx[AW]?\s*\(")
        offenders = []
        for fname in self._SOURCE_FILES:
            for line in self._live_lines(fname):
                if pattern.search(line):
                    offenders.append(f"{fname}: {line[:80]}")
        self.assertEqual(
            offenders, [],
            "Direct SetWindowsHookEx call found:\n" + "\n".join(offenders),
        )


class TestFormulaMode(unittest.TestCase):
    """Tests for formula_mode.convert_to_formula (Tier 1 rules-based)."""

    def test_formula_sum_basic(self):
        self.assertEqual(convert_to_formula("sum B2 to B10"), "=SUM(B2:B10)")

    def test_formula_sum_column_rows(self):
        self.assertEqual(convert_to_formula("sum column B rows 2 to 10"), "=SUM(B2:B10)")

    def test_formula_sum_total(self):
        self.assertEqual(convert_to_formula("total A1 to A20"), "=SUM(A1:A20)")

    def test_formula_average(self):
        self.assertEqual(convert_to_formula("average of A1 to A20"), "=AVERAGE(A1:A20)")

    def test_formula_average_mean(self):
        self.assertEqual(convert_to_formula("mean of B1 to B5"), "=AVERAGE(B1:B5)")

    def test_formula_count(self):
        self.assertEqual(convert_to_formula("count B2 to B10"), "=COUNT(B2:B10)")

    def test_formula_how_many(self):
        self.assertEqual(convert_to_formula("how many values in A1 to A10"), "=COUNT(A1:A10)")

    def test_formula_max(self):
        self.assertEqual(convert_to_formula("max of C1 to C20"), "=MAX(C1:C20)")

    def test_formula_min(self):
        self.assertEqual(convert_to_formula("minimum of D1 to D5"), "=MIN(D1:D5)")

    def test_formula_today(self):
        self.assertEqual(convert_to_formula("today"), "=TODAY()")

    def test_formula_now(self):
        self.assertEqual(convert_to_formula("now"), "=NOW()")

    def test_formula_if(self):
        self.assertEqual(
            convert_to_formula("if A1 is greater than 10 then yes else no"),
            '=IF(A1>10,"yes","no")',
        )

    def test_formula_if_less_than(self):
        self.assertEqual(
            convert_to_formula("if B2 is less than 5 then low else high"),
            '=IF(B2<5,"low","high")',
        )

    def test_formula_vlookup(self):
        result = convert_to_formula("vlookup A1 in B1 to D10 column 2")
        self.assertIsNotNone(result)
        self.assertTrue(result.startswith("=VLOOKUP("))
        self.assertIn("A1", result)
        self.assertIn("B1:D10", result)

    def test_formula_concat(self):
        result = convert_to_formula("join A1 and B1")
        self.assertIsNotNone(result)
        self.assertTrue(result.startswith("=CONCAT("))

    def test_formula_no_match(self):
        self.assertIsNone(convert_to_formula("hello world"))

    def test_formula_no_match_plain_sentence(self):
        self.assertIsNone(convert_to_formula("please send the report by Friday"))

    def test_formula_case_insensitive(self):
        self.assertEqual(convert_to_formula("SUM B1 TO B10"), "=SUM(B1:B10)")

    def test_formula_percentage(self):
        result = convert_to_formula("A1 divided by B1 as percent")
        self.assertIsNotNone(result)
        self.assertIn("A1", result)
        self.assertIn("B1", result)
        self.assertIn("100", result)


class TestFormulaAppDetection(unittest.TestCase):
    """Tests for is_formula_app window detection."""

    def test_excel_process(self):
        self.assertTrue(is_formula_app("EXCEL.EXE", "Budget.xlsx - Excel"))

    def test_excel_lowercase(self):
        self.assertTrue(is_formula_app("excel.exe", "Book1 - Excel"))

    def test_google_sheets_title(self):
        self.assertTrue(is_formula_app("chrome.exe", "Q1 Budget - Google Sheets"))

    def test_google_sheets_suffix(self):
        self.assertTrue(is_formula_app("msedge.exe", "Expenses - Sheets"))

    def test_not_formula_app(self):
        self.assertFalse(is_formula_app("notepad.exe", "Untitled - Notepad"))

    def test_not_formula_word(self):
        self.assertFalse(is_formula_app("winword.exe", "Document1 - Word"))


# ============================================================
# Excel Actions — normalize, navigation, table creation
# ============================================================

class TestNormalizePhoneticCellRefs(unittest.TestCase):
    """Tests for _normalize() phonetic cell reference handling added in session 30."""

    def test_phonetic_bee_5(self):
        self.assertEqual(_normalize("go to bee 5"), "go to B5")

    def test_phonetic_see_10(self):
        self.assertEqual(_normalize("go to see 10"), "go to C10")

    def test_phonetic_dee_3(self):
        self.assertEqual(_normalize("go to dee 3"), "go to D3")

    def test_phonetic_ay_1(self):
        self.assertEqual(_normalize("go to ay 1"), "go to A1")

    def test_phonetic_column_still_works(self):
        # Existing behaviour must not regress
        self.assertEqual(_normalize("sum column see"), "sum column C")

    def test_phonetic_column_with_row_range(self):
        self.assertEqual(_normalize("column see rows 2 to 10"), "column C rows 2 to 10")

    def test_trailing_punct_stripped(self):
        self.assertEqual(_normalize("go to B5."), "go to B5")

    def test_real_letter_unchanged(self):
        # "B5" is already correct — must not be mangled
        self.assertEqual(_normalize("go to B5"), "go to B5")

    def test_non_phonetic_word_unchanged(self):
        # "row 5" — "row" is not in the phonetic map
        self.assertEqual(_normalize("go to row 5"), "go to row 5")


class TestNavigationPatterns(unittest.TestCase):
    """Tests for _try_navigate() — pattern matching only, COM calls are mocked."""

    def _xl(self):
        from unittest.mock import MagicMock
        xl = MagicMock()
        xl.ActiveSheet.UsedRange.Rows.Count = 100
        return xl

    # --- Cell navigation ---
    def test_go_to_cell(self):
        xl = self._xl()
        self.assertTrue(_try_navigate(xl, "go to B5"))
        xl.ActiveSheet.Range("B5").Select.assert_called_once()

    def test_navigate_to_cell(self):
        xl = self._xl()
        self.assertTrue(_try_navigate(xl, "navigate to A1"))

    def test_jump_to_cell(self):
        xl = self._xl()
        self.assertTrue(_try_navigate(xl, "jump to C10"))

    def test_move_to_cell(self):
        xl = self._xl()
        self.assertTrue(_try_navigate(xl, "move to D4"))

    def test_select_cell(self):
        xl = self._xl()
        self.assertTrue(_try_navigate(xl, "select B2"))

    def test_cell_ref_uppercased(self):
        xl = self._xl()
        _try_navigate(xl, "go to b5")
        xl.ActiveSheet.Range("B5").Select.assert_called_once()

    # --- Column navigation ---
    def test_select_column(self):
        xl = self._xl()
        self.assertTrue(_try_navigate(xl, "select column C"))
        xl.ActiveSheet.Columns("C").Select.assert_called_once()

    def test_go_to_column(self):
        xl = self._xl()
        self.assertTrue(_try_navigate(xl, "go to column B"))

    def test_highlight_column(self):
        xl = self._xl()
        self.assertTrue(_try_navigate(xl, "highlight column A"))

    def test_column_uppercased(self):
        xl = self._xl()
        _try_navigate(xl, "select column c")
        xl.ActiveSheet.Columns("C").Select.assert_called_once()

    # --- Row navigation ---
    def test_select_row(self):
        xl = self._xl()
        self.assertTrue(_try_navigate(xl, "select row 5"))
        xl.ActiveSheet.Rows(5).Select.assert_called_once()

    def test_go_to_row(self):
        xl = self._xl()
        self.assertTrue(_try_navigate(xl, "go to row 10"))

    def test_navigate_to_row(self):
        xl = self._xl()
        self.assertTrue(_try_navigate(xl, "navigate to row 3"))

    # --- Home / A1 ---
    def test_go_home(self):
        xl = self._xl()
        self.assertTrue(_try_navigate(xl, "go home"))
        xl.ActiveSheet.Range("A1").Select.assert_called_once()

    def test_go_to_first_cell(self):
        xl = self._xl()
        self.assertTrue(_try_navigate(xl, "go to first cell"))

    def test_go_to_the_top(self):
        xl = self._xl()
        self.assertTrue(_try_navigate(xl, "go to the top"))

    def test_go_to_beginning(self):
        xl = self._xl()
        self.assertTrue(_try_navigate(xl, "go to the beginning"))

    # --- Last row ---
    def test_go_to_last_row(self):
        xl = self._xl()
        self.assertTrue(_try_navigate(xl, "go to last row"))

    def test_go_to_the_last_row(self):
        xl = self._xl()
        self.assertTrue(_try_navigate(xl, "go to the last row"))

    def test_go_to_bottom(self):
        xl = self._xl()
        self.assertTrue(_try_navigate(xl, "go to the bottom"))

    def test_go_to_end(self):
        xl = self._xl()
        self.assertTrue(_try_navigate(xl, "go to end"))

    # --- Select all ---
    def test_select_all(self):
        xl = self._xl()
        self.assertTrue(_try_navigate(xl, "select all"))
        xl.ActiveSheet.UsedRange.Select.assert_called_once()

    def test_select_everything(self):
        xl = self._xl()
        self.assertTrue(_try_navigate(xl, "select everything"))

    def test_select_all_data(self):
        xl = self._xl()
        self.assertTrue(_try_navigate(xl, "select all data"))

    # --- No match ---
    def test_no_match_formula_phrase(self):
        xl = self._xl()
        self.assertFalse(_try_navigate(xl, "sum column C"))

    def test_no_match_plain_text(self):
        xl = self._xl()
        self.assertFalse(_try_navigate(xl, "hello world"))

    def test_no_match_empty(self):
        xl = self._xl()
        self.assertFalse(_try_navigate(xl, ""))


class TestTableCreationPatterns(unittest.TestCase):
    """Tests for _try_create_table() — pattern matching only, COM calls are mocked."""

    def _xl(self):
        from unittest.mock import MagicMock
        xl = MagicMock()
        xl.ActiveCell.Row = 1
        xl.ActiveCell.Column = 1
        return xl

    # --- Basic table creation ---
    def test_create_a_table(self):
        xl = self._xl()
        self.assertTrue(_try_create_table(xl, "create a table"))

    def test_make_a_table(self):
        xl = self._xl()
        self.assertTrue(_try_create_table(xl, "make a table"))

    def test_insert_a_table(self):
        xl = self._xl()
        self.assertTrue(_try_create_table(xl, "insert a table"))

    def test_make_this_a_table(self):
        xl = self._xl()
        self.assertTrue(_try_create_table(xl, "make this a table"))

    def test_format_as_table(self):
        xl = self._xl()
        self.assertTrue(_try_create_table(xl, "format as table"))

    def test_insert_table_no_article(self):
        xl = self._xl()
        self.assertTrue(_try_create_table(xl, "insert table"))

    # --- Table with named columns ---
    def test_create_table_with_columns(self):
        xl = self._xl()
        self.assertTrue(_try_create_table(xl, "create a table with columns Name Date Amount"))

    def test_make_table_with_columns(self):
        xl = self._xl()
        self.assertTrue(_try_create_table(xl, "make a table with columns First Last Email"))

    def test_table_columns_written_as_headers(self):
        xl = self._xl()
        _try_create_table(xl, "create a table with columns Name Date Amount")
        # First header written to active cell
        xl.ActiveSheet.Cells(1, 1).Value  # accessed
        calls = [str(c) for c in xl.ActiveSheet.Cells.call_args_list]
        self.assertTrue(any("1, 1" in c or "(1, 1)" in c for c in calls))

    def test_table_with_columns_comma_separated(self):
        xl = self._xl()
        self.assertTrue(_try_create_table(xl, "create a table with columns Name, Date, Amount"))

    def test_table_with_columns_and_separator(self):
        xl = self._xl()
        self.assertTrue(_try_create_table(xl, "create a table with columns Name and Date and Amount"))

    # --- No match ---
    def test_no_match_formula(self):
        xl = self._xl()
        self.assertFalse(_try_create_table(xl, "sum column C"))

    def test_no_match_navigation(self):
        xl = self._xl()
        self.assertFalse(_try_create_table(xl, "go to B5"))

    def test_no_match_plain_text(self):
        xl = self._xl()
        self.assertFalse(_try_create_table(xl, "hello world"))


class TestExecuteExcelActionNoExcel(unittest.TestCase):
    """Tests for execute_excel_action() when Excel is not running."""

    def test_returns_false_when_excel_not_running(self):
        # In a test environment Excel is never open — must not raise, must return False
        with patch("formula_mode._get_excel", return_value=None):
            self.assertFalse(execute_excel_action("go to B5"))

    def test_returns_false_for_formula_phrase(self):
        with patch("formula_mode._get_excel", return_value=None):
            self.assertFalse(execute_excel_action("sum column C"))

    def test_returns_false_for_plain_text(self):
        with patch("formula_mode._get_excel", return_value=None):
            self.assertFalse(execute_excel_action("hello world"))


class TestExecuteExcelActionWithMockExcel(unittest.TestCase):
    """Tests for execute_excel_action() routing with a mocked Excel COM object."""

    def _xl(self):
        from unittest.mock import MagicMock
        xl = MagicMock()
        xl.ActiveSheet.UsedRange.Rows.Count = 50
        xl.ActiveCell.Row = 1
        xl.ActiveCell.Column = 1
        return xl

    def _run(self, text):
        xl = self._xl()
        with patch("formula_mode._get_excel", return_value=xl):
            result = execute_excel_action(text)
        return result, xl

    # --- Navigation routed correctly ---
    def test_navigation_returns_true(self):
        result, _ = self._run("go to B5")
        self.assertTrue(result)

    def test_table_creation_returns_true(self):
        result, _ = self._run("make a table")
        self.assertTrue(result)

    def test_formula_phrase_returns_false(self):
        # Formulas must NOT be intercepted by execute_excel_action
        result, _ = self._run("sum column C")
        self.assertFalse(result)

    def test_plain_text_returns_false(self):
        result, _ = self._run("let me know when you're done")
        self.assertFalse(result)

    # --- Hallucination stripping ---
    def test_strips_one_leading_word(self):
        result, _ = self._run("um go to B5")
        self.assertTrue(result)

    def test_strips_two_leading_words(self):
        result, _ = self._run("alt funding go to B5")
        self.assertTrue(result)

    def test_strips_three_leading_words(self):
        result, _ = self._run("alt funding some go to B5")
        self.assertTrue(result)

    def test_does_not_strip_when_not_needed(self):
        result, _ = self._run("go to A1")
        self.assertTrue(result)

    # --- Phonetic normalization flows through ---
    def test_phonetic_cell_ref_navigates(self):
        result, xl = self._run("go to bee 5")
        self.assertTrue(result)
        xl.ActiveSheet.Range("B5").Select.assert_called_once()

    def test_phonetic_cell_ref_with_hallucination(self):
        result, xl = self._run("alt funding go to bee 5")
        self.assertTrue(result)

    # --- Formula fallthrough (action returns False so formula mode takes over) ---
    def test_formula_not_consumed_by_action(self):
        result, _ = self._run("average of column B")
        self.assertFalse(result)

    def test_if_formula_not_consumed_by_action(self):
        result, _ = self._run("if A1 is greater than 10 then yes else no")
        self.assertFalse(result)


# ============================================================
# Terminal Mode
# ============================================================

class TestTerminalAppDetection(unittest.TestCase):
    """Tests for is_terminal_app() window detection."""

    def test_windows_terminal(self):
        self.assertTrue(is_terminal_app("WindowsTerminal.exe", "Windows Terminal"))

    def test_powershell_process(self):
        self.assertTrue(is_terminal_app("powershell.exe", "Windows PowerShell"))

    def test_powershell_core(self):
        self.assertTrue(is_terminal_app("pwsh.exe", "PowerShell 7"))

    def test_cmd(self):
        self.assertTrue(is_terminal_app("cmd.exe", "Command Prompt"))

    def test_cmd_admin(self):
        self.assertTrue(is_terminal_app("cmd.exe", "Administrator: Command Prompt"))

    def test_git_bash(self):
        self.assertTrue(is_terminal_app("bash.exe", "Git Bash"))

    def test_mintty(self):
        self.assertTrue(is_terminal_app("mintty.exe", "MINGW64:/c/Users/alex"))

    def test_wsl_title(self):
        self.assertTrue(is_terminal_app("bash.exe", "Ubuntu - WSL"))

    def test_powershell_title_only(self):
        self.assertTrue(is_terminal_app("chrome.exe", "PowerShell"))

    def test_terminal_title_only(self):
        self.assertTrue(is_terminal_app("alacritty.exe", "Terminal"))

    def test_not_terminal_notepad(self):
        self.assertFalse(is_terminal_app("notepad.exe", "Untitled - Notepad"))

    def test_not_terminal_excel(self):
        self.assertFalse(is_terminal_app("excel.exe", "Budget.xlsx - Excel"))

    def test_not_terminal_browser(self):
        self.assertFalse(is_terminal_app("chrome.exe", "GitHub - Google Chrome"))

    def test_not_terminal_word(self):
        self.assertFalse(is_terminal_app("winword.exe", "Document1 - Word"))

    def test_case_insensitive_process(self):
        self.assertTrue(is_terminal_app("POWERSHELL.EXE", "Windows PowerShell"))


class TestTerminalNormalize(unittest.TestCase):
    """Tests for normalize_for_terminal() symbol conversion."""

    # --- Path navigation ---
    def test_cd_slash_path(self):
        self.assertEqual(
            normalize_for_terminal("cd slash users slash alex"),
            "cd /users/alex",
        )

    def test_tilde_path(self):
        self.assertEqual(
            normalize_for_terminal("tilde slash projects slash koda"),
            "~/projects/koda",
        )

    def test_dot_dot_slash(self):
        self.assertEqual(normalize_for_terminal("dot dot slash src"), "../src")

    def test_dot_slash(self):
        self.assertEqual(normalize_for_terminal("dot slash build"), "./build")

    def test_dot_dot_only(self):
        self.assertEqual(normalize_for_terminal("cd dot dot"), "cd ..")

    def test_forward_slash(self):
        self.assertEqual(normalize_for_terminal("forward slash etc slash hosts"), "/etc/hosts")

    # --- Flags ---
    def test_double_dash_flag(self):
        self.assertEqual(normalize_for_terminal("git dash dash version"), "git --version")

    def test_double_dash_flag_multiword(self):
        self.assertEqual(
            normalize_for_terminal("npm install dash dash save dev"),
            "npm install --save dev",
        )

    def test_single_letter_flag(self):
        self.assertEqual(normalize_for_terminal("ls dash l"), "ls -l")

    def test_single_letter_flag_v(self):
        self.assertEqual(normalize_for_terminal("python dash v"), "python -v")

    def test_multiple_single_flags(self):
        result = normalize_for_terminal("ls dash l dash a")
        self.assertIn("-l", result)
        self.assertIn("-a", result)

    def test_double_dash_keyword(self):
        self.assertEqual(normalize_for_terminal("double dash verbose"), "--verbose")

    # --- Pipe and redirect ---
    def test_pipe(self):
        self.assertEqual(
            normalize_for_terminal("echo hello pipe grep world"),
            "echo hello | grep world",
        )

    def test_greater_than_redirect(self):
        result = normalize_for_terminal("echo hello greater than output")
        self.assertIn(">", result)

    def test_double_greater_than_append(self):
        result = normalize_for_terminal("echo hello double greater than output")
        self.assertIn(">>", result)

    def test_and_and(self):
        result = normalize_for_terminal("cd slash tmp and and ls")
        self.assertIn("&&", result)

    def test_double_ampersand(self):
        result = normalize_for_terminal("make double ampersand make install")
        self.assertIn("&&", result)

    # --- File extensions ---
    def test_dot_extension_txt(self):
        self.assertEqual(normalize_for_terminal("cat file dot txt"), "cat file.txt")

    def test_dot_extension_py(self):
        self.assertEqual(normalize_for_terminal("python script dot py"), "python script.py")

    def test_dot_extension_md(self):
        self.assertEqual(normalize_for_terminal("cat readme dot md"), "cat readme.md")

    # --- Tilde and dollar ---
    def test_tilde_home(self):
        result = normalize_for_terminal("cd tilde")
        self.assertIn("~", result)

    def test_dollar_sign(self):
        result = normalize_for_terminal("echo dollar sign home")
        self.assertIn("$", result)

    def test_dollar_alone(self):
        result = normalize_for_terminal("echo dollar PATH")
        self.assertIn("$", result)

    # --- Backslash (Windows paths) ---
    def test_backslash(self):
        result = normalize_for_terminal("cd C colon backslash users backslash alex")
        self.assertIn("\\", result)

    def test_back_slash_two_words(self):
        result = normalize_for_terminal("back slash windows backslash system32")
        self.assertIn("\\", result)

    # --- No mangling of normal commands ---
    def test_plain_git_command_unchanged(self):
        result = normalize_for_terminal("git status")
        self.assertEqual(result, "git status")

    def test_plain_cd_unchanged(self):
        result = normalize_for_terminal("cd projects")
        self.assertEqual(result, "cd projects")

    def test_empty_string(self):
        self.assertEqual(normalize_for_terminal(""), "")

    def test_no_symbols_unchanged(self):
        result = normalize_for_terminal("npm install")
        self.assertEqual(result, "npm install")

    # --- Auto-capitalize is NOT applied (caller responsibility, tested via config) ---
    def test_output_starts_lowercase(self):
        # normalize_for_terminal itself doesn't change case — it's on the caller
        # to disable auto_capitalize before calling. Verify the function preserves case.
        result = normalize_for_terminal("git status")
        self.assertTrue(result[0].islower())

    # --- Combined real-world phrases ---
    def test_full_cd_command(self):
        result = normalize_for_terminal("cd slash users slash alex slash projects slash koda")
        self.assertEqual(result, "cd /users/alex/projects/koda")

    def test_git_clone(self):
        result = normalize_for_terminal("git clone dash dash depth 1")
        self.assertIn("--depth", result)

    def test_find_command(self):
        result = normalize_for_terminal("find dot dash name star dot py")
        self.assertIn(".", result)
        self.assertIn("*", result)
        self.assertIn(".py", result)

    def test_pipe_chain(self):
        result = normalize_for_terminal("cat log dot txt pipe grep error pipe head dash n 20")
        self.assertIn("|", result)
        self.assertIn(".txt", result)


if __name__ == "__main__":
    unittest.main()
