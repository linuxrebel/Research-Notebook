from agents.fetch import detect_urls, fetch_sources
from agents.json_utils import parse_json
from agents.llm import complete
from agents.search import web_search
from logger import log, warn

_SYSTEM = (
    "You are a research assistant. Work strictly from the source documents "
    "provided. Do not invent facts. Address exactly what the topic asks."
)

_MAX_FOLLOWUP_QUERIES = 4
_MAX_SECONDARY_URLS = 3  # follow-up documents to actually fetch and read


async def _discover_urls(queries, limit):
    """Run each query through DDG for link discovery only (snippets discarded);
    return up to `limit` unique result URLs."""
    urls = []
    for q in queries:
        for r in await web_search(q):
            u = r.get("url")
            if u and u not in urls:
                urls.append(u)
    return urls[:limit]


async def _read_primary(topic, primary):
    """Read the primary document; return (findings_text, [follow-up queries])."""
    raw = await complete(
        max_tokens=1200,
        reasoning_effort="low",
        system=_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    f'Topic: "{topic}".\n'
                    "Below is the primary source document. Based ONLY on it:\n"
                    "1. Extract the findings relevant to the topic.\n"
                    f"2. List up to {_MAX_FOLLOWUP_QUERIES} specific web-search "
                    "queries for external data this document makes you want to "
                    "verify or explore (dependencies, comparisons, claims to "
                    "check). Empty list if none are needed.\n"
                    'Respond as JSON: {"findings": string, "queries": string[]}.\n\n'
                    f"Primary source:\n{primary}"
                ),
            }
        ],
    )
    try:
        obj = parse_json(raw)
        return obj.get("findings", ""), (obj.get("queries") or [])[:_MAX_FOLLOWUP_QUERIES]
    except Exception:
        warn("researcher", {"warning": "follow-up JSON parse failed", "raw": raw[:300]})
        return raw, []


async def _compile(topic, sources):
    """Synthesize notes that answer the topic, from fetched source documents."""
    return await complete(
        max_tokens=1500,
        reasoning_effort="none",
        system=_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    f'Research this topic: "{topic}".\n'
                    "Using ONLY the source documents below, compile findings that "
                    "address what the topic asks, as plain bullet points, each "
                    "tagged with its source URL.\n"
                    "Do not fabricate. If the sources do not cover something the "
                    "topic asks for, say so explicitly.\n\n"
                    f"Sources:\n{sources}"
                ),
            }
        ],
    )


async def research(topic):
    urls = detect_urls(topic)

    if not urls:
        # No primary document named: discover links for the topic, then READ
        # them — never synthesize from search snippets.
        discovered = await _discover_urls([topic], _MAX_SECONDARY_URLS)
        sources = await fetch_sources(discovered)
        notes = await _compile(topic, sources or "(no sources could be fetched)")
        log("researcher", {"topic": topic, "mode": "discover",
                           "read_urls": discovered, "notes": notes})
        return notes

    # Primary document(s) named in the topic: read them first, let what they say
    # drive follow-up discovery, then read those documents too (real-research
    # order — no snippet paraphrasing anywhere).
    primary = await fetch_sources(urls)
    _, queries = await _read_primary(topic, primary)

    secondary_urls = await _discover_urls(queries, _MAX_SECONDARY_URLS)
    secondary = await fetch_sources(secondary_urls)

    sources = primary
    if secondary:
        sources += "\n\n=== External context (follow-up sources) ===\n\n" + secondary

    notes = await _compile(topic, sources)
    log("researcher", {"topic": topic, "mode": "fetch", "primary_urls": urls,
                       "followup_queries": queries, "secondary_urls": secondary_urls,
                       "notes": notes})
    return notes
