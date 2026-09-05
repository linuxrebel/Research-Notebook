import json
import os

from anthropic import AsyncAnthropic

from agents.json_utils import parse_json
from logger import log

client = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


async def _request(notes):
    response = await client.messages.create(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=800,
        messages=[
            {
                "role": "user",
                "content": (
                    "Read these research notes and produce a JSON object with\n"
                    'this exact shape: { "title": string, "keyPoints": string[], '
                    '"takeaway": string }.\n'
                    "Return 3 key points. Respond with ONLY the JSON, no other text.\n\n"
                    f"Research notes:\n{notes}"
                ),
            }
        ],
    )
    return next((b.text for b in response.content if b.type == "text"), "{}")


async def summarize(notes):
    raw = await _request(notes)
    try:
        summary = parse_json(raw)
    except json.JSONDecodeError:
        log("summarizer", {"warning": "invalid JSON, retrying", "raw": raw})
        raw = await _request(notes)
        summary = parse_json(raw)  # second failure raises, aborting the pipeline

    log("summarizer", {"input": notes, "output": summary})
    return summary
