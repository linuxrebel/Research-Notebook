import json
import os

from anthropic import AsyncAnthropic

from logger import log

client = AsyncAnthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


async def evaluate(notes, summary):
    response = await client.messages.create(
        model=os.environ["CLAUDE_MODEL"],
        max_tokens=300,
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

    block = next((b for b in response.content if b.type == "text"), None)
    verdict = block.text.strip() if block else None
    log("evaluator", {"verdict": verdict, "summary": summary})
    return verdict
