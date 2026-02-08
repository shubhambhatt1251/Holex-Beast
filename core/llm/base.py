"""Base classes for LLM providers + shared data types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncGenerator, Optional


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """A single message in a conversation."""
    role: Role
    content: str | list
    name: Optional[str] = None              # Tool name for tool messages
    tool_calls: Optional[list] = None       # Tool calls from assistant
    tool_call_id: Optional[str] = None      # ID linking tool result to its call
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        role_str = self.role.value if isinstance(self.role, Enum) else str(self.role)
        d: dict = {"role": role_str, "content": self.content}
        if self.name:
            d["name"] = self.name
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        return d

    @classmethod
    def system(cls, content: str) -> "Message":
        return cls(role=Role.SYSTEM, content=content)

    @classmethod
    def user(cls, content: str) -> "Message":
        return cls(role=Role.USER, content=content)

    @classmethod
    def user_with_image(
        cls, text: str, image_url: str,
    ) -> "Message":
        """Create a multimodal user message with text and an image."""
        content = [
            {"type": "text", "text": text},
            {"type": "image_url", "image_url": {"url": image_url}},
        ]
        return cls(role=Role.USER, content=content)

    @classmethod
    def assistant(cls, content: str) -> "Message":
        return cls(role=Role.ASSISTANT, content=content)

    @classmethod
    def tool(cls, content: str, name: str, tool_call_id: str = "") -> "Message":
        return cls(role=Role.TOOL, content=content, name=name, tool_call_id=tool_call_id)


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    content: str
    model: str
    provider: str
    tokens_used: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0
    finish_reason: str = "stop"
    raw_response: Optional[dict] = None

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class StreamChunk:
    """A single chunk from a streaming response."""
    content: str
    is_final: bool = False
    model: str = ""
    provider: str = ""


@dataclass
class ModelInfo:
    """Information about an available model."""
    id: str
    name: str
    provider: str
    context_window: int = 4096
    max_output: int = 4096
    supports_tools: bool = False
    supports_vision: bool = False
    supports_streaming: bool = True
    description: str = ""


class BaseLLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    All providers (Groq, Gemini, Ollama) must implement this interface.
    """

    def __init__(self, name: str):
        self.name = name
        self._is_available = False

    @abstractmethod
    async def initialize(self) -> bool:
        """Initialize the provider. Returns True if ready."""
        ...

    @abstractmethod
    async def generate(
        self,
        messages: list[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[list[dict]] = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate a complete response."""
        ...

    @abstractmethod
    async def stream(
        self,
        messages: list[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream a response chunk by chunk."""
        ...

    @abstractmethod
    async def get_models(self) -> list[ModelInfo]:
        """List available models for this provider."""
        ...

    @property
    def is_available(self) -> bool:
        return self._is_available

    async def health_check(self) -> bool:
        """Check if the provider is reachable."""
        try:
            models = await self.get_models()
            self._is_available = len(models) > 0
            return self._is_available
        except Exception:
            self._is_available = False
            return False
