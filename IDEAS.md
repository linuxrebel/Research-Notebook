# Ideas

Running list. Newest at top. Mark done with `[x]` and a short note; leave open as `[ ]`.

- [ ] **Support local models via Ollama** — run the pipeline against a local model instead of the Anthropic API. Ollama exposes an OpenAI-compatible endpoint at `http://localhost:11434/v1`, so this means a configurable base URL + model name (env-driven) plus a client abstraction.

  **Model decision:** `ornith-1.5:9b` (9B dense, qwen35 core, 262k ctx, tools + thinking). Ornith is purpose-tuned for agentic + coding tasks, which matches this pipeline; provenance is public (Ornith research group, on HuggingFace + Ollama library). Baseline/control: `qwen3.5:latest` (neutral base). Quality escalation: `ornith-1.5:35B` (MoE) if 9B summarizer JSON is unreliable.

  **Port plan:**
  1. [x] **Client abstraction** — `agents/llm.py` `complete()` dispatches on `MODEL_PROVIDER` (`anthropic`|`ollama`). Ollama uses `openai.AsyncOpenAI` at `OLLAMA_BASE_URL`. Env: `MODEL` (falls back to `CLAUDE_MODEL`). Clients are lazy singletons (no key needed at import).
  2. [x] **Message/response shape** — `anthropic_text()` (joins `type=="text"` blocks) vs `openai_text()` (`choices[0].message.content`), both behind `complete()`.
  3. [x] **web_search** — done via DuckDuckGo (`ddgs`), no key. `agents/search.py` does the search; researcher feeds results to `complete()` and compiles sourced bullet notes. Unified path for both providers (dropped the Anthropic server-side web_search). Live: researcher now returns real 2026 findings with URLs.
  4. [x] **thinking output** — thinking models spend the token budget on reasoning and return empty `content` (finish_reason=length). `think:false` via extra_body is IGNORED by the compat endpoint; `reasoning_effort="none"` works. Wired as `ollama_extra()` (env `OLLAMA_REASONING_EFFORT`, default `none`). `parse_json` still backstops any leak.
  5. [x] **System prompt** — summarizer and evaluator pass their own `system` (strict JSON / one-word verdict), overriding ornith's baked-in prompt.
  6. [x] **Verify** — offline suite covers pure helpers (`tests/test_llm.py`) and mocked per-provider `complete()` (`tests/test_llm_complete.py`: text extraction, arg passing, system prepend, reasoning_effort, tools-ignored, unknown-provider). Live smoke on `ornith-1.5:9b` passes end-to-end. 41 tests total.

- [x] **Auto-hook output into Obsidian** — done. `summary.md` now carries YAML frontmatter (topic, date, verdict, tags). When `OBSIDIAN_VAULT` is set, each run symlinks it into `<vault>/Research/<slug>.md` (`hook_obsidian` in `agents/output.py`) and drops an `unhook.sh` into the result dir, hardcoded to that link and safe (removes only if it's a symlink). No-clobber: a real file at the target is left untouched. Env: `OBSIDIAN_VAULT`. Not yet done: wiki-links between related topics.

- [ ] **Query refinement before search** — the topic string is used as the DDG query verbatim (`research(topic)` → `web_search(topic)`). A step that rewrites the topic into better search terms (or multiple queries) could improve note quality. New pre-search step.

## Notes

- Faithful Python port of the "multi-agents 101" tutorial lives here; original Node version in `../site/`.
