from agents.llm import complete
from agents.search import format_results, web_search
from logger import log

_SYSTEM = (
    "You are a research assistant. Compile raw findings strictly from the "
    "search results provided. Do not invent facts or add opinions."
)


async def research(topic):
    results = await web_search(topic)
    notes = await complete(
        max_tokens=1500,
        system=_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    f'Research this topic: "{topic}".\n'
                    "Using ONLY the search results below, return raw findings as "
                    "plain bullet points, each with its source URL.\n"
                    "Do not summarize, do not add headers, do not add a conclusion. "
                    "Just facts.\n\n"
                    f"Search results:\n{format_results(results)}"
                ),
            }
        ],
    )

    log("researcher", {"topic": topic, "result_count": len(results), "notes": notes})
    return notes
