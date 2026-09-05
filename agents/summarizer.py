import json

from agents.json_utils import parse_json
from agents.llm import complete
from logger import log

_SYSTEM = "You are a JSON API. Respond with only valid JSON — no prose, no code fences."


def _messages(notes):
    return [
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
    ]


async def summarize(notes):
    raw = await complete(messages=_messages(notes), max_tokens=800, system=_SYSTEM)
    try:
        summary = parse_json(raw)
    except json.JSONDecodeError:
        log("summarizer", {"warning": "invalid JSON, retrying", "raw": raw})
        raw = await complete(messages=_messages(notes), max_tokens=800, system=_SYSTEM)
        summary = parse_json(raw)  # second failure raises, aborting the pipeline

    log("summarizer", {"input": notes, "output": summary})
    return summary
