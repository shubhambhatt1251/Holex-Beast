"""Download Vosk speech models on demand.

Fetches the right model zip from alphacephei.com, extracts it into
the models/ directory, and returns the path. Called from the voice
overlay when a user picks a language that isn't downloaded yet.
"""

from __future__ import annotations

import logging
import shutil
import zipfile
from pathlib import Path
from typing import Optional
from urllib.request import urlretrieve

from core.config import MODELS_DIR
from core.voice.stt import VOSK_MODEL_MAP

logger = logging.getLogger(__name__)

VOSK_BASE_URL = "https://alphacephei.com/vosk/models"


def model_path_for(lang_code: str) -> Optional[Path]:
    """Return the local path for a language's Vosk model, or None."""
    model_name = VOSK_MODEL_MAP.get(lang_code)
    if not model_name:
        return None
    return MODELS_DIR / model_name


def is_model_downloaded(lang_code: str) -> bool:
    """Check if the Vosk model for a language is already on disk."""
    path = model_path_for(lang_code)
    return path is not None and path.exists()


def download_model(
    lang_code: str,
    on_progress: Optional[callable] = None,
) -> Optional[Path]:
    """Download and extract the Vosk model for a language.

    Args:
        lang_code: Language code like 'hi', 'ta', 'bn', etc.
        on_progress: Optional callback(downloaded_bytes, total_bytes).

    Returns:
        Path to the extracted model directory, or None on failure.
    """
    model_name = VOSK_MODEL_MAP.get(lang_code)
    if not model_name:
        logger.error(f"No Vosk model mapped for: {lang_code}")
        return None

    dest = MODELS_DIR / model_name
    if dest.exists():
        logger.info(f"Model already exists: {dest}")
        return dest

    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    zip_url = f"{VOSK_BASE_URL}/{model_name}.zip"
    zip_path = MODELS_DIR / f"{model_name}.zip"

    logger.info(f"Downloading Vosk model: {zip_url}")

    try:
        def _reporthook(block_num, block_size, total_size):
            downloaded = block_num * block_size
            if on_progress and total_size > 0:
                on_progress(downloaded, total_size)

        urlretrieve(zip_url, str(zip_path), reporthook=_reporthook)

        # Extract
        logger.info(f"Extracting {zip_path.name}...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(str(MODELS_DIR))

        # Cleanup zip
        zip_path.unlink(missing_ok=True)

        if dest.exists():
            logger.info(f"Model ready: {dest}")
            return dest
        else:
            logger.error(f"Extraction succeeded but model dir not found: {dest}")
            return None

    except Exception as e:
        logger.error(f"Failed to download model for {lang_code}: {e}")
        # Cleanup partial download
        zip_path.unlink(missing_ok=True)
        if dest.exists():
            shutil.rmtree(dest, ignore_errors=True)
        return None


def list_downloaded_models() -> dict[str, Path]:
    """Return {lang_code: path} for all downloaded Vosk models."""
    result = {}
    for code, name in VOSK_MODEL_MAP.items():
        p = MODELS_DIR / name
        if p.exists():
            result[code] = p
    return result


def list_missing_models() -> list[str]:
    """Return language codes whose Vosk models are not downloaded."""
    return [
        code for code, name in VOSK_MODEL_MAP.items()
        if not (MODELS_DIR / name).exists()
    ]
