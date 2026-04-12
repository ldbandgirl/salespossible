"""
Web search tool — uses DuckDuckGo by default (no API key needed).
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

WEB_SEARCH_SCHEMA: dict[str, Any] = {
    "name": "web_search",
    "description": (
        "Search the web for current information about a company, person, market, "
        "or any topic. Returns a list of relevant results with titles, URLs, and snippets."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query",
            },
            "max_results": {
                "type": "integer",
                "description": "Maximum number of results to return (default 5, max 10)",
                "default": 5,
            },
        },
        "required": ["query"],
    },
}


async def web_search(inputs: dict[str, Any]) -> str:
    """Execute a web search and return formatted results."""
    query = inputs["query"]
    max_results = min(int(inputs.get("max_results", 5)), 10)

    try:
        from duckduckgo_search import AsyncDDGS

        async with AsyncDDGS() as ddgs:
            results = await ddgs.atext(query, max_results=max_results)

        if not results:
            return f"No results found for: {query}"

        lines = [f"Search results for: {query}\n"]
        for i, r in enumerate(results, 1):
            lines.append(
                f"{i}. **{r.get('title', 'No title')}**\n"
                f"   URL: {r.get('href', '')}\n"
                f"   {r.get('body', '')[:300]}\n"
            )

        return "\n".join(lines)

    except ImportError:
        return "duckduckgo-search not installed. Run: pip install duckduckgo-search"
    except Exception as e:
        logger.error("Web search error: %s", e)
        return f"Search failed: {e}"
