"""Tests for exception hierarchy, GUI theme palettes, and stylesheet generation."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_exception_hierarchy():
    """All custom exceptions should inherit from HolexError."""
    from core.exceptions import (
        AgentError,
        FirebaseError,
        HolexError,
        LLMError,
        PluginError,
        RAGError,
        VoiceError,
    )

    assert issubclass(LLMError, HolexError)
    assert issubclass(AgentError, HolexError)
    assert issubclass(VoiceError, HolexError)
    assert issubclass(RAGError, HolexError)
    assert issubclass(FirebaseError, HolexError)
    assert issubclass(PluginError, HolexError)


def test_exception_message():
    """Exceptions should carry messages."""
    from core.exceptions import LLMError

    try:
        raise LLMError("API rate limit exceeded")
    except LLMError as e:
        assert "rate limit" in str(e).lower()


def test_gui_palette_themes():
    """All three theme palettes should be loadable."""
    from gui.styles import DARK_PALETTE, LIGHT_PALETTE, MIDNIGHT_PALETTE, get_palette

    assert get_palette("dark") is DARK_PALETTE
    assert get_palette("midnight") is MIDNIGHT_PALETTE
    assert get_palette("light") is LIGHT_PALETTE


def test_stylesheet_generation():
    """Stylesheet generator should produce non-empty QSS."""
    from gui.styles import DARK_PALETTE
    from gui.styles.stylesheet import generate_stylesheet

    qss = generate_stylesheet(DARK_PALETTE)
    assert isinstance(qss, str)
    assert len(qss) > 1000  # should be substantial
    assert "QMainWindow" in qss or "QWidget" in qss
