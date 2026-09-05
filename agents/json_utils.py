import json
import re

_FENCE = re.compile(r"^```[a-zA-Z0-9]*\s*\n(.*?)\n?```$", re.DOTALL)


def parse_json(raw):
    """Parse a JSON object out of a model's text response.

    Tolerates ```` ```json ```` / ```` ``` ```` code fences and leading/trailing
    prose. Raises json.JSONDecodeError if no valid JSON can be recovered.
    """
    text = raw.strip()

    fence = _FENCE.match(text)
    if fence:
        text = fence.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fallback: slice from first "{" to last "}" and retry.
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            return json.loads(text[start : end + 1])
        raise
