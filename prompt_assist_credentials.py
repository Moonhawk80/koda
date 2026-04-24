"""
API credential storage for prompt-assist v2.

API keys for the optional LLM refinement backend (Claude / OpenAI) live in
the Windows Credential Manager via the `keyring` package — never in
config.json, never logged. Pulled fresh on every refinement call.

Design: docs/prompt-assist-v2-design.md §"LLM refinement backend".
"""

import logging

logger = logging.getLogger("koda")

SERVICE_NAME = "koda-prompt-assist"


def save_api_key(provider: str, key: str) -> bool:
    """Persist an API key to Windows Credential Manager. Returns True on success."""
    if not provider or not key:
        return False
    try:
        import keyring
        keyring.set_password(SERVICE_NAME, provider, key)
        return True
    except Exception as e:
        logger.error("save_api_key(%s) failed: %s", provider, e)
        return False


def get_api_key(provider: str) -> str:
    """Return the stored API key for the provider. Empty string if missing."""
    if not provider:
        return ""
    try:
        import keyring
        return keyring.get_password(SERVICE_NAME, provider) or ""
    except Exception as e:
        logger.warning("get_api_key(%s) failed: %s", provider, e)
        return ""


def delete_api_key(provider: str) -> bool:
    """Remove a stored API key. Returns True if deleted (or already absent)."""
    if not provider:
        return False
    try:
        import keyring
        keyring.delete_password(SERVICE_NAME, provider)
        return True
    except Exception:
        return True  # treat missing as success
