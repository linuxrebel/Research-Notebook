from agents.llm import complete
from logger import log


async def research(topic):
    notes = await complete(
        max_tokens=1500,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[
            {
                "role": "user",
                "content": (
                    f'Research this topic: "{topic}".\n'
                    "Return raw findings as plain bullet points with sources.\n"
                    "Do not summarize, do not add headers, do not add a conclusion.\n"
                    "Just facts."
                ),
            }
        ],
    )

    log("researcher", {"topic": topic, "notes": notes})
    return notes
