"""Tests for LLM model registry, model info fields, and base data classes."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_model_registry_has_models():
    """Model registry should contain models for all 3 providers."""
    from core.llm.models import ALL_MODELS

    assert "groq" in ALL_MODELS
    assert "gemini" in ALL_MODELS
    assert "ollama" in ALL_MODELS
    for provider, models in ALL_MODELS.items():
        assert len(models) > 0, f"No models for {provider}"


def test_model_registry_groq_models():
    """Groq should have the default model (Kimi K2)."""
    from core.llm.models import ALL_MODELS

    groq_models = ALL_MODELS["groq"]
    groq_ids = [m.id for m in groq_models]
    assert "moonshotai/kimi-k2-instruct" in groq_ids
    default = [m for m in groq_models if m.id == "moonshotai/kimi-k2-instruct"][0]
    assert default.provider == "groq"
    assert default.context_window > 0


def test_model_info_fields():
    """ModelInfo should have all required fields."""
    from core.llm.models import ALL_MODELS

    for provider, models in ALL_MODELS.items():
        for info in models:
            assert info.name, f"Model {info.id} missing name"
            assert info.provider, f"Model {info.id} missing provider"
            assert info.context_window > 0, f"Model {info.id} has invalid context_window"


def test_llm_base_message():
    """Message dataclass should work correctly."""
    from core.llm.base import Message

    msg = Message(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"


def test_llm_response():
    """LLMResponse dataclass should store response data."""
    from core.llm.base import LLMResponse

    resp = LLMResponse(
        content="Test response",
        model="test-model",
        provider="test",
        prompt_tokens=10,
        completion_tokens=20,
    )
    assert resp.content == "Test response"
    assert resp.model == "test-model"
    assert resp.prompt_tokens == 10
