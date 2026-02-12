"""Main agent - handles tool calling loops and generates responses."""

from __future__ import annotations

import json
import logging
import time
from typing import AsyncGenerator, Optional

from core.agent.prompts import RAG_CONTEXT_PROMPT, get_system_prompt
from core.agent.tools.base import BaseTool, ToolResult
from core.agent.tools.calculator import CalculatorTool
from core.agent.tools.code_runner import CodeRunnerTool
from core.agent.tools.notes import NotesTool
from core.agent.tools.reminders import RemindersTool
from core.agent.tools.system_control import SystemControlTool
from core.agent.tools.timer_alarm import TimerAlarmTool
from core.agent.tools.translate_convert import TranslateConvertTool
from core.agent.tools.weather import WeatherTool
from core.agent.tools.web_search import WebSearchTool
from core.agent.tools.wikipedia_tool import WikipediaTool
from core.config import get_settings
from core.events import EventType, get_event_bus
from core.llm.base import Message
from core.llm.router import LLMRouter

logger = logging.getLogger(__name__)

MAX_ITERATIONS = 5  # Maximum tool-calling loops


class HolexAgent:
    """
    The Brain.

    It takes user input, decides if it needs tools (Search, Calc, OS Control),
    executes them, and keeps looping until it has a final answer.
    """

    def __init__(self, router: LLMRouter):
        self.router = router
        self.bus = get_event_bus()
        self.settings = get_settings()

        # Register all tools
        self._tools: dict[str, BaseTool] = {}
        self._register_default_tools()

        # Conversation history
        self._history: list[Message] = []
        self._system_message = Message.system(get_system_prompt())
        self._max_history = 50  # Keep last 50 messages

    def clear_history(self) -> None:
        """Clear conversation history (called on new/clear chat)."""
        self._history.clear()

    def _register_default_tools(self) -> None:
        """Register all built-in tools."""
        tools = [
            WebSearchTool(),
            CalculatorTool(),
            WeatherTool(),
            WikipediaTool(),
            SystemControlTool(),
            CodeRunnerTool(),
            TimerAlarmTool(),
            RemindersTool(),
            TranslateConvertTool(),
            NotesTool(),
        ]
        for tool in tools:
            self._tools[tool.name] = tool
            logger.debug(f"Registered tool: {tool.name}")

    def register_tool(self, tool: BaseTool) -> None:
        """Register a custom tool (for plugins)."""
        self._tools[tool.name] = tool
        logger.info(f"Registered custom tool: {tool.name}")

    def get_tool_schemas(self) -> list[dict]:
        """Get OpenAI-format tool schemas for all registered tools."""
        return [tool.to_openai_tool() for tool in self._tools.values()]

    async def process_with_image(
        self,
        user_message: str,
        image_path: str,
    ) -> str:
        """
        Send an image + text to a vision model.
        Reads the file, base64 encodes it, and lets the router
        pick the right vision model (Llama 4 Scout usually).
        """
        import base64
        from pathlib import Path

        img_path = Path(image_path)
        if not img_path.exists():
            return f"Image file not found: {image_path}"

        # Read and encode the image
        suffix = img_path.suffix.lower()
        mime_map = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".bmp": "image/bmp",
        }
        mime = mime_map.get(suffix, "image/png")
        raw = img_path.read_bytes()
        b64 = base64.b64encode(raw).decode()
        data_url = f"data:{mime};base64,{b64}"

        # Build multimodal message
        prompt = user_message or "Describe this image in detail."
        vision_msg = Message.user_with_image(prompt, data_url)
        self._history.append(Message.user(f"[Image: {img_path.name}] {prompt}"))

        messages = [self._system_message] + [vision_msg]

        self.bus.emit(EventType.AGENT_THINKING, {
            "message": f"[Vision] {prompt}",
            "tool_count": 0,
        })

        try:
            response = await self.router.generate(
                messages=messages,
                auto_route=True,  # will auto-select Llama 4 via vision tier
            )
            self._history.append(Message.assistant(response.content))
            self._trim_history()

            self.bus.emit(EventType.AGENT_RESPONSE, {
                "content": response.content,
                "iterations": 1,
                "latency_ms": response.latency_ms,
                "provider": response.provider,
                "model": response.model,
            })
            return response.content

        except Exception as e:
            error_msg = f"Vision analysis failed: {e}"
            logger.error(error_msg)
            self._history.append(Message.assistant(error_msg))
            return error_msg

    async def process(
        self,
        user_message: str,
        rag_context: Optional[str] = None,
    ) -> str:
        """
        Process a user message and return the final response.
        Handles tool calling automatically.
        """
        start_time = time.perf_counter()

        # Add user message to history
        self._history.append(Message.user(user_message))

        # Build messages for LLM
        messages = self._build_messages(rag_context)

        self.bus.emit(EventType.AGENT_THINKING, {
            "message": user_message,
            "tool_count": len(self._tools),
        })

        # The Think-Act-Observe Loop
        for iteration in range(MAX_ITERATIONS):
            try:
                response = await self.router.generate(
                    messages=messages,
                    tools=self.get_tool_schemas(),
                )

                # Check if LLM wants to call tools
                raw = response.raw_response or {}
                tool_calls = self._extract_tool_calls(raw)

                if not tool_calls:
                    # No tool calls → final answer
                    final_text = response.content
                    self._history.append(Message.assistant(final_text))
                    self._trim_history()

                    latency = (time.perf_counter() - start_time) * 1000
                    self.bus.emit(EventType.AGENT_RESPONSE, {
                        "content": final_text,
                        "iterations": iteration + 1,
                        "latency_ms": latency,
                        "provider": response.provider,
                        "model": response.model,
                    })
                    return final_text

                # Execute tool calls
                import uuid

                # Ensure all tool calls have IDs and proper structure
                # This fixes the "missing tool_call_id" error when switching providers
                normalized_tool_calls = []
                for tc in tool_calls:
                    if not tc.get("id"):
                        tc["id"] = f"call_{uuid.uuid4().hex[:8]}"
                    normalized_tool_calls.append({
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"])
                        }
                    })

                # Add the assistant's request to history with proper IDs
                assistant_msg = Message.assistant(response.content or "")
                assistant_msg.tool_calls = normalized_tool_calls
                messages.append(assistant_msg)

                # Emit tool call events
                for tc in tool_calls:
                    self.bus.emit(EventType.AGENT_TOOL_CALL, {
                        "tool": tc["name"],
                        "args": tc["arguments"],
                        "iteration": iteration + 1,
                    })

                # Execute independent tool calls in parallel
                import asyncio as _aio
                results = await _aio.gather(
                    *[self._execute_tool(tc["name"], tc["arguments"]) for tc in tool_calls],
                    return_exceptions=True,
                )

                for tc, result in zip(tool_calls, results):
                    if isinstance(result, Exception):
                        result = ToolResult(success=False, output="", error=str(result))

                    self.bus.emit(EventType.AGENT_TOOL_RESULT, {
                        "tool": tc["name"],
                        "success": result.success,
                        "output_preview": str(result)[:200],
                    })

                    # Add tool result to messages (with call ID for Groq/OpenAI)
                    messages.append(Message.tool(
                        str(result), name=tc["name"], tool_call_id=tc["id"],
                    ))

            except Exception as e:
                logger.error(f"Agent iteration {iteration + 1} failed: {e}")
                self.bus.emit(EventType.AGENT_ERROR, {"error": str(e)})

                # Try to give a graceful response
                error_msg = f"I encountered an error: {str(e)}. Let me try to help anyway."
                self._history.append(Message.assistant(error_msg))
                return error_msg

        # Max iterations reached - summarize what we have
        return "I've done extensive research but couldn't finalize an answer. Here's what I found so far."

    async def stream_process(
        self,
        user_message: str,
        rag_context: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Process a user message with streaming response.
        Tool calls are handled internally with a full ReAct loop
        (up to MAX_ITERATIONS), only the final answer is streamed.
        """
        self._history.append(Message.user(user_message))
        messages = self._build_messages(rag_context)

        try:
            # ReAct loop — keep resolving tool calls until the LLM gives a text answer
            for iteration in range(MAX_ITERATIONS):
                response = await self.router.generate(
                    messages=messages,
                    tools=self.get_tool_schemas(),
                )

                raw = response.raw_response or {}
                tool_calls = self._extract_tool_calls(raw)

                if not tool_calls:
                    break  # No tools needed — stream final answer below

                # Execute proper tool call history construction
                import uuid
                normalized_tool_calls = []
                for tc in tool_calls:
                    if not tc.get("id"):
                        tc["id"] = f"call_{uuid.uuid4().hex[:8]}"
                    normalized_tool_calls.append({
                        "id": tc["id"],
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"])
                        }
                    })

                assistant_msg = Message.assistant(response.content or "")
                assistant_msg.tool_calls = normalized_tool_calls
                messages.append(assistant_msg)

                # Run independent tool calls in parallel
                import asyncio as _aio
                results = await _aio.gather(
                    *[self._execute_tool(tc["name"], tc["arguments"]) for tc in tool_calls],
                    return_exceptions=True,
                )

                for tc, result in zip(tool_calls, results):
                    if isinstance(result, Exception):
                        result = ToolResult(success=False, output="", error=str(result))
                    self.bus.emit(EventType.AGENT_TOOL_RESULT, {
                        "tool": tc["name"],
                        "success": result.success,
                    })
                    messages.append(Message.tool(
                        str(result), name=tc["name"], tool_call_id=tc["id"],
                    ))

            # Stream the final response
            full_response = ""
            async for chunk in self.router.stream(messages=messages):
                if chunk.content:
                    full_response += chunk.content
                    yield chunk.content

            self._history.append(Message.assistant(full_response))
            self._trim_history()

        except Exception as e:
            error_msg = f"Sorry, I encountered an error: {str(e)}"
            yield error_msg
            self._history.append(Message.assistant(error_msg))

    def _build_messages(self, rag_context: Optional[str] = None) -> list[Message]:
        """Build the full message list for LLM."""
        messages = [self._system_message]

        # Add RAG context if available
        if rag_context:
            messages.append(Message.system(
                RAG_CONTEXT_PROMPT.format(context=rag_context)
            ))

        # Add conversation history (trimmed)
        messages.extend(self._history[-self._max_history:])
        return messages

    def _extract_tool_calls(self, raw_response: dict) -> list[dict]:
        """Extract tool calls from various LLM response formats."""
        tool_calls = []

        # OpenAI/Groq format
        choices = raw_response.get("choices", [])
        if choices:
            message = choices[0].get("message", {})
            calls = message.get("tool_calls", [])
            for call in calls:
                func = call.get("function", {})
                try:
                    args = json.loads(func.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append({
                    "id": call.get("id", ""),
                    "name": func.get("name", ""),
                    "arguments": args,
                })

        # Gemini format
        candidates = raw_response.get("candidates", [])
        if candidates and not tool_calls:
            parts = candidates[0].get("content", {}).get("parts", [])
            for part in parts:
                fc = part.get("functionCall")
                if fc:
                    tool_calls.append({
                        "name": fc.get("name", ""),
                        "arguments": fc.get("args", {}),
                    })

        return tool_calls

    async def _execute_tool(self, tool_name: str, args: dict) -> ToolResult:
        """Execute a tool by name with given arguments."""
        tool = self._tools.get(tool_name)
        if not tool:
            return ToolResult(
                success=False, output="",
                error=f"Tool '{tool_name}' not found",
            )

        try:
            logger.info(f"Executing tool: {tool_name}({args})")
            return await tool.execute(**args)
        except Exception as e:
            logger.error(f"Tool {tool_name} crashed: {e}")
            return ToolResult(success=False, output="", error=str(e))

    def _trim_history(self) -> None:
        """Keep conversation history within bounds."""
        if len(self._history) > self._max_history:
            self._history = self._history[-self._max_history:]



    def get_history(self) -> list[Message]:
        """Get current conversation history."""
        return list(self._history)

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())

    @property
    def tool_count(self) -> int:
        return len(self._tools)
