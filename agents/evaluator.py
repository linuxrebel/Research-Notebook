import json

from agents.llm import complete
from logger import log

_SYSTEM = 'Respond with exactly one word: "APPROVED" or "REVISE". Nothing else.'


async def evaluate(notes, summary, topic):
    # medium reasoning sharpens the quality gate; max_tokens must cover the
    # reasoning tokens plus the one-word verdict or content comes back blank.
    verdict = await complete(
        max_tokens=1200,
        reasoning_effort="medium",
        system=_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    f'The research topic was: "{topic}".\n\n'
                    f"Research notes:\n{notes}\n\n"
                    f"Summary:\n{json.dumps(summary)}\n\n"
                    "Does the summary actually answer what the topic asks, "
                    "grounded in the notes (not generic or off-topic)?\n"
                    "Respond with ONLY\n"
                    '"APPROVED" or "REVISE".'
                ),
            }
        ],
    )

    verdict = verdict.strip()
    log("evaluator", {"verdict": verdict, "summary": summary})
    return verdict
