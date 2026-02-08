"""Model configs for Groq, Gemini, Ollama."""

from core.llm.base import ModelInfo

# Groq cloud models
GROQ_MODELS = [
    ModelInfo(
        id="moonshotai/kimi-k2-instruct",
        name="Kimi K2",
        provider="groq",
        context_window=131072,
        max_output=32768,
        supports_tools=True,
        supports_streaming=True,
        description="Kimi K2 - strong reasoning and chat",
    ),
    ModelInfo(
        id="moonshotai/kimi-k2-instruct-0905",
        name="Kimi K2 (262K)",
        provider="groq",
        context_window=262144,
        max_output=32768,
        supports_tools=True,
        supports_streaming=True,
        description="Kimi K2 with 262K context window",
    ),
    ModelInfo(
        id="meta-llama/llama-4-maverick-17b-128e-instruct",
        name="Llama 4 Maverick",
        provider="groq",
        context_window=131072,
        max_output=32768,
        supports_tools=True,
        supports_vision=True,
        supports_streaming=True,
        description="Llama 4 Maverick - 128-expert MoE with vision",
    ),
    ModelInfo(
        id="meta-llama/llama-4-scout-17b-16e-instruct",
        name="Llama 4 Scout",
        provider="groq",
        context_window=131072,
        max_output=32768,
        supports_tools=True,
        supports_vision=True,
        supports_streaming=True,
        description="Llama 4 Scout - 16-expert vision model",
    ),
    ModelInfo(
        id="llama-3.3-70b-versatile",
        name="Llama 3.3 70B",
        provider="groq",
        context_window=131072,
        max_output=32768,
        supports_tools=True,
        supports_streaming=True,
        description="Llama 3.3 70B - good all-rounder",
    ),
    ModelInfo(
        id="llama-3.1-8b-instant",
        name="Llama 3.1 8B Instant",
        provider="groq",
        context_window=131072,
        max_output=8192,
        supports_tools=True,
        supports_streaming=True,
        description="Small and fast, good for simple stuff",
    ),
    ModelInfo(
        id="qwen/qwen3-32b",
        name="Qwen 3 32B",
        provider="groq",
        context_window=131072,
        max_output=32768,
        supports_tools=True,
        supports_streaming=True,
        description="Qwen 3 32B - handles multiple languages well",
    ),
]

# Gemini models
GEMINI_MODELS = [
    ModelInfo(
        id="gemini-2.5-flash",
        name="Gemini 2.5 Flash",
        provider="gemini",
        context_window=1048576,
        max_output=65536,
        supports_tools=True,
        supports_vision=True,
        supports_streaming=True,
        description="Gemini 2.5 Flash - fast thinking model",
    ),
    ModelInfo(
        id="gemini-2.5-pro",
        name="Gemini 2.5 Pro",
        provider="gemini",
        context_window=1048576,
        max_output=65536,
        supports_tools=True,
        supports_vision=True,
        supports_streaming=True,
        description="Gemini 2.5 Pro - better at complex stuff",
    ),
    ModelInfo(
        id="gemini-2.0-flash",
        name="Gemini 2.0 Flash",
        provider="gemini",
        context_window=1048576,
        max_output=8192,
        supports_tools=True,
        supports_vision=True,
        supports_streaming=True,
        description="Gemini 2.0 Flash - older but solid",
    ),
]

# Ollama local models
OLLAMA_MODELS = [
    ModelInfo(
        id="llama3.2:3b",
        name="Llama 3.2 3B",
        provider="ollama",
        context_window=128000,
        max_output=4096,
        supports_tools=True,
        supports_streaming=True,
        description="Small and fast, runs on anything",
    ),
    ModelInfo(
        id="llama3.1:8b",
        name="Llama 3.1 8B",
        provider="ollama",
        context_window=128000,
        max_output=4096,
        supports_tools=True,
        supports_streaming=True,
        description="Larger, better quality",
    ),
    ModelInfo(
        id="mistral:7b",
        name="Mistral 7B",
        provider="ollama",
        context_window=32768,
        max_output=4096,
        supports_tools=True,
        supports_streaming=True,
        description="Mistral 7B",
    ),
    ModelInfo(
        id="deepseek-r1:8b",
        name="DeepSeek R1 8B",
        provider="ollama",
        context_window=128000,
        max_output=4096,
        supports_tools=False,
        supports_streaming=True,
        description="Reasoning model, slower but thorough",
    ),
    ModelInfo(
        id="nomic-embed-text",
        name="Nomic Embed Text",
        provider="ollama",
        context_window=8192,
        max_output=0,
        supports_tools=False,
        supports_streaming=False,
        description="Embedding model for RAG search",
    ),
]

# All models combined
ALL_MODELS: dict[str, list[ModelInfo]] = {
    "groq": GROQ_MODELS,
    "gemini": GEMINI_MODELS,
    "ollama": OLLAMA_MODELS,
}


def get_model_info(model_id: str, provider: str = "") -> ModelInfo | None:
    """Look up model info by ID, optionally filtered by provider."""
    if provider:
        for m in ALL_MODELS.get(provider, []):
            if m.id == model_id:
                return m
    else:
        for models in ALL_MODELS.values():
            for m in models:
                if m.id == model_id:
                    return m
    return None


def get_provider_models(provider: str) -> list[ModelInfo]:
    """Get all models for a specific provider."""
    return ALL_MODELS.get(provider, [])
