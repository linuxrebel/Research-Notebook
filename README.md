# Notebook

A local, multi-agent research tool. Give it a topic; a chain of agents reads
real sources, gathers facts into a cross-linked set of notes, and organizes them
into a brief. It is a **fact-gathering** tool — it collects what the sources say
(e.g. pros *and* cons) and deliberately does not issue a verdict.

Runs entirely on a **local model via Ollama** — no API key, no data leaving the
machine.

## How it works

Agents coordinated with a retry loop:

1. **Researcher** — reads sources, one at a time, writing each source's facts to
   its own note as they are gathered:
   - If the topic names URLs, it **fetches and reads them** — GitHub repos via
     the API (metadata + README + file tree), YouTube videos as their transcript
     (via yt-dlp), any other URL as page text through an ordered backend chain:
     urllib first, then the local **obscura** headless browser for pages behind
     a JS / anti-bot wall (Cloudflare, "Client Challenge"). Escalation is by
     *shape* — a challenge stub returns HTTP 200, so a thin/blocked response
     triggers the next backend, not the status code.
   - The primary document's own follow-up questions drive a DuckDuckGo search,
     which is used **only to discover links**. Every discovered link is then
     fetched and read too — nothing is synthesized from search snippets.
2. **Summarizer** — organizes the gathered facts into a strict-JSON brief
   (title, key points, notes). When the topic asks for pros and cons it includes
   both; it reports the findings and leaves the conclusion to the reader.
3. **Evaluator** — gates the brief on grounding + coverage (is every point
   supported by the notes; are both sides present when asked), replying
   `APPROVED` or `REVISE`.
4. **Coordinator** — creates the notebook, runs research → summarize → evaluate,
   and on `REVISE` re-summarizes/re-evaluates up to `MAX_ITERATIONS` (5).

## Output — an interlinked notebook

Each run writes a small Obsidian-style note-set to `~/research/<name>/`, built
incrementally (each source note is written as its facts are gathered, so work
survives an interrupt):

| Path                | Contents                                                     |
|---------------------|--------------------------------------------------------------|
| `index.md`          | map of content — links every source note + the synthesis     |
| `sources/<slug>.md` | facts from one source (frontmatter: url, date, fetched_via)   |
| `summary.md`        | synthesis of the findings, links back to the sources         |
| `result.json`       | the full pipeline result                                     |

Notes cross-link each other with `[[wikilinks]]`, so dropping the folder into an
Obsidian vault lets Obsidian draw the graph/mind map on its own.

## Requirements

- Python 3
- [Ollama](https://ollama.com/download) with the configured model pulled
  (default `ornith-1.5:9b`):
  ```bash
  ollama pull ornith-1.5:9b
  ```
- Python deps: `pip install -r requirements.txt`
- Optional fetch backends (the tool still runs without them, on urllib):
  - [obscura](https://github.com/h4ckf0r0day/obscura/releases) — local headless
    browser (Rust/V8, no Chromium); reads JS / anti-bot-walled pages
  - [yt-dlp](https://github.com/yt-dlp/yt-dlp) — reads YouTube URLs as transcripts

## Usage

Interactive CLI (asks what to investigate, confirms, then runs):

```bash
python cli.py
```

HTTP API (the non-interactive hook for other applications):

```bash
python server.py
# POST /run {"topic": "..."}   GET /health
```

Installed via `install.sh`, the command is `Notebook` (see `NOTEBOOK_PLAN.md`).

## Configuration (`.env`)

| Variable                 | Purpose                                                       | Default                     |
|--------------------------|--------------------------------------------------------------|-----------------------------|
| `MODEL`                  | Ollama model name                                            | `ornith-1.5:9b`             |
| `OLLAMA_BASE_URL`        | Ollama endpoint (`/v1`; the native `/api/chat` base is derived from it) | `http://localhost:11434/v1` |
| `OLLAMA_REASONING_EFFORT`| `none` disables thinking; `low`/`medium`/`high` keep it       | `none`                      |
| `OLLAMA_NUM_CTX`         | pin a fixed context window; unset = sized to each call's content | unset                    |
| `OLLAMA_TIMEOUT`         | seconds per model call (CPU generation is slow)              | `1800`                      |
| `OLLAMA_KEEP_ALIVE`      | pin the model in memory between runs                         | `30m`                       |
| `PORT`                   | API server port                                             | `3000`                      |
| `RESEARCH_DIR`           | where the notebook is written                               | `~/research`                |
| `OBSIDIAN_VAULT`         | if set, link output into this vault (see below)             | unset                       |
| `FETCH_BACKEND`          | pin the web-page backend (`urllib` or `obscura`); unset = urllib then obscura | unset            |

`.env` is gitignored and generated by `install.sh`. The defaults run entirely on
Ollama with no credentials.

### A note on the local model

Generation on a CPU-only box is slow (~2–4 tok/s on `ornith-1.5:9b`); a full run
is minutes, not seconds — the tool trades speed for reading real sources and
gathering accurate facts. The Ollama path uses the **native `/api/chat`**
endpoint because only it honors `num_ctx` (the OpenAI-compat `/v1` path silently
clamps the window and truncates documents). `num_ctx` is sized to each call's
content by default so it never allocates more window than needed; set
`OLLAMA_NUM_CTX` to pin a fixed value.

## Obsidian integration

Set `OBSIDIAN_VAULT` to a vault path and each run symlinks the whole run folder
into `<vault>/Research/<name>`, so every note in it — index, sources, summary —
lands in the vault and its `[[wikilinks]]` resolve there. An `unhook.sh` is
dropped into the result dir to remove that link. The vault is auto-provisioned
(created with a minimal `.obsidian/` marker) and registered in Obsidian's
switcher on first use. A real path already at the target is never clobbered.

## Layout

```
agents/
  fetch.py        read sources (GitHub API / YouTube via yt-dlp / urllib->obscura)
  search.py       DuckDuckGo link discovery
  researcher.py   per-source fact gathering
  summarizer.py   gathered facts -> strict-JSON brief (no verdict)
  evaluator.py    grounding / coverage gate (APPROVED / REVISE)
  coordinator.py  pipeline + retry loop
  notebook.py     incremental interlinked note-set writer
  output.py       slug + Obsidian folder hook
  llm.py          local model access (native Ollama /api/chat)
  json_utils.py   robust JSON parsing
cli.py            interactive entry point
server.py         HTTP API entry point
logger.py         run logging
tests/            offline test suite (mocked; no network)
```

## Development

```bash
python -m pytest -q
```

Tests are fully offline (mocked providers, isolated Obsidian config) and safe to
run repeatedly.

Trackers: [`BUGS.md`](BUGS.md), [`IDEAS.md`](IDEAS.md). The packaged
installer/CLI design is in [`NOTEBOOK_PLAN.md`](NOTEBOOK_PLAN.md).
