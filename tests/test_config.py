"""Tests for application settings — singleton behaviour, defaults, and nested config."""

import sys
from pathlib import Path

# Ensure project root on path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_settings_singleton():
    """Settings should always return the same instance."""
    from core.config import get_settings
    s1 = get_settings()
    s2 = get_settings()
    assert s1 is s2


def test_settings_defaults():
    """Default settings should have sensible values."""
    from core.config import get_settings
    s = get_settings()
    assert s.app_name == "Holex Beast"
    assert s.groq.default_model == "moonshotai/kimi-k2-instruct"
    assert s.gemini.default_model == "gemini-2.5-flash"
    assert 0.0 <= s.groq.temperature <= 2.0


def test_settings_nested():
    """Nested settings should be accessible."""
    from core.config import get_settings
    s = get_settings()
    assert hasattr(s, 'groq')
    assert hasattr(s, 'gemini')
    assert hasattr(s, 'ollama')
    assert hasattr(s, 'firebase')
    assert hasattr(s, 'voice')
    assert hasattr(s, 'rag')
