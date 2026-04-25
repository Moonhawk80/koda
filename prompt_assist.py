"""
Koda Prompt Assist — transforms spoken thoughts into well-structured LLM prompts.

When users speak naturally ("I need help writing a Python script that reads CSV
files and removes duplicate rows based on email"), this module restructures it
into a clear, effective prompt with context, constraints, and format guidance.

Works in two modes:
  1. Template-based (offline, always available) — detects intent and applies
     structured prompt templates with best-practice framing.
  2. LLM-refined (optional, requires Ollama) — uses a local model to further
     polish the structured prompt.
"""

import re
import logging

logger = logging.getLogger("koda")

# ============================================================
# INTENT DETECTION
# ============================================================

# Keywords that signal each category.
# Checked in priority order — more specific intents first, broad "code" last.
_INTENT_PATTERNS = [
    ("debug", [
        r"\b(debug|fix(?:ing)?|error|bug|crash\w*|broken|not working|issue|traceback|exception)\b",
        r"\b(fails?|failing|broke|doesn't work|won't work|can't get|slow)\b",
        r"\breturns? (undefined|null|none|wrong|unexpected|nothing|empty)\b",
        r"\b(why is .* (slow|failing|broken|wrong))",
        r"\b(instead of|expected .* (but|got))\b",
    ]),
    ("explain", [
        r"\b(explain|what is|what are|how does|how do|why does|why do|tell me about)\b",
        r"\b(difference between|compare|understand|meaning|concept|definition)\b",
        r"\bhow .* works?\b",
    ]),
    ("review", [
        r"\b(review|evaluate|assess|audit|improve|optimize|refactor)\b",
        r"\b(code review|pull request|pr\b|feedback on|look at .* code|check .* (code|for))",
    ]),
    ("write", [
        r"\b(draft|compose|email|message|letter|document|blog|article|post)\b",
        r"\b(rewrite|rephrase|summarize|summary|translate)\b",
        r"\bwrite .* (email|message|letter|document|blog|article)\b",
    ]),
    ("code", [
        r"\b(create|build|code|script|function|class|program|implement|develop)\b",
        r"\bwrite .* (code|script|function|class|program|app|component|module)\b",
        r"\b(algorithm|data structure|regex|query|sql|database)\b",
        r"\b(python|javascript|typescript|java|rust|go|html|css|react|api|endpoint)\b",
    ]),
]


def detect_intent(text):
    """Detect the user's intent from their speech.

    Returns one of: 'debug', 'code', 'explain', 'review', 'write', 'general'.
    """
    lower = text.lower()
    for intent, patterns in _INTENT_PATTERNS:
        for pattern in patterns:
            if re.search(pattern, lower):
                return intent
    return "general"


# ============================================================
# CONTEXT EXTRACTION
# ============================================================

def _extract_language(text):
    """Try to detect a programming language from the speech."""
    lang_map = {
        r"\bpython\b": "Python",
        r"\bjavascript\b": "JavaScript",
        r"\btypescript\b": "TypeScript",
        r"\bjava\b": "Java",
        r"\bc\+\+\b": "C++",
        r"\bc sharp\b|c#": "C#",
        r"\brust\b": "Rust",
        r"\bgo\b(?:lang)?\b": "Go",
        r"\bruby\b": "Ruby",
        r"\bphp\b": "PHP",
        r"\bswift\b": "Swift",
        r"\bsql\b": "SQL",
        r"\bhtml\b": "HTML/CSS",
        r"\breact\b": "React",
        r"\bnode\b": "Node.js",
    }
    lower = text.lower()
    for pattern, name in lang_map.items():
        if re.search(pattern, lower):
            return name
    return None


def _clean_for_prompt(text):
    """Light cleanup of speech for embedding in a prompt."""
    # Remove leading filler
    text = re.sub(r"^(okay|ok|so|um|uh|well|like|basically|alright|hey|hi)\s*,?\s*",
                  "", text, flags=re.IGNORECASE)
    # Remove trailing filler
    text = re.sub(r"\s*(please|thanks|thank you|if you can|if possible)\s*\.?\s*$",
                  "", text, flags=re.IGNORECASE)
    # Collapse whitespace
    text = re.sub(r"\s+", " ", text).strip()
    # Ensure it ends with punctuation
    if text and text[-1] not in ".!?":
        text += "."
    return text


# ============================================================
# DETAIL EXTRACTION
# ============================================================

def _extract_details(text):
    """Extract specific details from speech that should be preserved in the prompt.

    Returns a dict of extracted detail categories. Empty categories are omitted.
    """
    details = {}
    lower = text.lower()

    # Colors
    color_pattern = r"\b(red|blue|green|yellow|orange|purple|pink|black|white|gray|grey|navy|teal|cyan|magenta|gold|silver|dark\s+\w+|light\s+\w+)\b"
    colors = list(set(re.findall(color_pattern, lower)))
    if colors:
        details["colors"] = colors

    # Numbers with context (e.g. "21 people", "10 years", "500 users")
    number_phrases = re.findall(
        r"\b(\d+(?:,\d{3})*(?:\.\d+)?)\s*(people|employees|users|customers|clients|"
        r"years?|months?|weeks?|days?|hours?|pages?|items?|records?|rows?|"
        r"percent|%|dollars?|bucks|\$|MB|GB|TB|ms|seconds?|minutes?)\b",
        lower
    )
    if number_phrases:
        details["quantities"] = [f"{num} {unit}" for num, unit in number_phrases]

    # Company/brand names — capitalized multi-word phrases that aren't common words
    _common_starts = {"i", "the", "a", "an", "it", "we", "they", "he", "she", "my",
                      "this", "that", "what", "how", "why", "when", "where", "which",
                      "please", "help", "make", "create", "build", "write", "fix",
                      "and", "but", "or", "for", "with", "from", "about", "also",
                      "maybe", "probably", "definitely", "actually", "basically"}
    # Look for capitalized phrases in the ORIGINAL text (not lowered)
    cap_phrases = re.findall(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", text)
    names = [p for p in cap_phrases if p.split()[0].lower() not in _common_starts]
    if names:
        details["names"] = list(set(names))

    # Specific technologies/frameworks (beyond just language detection)
    tech_patterns = {
        r"\breact\b": "React", r"\bnext\.?js\b": "Next.js", r"\bvue\b": "Vue",
        r"\bangular\b": "Angular", r"\bsvelte\b": "Svelte", r"\bdjango\b": "Django",
        r"\bflask\b": "Flask", r"\bfastapi\b": "FastAPI", r"\bexpress\b": "Express",
        r"\bnode\.?js\b": "Node.js", r"\btailwind\b": "Tailwind CSS",
        r"\bbootstrap\b": "Bootstrap", r"\bpostgres\w*\b": "PostgreSQL",
        r"\bmongo\w*\b": "MongoDB", r"\bredis\b": "Redis", r"\bsupabase\b": "Supabase",
        r"\bfirebase\b": "Firebase", r"\baws\b": "AWS", r"\bazure\b": "Azure",
        r"\bdocker\b": "Docker", r"\bkubernetes\b": "Kubernetes",
        r"\bgraphql\b": "GraphQL", r"\brest\s*api\b": "REST API",
        r"\boauth\b": "OAuth", r"\bjwt\b": "JWT", r"\bwebsocket\b": "WebSocket",
        r"\bshadcn\b": "shadcn/ui", r"\bprisma\b": "Prisma", r"\bdrizzle\b": "Drizzle",
    }
    techs = []
    for pattern, name in tech_patterns.items():
        if re.search(pattern, lower):
            techs.append(name)
    if techs:
        details["technologies"] = techs

    # URLs and domains — non-capturing groups so findall returns full matches,
    # not just the TLD fragment (fixes the "URLs: com" bug where 'example.com'
    # would return just 'com' because only the TLD was captured).
    urls = re.findall(r"https?://\S+|www\.\S+|\b\w+\.(?:com|org|io|dev|net|app)\b", text)
    if urls:
        details["urls"] = list(set(urls))

    # File types and paths
    files = re.findall(r"\b[\w/\\]+\.(?:py|js|ts|tsx|jsx|json|csv|sql|html|css|md|yaml|yml|env|txt)\b", text)
    if files:
        details["files"] = list(set(files))

    return details


def _format_details(details):
    """Format extracted details into a concise context block."""
    if not details:
        return ""

    lines = []
    if "names" in details:
        lines.append(f"Names/brands: {', '.join(details['names'])}")
    if "quantities" in details:
        lines.append(f"Key numbers: {', '.join(details['quantities'])}")
    if "colors" in details:
        lines.append(f"Colors: {', '.join(details['colors'])}")
    if "technologies" in details:
        lines.append(f"Tech stack: {', '.join(details['technologies'])}")
    if "files" in details:
        lines.append(f"Files: {', '.join(details['files'])}")
    if "urls" in details:
        lines.append(f"URLs: {', '.join(details['urls'])}")

    return "\n".join(lines)


# ============================================================
# PROMPT TEMPLATES
# ============================================================

def _template_code(cleaned, language, context):
    """Structure a code request into a clear prompt."""
    parts = [cleaned]
    if language:
        parts.append(f"\nLanguage: {language}")
    parts.append(
        "\nRequirements:\n"
        "- Write complete, working code\n"
        "- Handle edge cases\n"
        "- Follow best practices"
    )
    return "\n".join(parts)


def _template_debug(cleaned, language, context):
    """Structure a debug request into a clear prompt."""
    parts = [f"I need help debugging an issue.\n\nProblem: {cleaned}"]
    if language:
        parts.append(f"\nLanguage/stack: {language}")
    parts.append(
        "\nPlease:\n"
        "1. Identify the likely root cause\n"
        "2. Explain why it's happening\n"
        "3. Provide the fix with code\n"
        "4. Suggest how to prevent it in the future"
    )
    return "\n".join(parts)


def _template_explain(cleaned, language, context):
    """Structure an explanation request."""
    parts = [cleaned]
    parts.append(
        "\nPlease explain:\n"
        "- What it is and why it matters\n"
        "- How it works (with examples)\n"
        "- Common pitfalls or misconceptions\n"
        "- When to use it vs alternatives"
    )
    return "\n".join(parts)


def _template_review(cleaned, language, context):
    """Structure a code review request."""
    parts = [cleaned]
    if language:
        parts.append(f"\nLanguage: {language}")
    parts.append(
        "\nReview for:\n"
        "- Bugs or logic errors\n"
        "- Security vulnerabilities\n"
        "- Performance issues\n"
        "- Code clarity and maintainability\n\n"
        "Prioritize findings by severity."
    )
    return "\n".join(parts)


def _template_write(cleaned, language, context):
    """Structure a writing/drafting request."""
    parts = [cleaned]
    parts.append(
        "\nGuidelines:\n"
        "- Match the appropriate tone and formality\n"
        "- Be clear and concise\n"
        "- Structure with logical flow"
    )
    return "\n".join(parts)


def _template_general(cleaned, language, context):
    """General intent — return user's own words. Modern frontier models
    (Claude 4, GPT-5) don't need a generic 'please be thorough' closer;
    it adds noise without quality lift. If the user wanted structure,
    they'd say so."""
    return cleaned


_TEMPLATES = {
    "code": _template_code,
    "debug": _template_debug,
    "explain": _template_explain,
    "review": _template_review,
    "write": _template_write,
    "general": _template_general,
}


# ============================================================
# LLM REFINEMENT (optional)
# ============================================================

_REFINE_SYSTEM_PROMPT = (
    "You are a prompt engineering expert. The user dictated a request by voice "
    "and it has been lightly structured. Your job is to refine it into an "
    "excellent prompt that will get the best response from an AI assistant.\n\n"
    "Rules:\n"
    "- Keep the user's original intent exactly\n"
    "- Add clarity and structure where helpful\n"
    "- Don't add requirements the user didn't ask for\n"
    "- Don't be verbose — clear and concise wins\n"
    "- Output ONLY the refined prompt, nothing else\n"
    "- Don't wrap in quotes or add meta-commentary"
)


def _llm_refine(structured_prompt, config):
    """Use a local LLM to further refine the structured prompt."""
    try:
        import ollama
        llm_model = config.get("prompt_assist", {}).get("model",
                    config.get("llm_polish", {}).get("model", "phi3:mini"))
        response = ollama.chat(
            model=llm_model,
            messages=[
                {"role": "system", "content": _REFINE_SYSTEM_PROMPT},
                {"role": "user", "content": structured_prompt},
            ],
        )
        result = response["message"]["content"].strip()
        return result if result else structured_prompt
    except Exception as e:
        logger.warning("Prompt assist LLM refinement failed: %s", e)
        return structured_prompt


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def refine_prompt(raw_speech, config):
    """Transform raw speech into a well-structured LLM prompt.

    Args:
        raw_speech: The raw transcribed text from Whisper.
        config: Koda config dict.

    Returns:
        A refined, structured prompt string ready to paste into an LLM.
    """
    if not raw_speech or not raw_speech.strip():
        return raw_speech

    # Step 1: Light cleanup
    cleaned = _clean_for_prompt(raw_speech)
    if not cleaned:
        return raw_speech

    # Step 2: Detect intent and extract details
    intent = detect_intent(raw_speech)  # use raw speech for better detection
    language = _extract_language(raw_speech)
    details = _extract_details(raw_speech)
    context = _format_details(details)

    logger.debug("Prompt assist: intent=%s, language=%s, details=%s", intent, language, list(details.keys()))

    # Step 3: Apply template with extracted context
    template_fn = _TEMPLATES.get(intent, _template_general)
    structured = template_fn(cleaned, language, context)

    # Step 4: Optional LLM refinement
    # refine_backend is the user's install-time default (set via configure.py
    # step 10 — "none" / "ollama" / "api"). llm_refine is a per-call override
    # (e.g. prompt_conversation flips it True when the user clicks the Refine
    # button to force polish even if their default backend is "none").
    pa_config = config.get("prompt_assist", {})
    backend = pa_config.get("refine_backend", "none")
    if backend in ("ollama", "api") or pa_config.get("llm_refine", False):
        structured = _llm_refine(structured, config)

    logger.debug("Prompt assist output: %r", structured[:200])
    return structured
