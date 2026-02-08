"""Groq provider - talks to their OpenAI-compatible API."""

from __future__ import annotations

import logging
import time
from typing import AsyncGenerator, Optional

import httpx

from core.exceptions import LLMError, RateLimitError
from core.llm.base import (
    BaseLLMProvider,
    LLMResponse,
    Message,
    ModelInfo,
    StreamChunk,
)
from core.llm.models import GROQ_MODELS

logger = logging.getLogger(__name__)


class GroqProvider(BaseLLMProvider):
    """Groq cloud LLM. Fast inference, OpenAI-compatible endpoints."""

    def __init__(self, api_key: str, base_url: str = "https://api.groq.com/openai/v1"):
        super().__init__("groq")
        self.api_key = api_key
        self.base_url = base_url

    def _get_client(self) -> httpx.AsyncClient:
        """Get a fresh httpx client (avoids cross-event-loop issues)."""
        return httpx.AsyncClient(
            base_url=self.base_url,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(60.0, connect=10.0),
        )

    async def initialize(self) -> bool:
        """Verify API key by making a test request."""
        try:
            self._is_available = await self.health_check()
            if self._is_available:
                logger.info("Groq provider ready")
            else:
                logger.warning(
                    "Groq health check failed - API key might be wrong. "
                    "Get one at https://console.groq.com"
                )
            return self._is_available
        except Exception as e:
            logger.error(f"Groq init failed: {e}")
            self._is_available = False
            return False

    async def generate(
        self,
        messages: list[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[list[dict]] = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate a complete response via Groq."""
        model = model or "llama-3.3-70b-versatile"
        start = time.perf_counter()

        payload: dict = {
            "model": model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        client = self._get_client()
        try:
            resp = await client.post("/chat/completions", json=payload)

            if resp.status_code == 429:
                retry_after = float(resp.headers.get("retry-after", 60))
                raise RateLimitError("groq", retry_after)

            resp.raise_for_status()
            data = resp.json()

            choice = data["choices"][0]
            usage = data.get("usage", {})

            return LLMResponse(
                content=choice["message"].get("content", ""),
                model=data.get("model", model),
                provider="groq",
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                tokens_used=usage.get("total_tokens", 0),
                latency_ms=(time.perf_counter() - start) * 1000,
                finish_reason=choice.get("finish_reason", "stop"),
                raw_response=data,
            )

        except RateLimitError:
            raise
        except httpx.HTTPStatusError as e:
            raise LLMError(f"Groq API error: {e.response.status_code} - {e.response.text}")
        except LLMError:
            raise
        except Exception as e:
            raise LLMError(f"Groq request failed: {type(e).__name__}: {e}")
        finally:
            await client.aclose()

    async def stream(
        self,
        messages: list[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream response chunks from Groq."""
        model = model or "llama-3.3-70b-versatile"

        payload = {
            "model": model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        client = self._get_client()
        try:
            async with client.stream(
                "POST", "/chat/completions", json=payload
            ) as resp:
                if resp.status_code == 429:
                    raise RateLimitError("groq")
                resp.raise_for_status()

                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        yield StreamChunk(content="", is_final=True, model=model, provider="groq")
                        break

                    import json
                    data = json.loads(data_str)
                    delta = data["choices"][0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        yield StreamChunk(
                            content=content,
                            is_final=False,
                            model=model,
                            provider="groq",
                        )

        except RateLimitError:
            raise
        except Exception as e:
            raise LLMError(f"Groq stream failed: {e}")
        finally:
            await client.aclose()

    async def get_models(self) -> list[ModelInfo]:
        """Return available Groq models."""
        client = self._get_client()
        try:
            resp = await client.get("/models")
            resp.raise_for_status()
            return GROQ_MODELS
        except Exception:
            return []
        finally:
            await client.aclose()

    async def close(self) -> None:
        """Cleanup (per-request clients are closed after each request)."""
        pass
