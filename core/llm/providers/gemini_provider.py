"""
Gemini LLM Provider

Hits the v1beta REST API directly so we don't need the google SDK.
Supports function calling, vision, and streaming.
"""

from __future__ import annotations

import json
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
    Role,
    StreamChunk,
)
from core.llm.models import GEMINI_MODELS

logger = logging.getLogger(__name__)

GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider(BaseLLMProvider):
    """Google Gemini via the REST API (no SDK needed)."""

    def __init__(self, api_key: str):
        super().__init__("gemini")
        self.api_key = api_key

    def _get_client(self) -> httpx.AsyncClient:
        """Fresh per-request client to avoid cross-event-loop issues."""
        return httpx.AsyncClient(
            timeout=httpx.Timeout(90.0, connect=10.0),
            headers={"x-goog-api-key": self.api_key},
        )

    async def initialize(self) -> bool:
        """Verify the API key with a lightweight models list call."""
        try:
            self._is_available = await self.health_check()
            if self._is_available:
                logger.info("Gemini provider ready")
            else:
                logger.warning(
                    "Gemini health check failed - check your API key. "
                    "Get one at https://aistudio.google.com/apikey"
                )
            return self._is_available
        except Exception as e:
            logger.error(f"Gemini init failed: {e}")
            self._is_available = False
            return False

    def _convert_messages(self, messages: list[Message]) -> tuple[str, list[dict]]:
        """Convert Message objects to Gemini API format."""
        system_instruction = ""
        contents = []

        for msg in messages:
            if msg.role == Role.SYSTEM:
                system_instruction = msg.content
            elif msg.role == Role.USER:
                if isinstance(msg.content, list):
                    # Multimodal message (text + image) — convert to Gemini format
                    parts = []
                    for part in msg.content:
                        if isinstance(part, dict) and part.get("type") == "text":
                            parts.append({"text": part["text"]})
                        elif isinstance(part, dict) and part.get("type") == "image_url":
                            url = part["image_url"]["url"]
                            if url.startswith("data:"):
                                header, b64_data = url.split(",", 1)
                                mime_type = header.split(":")[1].split(";")[0]
                                parts.append({"inlineData": {"mimeType": mime_type, "data": b64_data}})
                    contents.append({"role": "user", "parts": parts or [{"text": ""}]})
                else:
                    contents.append({
                        "role": "user",
                        "parts": [{"text": msg.content}]
                    })
            elif msg.role == Role.ASSISTANT:
                contents.append({
                    "role": "model",
                    "parts": [{"text": msg.content}]
                })
            elif msg.role == Role.TOOL:
                contents.append({
                    "role": "function",
                    "parts": [{"functionResponse": {
                        "name": msg.name or "tool",
                        "response": {"result": msg.content}
                    }}]
                })

        return system_instruction, contents

    async def generate(
        self,
        messages: list[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        tools: Optional[list[dict]] = None,
        **kwargs,
    ) -> LLMResponse:
        """Generate a complete response via Gemini."""
        model = model or "gemini-2.5-flash"
        start = time.perf_counter()

        system_instruction, contents = self._convert_messages(messages)

        url = f"{GEMINI_API_BASE}/models/{model}:generateContent"

        payload: dict = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
                "topP": 0.95,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }
        if tools:
            # Convert OpenAI tool format to Gemini format
            gemini_tools = self._convert_tools(tools)
            if gemini_tools:
                payload["tools"] = gemini_tools

        client = self._get_client()
        try:
            resp = await client.post(url, json=payload)

            if resp.status_code == 429:
                raise RateLimitError("gemini")
            resp.raise_for_status()

            data = resp.json()
            candidate = data["candidates"][0]
            content_parts = candidate["content"]["parts"]
            text = "".join(p.get("text", "") for p in content_parts)

            usage = data.get("usageMetadata", {})

            return LLMResponse(
                content=text,
                model=model,
                provider="gemini",
                prompt_tokens=usage.get("promptTokenCount", 0),
                completion_tokens=usage.get("candidatesTokenCount", 0),
                tokens_used=usage.get("totalTokenCount", 0),
                latency_ms=(time.perf_counter() - start) * 1000,
                finish_reason=candidate.get("finishReason", "STOP"),
                raw_response=data,
            )

        except RateLimitError:
            raise
        except httpx.HTTPStatusError as e:
            raise LLMError(f"Gemini API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            raise LLMError(f"Gemini request failed: {e}")
        finally:
            await client.aclose()

    async def stream(
        self,
        messages: list[Message],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
        **kwargs,
    ) -> AsyncGenerator[StreamChunk, None]:
        """Stream response chunks from Gemini."""
        model = model or "gemini-2.5-flash"
        system_instruction, contents = self._convert_messages(messages)

        url = (
            f"{GEMINI_API_BASE}/models/{model}:streamGenerateContent"
            f"?alt=sse"
        )

        payload: dict = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        client = self._get_client()
        try:
            async with client.stream("POST", url, json=payload) as resp:
                if resp.status_code == 429:
                    raise RateLimitError("gemini")
                resp.raise_for_status()

                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if not data_str:
                        continue
                    try:
                        data = json.loads(data_str)
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            text = "".join(p.get("text", "") for p in parts)
                            if text:
                                yield StreamChunk(
                                    content=text,
                                    is_final=False,
                                    model=model,
                                    provider="gemini",
                                )
                    except json.JSONDecodeError:
                        continue

            yield StreamChunk(content="", is_final=True, model=model, provider="gemini")

        except RateLimitError:
            raise
        except Exception as e:
            raise LLMError(f"Gemini stream failed: {e}")
        finally:
            await client.aclose()

    def _convert_tools(self, openai_tools: list[dict]) -> list[dict]:
        """Convert OpenAI tool format to Gemini function declarations."""
        declarations = []
        for tool in openai_tools:
            if tool.get("type") == "function":
                func = tool["function"]
                declarations.append({
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "parameters": func.get("parameters", {}),
                })
        if declarations:
            return [{"functionDeclarations": declarations}]
        return []

    async def get_models(self) -> list[ModelInfo]:
        """Return available Gemini models."""
        client = self._get_client()
        try:
            url = f"{GEMINI_API_BASE}/models"
            resp = await client.get(url)
            resp.raise_for_status()
            return GEMINI_MODELS
        except Exception:
            return []
        finally:
            await client.aclose()

    async def close(self) -> None:
        """Nothing to clean up — clients are closed after each request."""
        pass
        pass
