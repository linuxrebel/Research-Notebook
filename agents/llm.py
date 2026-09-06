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
import urllib.request

from logger import log

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


def openai_text(choices):
    """Extract assistant text from an OpenAI/Ollama chat completion."""
    return choices[0].message.content or ""


def ollama_extra(reasoning_effort=None):
    """Extra request kwargs for Ollama.

    Thinking models (ornith, qwen3.5) spend the token budget on reasoning and
    can return empty `content` (finish_reason=length). `reasoning_effort=none`
    turns thinking off so the budget goes to the answer; "low"/"medium"/"high"
    enable increasing amounts of reasoning (raise max_tokens to leave room for
    the answer). A per-call value overrides OLLAMA_REASONING_EFFORT; "" allows
    the model's own default.
    """
    effort = (
        reasoning_effort
        if reasoning_effort is not None
        else os.environ.get("OLLAMA_REASONING_EFFORT", "none")
    )
    return {"reasoning_effort": effort} if effort else {}


def _ollama_native_base():
    """Ollama's native API base (strip the OpenAI-compat /v1 suffix)."""
    base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1").rstrip("/")
    if base.endswith("/v1"):
        base = base[:-3]
    return base.rstrip("/")


def ollama_running(timeout=3):
    """True if the Ollama server answers on OLLAMA_BASE_URL. Used for a friendly
    preflight before a run; the actual completion still surfaces real errors."""
    try:
        with urllib.request.urlopen(_ollama_native_base() + "/api/tags", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


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
        log("llm", {"keep_warm_failed": str(e)[:150]})


def _anthropic_client():
    if "anthropic" not in _clients:
        from anthropic import AsyncAnthropic

        _clients["anthropic"] = AsyncAnthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY")
        )
    return _clients["anthropic"]


def _ollama_client():
    if "ollama" not in _clients:
        from openai import AsyncOpenAI

        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        _clients["ollama"] = AsyncOpenAI(base_url=base_url, api_key="ollama")
    return _clients["ollama"]


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
            log("llm", {"warning": "tools ignored under ollama provider", "model": model})
        client = _ollama_client()
        response = await client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=with_system(messages, system),
            **ollama_extra(reasoning_effort),
        )
        return openai_text(response.choices)

    raise ValueError(f"unknown MODEL_PROVIDER: {provider!r} (use 'anthropic' or 'ollama')")
