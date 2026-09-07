import os
from types import SimpleNamespace

import pytest

import agents.llm as llm
from agents.llm import (
    _ollama_native_base,
    _ollama_num_ctx,
    _think_param,
    anthropic_text,
    keep_warm,
    ollama_reply_text,
    resolve_model,
    resolve_provider,
    with_system,
)


def test_resolve_provider_default(monkeypatch):
    monkeypatch.delenv("MODEL_PROVIDER", raising=False)
    assert resolve_provider() == "ollama"


def test_resolve_provider_env(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "Anthropic")
    assert resolve_provider() == "anthropic"


def test_resolve_model_prefers_MODEL(monkeypatch):
    monkeypatch.setenv("MODEL", "ornith-1.5:9b")
    monkeypatch.setenv("CLAUDE_MODEL", "claude-sonnet-5")
    assert resolve_model() == "ornith-1.5:9b"


def test_resolve_model_falls_back_to_claude_model(monkeypatch):
    monkeypatch.delenv("MODEL", raising=False)
    monkeypatch.setenv("CLAUDE_MODEL", "claude-sonnet-5")
    assert resolve_model() == "claude-sonnet-5"


def test_resolve_model_missing_raises(monkeypatch):
    monkeypatch.delenv("MODEL", raising=False)
    monkeypatch.delenv("CLAUDE_MODEL", raising=False)
    with pytest.raises(RuntimeError):
        resolve_model()


def test_with_system_prepends():
    msgs = [{"role": "user", "content": "hi"}]
    out = with_system(msgs, "be brief")
    assert out[0] == {"role": "system", "content": "be brief"}
    assert out[1:] == msgs


def test_with_system_noop_when_none():
    msgs = [{"role": "user", "content": "hi"}]
    assert with_system(msgs, None) is msgs


def test_anthropic_text_joins_text_blocks_only():
    blocks = [
        SimpleNamespace(type="text", text="one"),
        SimpleNamespace(type="tool_use", text="ignored"),
        SimpleNamespace(type="text", text="two"),
    ]
    assert anthropic_text(blocks) == "one\ntwo"


def test_reply_text_returns_content():
    assert ollama_reply_text({"content": "hello"}) == "hello"


def test_reply_text_falls_back_to_thinking_when_blank():
    # reasoning model spent the budget on hidden thinking; surface it, not ""
    assert ollama_reply_text({"content": "", "thinking": "step 1..."}) == "step 1..."


def test_reply_text_empty_when_nothing():
    assert ollama_reply_text({"content": ""}) == ""


def test_think_param_defaults_to_false(monkeypatch):
    monkeypatch.delenv("OLLAMA_REASONING_EFFORT", raising=False)
    assert _think_param() is False  # env default "none" -> thinking off


def test_think_param_blank_omits(monkeypatch):
    monkeypatch.setenv("OLLAMA_REASONING_EFFORT", "")
    assert _think_param() is None  # omit -> model default


def test_think_param_keeps_level(monkeypatch):
    monkeypatch.setenv("OLLAMA_REASONING_EFFORT", "low")
    assert _think_param() == "low"


def test_think_param_override_beats_env(monkeypatch):
    monkeypatch.setenv("OLLAMA_REASONING_EFFORT", "none")
    assert _think_param("medium") == "medium"


def test_think_param_override_none_turns_off(monkeypatch):
    monkeypatch.setenv("OLLAMA_REASONING_EFFORT", "high")
    assert _think_param("none") is False


def test_num_ctx_sizes_small_prompt_to_bucket(monkeypatch):
    monkeypatch.delenv("OLLAMA_NUM_CTX", raising=False)
    msgs = [{"role": "user", "content": "hi"}]
    assert _ollama_num_ctx(msgs, max_tokens=50) == 2048  # tiny -> smallest bucket


def test_num_ctx_grows_with_content(monkeypatch):
    monkeypatch.delenv("OLLAMA_NUM_CTX", raising=False)
    msgs = [{"role": "user", "content": "x" * 40000}]  # ~10k tokens
    # 10000 + 1200 + 512 = 11712 -> next bucket up
    assert _ollama_num_ctx(msgs, max_tokens=1200) == 16384


def test_num_ctx_env_pins_fixed(monkeypatch):
    monkeypatch.setenv("OLLAMA_NUM_CTX", "4096")
    msgs = [{"role": "user", "content": "x" * 40000}]
    assert _ollama_num_ctx(msgs, max_tokens=1200) == 4096  # explicit pin wins


def test_native_base_strips_v1(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    assert _ollama_native_base() == "http://localhost:11434"


def test_native_base_without_v1(monkeypatch):
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://host:1234")
    assert _ollama_native_base() == "http://host:1234"


def test_keep_warm_skips_for_anthropic(monkeypatch):
    import asyncio

    monkeypatch.setenv("MODEL_PROVIDER", "anthropic")

    def boom(*a, **k):
        raise AssertionError("should not hit the network for anthropic")

    monkeypatch.setattr(llm.urllib.request, "urlopen", boom)
    asyncio.run(keep_warm())  # no exception = it returned early


def test_keep_warm_skips_when_disabled(monkeypatch):
    import asyncio

    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_KEEP_ALIVE", "")

    def boom(*a, **k):
        raise AssertionError("should not ping when keep-alive is blank")

    monkeypatch.setattr(llm.urllib.request, "urlopen", boom)
    asyncio.run(keep_warm())
