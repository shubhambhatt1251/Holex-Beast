"""Ollama provider - local LLM inference, no API key needed."""

from __future__ import annotations

import json
import logging
import time
from typing import AsyncGenerator, Optional

import httpx

from core.exceptions import LLMError
from core.llm.base import (
    BaseLLMProvider,
    LLMResponse,
    Message,
    ModelInfo,
    StreamChunk,
)
from core.llm.models import OLLAMA_MODELS

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    """Talks to the Ollama REST API on localhost. Works offline."""

    def __init__(self, base_url: str = "http://localhost:11434"):
        super().__init__("ollama")
        self.base_url = base_url.rstrip("/")
        self._installed_models: list[str] = []

    def _get_client(self) -> httpx.AsyncClient:
        """Get a fresh httpx client (avoids cross-event-loop issues)."""
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(120.0, connect=5.0),
        )

    async def initialize(self) -> bool:
        """Initialize and check if Ollama is running."""
        client = self._get_client()
        try:
            resp = await client.get("/api/tags")
            if resp.status_code == 200:
                data = resp.json()
                self._installed_models = [
                    m["name"] for m in data.get("models", [])
                ]
                self._is_available = True
                logger.info(
                    f"Ollama initialized - {len(self._installed_models)} models: "
                    f"{', '.join(self._installed_models[:5])}"
                )
            else:
                self._is_available = False
            return self._is_available
        except httpx.ConnectError:
            logger.warning("Ollama not running. Start with: ollama serve")
            self._is_available = False
            return False
        except Exception as e:
            logger.error(f"Ollama initialization failed: {e}")
            self._is_available = False
            return False
        finally:
            await client.aclose()

    async def generate(
        self,
        messages: list[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: Optional[list[dict]] = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate a complete response via Ollama."""
        model = model or "llama3.2:3b"
        start = time.perf_counter()

        payload: dict = {
            "model": model,
            "messages": [m.to_dict() for m in messages],
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if tools:
            payload["tools"] = tools

        client = self._get_client()
        try:
            resp = await client.post("/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()

            return LLMResponse(
                content=data.get("message", {}).get("content", ""),
                model=data.get("model", model),
                provider="ollama",
                prompt_tokens=data.get("prompt_eval_count", 0),
                completion_tokens=data.get("eval_count", 0),
                tokens_used=(
                    data.get("prompt_eval_count", 0)
                    + data.get("eval_count", 0)
                ),
                latency_ms=(time.perf_counter() - start) * 1000,
                finish_reason="stop",
                raw_response=data,
            )

        except httpx.ConnectError:
            raise LLMError("Ollama server not running. Start with: ollama serve")
        except Exception as e:
            raise LLMError(f"Ollama request failed: {e}")
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
        """Stream response chunks from Ollama."""
        model = model or "llama3.2:3b"

        payload = {
            "model": model,
            "messages": [m.to_dict() for m in messages],
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        client = self._get_client()
        try:
            async with client.stream(
                "POST", "/api/chat", json=payload
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        done = data.get("done", False)

                        if content:
                            yield StreamChunk(
                                content=content,
                                is_final=False,
                                model=model,
                                provider="ollama",
                            )
                        if done:
                            yield StreamChunk(
                                content="",
                                is_final=True,
                                model=model,
                                provider="ollama",
                            )
                            break
                    except json.JSONDecodeError:
                        continue

        except httpx.ConnectError:
            raise LLMError("Ollama server not running")
        except Exception as e:
            raise LLMError(f"Ollama stream failed: {e}")
        finally:
            await client.aclose()

    async def get_models(self) -> list[ModelInfo]:
        """Return locally installed Ollama models."""
        client = self._get_client()
        try:
            resp = await client.get("/api/tags")
            resp.raise_for_status()
            data = resp.json()

            models = []
            for m in data.get("models", []):
                name = m["name"]
                known = next((km for km in OLLAMA_MODELS if km.id == name), None)
                if known:
                    models.append(known)
                else:
                    models.append(ModelInfo(
                        id=name,
                        name=name,
                        provider="ollama",
                        context_window=4096,
                        description=f"Local model: {name}",
                    ))
            return models
        except Exception:
            return []
        finally:
            await client.aclose()

    async def pull_model(self, model: str) -> AsyncGenerator[dict, None]:
        """Pull/download a model. Yields progress updates."""
        client = self._get_client()
        try:
            async with client.stream(
                "POST", "/api/pull", json={"name": model}
            ) as resp:
                async for line in resp.aiter_lines():
                    if line.strip():
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            continue
        finally:
            await client.aclose()

    async def generate_embeddings(
        self, text: str, model: str = "nomic-embed-text"
    ) -> list[float]:
        """Generate embeddings using Ollama (for RAG)."""
        client = self._get_client()
        try:
            resp = await client.post(
                "/api/embeddings",
                json={"model": model, "prompt": text},
            )
            resp.raise_for_status()
            return resp.json().get("embedding", [])
        except Exception as e:
            raise LLMError(f"Ollama embeddings failed: {e}")
        finally:
            await client.aclose()

    @property
    def installed_models(self) -> list[str]:
        return self._installed_models

    async def close(self) -> None:
        """Cleanup (per-request clients are closed after each request)."""
        pass
