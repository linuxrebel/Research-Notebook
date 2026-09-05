# Ideas

Running list. Newest at top. Mark done with `[x]` and a short note; leave open as `[ ]`.

- [ ] **Support local models via Ollama** — run the pipeline against a local model instead of the Anthropic API. Ollama exposes an OpenAI-compatible endpoint at `http://localhost:11434/v1`, so this means a configurable base URL + model name (env-driven) plus a client abstraction.

  **Model decision:** `ornith-1.5:9b` (9B dense, qwen35 core, 262k ctx, tools + thinking). Ornith is purpose-tuned for agentic + coding tasks, which matches this pipeline; provenance is public (Ornith research group, on HuggingFace + Ollama library). Baseline/control: `qwen3.5:latest` (neutral base). Quality escalation: `ornith-1.5:35B` (MoE) if 9B summarizer JSON is unreliable.

  **Port plan:**
  1. [x] **Client abstraction** — `agents/llm.py` `complete()` dispatches on `MODEL_PROVIDER` (`anthropic`|`ollama`). Ollama uses `openai.AsyncOpenAI` at `OLLAMA_BASE_URL`. Env: `MODEL` (falls back to `CLAUDE_MODEL`). Clients are lazy singletons (no key needed at import).
  2. [x] **Message/response shape** — `anthropic_text()` (joins `type=="text"` blocks) vs `openai_text()` (`choices[0].message.content`), both behind `complete()`.
  3. [ ] **web_search** — no Ollama equivalent for `web_search_20250305`. Researcher needs a real search tool (SearXNG / DuckDuckGo / Brave API) wired as a tool call, or a non-search notes path. **Biggest build item — NEXT.** Confirmed live: without it, ornith refuses ("no web access") and the pipeline summarizes the refusal.
  4. [x] **thinking output** — thinking models spend the token budget on reasoning and return empty `content` (finish_reason=length). `think:false` via extra_body is IGNORED by the compat endpoint; `reasoning_effort="none"` works. Wired as `ollama_extra()` (env `OLLAMA_REASONING_EFFORT`, default `none`). `parse_json` still backstops any leak.
  5. [x] **System prompt** — summarizer and evaluator pass their own `system` (strict JSON / one-word verdict), overriding ornith's baked-in prompt.
  6. [~] **Verify** — offline suite covers pure helpers (`tests/test_llm.py`); live smoke on `ornith-1.5:9b` passes end-to-end (valid JSON, coordinator loop OK). Per-provider mocked `complete()` tests still TODO.

## Notes

- Faithful Python port of the "multi-agents 101" tutorial lives here; original Node version in `../site/`.
