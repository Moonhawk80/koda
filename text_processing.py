"""
Text post-processing pipeline for Koda.
Cleans up Whisper transcription output before pasting.
"""

import re
from datetime import datetime


# --- Custom Vocabulary Replacement ---

def apply_custom_vocabulary(text, custom_words):
    """Replace misheard words with correct versions using case-insensitive word boundary matching."""
    if not custom_words:
        return text
    for misheard, correct in custom_words.items():
        pattern = re.compile(r'\b' + re.escape(misheard) + r'\b', re.IGNORECASE)
        text = pattern.sub(correct, text)
    return text


# --- Filler Word Removal ---

FILLER_PATTERNS = [
    # Pure fillers
    r'\b(um|uh|uhh|umm|hmm|hm|er|err|ah|ahh)\b',
    # Discourse markers
    r'\b(you know|I mean|sort of|kind of)\b',
    # Hedging words (common in speech, rarely useful in prompts)
    r'\b(basically|actually|literally|honestly|obviously|clearly)\b',
]

# Words that can legitimately repeat (number words, common words)
_STUTTER_SAFE = {
    "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety",
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
    "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
    "seventeen", "eighteen", "nineteen", "hundred", "thousand", "million",
    "the", "that", "had", "is", "was", "in", "on", "to",
}


def _remove_stutters(text):
    """Remove repeated words (stuttered starts) but preserve intentional repeats like 'twenty twenty'."""
    def _stutter_replace(match):
        word = match.group(1).lower()
        if word in _STUTTER_SAFE:
            return match.group(0)  # Keep it
        return match.group(1)  # Remove the duplicate
    return re.sub(r'\b(\w+)\s+\1\b', _stutter_replace, text, flags=re.IGNORECASE)


def remove_filler_words(text):
    """Remove common filler words and speech artifacts."""
    for pattern in FILLER_PATTERNS:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    # Remove stuttered words (but not number words)
    text = _remove_stutters(text)
    # Clean up double/triple spaces
    text = re.sub(r'\s{2,}', ' ', text)
    # Clean up orphaned commas/periods (but preserve ellipsis "...")
    text = re.sub(r',\s*,', ',', text)
    text = re.sub(r'(?<!\.)\.(\s*\.)(?!\.)', '.', text)  # collapse ". ." but not "..."
    text = re.sub(r'^\s*[,\.]\s*', '', text)
    return text.strip()


# --- Smart Capitalization ---

def auto_capitalize(text):
    """Fix sentence-start capitalization and 'i' → 'I'."""
    if not text:
        return text
    # Capitalize first letter
    text = text[0].upper() + text[1:]
    # Capitalize after sentence endings
    text = re.sub(r'([.!?]\s+)(\w)', lambda m: m.group(1) + m.group(2).upper(), text)
    # Fix standalone 'i'
    text = re.sub(r'\bi\b', 'I', text)
    return text


# --- Code Vocabulary ---

CODE_VOCAB = {
    # Brackets and parens
    "open paren": "(", "close paren": ")",
    "open parenthesis": "(", "close parenthesis": ")",
    "open bracket": "[", "close bracket": "]",
    "open brace": "{", "close brace": "}",
    "open curly": "{", "close curly": "}",
    # Punctuation
    "semicolon": ";", "colon": ":",
    "comma": ",", "period": ".", "dot": ".",
    "exclamation mark": "!", "question mark": "?",
    # Operators
    "equals": "=", "double equals": "==", "triple equals": "===",
    "not equals": "!=", "plus equals": "+=", "minus equals": "-=",
    "arrow": "->", "fat arrow": "=>",
    "greater than": ">", "less than": "<",
    "plus": "+", "minus": "-",
    # Symbols
    "hash": "#", "hashtag": "#",
    "at sign": "@", "at symbol": "@",
    "ampersand": "&", "double ampersand": "&&",
    "pipe": "|", "double pipe": "||",
    "tilde": "~", "backtick": "`",
    "forward slash": "/", "backslash": "\\",
    "underscore": "_", "dash": "-",
    # Whitespace
    "new line": "\n", "newline": "\n",
    "tab": "\t",
    # Quotes
    "double quote": '"', "single quote": "'",
    "open quote": '"', "close quote": '"',
    # Common code words
    "null": "null", "none": "None",
    "true": "True", "false": "False",
}

# Sort by longest key first to match multi-word patterns before single words
_SORTED_VOCAB = sorted(CODE_VOCAB.items(), key=lambda x: len(x[0]), reverse=True)


def expand_code_vocabulary(text):
    """Replace spoken code terms with their symbol equivalents."""
    for spoken, symbol in _SORTED_VOCAB:
        text = re.sub(
            r'\b' + re.escape(spoken) + r'\b',
            lambda m, s=symbol: s,
            text,
            flags=re.IGNORECASE,
        )
    return text


# --- Case Formatting ---

CASE_FORMATTERS = {
    "camel case": lambda words: words[0].lower() + ''.join(w.capitalize() for w in words[1:]),
    "snake case": lambda words: '_'.join(w.lower() for w in words),
    "pascal case": lambda words: ''.join(w.capitalize() for w in words),
    "kebab case": lambda words: '-'.join(w.lower() for w in words),
    "upper case": lambda words: ' '.join(w.upper() for w in words),
    "screaming snake": lambda words: '_'.join(w.upper() for w in words),
    "constant case": lambda words: '_'.join(w.upper() for w in words),
}


def apply_case_formatting(text):
    """Detect 'camel case foo bar' and format accordingly."""
    for command, formatter in CASE_FORMATTERS.items():
        pattern = re.compile(
            r'\b' + re.escape(command) + r'\s+(.+?)(?:\.|,|$)',
            re.IGNORECASE,
        )
        match = pattern.search(text)
        if match:
            words = match.group(1).strip().split()
            if words:
                formatted = formatter(words)
                text = text[:match.start()] + formatted + text[match.end():]
    return text


# --- Auto-Formatting: Numbers ---

# Word-to-number mapping
_ONES = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19,
}
_TENS = {
    "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
_SCALES = {
    "hundred": 100, "thousand": 1000, "million": 1_000_000,
    "billion": 1_000_000_000, "trillion": 1_000_000_000_000,
}

# All number words for pattern matching
_NUMBER_WORDS = set(_ONES) | set(_TENS) | set(_SCALES) | {"and", "a"}


def _words_to_number(words):
    """Convert a list of number words to an integer. Returns None if not valid."""
    if not words:
        return None

    # Filter out "and"
    words = [w for w in words if w != "and"]
    if not words:
        return None

    # Handle "a hundred", "a thousand" etc.
    if words[0] == "a":
        words[0] = "one"

    current = 0
    result = 0

    for word in words:
        if word in _ONES:
            current += _ONES[word]
        elif word in _TENS:
            current += _TENS[word]
        elif word == "hundred":
            current = (current if current else 1) * 100
        elif word in ("thousand", "million", "billion", "trillion"):
            current = (current if current else 1) * _SCALES[word]
            result += current
            current = 0
        else:
            return None

    return result + current


def format_spoken_numbers(text):
    """Convert spoken numbers to digits.

    "one hundred twenty three" → "123"
    "two thousand and five" → "2005"
    "forty two percent" → "42%"
    Only converts when a scale word (hundred, thousand, million, etc.) is present,
    to avoid mangling times ("two thirty") or years ("twenty twenty").
    """
    words = text.split()
    result = []
    i = 0

    while i < len(words):
        # Check if this word starts a number sequence
        word_lower = words[i].lower().rstrip(".,!?;:")
        trailing_punct = words[i][len(word_lower):]

        if word_lower in _NUMBER_WORDS and word_lower != "and" and word_lower != "a":
            # Collect consecutive number words
            num_words = [word_lower]
            j = i + 1
            while j < len(words):
                next_lower = words[j].lower().rstrip(".,!?;:")
                if next_lower in _NUMBER_WORDS:
                    num_words.append(next_lower)
                    j += 1
                else:
                    break

            # Only convert if a scale word is present (hundred, thousand, etc.)
            # This prevents "two thirty" (time) and "twenty twenty" (year) from converting
            has_scale = any(w in _SCALES for w in num_words)
            if has_scale and len(num_words) >= 2:
                number = _words_to_number(num_words)
                if number is not None:
                    # Check for trailing "percent" / "dollars" etc.
                    suffix = ""
                    if j < len(words):
                        next_lower = words[j].lower().rstrip(".,!?;:")
                        if next_lower == "percent":
                            suffix = "%"
                            trailing_punct = words[j][len(next_lower):]
                            j += 1
                        elif next_lower in ("dollars", "dollar"):
                            result.append(f"${number:,}")
                            i = j + 1  # skip the "dollars" word
                            continue

                    result.append(f"{number:,}{suffix}{trailing_punct}")
                    i = j
                    continue

            # Not a valid number sequence, keep original
            result.append(words[i])
            i += 1
        else:
            result.append(words[i])
            i += 1

    return " ".join(result)


# --- Auto-Formatting: Dates ---

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}

_ORDINALS = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
    "eleventh": 11, "twelfth": 12, "thirteenth": 13, "fourteenth": 14,
    "fifteenth": 15, "sixteenth": 16, "seventeenth": 17, "eighteenth": 18,
    "nineteenth": 19, "twentieth": 20, "twenty first": 21, "twenty second": 22,
    "twenty third": 23, "twenty fourth": 24, "twenty fifth": 25,
    "twenty sixth": 26, "twenty seventh": 27, "twenty eighth": 28,
    "twenty ninth": 29, "thirtieth": 30, "thirty first": 31,
}


def _parse_spoken_year(words):
    """Parse spoken year like 'twenty twenty six' → 2026, 'nineteen ninety nine' → 1999."""
    if not words:
        return None

    # Try "twenty twenty six" pattern → prefix (20/19) + suffix
    if len(words) >= 2 and words[0] in ("twenty", "nineteen"):
        prefix = 20 if words[0] == "twenty" else 19
        suffix_words = words[1:]
        suffix = _words_to_number(suffix_words)
        if suffix is not None and 0 <= suffix <= 99:
            return prefix * 100 + suffix

    # Try standard number parsing for "two thousand twenty six" etc.
    year = _words_to_number(words)
    if year and 1900 <= year <= 2100:
        return year

    return None


def format_spoken_dates(text):
    """Convert spoken dates to formatted dates.

    "january fifth twenty twenty six" → "January 5, 2026"
    "march 3rd" → "March 3"
    "december twenty fifth" → "December 25"
    """
    text_lower = text.lower()

    for month_name, month_num in _MONTHS.items():
        if month_name not in text_lower:
            continue

        month_cap = month_name.capitalize()

        # Pattern: "month ordinal [year]" — e.g., "january fifth twenty twenty six"
        for ordinal, day in sorted(_ORDINALS.items(), key=lambda x: len(x[0]), reverse=True):
            # Match "month ordinal" with optional trailing words that could be a year
            pattern = re.compile(
                r'\b' + month_name + r'\s+' + re.escape(ordinal) +
                r'((?:\s+(?:twenty|nineteen|two|one|thousand|hundred|\w+)){0,5})?',
                re.IGNORECASE,
            )
            match = pattern.search(text)
            if match:
                year_str = (match.group(1) or "").strip()
                year = None
                # Try to parse year from trailing words
                if year_str:
                    year_words = year_str.split()
                    # Only try year parsing if first word looks like a year prefix
                    if year_words[0].lower() in ("twenty", "nineteen", "two", "one"):
                        year = _parse_spoken_year(year_words)
                        # If year parse failed, don't consume those words
                        if year is None:
                            # Re-match without the year portion
                            pattern2 = re.compile(
                                r'\b' + month_name + r'\s+' + re.escape(ordinal) + r'\b',
                                re.IGNORECASE,
                            )
                            match = pattern2.search(text)
                            if not match:
                                continue

                if year:
                    replacement = f"{month_cap} {day}, {year}"
                else:
                    replacement = f"{month_cap} {day}"
                text = text[:match.start()] + replacement + text[match.end():]
                break

        # Pattern: "month Nth" — e.g., "march 3rd", "june 15th"
        pattern = re.compile(
            r'\b' + month_name + r'\s+(\d{1,2})(?:st|nd|rd|th)\b',
            re.IGNORECASE,
        )
        match = pattern.search(text)
        if match:
            day = int(match.group(1))
            if 1 <= day <= 31:
                text = text[:match.start()] + f"{month_cap} {day}" + text[match.end():]

    return text


# --- Auto-Formatting: Smart Punctuation ---

def format_smart_punctuation(text):
    """Convert spoken punctuation into proper typographic forms.

    "dash dash" or "em dash" → "—"
    "dot dot dot" or "ellipsis" → "..."
    "open quote ... close quote" handled by code_vocabulary
    """
    replacements = [
        # Em dash
        (r'\bem dash\b', '—'),
        (r'\bdash dash\b', '—'),
        (r'\b--\b', '—'),
        # En dash
        (r'\ben dash\b', '–'),
        # Ellipsis
        (r'\bellipsis\b', '...'),
        (r'\bdot dot dot\b', '...'),
        # Common spoken punctuation
        (r'\bexclamation point\b', '!'),
        (r'\bquestion mark\b', '?'),
        (r'\bcomma\b', ','),
        (r'\bperiod\b', '.'),
        (r'\bcolon\b', ':'),
        (r'\bsemicolon\b', ';'),
        # Symbols that Whisper sometimes spells out
        (r'\bampersand\b', '&'),
        (r'\bat sign\b', '@'),
        (r'\bhash sign\b', '#'),
        (r'\bpercent sign\b', '%'),
    ]

    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

    # Clean up spaces before punctuation marks
    text = re.sub(r'\s+([.,;:!?%])', r'\1', text)

    return text


# --- Auto-Formatting: Email & URL ---

_TLDS = {
    "com", "org", "net", "edu", "gov", "io", "co", "uk", "us", "ca", "de",
    "fr", "es", "it", "nl", "au", "jp", "br", "in", "ru", "app", "dev",
    "ai", "me", "info", "biz", "xyz",
}


def _strip_punct(word):
    """Strip trailing punctuation from a word, return (clean_word, trailing_punct)."""
    clean = word.rstrip(".,!?;:")
    trailing = word[len(clean):]
    return clean, trailing


def format_spoken_emails(text):
    """Convert spoken email addresses to proper format.

    "alex at altfunding dot com" → "alex@altfunding.com"
    "info at company dot co dot uk" → "info@company.co.uk"
    "john dot doe at gmail dot com" → "john.doe@gmail.com"
    Only triggers when the pattern ends with a known TLD after "dot".
    """
    words = text.split()
    result = []
    i = 0

    while i < len(words):
        # Look for "at" that could be part of an email
        word_clean = _strip_punct(words[i])[0]
        if word_clean.lower() == "at" and i > 0 and i + 2 < len(words):
            # Scan forward for "dot tld" pattern
            domain_parts = []
            j = i + 1
            while j < len(words):
                domain_parts.append(words[j])
                # Check if next is "dot" + word (strip punctuation from "dot" check)
                if j + 2 <= len(words) - 1 and _strip_punct(words[j + 1])[0].lower() == "dot":
                    domain_parts.append(words[j + 1])
                    j += 2
                else:
                    break

            # Check if we have a valid email pattern: at least "domain dot tld"
            # and the last word after a "dot" is a known TLD
            # Strip punctuation when checking for "dot" keywords
            dot_count = sum(1 for p in domain_parts if _strip_punct(p)[0].lower() == "dot")
            last_word = domain_parts[-1].lower().rstrip(".,!?;:") if domain_parts else ""

            if dot_count >= 1 and last_word in _TLDS:
                # Build local part (look back for "word dot word" patterns)
                local_parts = [result.pop()]
                while result and len(result) >= 2 and _strip_punct(result[-1])[0].lower() == "dot":
                    result.pop()  # remove "dot"
                    local_parts.insert(0, result.pop())  # remove word before dot

                # Strip punctuation from local parts
                local = ".".join(_strip_punct(p)[0] for p in local_parts)

                # Build domain — strip punctuation from each part to avoid double dots
                domain = ".".join(
                    _strip_punct(p)[0] for p in domain_parts
                    if _strip_punct(p)[0].lower() != "dot"
                )

                # Preserve trailing punctuation from the last word of the match
                _, trailing = _strip_punct(domain_parts[-1])

                result.append(f"{local}@{domain}{trailing}")
                i = j + 1
                continue

        result.append(words[i])
        i += 1

    text = " ".join(result)

    # Also handle "at" when domain already has real dots (Whisper sometimes formats them)
    # e.g., "alex at altfunding.com" → "alex@altfunding.com"
    # Skip when the word before "at" looks like a verb (looked, arrived, etc.)
    _VERB_SUFFIXES = ("ed", "ing", "tion", "ly", "ous", "ive", "able", "ible")

    def _email_at_replace(m):
        before = m.group(1)
        if before.lower().endswith(_VERB_SUFFIXES) or before.lower() in (
            "look", "am", "is", "are", "was", "were", "be", "been", "the",
            "a", "an", "this", "that", "it", "i", "we", "they", "not",
        ):
            return m.group(0)  # Keep original
        return f"{m.group(1)}@{m.group(2)}"

    text = re.sub(
        r'\b(\w[\w.]*)\s+at\s+(\w+\.\w[\w.]*)\b',
        _email_at_replace,
        text,
        flags=re.IGNORECASE,
    )

    return text


# --- Processing Pipeline ---

def process_text(text, config):
    """Run the full post-processing pipeline based on config."""
    if not text:
        return text

    pp = config.get("post_processing", {})

    # Always apply case formatting before other processing
    if pp.get("code_vocabulary", False):
        text = apply_case_formatting(text)
        text = expand_code_vocabulary(text)

    # Auto-formatting runs before filler removal so "dot dot dot" → "..." isn't
    # eaten by the stutter remover, and dates/numbers are parsed from clean speech
    if pp.get("auto_format", True):
        text = format_spoken_emails(text)
        text = format_smart_punctuation(text)
        text = format_spoken_dates(text)
        text = format_spoken_numbers(text)

    if pp.get("remove_filler_words", True):
        text = remove_filler_words(text)

    if pp.get("auto_capitalize", True):
        text = auto_capitalize(text)

    return text.strip()
