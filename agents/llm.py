"""Provider-agnostic LLM access.

One entry point, `complete()`, returns plain text from either the Anthropic API
or a local Ollama model (via its OpenAI-compatible endpoint). Provider and model
are chosen by environment variables so no agent code changes when switching.

Env:
    MODEL_PROVIDER   "anthropic" | "ollama"   (default "ollama")
    MODEL            model name; falls back to CLAUDE_MODEL for back-compat
    OLLAMA_BASE_URL  default "http://localhost:11434/v1"
    ANTHROPIC_API_KEY   (anthropic provider only)
"""

import asyncio
import json
import os
import urllib.error
import urllib.request

from logger import error, log, warn

_clients = {}


def resolve_provider():
    return os.environ.get("MODEL_PROVIDER", "ollama").lower()


def resolve_model():
    model = os.environ.get("MODEL") or os.environ.get("CLAUDE_MODEL")
    if not model:
        raise RuntimeError("no model configured: set MODEL (or CLAUDE_MODEL)")
    return model


def with_system(messages, system):
    """Prepend a system message (OpenAI-style) when one is given."""
    if not system:
        return messages
    return [{"role": "system", "content": system}, *messages]


def anthropic_text(content_blocks):
    """Join the text blocks of an Anthropic response, dropping tool-use blocks."""
    return "\n".join(b.text for b in content_blocks if b.type == "text")


_CTX_BUCKETS = (2048, 4096, 8192, 16384, 32768, 65536, 131072)


def _estimate_tokens(messages):
    """Rough upper-ish token count for the prompt. ~3 chars/token: fetched docs
    are markdown/code/URLs, which tokenize denser than the ~4 chars/token of
    plain prose, so undercounting here would size the window too small. The
    grow-on-overflow retry in ollama_chat is the backstop when it still misses."""
    return sum(len(m.get("content") or "") for m in messages) // 3


def _ollama_num_ctx(messages, max_tokens):
    """Context window to request from Ollama, sized to the actual content.

    A fixed huge window is a CPU tax: Ollama allocates (and, on a size change,
    reloads the model with) the whole KV cache, and on CPU that alone can take
    minutes before the first token. So size to what this call needs — prompt +
    generation + margin — rounded up to a bucket for cache reuse across calls.
    The whole fetched document still fits; we just don't allocate 32k for a 3k
    prompt. Set OLLAMA_NUM_CTX to pin a fixed window instead."""
    fixed = os.environ.get("OLLAMA_NUM_CTX")
    if fixed:
        return int(fixed)
    need = _estimate_tokens(messages) + max_tokens + 512
    return next((b for b in _CTX_BUCKETS if need <= b), need)


def _ollama_timeout():
    """HTTP timeout (seconds) for one /api/chat call. Generous by default: on a
    CPU-only box this 9b model generates at only ~2 tokens/sec, so a call that
    produces several hundred tokens legitimately runs for many minutes. Too low
    a timeout kills a working call. Override with OLLAMA_TIMEOUT."""
    return float(os.environ.get("OLLAMA_TIMEOUT", "1800"))


def _think_param(reasoning_effort=None):
    """Native /api/chat `think` value from an effort string.

    "none" -> False (thinking off); "low"/"medium"/"high" -> that level (ornith
    honors levels); "" -> None (omit; model default). Per-call value overrides
    OLLAMA_REASONING_EFFORT.
    """
    effort = (
        reasoning_effort
        if reasoning_effort is not None
        else os.environ.get("OLLAMA_REASONING_EFFORT", "none")
    )
    if not effort:
        return None
    return False if effort == "none" else effort


def ollama_reply_text(message):
    """Text from a native /api/chat message dict.

    On reasoning models a tight budget can be spent entirely on hidden thinking,
    leaving `content` blank (finish on length). Surface the thinking rather than
    returning "" and ending the turn on a silent blank.
    """
    content = (message.get("content") or "").strip()
    if content:
        return content
    for key in ("thinking", "reasoning", "reasoning_content"):
        t = message.get(key)
        if t and t.strip():
            return t.strip()
    return ""


def _ollama_native_base():
    """Ollama's native API base (strip the OpenAI-compat /v1 suffix)."""
    base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1").rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return base.rstrip("/")


async def keep_warm():
    """Pin the Ollama model in memory for OLLAMA_KEEP_ALIVE so repeated runs skip
    the cold reload.

    keep_alive is honored only by Ollama's native /api/generate, not the
    OpenAI-compat endpoint we use for completions — but both share the same loaded
    model instance, so this native ping sets the TTL for the model the compat
    calls then reuse. No-op unless provider is ollama and keep-alive is set.
    """
    if resolve_provider() != "ollama":
        return
    ka = os.environ.get("OLLAMA_KEEP_ALIVE", "30m")
    if not ka:
        return

    def _ping():
        body = json.dumps({"model": resolve_model(), "keep_alive": ka}).encode()
        req = urllib.request.Request(
            _ollama_native_base() + "/api/generate",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=180) as r:
            r.read()

    try:
        await asyncio.to_thread(_ping)
        log("llm", {"keep_warm": resolve_model(), "keep_alive": ka})
    except Exception as e:  # keep-alive is best-effort; never block the run
        error("llm", {"keep_warm_failed": str(e)[:150]})


def _anthropic_client():
    if "anthropic" not in _clients:
        from anthropic import AsyncAnthropic

        _clients["anthropic"] = AsyncAnthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY")
        )
    return _clients["anthropic"]


async def ollama_chat(*, model, messages, max_tokens, reasoning_effort=None):
    """One completion via Ollama's NATIVE /api/chat.

    Native — not the OpenAI-compat /v1 endpoint — because only the native API
    honors options.num_ctx. Over /v1, num_ctx is silently ignored and the model
    stays at its default 4096-token window, which truncates fetched documents.
    """
    think = _think_param(reasoning_effort)
    num_ctx = _ollama_num_ctx(messages, max_tokens)
    pinned = bool(os.environ.get("OLLAMA_NUM_CTX"))

    def _post(ctx):
        options = {"num_ctx": ctx, "num_predict": max_tokens}
        body = {"model": model, "messages": messages, "stream": False, "options": options}
        if think is not None:
            body["think"] = think
        req = urllib.request.Request(
            _ollama_native_base() + "/api/chat",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=_ollama_timeout()) as r:
                return json.loads(r.read()), None
        except urllib.error.HTTPError as e:
            return None, (e.code, e.read().decode("utf-8", "replace")[:200])

    while True:
        data, err = await asyncio.to_thread(_post, num_ctx)
        if err is None:
            return ollama_reply_text(data.get("message", {}))
        code, detail = err
        # Estimate too small: the real prompt overflowed the window. Grow to the
        # next bucket and retry so the whole document still fits — unless the
        # window was explicitly pinned via OLLAMA_NUM_CTX.
        bigger = next((b for b in _CTX_BUCKETS if b > num_ctx), None)
        if code == 400 and "context" in detail.lower() and bigger and not pinned:
            warn("llm", {"grow_num_ctx": {"from": num_ctx, "to": bigger}})
            num_ctx = bigger
            continue
        raise RuntimeError(f"ollama /api/chat {code}: {detail}")


async def complete(*, messages, max_tokens, system=None, tools=None, reasoning_effort=None):
    """Run one completion and return its text, dispatching on MODEL_PROVIDER.

    reasoning_effort applies to Ollama thinking models (per-call override of
    OLLAMA_REASONING_EFFORT); ignored by the anthropic provider.
    """
    provider = resolve_provider()
    model = resolve_model()

    if provider == "anthropic":
        client = _anthropic_client()
        kwargs = {"model": model, "max_tokens": max_tokens, "messages": messages}
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools
        response = await client.messages.create(**kwargs)
        return anthropic_text(response.content)

    if provider == "ollama":
        if tools:
            # ponytail: server-side tools (e.g. web_search) have no Ollama
            # equivalent yet — see IDEAS.md step 3. Ignore for now; the agent
            # answers from parametric knowledge until a real search tool lands.
            warn("llm", {"warning": "tools ignored under ollama provider", "model": model})
        return await ollama_chat(
            model=model,
            messages=with_system(messages, system),
            max_tokens=max_tokens,
            reasoning_effort=reasoning_effort,
        )

    raise ValueError(f"unknown MODEL_PROVIDER: {provider!r} (use 'anthropic' or 'ollama')")
