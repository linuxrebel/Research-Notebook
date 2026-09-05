import json

from agents.json_utils import parse_json
from agents.llm import complete
from logger import log

_SYSTEM = (
    "You are a JSON API. Respond with only valid JSON — no prose, no code fences. "
    "Follow every constraint exactly."
)


def _messages(notes):
    return [
        {
            "role": "user",
            "content": (
                "Read these research notes and produce a JSON object with\n"
                'this exact shape: { "title": string, "keyPoints": string[], '
                '"takeaway": string }.\n'
                "The keyPoints array MUST contain EXACTLY 3 strings — not more, "
                "not fewer. Choose the 3 most important points.\n"
                "Respond with ONLY the JSON, no other text.\n\n"
                f"Research notes:\n{notes}"
            ),
        }
    ]


def clamp_key_points(summary, n=3):
    """Keep at most n keyPoints.

    ponytail: small local models (ornith-1.5:9b) ignore "exactly 3" and return
    roughly one point per input bullet. The design wants 3, so enforce it
    deterministically instead of looping the evaluator to MAX_ITERATIONS.
    """
    kp = summary.get("keyPoints")
    if isinstance(kp, list) and len(kp) > n:
        summary["keyPoints"] = kp[:n]
    return summary


async def summarize(notes):
    raw = await complete(messages=_messages(notes), max_tokens=800, system=_SYSTEM)
    try:
        summary = parse_json(raw)
    except json.JSONDecodeError:
        log("summarizer", {"warning": "invalid JSON, retrying", "raw": raw})
        raw = await complete(messages=_messages(notes), max_tokens=800, system=_SYSTEM)
        summary = parse_json(raw)  # second failure raises, aborting the pipeline

    summary = clamp_key_points(summary)
    log("summarizer", {"input": notes, "output": summary})
    return summary
