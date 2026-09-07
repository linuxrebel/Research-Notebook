# Bugs

Running list. Newest at top. Mark done with `[x]` and a short note; leave open as `[ ]`.

- [x] **`Notebook` can't read `/opt/Notebook/.env` (PermissionError)** — fixed. Root's umask (077) created `.env` mode `600` (owner-only), so the unprivileged user hit `PermissionError` at `load_dotenv()`. Confirmed DAC, not SELinux (`chmod 755` by hand cleared it). Fix in `install.sh`: `chmod 0644 "$DEST/.env"` after write/restore (no secret — provider=ollama). Also fixed the sibling cause: `rsync -a` preserved source ownership (james) on copied files while root-generated files (`.venv/`, `.env`) were root — added `--no-o --no-g` so the whole install lands root-owned.

- [x] **Summarizer over-produces keyPoints on local models** — `ornith-1.5:9b` ignores "exactly 3 key points" and returns ~one per input bullet (5, 15, …). The evaluator checks for 3, so it returned REVISE every time and the coordinator looped to MAX_ITERATIONS (slow / timeout). Fixed deterministically: `clamp_key_points()` trims to 3 after parse (prompt tightening alone didn't work). Covered by `tests/test_summarizer.py`.

- [x] **Harden `json.loads` in summarizer** — done. Extracted `parse_json` into `agents/json_utils.py` (strips ```` ```json ````/```` ``` ```` fences, falls back to first-`{`…last-`}` slice). `summarize` now retries the model once on `JSONDecodeError`, then raises on a second failure (aborts to CLI error / HTTP 500). Covered by `tests/test_json_utils.py` (7 cases, offline, no key). Schema validation deliberately out of scope for now (valid-JSON only).
