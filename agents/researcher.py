import os

from anthropic import AsyncAnthropic

from logger import log

client = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


async def research(topic):
    response = await client.messages.create(
        model=os.environ["CLAUDE_MODEL"],
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

    notes = "\n".join(
        block.text for block in response.content if block.type == "text"
    )

    log("researcher", {"topic": topic, "notes": notes})
    return notes
