"""
Tests for Koda Phase 2-4 features.

Covers: text processing (auto-formatting, emails, numbers, dates, punctuation),
voice commands, profile matching, and usage stats.
"""

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
)
from voice_commands import extract_and_execute_commands
from profiles import match_profile, deep_merge


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


if __name__ == "__main__":
    unittest.main()
