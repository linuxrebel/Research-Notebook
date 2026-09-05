# Bugs

Running list. Newest at top. Mark done with `[x]` and a short note; leave open as `[ ]`.

- [x] **Harden `json.loads` in summarizer** — done. Extracted `parse_json` into `agents/json_utils.py` (strips ```` ```json ````/```` ``` ```` fences, falls back to first-`{`…last-`}` slice). `summarize` now retries the model once on `JSONDecodeError`, then raises on a second failure (aborts to CLI error / HTTP 500). Covered by `tests/test_json_utils.py` (7 cases, offline, no key). Schema validation deliberately out of scope for now (valid-JSON only).
