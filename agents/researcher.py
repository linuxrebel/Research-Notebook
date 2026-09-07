from agents.fetch import detect_urls, fetch_one
from agents.json_utils import parse_json
from agents.llm import complete
from agents.search import web_search
from logger import log, warn

_SYSTEM = (
    "You are a research assistant gathering facts. Work strictly from the source "
    "document provided. Do not invent facts, and do not draw conclusions or make "
    "recommendations — collect what the source states."
)

_MAX_FOLLOWUP_QUERIES = 4
_MAX_SECONDARY_URLS = 3  # follow-up documents to actually fetch and read


async def _extract(topic, url, text, want_queries):
    """Read one source; return (facts_markdown, follow_up_queries).

    Extraction, not deliberation — reasoning_effort="none" so the budget goes to
    the facts, not a hidden thinking pass (which returns blank on this model).
    """
    ask_queries = (
        f"2. List up to {_MAX_FOLLOWUP_QUERIES} web-search queries for external "
        "facts this document makes worth checking (dependencies, comparisons, "
        "claims to verify). Empty list if none.\n"
    ) if want_queries else ""
    shape = '{"facts": string, "queries": string[]}' if want_queries else '{"facts": string}'
    raw = await complete(
        max_tokens=1500,
        reasoning_effort="none",
        system=_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    f'Topic: "{topic}".\n'
                    f"Source ({url}):\n{text}\n\n"
                    "From this source only:\n"
                    "1. Write the facts relevant to the topic as markdown bullet "
                    "points. When a fact names a notable technology, project, or "
                    "concept, wrap that name in [[wikilinks]] so it becomes a "
                    "graph node. If the topic asks for pros and cons, gather BOTH "
                    "as facts; do not decide the question.\n"
                    f"{ask_queries}"
                    f"Respond as JSON: {shape}.\n"
                ),
            }
        ],
    )
    try:
        obj = parse_json(raw)
        facts = obj.get("facts", "").strip() or raw.strip()
        return facts, (obj.get("queries") or [])[:_MAX_FOLLOWUP_QUERIES]
    except Exception:
        warn("researcher", {"warning": "extract JSON parse failed", "url": url, "raw": raw[:200]})
        return raw.strip(), []


async def _discover(queries, limit):
    """DDG for link discovery only (snippets discarded); up to `limit` URLs."""
    urls = []
    for q in queries:
        for r in await web_search(q):
            u = r.get("url")
            if u and u not in urls:
                urls.append(u)
    return urls[:limit]


async def research(topic, notebook):
    """Gather facts source-by-source into `notebook`, writing each note as it is
    read. Returns the combined notes for the synthesis stage."""
    urls = detect_urls(topic)
    queries = []

    if urls:
        # Primary document(s) named in the topic: read each, note its facts, and
        # let the first one's follow-up queries drive discovery.
        for i, url in enumerate(urls):
            title, text = await fetch_one(url)
            facts, q = await _extract(topic, url, text, want_queries=(i == 0))
            notebook.add_source(url, facts, title=title)
            if i == 0:
                queries = q
        secondary = await _discover(queries, _MAX_SECONDARY_URLS)
    else:
        # No primary document: discover links for the topic, then read them.
        secondary = await _discover([topic], _MAX_SECONDARY_URLS)

    for url in secondary:
        title, text = await fetch_one(url)
        facts, _ = await _extract(topic, url, text, want_queries=False)
        notebook.add_source(url, facts, title=title)

    notes = notebook.combined_notes()
    log("researcher", {"topic": topic, "primary_urls": urls, "followup_queries": queries,
                       "secondary_urls": secondary, "source_count": len(notebook.sources)})
    return notes
