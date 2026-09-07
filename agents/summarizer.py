import json

from agents.json_utils import parse_json
from agents.llm import complete
from logger import log

_SYSTEM = (
    "You are a JSON API. Respond with only valid JSON — no prose, no code fences. "
    "Follow every constraint exactly."
)


def _messages(notes, topic):
    return [
        {
            "role": "user",
            "content": (
                f'The research topic was: "{topic}".\n'
                "Read these research notes and produce a JSON object with\n"
                'this exact shape: { "title": string, "keyPoints": string[], '
                '"takeaway": string }.\n'
                "keyPoints: 3 to 7 strings that directly answer what the topic "
                "asks. If the topic asks for pros/cons, viability, or a verdict, "
                "the points must carry them — not generic background.\n"
                "takeaway: one paragraph stating the actual answer/verdict the "
                "topic asked for.\n"
                "Respond with ONLY the JSON, no other text.\n\n"
                f"Research notes:\n{notes}"
            ),
        }
    ]


def clamp_key_points(summary, n=7):
    """Keep at most n keyPoints.

    ponytail: small local models (ornith-1.5:9b) ignore point-count limits and
    return roughly one point per input bullet. Cap deterministically instead of
    looping the evaluator to MAX_ITERATIONS.
    """
    kp = summary.get("keyPoints")
    if isinstance(kp, list) and len(kp) > n:
        summary["keyPoints"] = kp[:n]
    return summary


# low reasoning helps pick the best points; max_tokens leaves room for
# reasoning + the JSON so the answer isn't starved (blank-content bug).
_MAX_TOKENS = 1200
_REASONING = "low"


async def summarize(notes, topic):
    raw = await complete(
        messages=_messages(notes, topic), max_tokens=_MAX_TOKENS, system=_SYSTEM,
        reasoning_effort=_REASONING,
    )
    try:
        summary = parse_json(raw)
    except json.JSONDecodeError:
        log("summarizer", {"warning": "invalid JSON, retrying", "raw": raw})
        raw = await complete(
            messages=_messages(notes, topic), max_tokens=_MAX_TOKENS, system=_SYSTEM,
            reasoning_effort=_REASONING,
        )
        summary = parse_json(raw)  # second failure raises, aborting the pipeline

    summary = clamp_key_points(summary)
    log("summarizer", {"input": notes, "output": summary})
    return summary
