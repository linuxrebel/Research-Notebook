"""Web search for the researcher — DuckDuckGo via the `ddgs` package.

No API key, no signup. Replaces the Anthropic server-side web_search tool so the
researcher works the same under any provider (local Ollama included).
"""

import asyncio

from ddgs import DDGS


def _search_sync(query, max_results):
    return DDGS().text(query, max_results=max_results)


async def web_search(query, max_results=5):
    """Return a list of {title, url, snippet} dicts. Runs the blocking ddgs call
    off the event loop."""
    results = await asyncio.to_thread(_search_sync, query, max_results)
    return [
        {
            "title": r.get("title", ""),
            "url": r.get("href", ""),
            "snippet": r.get("body", ""),
        }
        for r in results
    ]


def format_results(results):
    """Render search results as source-tagged bullets for the model prompt."""
    if not results:
        return "(no search results)"
    return "\n".join(
        f"- {r['title']}\n  {r['snippet']}\n  Source: {r['url']}" for r in results
    )
