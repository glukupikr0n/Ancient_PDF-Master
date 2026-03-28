"""Language configuration and Tesseract language validation."""

from __future__ import annotations

import pytesseract

SUPPORTED_LANGUAGES = {
    "grc": "Ancient Greek (Ἀρχαία Ἑλληνική)",
    "lat": "Latin (Latina)",
    "eng": "English",
}

DEFAULT_LANG = "grc+lat+eng"


def get_installed_languages() -> list[str]:
    """Return list of Tesseract language packs installed on the system."""
    try:
        return pytesseract.get_languages(config="")
    except pytesseract.TesseractNotFoundError:
        raise RuntimeError(
            "Tesseract is not installed.\n"
            "macOS: brew install tesseract\n"
            "Linux: sudo apt install tesseract-ocr"
        )


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
            f"Missing Tesseract language packs:\n" + "\n".join(install_hints)
        )

    return lang_string


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
