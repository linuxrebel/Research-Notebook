import os
from types import SimpleNamespace

import pytest

import agents.llm as llm
from agents.llm import (
    _ollama_native_base,
    anthropic_text,
    keep_warm,
    ollama_extra,
    openai_text,
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


def test_openai_text_extracts_content():
    choices = [SimpleNamespace(message=SimpleNamespace(content="hello"))]
    assert openai_text(choices) == "hello"


def test_openai_text_none_becomes_empty():
    choices = [SimpleNamespace(message=SimpleNamespace(content=None))]
    assert openai_text(choices) == ""


def test_ollama_extra_defaults_to_none(monkeypatch):
    monkeypatch.delenv("OLLAMA_REASONING_EFFORT", raising=False)
    assert ollama_extra() == {"reasoning_effort": "none"}


def test_ollama_extra_blank_omits(monkeypatch):
    monkeypatch.setenv("OLLAMA_REASONING_EFFORT", "")
    assert ollama_extra() == {}


def test_ollama_extra_custom(monkeypatch):
    monkeypatch.setenv("OLLAMA_REASONING_EFFORT", "low")
    assert ollama_extra() == {"reasoning_effort": "low"}


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
