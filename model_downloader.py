"""
Mirror downloads of speech models hosted on the Moonhawk80/koda GitHub
release page. faster-whisper's default name resolution maps short names
like "large-v3-turbo" to HuggingFace repos that may not exist
(Systran/faster-whisper-large-v3-turbo is missing as of 2026-05-02 —
the working community port lives under a different namespace). We mirror
the canonical files on our own GH release so we control the URL, can
pin versions, and never depend on third-party hosts at runtime.

Models land in CONFIG_DIR/models/<model_size>/ as a fully-extracted
faster-whisper snapshot directory (model.bin, config.json,
preprocessor_config.json, tokenizer.json, vocabulary.json). The dir
path is what gets passed to WhisperModel(path, ...).
"""

import logging
import os
import shutil
import tarfile
import tempfile
import urllib.request

logger = logging.getLogger(__name__)

# model_size -> tarball download URL on our GitHub release. Add a row here
# when we mirror a new model. The release tag is intentionally separate from
# Koda version tags so model assets don't bloat code releases.
MIRRORED_MODELS = {
    "large-v3-turbo": (
        "https://github.com/Moonhawk80/koda/releases/download/"
        "whisper-models-v1/whisper-large-v3-turbo.tar.gz"
    ),
}

# Canonical files in a faster-whisper snapshot. is_available() spot-checks
# the two mandatory ones to avoid loading a half-extracted directory.
_REQUIRED_FILES = ("model.bin", "config.json")


def model_dir_for(model_size: str, root: str) -> str:
    """Where the extracted snapshot lives on disk."""
    return os.path.join(root, "models", model_size)


def is_available(model_size: str, root: str) -> bool:
    """True if the model is fully extracted and ready for WhisperModel(path)."""
    target = model_dir_for(model_size, root)
    if not os.path.isdir(target):
        return False
    return all(os.path.exists(os.path.join(target, f)) for f in _REQUIRED_FILES)


def download_and_extract(model_size: str, root: str, progress_cb=None) -> str:
    """Download the tarball for `model_size`, extract under `root`/models/,
    return the final model directory path.

    progress_cb(downloaded_bytes: int, total_bytes: int) is called periodically
    during the HTTP read — callers should throttle UI updates themselves.
    Raises on any failure; callers (load_whisper_model) handle fallback.
    """
    if model_size not in MIRRORED_MODELS:
        raise ValueError(f"No mirror configured for model {model_size!r}")

    url = MIRRORED_MODELS[model_size]
    target_dir = model_dir_for(model_size, root)
    os.makedirs(os.path.dirname(target_dir), exist_ok=True)

    # Download to a temp file (atomic semantics — staging dir below ensures
    # we never expose a half-extracted target_dir to load_whisper_model).
    fd, tmp_path = tempfile.mkstemp(suffix=".tar.gz")
    os.close(fd)
    try:
        logger.info("Downloading %s from %s", model_size, url)
        with urllib.request.urlopen(url) as response:
            total = int(response.headers.get("Content-Length", 0))
            chunk_size = 1024 * 1024  # 1 MB
            downloaded = 0
            with open(tmp_path, "wb") as out:
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    out.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb is not None:
                        progress_cb(downloaded, total)

        staging_dir = target_dir + ".staging"
        if os.path.exists(staging_dir):
            shutil.rmtree(staging_dir)
        os.makedirs(staging_dir)
        with tarfile.open(tmp_path, "r:gz") as tar:
            tar.extractall(staging_dir)

        # Atomic swap — only after a fully-extracted staging dir exists.
        if os.path.exists(target_dir):
            shutil.rmtree(target_dir)
        os.rename(staging_dir, target_dir)
        logger.info("Extracted %s to %s", model_size, target_dir)
        return target_dir
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
