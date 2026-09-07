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
                "Organize the gathered facts below into a JSON object with\n"
                'this exact shape: { "title": string, "keyPoints": string[], '
                '"takeaway": string }.\n'
                "keyPoints: 3 to 7 strings, each a fact grounded in the notes. If "
                "the topic asks for pros and cons, include BOTH; label them (e.g. "
                '"Pro: ...", "Con: ..."). Do not invent facts not in the notes.\n'
                "takeaway: a short neutral summary of what the sources show. This "
                "is a fact collection — do NOT decide the question, recommend, or "
                "issue a verdict; report the findings and any trade-offs and let "
                "the reader conclude.\n"
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


# low reasoning helps pick the best points; the budget must cover the reasoning
# pass AND the JSON answer. Sized for full-document notes: at 1200 the thinking
# alone consumed the whole budget and the content came back blank (measured on
# ornith-1.5:9b). Generous here on purpose — quality over speed on a local box.
_MAX_TOKENS = 4000
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
