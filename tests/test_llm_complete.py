"""Mocked tests for complete() — no network, no real clients.

The anthropic path patches the lazy client factory with a fake. The ollama path
goes through the native /api/chat endpoint (urllib), so it patches urlopen with
a fake that records the posted body and returns a canned native response.
"""

import asyncio
import json
from types import SimpleNamespace

import pytest

import agents.llm as llm


class _FakeResp:
    def __init__(self, payload):
        self._b = json.dumps(payload).encode()

    def read(self):
        return self._b

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def fake_urlopen(message, sink):
    """Return a urlopen stand-in that records each posted body into `sink` and
    replies with {"message": message}."""

    def _open(req, *a, **k):
        sink.append(json.loads(req.data.decode()))
        return _FakeResp({"message": message})

    return _open


class FakeAnthropic:
    def __init__(self):
        self.calls = []
        parent = self

        class Messages:
            async def create(self, **kwargs):
                parent.calls.append(kwargs)
                return SimpleNamespace(
                    content=[
                        SimpleNamespace(type="text", text="A1"),
                        SimpleNamespace(type="tool_use", text="ignored"),
                        SimpleNamespace(type="text", text="A2"),
                    ]
                )

        self.messages = Messages()


def _run(coro):
    return asyncio.run(coro)


def test_anthropic_joins_text_and_passes_args(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "anthropic")
    monkeypatch.setenv("MODEL", "claude-x")
    fake = FakeAnthropic()
    monkeypatch.setattr(llm, "_anthropic_client", lambda: fake)

    out = _run(
        llm.complete(
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=123,
            system="sys",
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
        )
    )

    assert out == "A1\nA2"
    kw = fake.calls[0]
    assert kw["model"] == "claude-x"
    assert kw["max_tokens"] == 123
    assert kw["system"] == "sys"
    assert kw["tools"][0]["name"] == "web_search"
    assert kw["messages"] == [{"role": "user", "content": "hi"}]


def test_anthropic_omits_optional_args(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "anthropic")
    monkeypatch.setenv("MODEL", "claude-x")
    fake = FakeAnthropic()
    monkeypatch.setattr(llm, "_anthropic_client", lambda: fake)

    _run(llm.complete(messages=[{"role": "user", "content": "hi"}], max_tokens=10))

    kw = fake.calls[0]
    assert "system" not in kw
    assert "tools" not in kw


def test_ollama_returns_content_and_prepends_system(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("MODEL", "ornith-1.5:9b")
    monkeypatch.delenv("OLLAMA_REASONING_EFFORT", raising=False)
    monkeypatch.delenv("OLLAMA_NUM_CTX", raising=False)
    bodies = []
    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen({"content": "hello"}, bodies))

    out = _run(
        llm.complete(
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=50,
            system="be brief",
        )
    )

    assert out == "hello"
    body = bodies[0]
    assert body["model"] == "ornith-1.5:9b"
    assert body["messages"][0] == {"role": "system", "content": "be brief"}
    assert body["messages"][1] == {"role": "user", "content": "hi"}
    assert body["options"]["num_ctx"] == 2048  # sized to the tiny prompt, not fixed-huge
    assert body["options"]["num_predict"] == 50
    assert body["think"] is False  # env default "none" -> thinking off


def test_ollama_ignores_tools_but_still_completes(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("MODEL", "ornith-1.5:9b")
    bodies = []
    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen({"content": "ok"}, bodies))

    out = _run(
        llm.complete(
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=50,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
        )
    )

    assert out == "ok"
    assert "tools" not in bodies[0]  # tools not forwarded to ollama


def test_ollama_per_call_reasoning_override(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("MODEL", "ornith-1.5:9b")
    monkeypatch.setenv("OLLAMA_REASONING_EFFORT", "none")
    bodies = []
    monkeypatch.setattr(llm.urllib.request, "urlopen", fake_urlopen({"content": "ok"}, bodies))

    _run(
        llm.complete(
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=1200,
            reasoning_effort="medium",
        )
    )
    assert bodies[0]["think"] == "medium"  # level preserved


def test_ollama_blank_content_surfaces_thinking(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("MODEL", "ornith-1.5:9b")
    bodies = []
    monkeypatch.setattr(
        llm.urllib.request, "urlopen",
        fake_urlopen({"content": "", "thinking": "reasoned answer"}, bodies),
    )

    out = _run(llm.complete(messages=[{"role": "user", "content": "hi"}], max_tokens=50))
    assert out == "reasoned answer"


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "bogus")
    monkeypatch.setenv("MODEL", "x")
    with pytest.raises(ValueError):
        _run(llm.complete(messages=[{"role": "user", "content": "hi"}], max_tokens=10))
