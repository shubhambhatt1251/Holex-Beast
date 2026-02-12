"""
LLM Router

Picks the best provider/model for each request and handles
failover if one goes down.

Order: Groq -> Gemini -> Ollama (local fallback)
"""

from __future__ import annotations

import logging
import re
from typing import AsyncGenerator, Optional

from core.config import AppSettings, get_settings
from core.events import EventType, get_event_bus
from core.exceptions import (
    AllProvidersFailedError,
    LLMError,
    ProviderNotAvailableError,
    RateLimitError,
)
from core.llm.base import (
    BaseLLMProvider,
    LLMResponse,
    Message,
    ModelInfo,
    Role,
    StreamChunk,
)
from core.llm.providers.gemini_provider import GeminiProvider
from core.llm.providers.groq_provider import GroqProvider
from core.llm.providers.ollama_provider import OllamaProvider

logger = logging.getLogger(__name__)

# --- Query classification patterns ---

# Complex queries that need a bigger model
_COMPLEX_PATTERNS = re.compile(
    r"(?i)\b("
    r"explain|analyze|compare|contrast|summarize|write\s+(?:a\s+)?(?:code|essay|report|article|story|poem)"
    r"|debug|refactor|optimize|implement|architecture|algorithm|design pattern"
    r"|step[\s-]?by[\s-]?step|in[\s-]?depth|detailed|comprehensive|thoroughly"
    r"|pros?\s+and\s+cons?|advantages?\s+and\s+disadvantages?"
    r"|translate|convert|rewrite|improve|review"
    r"|math|equation|calculus|physics|chemistry|science"
    r"|research|thesis|academic|peer[\s-]?review"
    r")\b"
)

# Simple stuff - greetings, one-word answers
_SIMPLE_PATTERNS = re.compile(
    r"(?i)^("
    r"hi|hello|hey|thanks|thank you|ok|okay|yes|no|bye|good\s?(morning|night|evening)"
    r"|what(?:'s| is) (?:your name|the time|the date|up)"
    r"|how are you|who are you|tell me a joke"
    r")[\s!?.]*$"
)

# Queries that probably need a tool call — broad voice command coverage
_TOOL_PATTERNS = re.compile(
    r"(?i)\b("
    # Web search
    r"search|google|look\s+up|find\s+(?:me|out)"
    # Weather
    r"|what(?:'s| is) the weather"
    # Math
    r"|calculate|compute|solve|(?:what|how much) is \d"
    # System control — apps
    r"|open\s+\w+|close\s+\w+|launch\s+\w+|start\s+\w+|run\s+\w+|quit\s+\w+|kill\s+\w+|exit\s+\w+"
    # Volume / audio
    r"|volume|mute|unmute|louder|quieter|sound"
    # Brightness
    r"|brightness|bright|dim"
    # Screenshot
    r"|screenshot|screen\s*shot|capture|snap"
    # Lock / sleep / power
    r"|lock\s+(screen|computer|pc)|sleep|shut\s*down|restart|power\s+off"
    # Browser / YouTube
    r"|play\s+|search\s+(for|on)\s+youtube|youtube|google\s+"
    r"|open\s+(?:website|url|link|page)|go\s+to\s+\w+"
    r"|browse|navigate"
    # WiFi / Bluetooth
    r"|wifi|wi-fi|bluetooth|internet"
    # File / folder
    r"|open\s+(?:folder|file|document|desktop|download)"
    r"|show\s+(?:desktop|files|folder)"
    # Window management
    r"|minimize|maximize|switch\s+(?:to|window)|close\s+(?:this|window|tab)"
    # Clipboard
    r"|copy|clipboard|paste|type\s+\w+"
    # Wikipedia
    r"|wikipedia|wiki|who (?:is|was)|when (?:did|was)"
    # Code
    r"|run (?:this |the )?(?:code|script|python)"
    # Timer / alarm / stopwatch
    r"|set\s+(?:a\s+)?timer|alarm|stopwatch|countdown|remind\s+me"
    r"|wake\s+me|\d+\s*(?:minutes?|hours?|seconds?)\s+timer"
    # Reminders
    r"|remind(?:er)?|don'?t\s+(?:let\s+me\s+)?forget|remember\s+to"
    # Translation / conversion
    r"|translate|translat\w+|convert\s+\d|how\s+(?:many|much)\s+\w+\s+(?:in|to)\s+\w+"
    r"|\d+\s*(?:miles?|km|kg|lbs?|pounds?|celsius|fahrenheit|meters?)\s+(?:in|to)"
    # Dictionary
    r"|define\s+\w+|meaning\s+of|definition\s+of|what\s+does\s+\w+\s+mean"
    # Notes / todos
    r"|(?:add|create|make|take|write)\s+(?:a\s+)?(?:note|todo|to-do)"
    r"|(?:my|list|show)\s+(?:notes?|todos?|to-dos?)"
    r"|delete\s+(?:note|todo)|complete\s+todo"
    # System info / processes
    r"|system\s+info|battery|processes|kill\s+process"
    r"|recycle\s+bin|wallpaper|zip\s+|unzip"
    r")\b"
)

# Image/vision related queries
_VISION_PATTERNS = re.compile(
    r"(?i)\b("
    r"image|picture|photo|describe\s+this|what(?:'s| is)\s+(?:in|on)\s+(?:this|the)\s+(?:image|photo|picture)"
    r"|look\s+at|analyze\s+(?:this|the)\s+(?:image|photo|picture)"
    r"|ocr|read\s+(?:this|the)\s+(?:text|image)|identify|recognize"
    r"|vision|visual"
    r")\b"
)


def classify_query(text: str, has_image: bool = False) -> str:
    """
    Figure out what kind of query this is so we pick the right model.
    Returns one of: vision, simple, tool, complex, normal
    """
    text = text.strip()

    # Image attached or vision keywords -> vision model
    if has_image or _VISION_PATTERNS.search(text):
        return "vision"

    # Check simple first (greetings, system commands)
    if _SIMPLE_PATTERNS.match(text):
        return "simple"

    # Check if tools are needed
    if _TOOL_PATTERNS.search(text):
        return "tool"

    # Check complex patterns
    if _COMPLEX_PATTERNS.search(text):
        return "complex"

    # Long messages are likely complex
    if len(text) > 500:
        return "complex"

    return "normal"


# Which model to use for each tier per provider
_TIER_MODELS = {
    "simple": {
        "groq": "llama-3.1-8b-instant",                          # Fastest
        "gemini": "gemini-2.5-flash",
        "ollama": "llama3.2:3b",
    },
    "tool": {
        "groq": "moonshotai/kimi-k2-instruct",                   # Strong tool-calling
        "gemini": "gemini-2.5-flash",
        "ollama": "llama3.2:3b",
    },
    "complex": {
        "groq": "moonshotai/kimi-k2-instruct-0905",              # 262K context, deepest reasoning
        "gemini": "gemini-2.5-pro",
        "ollama": "llama3.1:8b",
    },
    "normal": {
        "groq": "moonshotai/kimi-k2-instruct",                   # Default best
        "gemini": "gemini-2.5-flash",
        "ollama": "llama3.2:3b",
    },
    "vision": {
        "groq": "meta-llama/llama-4-scout-17b-16e-instruct",     # Llama 4 vision
        "gemini": "gemini-2.5-flash",                             # Gemini has vision too
        "ollama": "llama3.2:3b",
    },
}


class LLMRouter:
    """
    Routes LLM requests to the right provider.

    Tries Groq first (fastest), falls back to Gemini,
    then Ollama if nothing else works.
    """

    def __init__(self, settings: Optional[AppSettings] = None):
        self.settings = settings or get_settings()
        self.bus = get_event_bus()

        # Initialize providers
        self._providers: dict[str, BaseLLMProvider] = {}
        self._current_provider: Optional[str] = None
        self._current_model: Optional[str] = None
        self._failover_order: list[str] = []

        # Configurable defaults (can be updated via settings panel)
        self.default_temperature: float = 0.7
        self.default_max_tokens: int = 4096

        # Stats
        self._request_count = 0
        self._total_tokens = 0
        self._total_latency_ms = 0

    async def initialize(self) -> None:
        """Initialize all configured providers."""
        logger.info("Initializing LLM providers...")

        # Try Groq
        if self.settings.is_groq_configured:
            groq = GroqProvider(
                api_key=self.settings.groq.api_key,
                base_url=self.settings.groq.base_url,
            )
            if await groq.initialize():
                self._providers["groq"] = groq
                logger.info("  Groq connected")

        # Try Gemini
        if self.settings.is_gemini_configured:
            gemini = GeminiProvider(api_key=self.settings.gemini.api_key)
            if await gemini.initialize():
                self._providers["gemini"] = gemini
                logger.info("  Gemini connected")

        # Try Ollama
        ollama = OllamaProvider(base_url=self.settings.ollama.base_url)
        if await ollama.initialize():
            self._providers["ollama"] = ollama
            logger.info(f"  Ollama connected ({len(ollama.installed_models)} models)")

        # Set failover order
        self._failover_order = self._build_failover_order()

        # Set default provider
        if self._failover_order:
            default = self.settings.default_provider.value
            if default in self._providers:
                self._current_provider = default
            else:
                self._current_provider = self._failover_order[0]

            self._current_model = self._get_default_model(self._current_provider)
            logger.info(
                f"Using: {self._current_provider} / {self._current_model}"
            )
            self.bus.emit(EventType.LLM_PROVIDER_CHANGED, {
                "provider": self._current_provider,
                "model": self._current_model,
            })
        else:
            logger.error("No LLM providers available! Check your API keys.")

    def _build_failover_order(self) -> list[str]:
        """Build provider failover priority list."""
        order = []
        # User's preferred order
        priority = [
            self.settings.default_provider.value,
            self.settings.fallback_provider.value,
        ]
        # Add remaining
        all_providers = ["groq", "gemini", "ollama"]
        for p in priority + all_providers:
            if p in self._providers and p not in order:
                order.append(p)
        return order

    def _get_default_model(self, provider: str) -> str:
        """Get the default model for a provider."""
        defaults = {
            "groq": self.settings.groq.default_model,
            "gemini": self.settings.gemini.default_model,
            "ollama": self.settings.ollama.default_model,
        }
        return defaults.get(provider, "")

    async def generate(
        self,
        messages: list[Message],
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        tools: Optional[list[dict]] = None,
        auto_route: bool = True,
    ) -> LLMResponse:
        """
        Generate a response with automatic failover.
        If auto_route=True (default), picks the best model based on
        the last user message's complexity.
        """
        provider = provider or self._current_provider
        model = model or self._current_model
        temperature = temperature if temperature is not None else self.settings.temperature
        max_tokens = max_tokens if max_tokens is not None else self.settings.max_tokens
        if auto_route and provider:
            user_text = ""
            has_image = False
            for m in reversed(messages):
                if isinstance(m, Message) and m.role == Role.USER:
                    # Handle multimodal content (list of parts) vs plain string
                    if isinstance(m.content, list):
                        has_image = any(
                            isinstance(p, dict) and p.get("type") == "image_url"
                            for p in m.content
                        )
                        user_text = " ".join(
                            p.get("text", "") for p in m.content
                            if isinstance(p, dict) and p.get("type") == "text"
                        )
                    else:
                        user_text = m.content or ""
                    break
            if user_text or has_image:
                tier = classify_query(user_text, has_image=has_image)
                routed_model = _TIER_MODELS.get(tier, {}).get(provider, model)
                if routed_model and routed_model != model:
                    logger.info(f"Auto-route: [{tier}] -> {provider}/{routed_model}")
                    model = routed_model

        self.bus.emit(EventType.LLM_REQUEST, {
            "provider": provider,
            "model": model,
            "message_count": len(messages),
        })

        errors: list[str] = []

        # Try providers in failover order
        providers_to_try = [provider] if provider else []
        providers_to_try.extend(
            p for p in self._failover_order if p not in providers_to_try
        )

        for prov_name in providers_to_try:
            if prov_name not in self._providers:
                continue

            prov = self._providers[prov_name]
            # Failover: preserve the original tier model for this provider
            if prov_name == provider:
                use_model = model
            else:
                # Look up the correct tier model for the failover provider
                user_text = ""
                for m in reversed(messages):
                    if isinstance(m, Message) and m.role == Role.USER:
                        user_text = m.content if isinstance(m.content, str) else ""
                        break
                tier = classify_query(user_text) if user_text else "normal"
                use_model = _TIER_MODELS.get(tier, {}).get(prov_name, self._get_default_model(prov_name))

            try:
                response = await prov.generate(
                    messages=messages,
                    model=use_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    tools=tools,
                )
                self._request_count += 1
                self._total_tokens += response.tokens_used
                self._total_latency_ms += response.latency_ms

                self.bus.emit(EventType.LLM_RESPONSE, {
                    "provider": prov_name,
                    "model": response.model,
                    "tokens": response.tokens_used,
                    "latency_ms": response.latency_ms,
                })

                return response

            except RateLimitError:
                logger.warning(f"{prov_name} rate limited, trying next...")
                errors.append(f"{prov_name}: Rate limited")
                continue
            except LLMError as e:
                logger.warning(f"{prov_name} failed: {e.message}")
                errors.append(f"{prov_name}: {e.message}")
                continue
            except Exception as e:
                logger.error(f"{prov_name} unexpected error: {e}")
                errors.append(f"{prov_name}: {str(e)}")
                continue

        # All providers failed
        self.bus.emit(EventType.LLM_ERROR, {"errors": errors})
        raise AllProvidersFailedError()

    async def stream(
        self,
        messages: list[Message],
        provider: Optional[str] = None,
        model: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        auto_route: bool = True,
    ) -> AsyncGenerator[StreamChunk, None]:
        """
        Stream a response with automatic failover.
        Yields StreamChunk objects with content pieces.
        """
        provider = provider or self._current_provider
        model = model or self._current_model
        temperature = temperature if temperature is not None else self.settings.temperature
        max_tokens = max_tokens if max_tokens is not None else self.settings.max_tokens

        # Auto-route to the best model for this query
        if auto_route and provider:
            user_text = ""
            has_image = False
            for m in reversed(messages):
                if isinstance(m, Message) and m.role == Role.USER:
                    if isinstance(m.content, list):
                        has_image = any(
                            isinstance(p, dict) and p.get("type") == "image_url"
                            for p in m.content
                        )
                        user_text = " ".join(
                            p.get("text", "") for p in m.content
                            if isinstance(p, dict) and p.get("type") == "text"
                        )
                    else:
                        user_text = m.content or ""
                    break
            if user_text or has_image:
                tier = classify_query(user_text, has_image=has_image)
                routed_model = _TIER_MODELS.get(tier, {}).get(provider, model)
                if routed_model and routed_model != model:
                    logger.info(f"Auto-route (stream): [{tier}] -> {provider}/{routed_model}")
                    model = routed_model

        self.bus.emit(EventType.LLM_STREAM_START, {
            "provider": provider,
            "model": model,
        })

        providers_to_try = [provider] if provider else []
        providers_to_try.extend(
            p for p in self._failover_order if p not in providers_to_try
        )

        for prov_name in providers_to_try:
            if prov_name not in self._providers:
                continue

            prov = self._providers[prov_name]
            use_model = model if prov_name == provider else self._get_default_model(prov_name)

            try:
                async for chunk in prov.stream(
                    messages=messages,
                    model=use_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                ):
                    if chunk.content:
                        self.bus.emit(EventType.LLM_STREAM_CHUNK, {
                            "content": chunk.content,
                            "provider": prov_name,
                        })
                    if chunk.is_final:
                        self.bus.emit(EventType.LLM_STREAM_END, {
                            "provider": prov_name,
                            "model": use_model,
                        })
                    yield chunk
                return  # Success, don't try next provider

            except RateLimitError:
                logger.warning(f"{prov_name} rate limited during stream")
                continue
            except LLMError as e:
                logger.warning(f"{prov_name} stream failed: {e.message}")
                continue

        self.bus.emit(EventType.LLM_ERROR, {"errors": ["All providers failed"]})
        raise AllProvidersFailedError()

    # --- Provider switching ---────

    def switch_provider(self, provider: str, model: Optional[str] = None) -> None:
        """Switch the active provider and optionally the model."""
        if provider not in self._providers:
            raise ProviderNotAvailableError(provider)

        self._current_provider = provider
        self._current_model = model or self._get_default_model(provider)

        self.bus.emit(EventType.LLM_PROVIDER_CHANGED, {
            "provider": self._current_provider,
            "model": self._current_model,
        })
        logger.info(f"Switched to {provider} / {self._current_model}")

    def switch_model(self, model: str) -> None:
        """Switch the active model on current provider."""
        self._current_model = model
        self.bus.emit(EventType.LLM_MODEL_CHANGED, {
            "provider": self._current_provider,
            "model": model,
        })

    async def get_all_models(self) -> dict[str, list[ModelInfo]]:
        """Get available models from all providers."""
        result = {}
        for name, prov in self._providers.items():
            try:
                result[name] = await prov.get_models()
            except Exception:
                result[name] = []
        return result

    @property
    def current_provider(self) -> Optional[str]:
        return self._current_provider

    @property
    def current_model(self) -> Optional[str]:
        return self._current_model

    @property
    def available_providers(self) -> list[str]:
        return list(self._providers.keys())

    @property
    def is_online(self) -> bool:
        """Check if any cloud provider is available."""
        return "groq" in self._providers or "gemini" in self._providers

    @property
    def is_offline_capable(self) -> bool:
        """Check if offline mode is available."""
        return "ollama" in self._providers

    @property
    def stats(self) -> dict:
        avg_latency = (
            self._total_latency_ms / self._request_count
            if self._request_count > 0
            else 0
        )
        return {
            "total_requests": self._request_count,
            "total_tokens": self._total_tokens,
            "avg_latency_ms": round(avg_latency, 1),
            "providers": self.available_providers,
            "current": f"{self._current_provider}/{self._current_model}",
        }

    async def shutdown(self) -> None:
        """Close all provider connections."""
        for name, prov in self._providers.items():
            try:
                if hasattr(prov, "close"):
                    await prov.close()
            except Exception as e:
                logger.warning(f"Error closing {name}: {e}")
        self._providers.clear()
        logger.info("LLM Router shut down")
