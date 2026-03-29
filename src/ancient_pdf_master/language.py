"""Language configuration and Tesseract language validation."""

from __future__ import annotations

import os
from pathlib import Path

import pytesseract

SUPPORTED_LANGUAGES = {
    "grc": "Ancient Greek (Ἀρχαία Ἑλληνική)",
    "lat": "Latin (Latina)",
    "eng": "English",
    "ell": "Greek Modern (Ελληνικά)",
    "heb": "Hebrew (עברית)",
    "ara": "Arabic (العربية)",
    "syr": "Syriac (ܣܘܪܝܝܐ)",
    "san": "Sanskrit (संस्कृतम्)",
    "deu": "German (Deutsch)",
    "fra": "French (Français)",
    "ita": "Italian (Italiano)",
    "spa": "Spanish (Español)",
}

DEFAULT_LANG = "grc+lat+eng"


def get_installed_languages() -> list[str]:
    """Return list of Tesseract language packs installed on the system,
    including custom-trained models."""
    try:
        langs = pytesseract.get_languages(config="")
    except pytesseract.TesseractNotFoundError:
        raise RuntimeError(
            "Tesseract is not installed.\n"
            "macOS: brew install tesseract\n"
            "Linux: sudo apt install tesseract-ocr"
        )

    # Add custom-trained models
    custom = get_custom_model_languages()
    for lang in custom:
        if lang not in langs:
            langs.append(lang)

    return langs


def get_custom_model_languages() -> list[str]:
    """Get language codes from custom-trained .traineddata files."""
    from .training import get_custom_models_dir
    models_dir = get_custom_models_dir()
    return [f.stem for f in models_dir.glob("*.traineddata")]


def get_tessdata_for_lang(lang: str) -> str | None:
    """Get the --tessdata-dir argument needed for a custom model.

    Returns None if the lang is a system-installed language.
    Returns the custom models directory path if it's a custom model.
    """
    from .training import get_custom_models_dir
    models_dir = get_custom_models_dir()
    if (models_dir / f"{lang}.traineddata").exists():
        return str(models_dir)
    return None


def validate_languages(lang_string: str) -> str:
    """Validate that all requested languages are installed.

    Args:
        lang_string: Tesseract-format language string (e.g. 'grc+lat+eng')

    Returns:
        The validated language string.

    Raises:
        ValueError: If any language is not installed.
    """
    requested = lang_string.split("+")
    installed = get_installed_languages()

    missing = [lang for lang in requested if lang not in installed]
    if missing:
        install_hints = []
        for lang in missing:
            name = SUPPORTED_LANGUAGES.get(lang, lang)
            install_hints.append(
                f"  - {name} ({lang}): "
                f"brew install tesseract-lang  OR  "
                f"sudo apt install tesseract-ocr-{lang}"
            )
        raise ValueError(
            f"Missing Tesseract language packs:\n" + "\n".join(install_hints) +
            f"\n\nNote: grc, lat, eng are bundled with the app. "
            f"Check TESSDATA_PREFIX if they're not detected."
        )

    return lang_string


def build_tesseract_config(lang_string: str) -> dict:
    """Build Tesseract configuration that supports mixed system + custom models.

    If the lang string includes custom models, sets up TESSDATA_PREFIX
    with symlinks so Tesseract can find both system and custom models.

    Returns:
        dict with keys: lang, config_extra, tessdata_dir (or empty dict if no custom)
    """
    from .training import get_custom_models_dir
    import tempfile

    requested = lang_string.split("+")
    custom_dir = get_custom_models_dir()
    has_custom = any((custom_dir / f"{lang}.traineddata").exists() for lang in requested)

    if not has_custom:
        return {}

    # Create a temp tessdata dir with symlinks to both system and custom models
    # so Tesseract can find all requested languages in one --tessdata-dir
    merged_dir = custom_dir / "_merged"
    merged_dir.mkdir(exist_ok=True)

    # Symlink system tessdata files
    from .training import find_tessdata_dir
    sys_tessdata = find_tessdata_dir()
    if sys_tessdata:
        for f in sys_tessdata.glob("*.traineddata"):
            link = merged_dir / f.name
            if not link.exists():
                try:
                    link.symlink_to(f)
                except OSError:
                    import shutil
                    shutil.copy2(f, link)

    # Symlink/copy custom models
    for f in custom_dir.glob("*.traineddata"):
        link = merged_dir / f.name
        if link.exists():
            link.unlink()
        try:
            link.symlink_to(f)
        except OSError:
            import shutil
            shutil.copy2(f, link)

    return {"tessdata_dir": str(merged_dir)}


def check_tesseract_available() -> tuple[bool, str]:
    """Check if Tesseract is available and return status message."""
    try:
        version = pytesseract.get_tesseract_version()
        return True, f"Tesseract {version}"
    except pytesseract.TesseractNotFoundError:
        return False, (
            "Tesseract not found. Install it:\n"
            "  macOS: brew install tesseract\n"
            "  Linux: sudo apt install tesseract-ocr"
        )
