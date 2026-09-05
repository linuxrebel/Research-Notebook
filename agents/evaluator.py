import json

from agents.llm import complete
from logger import log

_SYSTEM = 'Respond with exactly one word: "APPROVED" or "REVISE". Nothing else.'


async def evaluate(notes, summary):
    verdict = await complete(
        max_tokens=300,
        system=_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Research notes:\n{notes}\n\n"
                    f"Summary:\n{json.dumps(summary)}\n\n"
                    "Does the summary have 3 distinct, high-quality key points\n"
                    "that are clearly interesting and well-developed?\n"
                    "Respond with ONLY\n"
                    '"APPROVED" or "REVISE".'
                ),
            }
        ],
    )

    verdict = verdict.strip()
    log("evaluator", {"verdict": verdict, "summary": summary})
    return verdict
