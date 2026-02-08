"""Web search using DuckDuckGo (no API key needed)."""

from __future__ import annotations

import asyncio
import logging

from core.agent.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class WebSearchTool(BaseTool):
    """Search the web using DuckDuckGo."""

    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return (
            "Search the web for current information, news, prices, facts, "
            "or anything that requires up-to-date data. Returns top results "
            "with titles, snippets, and URLs."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Number of results to return (default 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        }

    async def execute(self, query: str, max_results: int = 5, **kwargs) -> ToolResult:
        try:
            from duckduckgo_search import DDGS

            # Run sync DDGS in a thread so we don't block the event loop
            def _search():
                with DDGS() as ddgs:
                    return list(ddgs.text(query, max_results=max_results))

            raw = await asyncio.to_thread(_search)

            results = [
                {
                    "title": r.get("title", ""),
                    "snippet": r.get("body", ""),
                    "url": r.get("href", ""),
                }
                for r in raw
            ]

            if not results:
                return ToolResult(
                    success=True,
                    output="No results found for this query.",
                    data=[],
                )

            formatted = []
            for i, r in enumerate(results, 1):
                formatted.append(
                    f"{i}. **{r['title']}**\n"
                    f"   {r['snippet']}\n"
                    f"   🔗 {r['url']}"
                )

            return ToolResult(
                success=True,
                output="\n\n".join(formatted),
                data=results,
            )

        except ImportError:
            return ToolResult(
                success=False,
                output="",
                error="duckduckgo-search package not installed. Run: pip install duckduckgo-search",
            )
        except Exception as e:
            logger.error(f"Web search failed: {e}")
            return ToolResult(success=False, output="", error=str(e))
