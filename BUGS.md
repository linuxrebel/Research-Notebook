# Bugs

Running list. Newest at top. Mark done with `[x]` and a short note; leave open as `[ ]`.

- [ ] **`Notebook` can't read `/opt/Notebook/.env` (PermissionError)** — ATTACK NEXT SESSION. Running `Notebook` as the unprivileged user dies at `load_dotenv()`:
  `PermissionError: [Errno 13] Permission denied: '/opt/Notebook/.env'`.
  `install.sh` generates `.env` as root, so the running user can't read it. Not yet reproduced/diagnosed — candidate causes to check, in order:
  (1) **DAC perms** — file created root-owned with restrictive mode; `ls -l /opt/Notebook/.env` + check the umask at install. Fix: `chmod 0644` (local `.env` holds no secret when provider=ollama) or `chown "$REAL_USER"`.
  (2) **SELinux** (Fedora 44, likely enforcing) — root-created file in `/opt` may carry a context the user process can't read; check `ls -Z` and `ausearch -m avc`. If so, DAC chmod won't help; needs `restorecon`/context fix or relocating `.env`.
  Decide the real fix after confirming which. Other install-written files load fine (cli.py ran), so it's `.env`-specific, not a dir-traversal problem. Seen on Fedora 44, python3.14 venv.

- [x] **Summarizer over-produces keyPoints on local models** — `ornith-1.5:9b` ignores "exactly 3 key points" and returns ~one per input bullet (5, 15, …). The evaluator checks for 3, so it returned REVISE every time and the coordinator looped to MAX_ITERATIONS (slow / timeout). Fixed deterministically: `clamp_key_points()` trims to 3 after parse (prompt tightening alone didn't work). Covered by `tests/test_summarizer.py`.

- [x] **Harden `json.loads` in summarizer** — done. Extracted `parse_json` into `agents/json_utils.py` (strips ```` ```json ````/```` ``` ```` fences, falls back to first-`{`…last-`}` slice). `summarize` now retries the model once on `JSONDecodeError`, then raises on a second failure (aborts to CLI error / HTTP 500). Covered by `tests/test_json_utils.py` (7 cases, offline, no key). Schema validation deliberately out of scope for now (valid-JSON only).
