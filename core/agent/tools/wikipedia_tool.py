"""Wikipedia lookups via the MediaWiki REST API."""

from __future__ import annotations

import logging

from core.agent.tools.base import BaseTool, ToolResult

logger = logging.getLogger(__name__)


class WikipediaTool(BaseTool):
    """Look up factual information from Wikipedia."""

    @property
    def name(self) -> str:
        return "wikipedia"

    @property
    def description(self) -> str:
        return (
            "Search Wikipedia for factual, historical, or encyclopedic information. "
            "Returns a summary of the topic. Use for definitions, biographies, "
            "science facts, historical events, etc."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The topic to look up on Wikipedia",
                },
                "sentences": {
                    "type": "integer",
                    "description": "Number of sentences in summary (default 5)",
                    "default": 5,
                },
            },
            "required": ["topic"],
        }

    async def execute(self, topic: str, sentences: int = 5, **kwargs) -> ToolResult:
        try:
            import httpx

            async with httpx.AsyncClient(timeout=10) as client:
                # Use Wikipedia REST API
                resp = await client.get(
                    f"https://en.wikipedia.org/api/rest_v1/page/summary/{topic.replace(' ', '_')}",
                    headers={"User-Agent": "HolexBeast/1.0"},
                    follow_redirects=True,
                )

                if resp.status_code == 404:
                    # Try search
                    search_resp = await client.get(
                        "https://en.wikipedia.org/w/api.php",
                        params={
                            "action": "opensearch",
                            "search": topic,
                            "limit": 3,
                            "format": "json",
                        },
                    )
                    search_data = search_resp.json()
                    suggestions = search_data[1] if len(search_data) > 1 else []

                    if suggestions:
                        # Try first suggestion
                        resp = await client.get(
                            f"https://en.wikipedia.org/api/rest_v1/page/summary/{suggestions[0].replace(' ', '_')}",
                            headers={"User-Agent": "HolexBeast/1.0"},
                            follow_redirects=True,
                        )
                    else:
                        return ToolResult(
                            success=False, output="",
                            error=f"No Wikipedia article found for '{topic}'",
                        )

                if resp.status_code != 200:
                    return ToolResult(
                        success=False, output="",
                        error=f"Wikipedia API returned status {resp.status_code}",
                    )

                data = resp.json()
                title = data.get("title", topic)
                extract = data.get("extract", "No content available.")
                url = data.get("content_urls", {}).get("desktop", {}).get("page", "")

                # Trim to requested sentences
                sents = extract.split(". ")
                if len(sents) > sentences:
                    extract = ". ".join(sents[:sentences]) + "."

                output = f"## 📚 {title}\n\n{extract}"
                if url:
                    output += f"\n\n🔗 [Read more on Wikipedia]({url})"

                return ToolResult(success=True, output=output, data=data)

        except ImportError:
            return ToolResult(
                success=False, output="",
                error="httpx not installed",
            )
        except Exception as e:
            logger.error(f"Wikipedia lookup failed: {e}")
            return ToolResult(success=False, output="", error=str(e))
