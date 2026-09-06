# Notebook — Implementation Plan & Verification Checklist

Product: an interactive CLI research tool. Interactivity is the point — it
forces a human in the loop to limit guessing. The API/server path
(`server.py`) stays as the non-interactive hook for other applications.

Status legend: `[ ]` todo · `[x]` done & verified.

---

## Locked decisions

- **Command name:** `Notebook`.
- **Mode:** interactive only. No positional-arg bypass in the CLI. Machines use the API (`server.py`) instead.
- **Install location:** `/opt/Notebook`, CLI symlinked to `/usr/local/bin/Notebook`.
- **Python:** dedicated venv at `/opt/Notebook/.venv`, built fresh at install.
- **`.env`:** generated from scratch at install time (interactive prompts).
- **Edit mechanism:** readline pre-filled input line (in-terminal, no external editor).
- **Vault name:** dedicated `Notebook` vault holds all research; user may instead nest under an existing vault.
- **Vault home:** discovered from the user's Obsidian registry (not hardcoded).
- **Collision:** on an existing output dir, user chooses reuse / new name / abort.
- **Obsidian required:** install aborts if Obsidian not found, telling the user to install and re-run.
- **Privilege:** install runs as root (root-owned `/opt/Notebook`); the tool is executable by any unprivileged user afterward. No user-local install mode.
- **Ollama checks:** at **install** — verify Ollama is installed and the chosen model is pulled (else give download link / `ollama pull` command and abort). At **run** — verify Ollama is reachable/running (else tell user to start it and re-run, then exit).
- **Update:** `install.sh` reinstalls over an existing install. An existing `/opt/Notebook/.env` is **preserved** and the config prompts are skipped (config only changes on a fresh install or manual edit).
- **Branch:** `development` (local-only repo, no remote). Releases to `main` only.

---

## 1. Interactive CLI (`cli.py`)

- [ ] Running `Notebook` (no args) starts the interactive flow.
- [ ] **Preflight** — before the flow (or before starting the pipeline), verify Ollama is reachable/running. If not, print "Start Ollama, then re-run Notebook." and exit non-zero.
- [ ] Step 1 — asks what to investigate; empty input aborts with a clear message.
- [ ] Step 2 — shows the topic on an **editable** readline line to fix typos; empty after edit aborts.
- [ ] Step 3 — suggests a directory name (slug of topic) on an editable line; user accepts or retypes.
- [ ] Step 4 — collision: if `$HOME/research/<name>/` exists, prompt **[r]euse / [n]ew name / [a]bort**; new-name loops back to the name step.
- [ ] Step 5 — prints a summary (topic + output dir) and asks `Start? [y/N]`; anything but yes aborts.
- [ ] On confirm, runs the pipeline and writes to the chosen dir.
- **Verify:** drive each path with piped input — accept, edit, empty-abort, collision reuse/new/abort, final decline. Confirm exit codes and that no pipeline runs on abort.

## 2. Pipeline threading

- [ ] `run_pipeline(topic, dir_name=None)` passes the name through to output.
- [ ] `write_outputs(result, base_dir=None, name=None)` — `name` sets the output subdir; defaults to slug (backward-compatible).
- [ ] `hook_obsidian(result, out_dir, name=None)` — vault note filename matches the chosen dir name; defaults to slug.
- **Verify:** existing 58 tests still pass; add/adjust tests so `name` overrides the slug in both the output dir and the vault link, and `name=None` keeps slug behavior.

## 3. Launcher (`Notebook`)

- [ ] Resolves its own real path (works through the `/usr/local/bin` symlink).
- [ ] Uses `/opt/Notebook/.venv/bin/python` if present, else system `python3` (in-repo dev).
- [ ] `cd`s into its dir and execs `cli.py "$@"`.
- **Verify:** run via symlink from an unrelated cwd; confirm it launches the CLI with the venv python after install.

## 4. Installer (`install.sh`)

- [ ] Refuses unless root; prints `sudo ./install.sh` and exits non-zero otherwise.
- [ ] Resolves the **real** (non-root) user via `$SUDO_USER` and their home; aborts if unresolved.
- [ ] Detects Obsidian (native binary / flatpak / snap / config presence). Absent → message to install + re-run, exit non-zero.
- [ ] Verifies **Ollama installed** (`command -v ollama`). Absent → point to `https://ollama.com/download`, exit non-zero.
- [ ] Verifies the **chosen model is pulled** (`ollama list`). Absent → print `ollama pull <model>`, exit non-zero. (Runs after the model is chosen/known — on update, uses the model from the preserved `.env`.)
- [ ] **Update path** — if `/opt/Notebook/.env` already exists, preserve it and skip all config prompts (model / vault / URL); reinstall only refreshes code + venv. Fresh install (no `.env`) runs the prompts.
- [ ] Discovers vault home = common parent of existing vaults from the user's `obsidian.json`; falls back to `~/Obsidian_Vaults` if none.
- [ ] Vault prompt: default dedicated `Notebook` vault at `<home>/Notebook`, or pick an existing vault to nest under.
- [ ] Prompts model (default `ornith-1.5:9b`) and Ollama base URL (default localhost).
- [ ] Copies project to `/opt/Notebook`, excluding `.git`, `.venv`, `__pycache__`, `.pytest_cache`, `.env`.
- [ ] Builds venv + installs `requirements.txt`.
- [ ] Generates `/opt/Notebook/.env` with chosen values (`RESEARCH_DIR` = real user's `~/research`, `OBSIDIAN_VAULT` = chosen path).
- [ ] Symlinks `/opt/Notebook/Notebook` → `/usr/local/bin/Notebook`; makes launcher + uninstall executable.
- **Verify (dry, non-destructive first):** shellcheck; run in a throwaway root context or with `DEST`/`BIN` overridden to temp paths; confirm root-refusal, Obsidian-absent path, vault discovery output, generated `.env` contents, venv builds, symlink resolves. Do **not** run the real `/opt` install until the user approves.

## 5. Uninstaller (`uninstall.sh`, installed into `/opt/Notebook`)

- [ ] Refuses unless root.
- [ ] Removes `/usr/local/bin/Notebook` symlink and `/opt/Notebook`.
- [ ] Leaves `$HOME/research/` and all Obsidian vaults untouched (user data — never deleted).
- **Verify:** after a temp-path install, run it; confirm only the install artifacts are gone and user data remains.

## 6. API / server untouched

- [ ] `server.py` behavior unchanged; remains the machine hook.
- **Verify:** server tests / import still pass; no edits in its file.

---

## Cross-cutting safety checks

- [ ] Test runs never touch the real Obsidian config (conftest isolation holds).
- [ ] No secrets committed: `.env` stays gitignored; installer-generated `.env` lives only under `/opt/Notebook`.
- [ ] Root-run install writes user-owned paths correctly (vault + research dir owned by the real user, not root).
- [ ] Full suite green before and after each change.
- [ ] Every changed line traces to an item above (no scope creep).

## Resolved (was: open questions)

- **Ownership / privilege:** install is root-owned (`/opt/Notebook`); the tool runs as any unprivileged user. Runtime (running as the user) creates `~/research` and the vault, so they end up user-owned — install does not pre-create or `chown` them.
- **Ollama verification:** install-time checks Ollama is installed + the model is pulled (download link / `ollama pull` on failure). Runtime checks Ollama is running (start-and-re-run message on failure).
- **Update:** reinstall preserves an existing `.env` and skips config prompts; refreshes code + venv only.
