# Ideas

Running list. Newest at top. Mark done with `[x]` and a short note; leave open as `[ ]`.

- [ ] **Support local models via Ollama** — run the pipeline against a local model instead of the Anthropic API. Ollama exposes an OpenAI-compatible endpoint at `http://localhost:11434/v1`, so this means a configurable base URL + model name (env-driven) plus a client abstraction.

  **Model decision:** `ornith-1.5:9b` (9B dense, qwen35 core, 262k ctx, tools + thinking). Ornith is purpose-tuned for agentic + coding tasks, which matches this pipeline; provenance is public (Ornith research group, on HuggingFace + Ollama library). Baseline/control: `qwen3.5:latest` (neutral base). Quality escalation: `ornith-1.5:35B` (MoE) if 9B summarizer JSON is unreliable.

  **Port plan (no code yet):**
  1. **Client abstraction** — swap `AsyncAnthropic` for a provider that points at Ollama's OpenAI-compat endpoint. Options: `openai` AsyncOpenAI with `base_url` + `api_key="ollama"`, or the `ollama` Python lib. Env: `MODEL_PROVIDER` (`anthropic`|`ollama`), `OLLAMA_BASE_URL`, model name (rename `CLAUDE_MODEL` → `MODEL` or keep both).
  2. **Message/response shape** — Ollama's OpenAI-compat returns `choices[].message.content` (a string), not Anthropic's `content` blocks with `type`. The researcher/summarizer/evaluator all filter `block.type == "text"` — that logic changes per provider. Abstract "get text from response" behind the client wrapper.
  3. **web_search** — no Ollama equivalent for `web_search_20250305`. Researcher needs a real search tool (SearXNG / DuckDuckGo / Brave API) wired as a tool call, or a non-search notes path. **Biggest build item.**
  4. **thinking output** — ornith/qwen3.5 emit reasoning. Via OpenAI-compat it's usually separate, but if it leaks into content, `parse_json` fence-strip + brace-slice (see BUGS.md, done) already recovers. Can hard-disable with `think: false`.
  5. **System prompt** — ornith ships a baked-in agentic prompt. For the summarizer's strict "ONLY JSON" output, override with our own `system` message.
  6. **Verify** — extend the offline test suite around the client abstraction (mock responses per provider); live smoke test against `ornith-1.5:9b` once wired.

## Notes

- Faithful Python port of the "multi-agents 101" tutorial lives here; original Node version in `../site/`.
