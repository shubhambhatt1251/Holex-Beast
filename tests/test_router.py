"""Tests for the smart LLM router — query classification, tier mapping, and model registry."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_classify_simple_greeting():
    """Simple greetings should route to the 'simple' tier."""
    from core.llm.router import classify_query

    assert classify_query("hello") == "simple"
    assert classify_query("Hi!") == "simple"
    assert classify_query("good morning") == "simple"
    assert classify_query("thanks") == "simple"
    assert classify_query("bye") == "simple"


def test_classify_tool_queries():
    """Queries needing tools should route to the 'tool' tier."""
    from core.llm.router import classify_query

    assert classify_query("search for the latest Python news") == "tool"
    assert classify_query("what's the weather in Tokyo?") == "tool"
    assert classify_query("calculate 15 * 37") == "tool"
    assert classify_query("open notepad") == "tool"  # voice commands route to tool tier
    assert classify_query("run this python code") == "tool"


def test_classify_complex_queries():
    """Complex analytical queries should route to the 'complex' tier."""
    from core.llm.router import classify_query

    assert classify_query("explain how transformers work in deep learning") == "complex"
    assert classify_query("compare React vs Vue for a new project") == "complex"
    assert classify_query("debug this function and optimize it") == "complex"
    assert classify_query("write a detailed essay on climate change") == "complex"


def test_classify_long_messages():
    """Messages over 500 chars should be classified as complex."""
    from core.llm.router import classify_query

    long_msg = "This is a message. " * 30  # 600 chars
    assert classify_query(long_msg) == "complex"


def test_classify_normal_fallback():
    """Regular messages should fall through to the 'normal' tier."""
    from core.llm.router import classify_query

    assert classify_query("how does a car engine work") == "normal"
    assert classify_query("what is photosynthesis") == "normal"


def test_classify_vision_queries():
    """Vision-related queries or has_image flag should route to 'vision' tier."""
    from core.llm.router import classify_query

    # Explicit has_image flag always wins
    assert classify_query("what is this", has_image=True) == "vision"
    assert classify_query("hello", has_image=True) == "vision"

    # Vision keywords detected from text
    assert classify_query("describe this image") == "vision"
    assert classify_query("analyze the photo I uploaded") == "vision"
    assert classify_query("what do you see in this picture") == "vision"
    assert classify_query("read the text in this screenshot") == "vision"


def test_tier_model_mapping_exists():
    """The tier-to-model mapping should cover all five tiers and all providers."""
    from core.llm.router import _TIER_MODELS

    for tier in ("simple", "tool", "complex", "normal", "vision"):
        assert tier in _TIER_MODELS, f"Missing tier: {tier}"
        mapping = _TIER_MODELS[tier]
        assert "groq" in mapping or "gemini" in mapping, f"No providers in tier {tier}"


def test_gemini_models_registered():
    """Gemini provider should have 2.5 Flash/Pro models in the registry."""
    from core.llm.models import ALL_MODELS

    gemini_ids = [m.id for m in ALL_MODELS["gemini"]]
    assert "gemini-2.5-flash" in gemini_ids
    assert "gemini-2.5-pro" in gemini_ids


def test_ollama_models_registered():
    """Ollama provider should have local models in the registry."""
    from core.llm.models import ALL_MODELS

    ollama_ids = [m.id for m in ALL_MODELS["ollama"]]
    assert "llama3.2:3b" in ollama_ids


def test_model_info_context_windows():
    """All models should have positive context windows."""
    from core.llm.models import ALL_MODELS

    for provider, models in ALL_MODELS.items():
        for m in models:
            assert m.context_window > 0, f"{m.id} has invalid context window"


def test_groq_vision_models_flagged():
    """Llama 4 models on Groq should have supports_vision=True."""
    from core.llm.models import ALL_MODELS

    groq_models = {m.id: m for m in ALL_MODELS["groq"]}
    assert groq_models["meta-llama/llama-4-scout-17b-16e-instruct"].supports_vision is True
    assert groq_models["meta-llama/llama-4-maverick-17b-128e-instruct"].supports_vision is True
    # Non-vision models should be False
    assert groq_models["llama-3.3-70b-versatile"].supports_vision is False


def test_message_user_with_image():
    """Message.user_with_image should create multimodal content."""
    from core.llm.base import Message

    msg = Message.user_with_image("describe this", "data:image/png;base64,abc123")
    assert msg.role == "user"
    assert isinstance(msg.content, list)
    assert len(msg.content) == 2
    assert msg.content[0]["type"] == "text"
    assert msg.content[0]["text"] == "describe this"
    assert msg.content[1]["type"] == "image_url"
    assert msg.content[1]["image_url"]["url"] == "data:image/png;base64,abc123"
