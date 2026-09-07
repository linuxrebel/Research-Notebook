import json

from agents.llm import complete
from logger import log

_SYSTEM = 'Respond with exactly one word: "APPROVED" or "REVISE". Nothing else.'


async def evaluate(notes, summary, topic):
    # medium reasoning sharpens the quality gate; the budget must cover the
    # reasoning tokens plus the one-word verdict or content comes back blank
    # (and a blank verdict reads as REVISE, looping the pipeline). Sized generous
    # for full-document notes — quality over speed on a local box.
    verdict = await complete(
        max_tokens=4000,
        reasoning_effort="medium",
        system=_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    f'The research topic was: "{topic}".\n\n'
                    f"Research notes:\n{notes}\n\n"
                    f"Summary:\n{json.dumps(summary)}\n\n"
                    "This is a fact-gathering summary. APPROVE it if every point "
                    "is grounded in the notes (nothing invented) and it covers "
                    "what the topic asks — including BOTH sides when the topic "
                    "asks for pros and cons. Do not require it to reach a verdict; "
                    "a neutral fact collection is correct. Otherwise REVISE.\n"
                    "Respond with ONLY\n"
                    '"APPROVED" or "REVISE".'
                ),
            }
        ],
    )

    verdict = verdict.strip()
    log("evaluator", {"verdict": verdict, "summary": summary})
    return verdict
