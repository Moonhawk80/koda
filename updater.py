"""
Auto-update checker for Koda.
Checks GitHub releases on startup, notifies user if a newer version is available.
"""

import json
import logging
import threading
import urllib.request
import urllib.error
import webbrowser
from packaging.version import Version

logger = logging.getLogger("koda")

GITHUB_REPO = "Moonhawk80/koda"
RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{GITHUB_REPO}/releases/latest"


def check_for_update(current_version, callback=None):
    """Check GitHub for a newer release. Runs in a background thread.

    Args:
        current_version: Current app version string (e.g. "4.1.0")
        callback: Called with (latest_version, download_url) if update available,
                  or (None, None) if up to date or check failed.
    """
    thread = threading.Thread(
        target=_check_update_worker,
        args=(current_version, callback),
        daemon=True,
    )
    thread.start()
    return thread


def _check_update_worker(current_version, callback):
    """Worker thread that hits the GitHub API."""
    try:
        latest_version, download_url = _fetch_latest_release()
        if latest_version and _is_newer(latest_version, current_version):
            logger.info("Update available: %s (current: %s)", latest_version, current_version)
            if callback:
                callback(latest_version, download_url)
        else:
            logger.debug("Koda is up to date (current: %s, latest: %s)",
                         current_version, latest_version)
            if callback:
                callback(None, None)
    except Exception as e:
        logger.debug("Update check failed: %s", e)
        if callback:
            callback(None, None)


def _fetch_latest_release():
    """Fetch the latest release info from GitHub API.

    Returns:
        (version_string, download_url) or (None, None) on failure.
    """
    req = urllib.request.Request(
        RELEASES_API,
        headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "Koda-Voice-App",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    tag = data.get("tag_name", "")
    # Strip leading 'v' if present (e.g. "v4.2.0" -> "4.2.0")
    version = tag.lstrip("v")

    # Find installer asset URL, fall back to release page
    download_url = RELEASES_PAGE
    for asset in data.get("assets", []):
        name = asset.get("name", "")
        if name.startswith("KodaSetup") and name.endswith(".exe"):
            download_url = asset.get("browser_download_url", RELEASES_PAGE)
            break

    return version, download_url


def _is_newer(latest, current):
    """Compare version strings. Returns True if latest > current."""
    try:
        return Version(latest) > Version(current)
    except Exception:
        # Fallback: simple string comparison
        return latest != current


def open_releases_page():
    """Open the GitHub releases page in the default browser."""
    webbrowser.open(RELEASES_PAGE)
