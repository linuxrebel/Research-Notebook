import asyncio

from agents import researcher


def _run(coro):
    return asyncio.run(coro)


def test_extract_facts_as_list_becomes_bullets(monkeypatch):
    """Model returned facts as a JSON array -> join to bullets, not raw JSON dump."""
    async def fake_complete(**kw):
        return '{"facts": ["fact one", "fact two"], "queries": ["q1"]}'

    monkeypatch.setattr(researcher, "complete", fake_complete)
    facts, queries = _run(researcher._extract("t", "http://x", "body", want_queries=True))
    assert facts == "- fact one\n- fact two"
    assert queries == ["q1"]


def test_extract_facts_as_string_passthrough(monkeypatch):
    async def fake_complete(**kw):
        return '{"facts": "- already a bullet", "queries": []}'

    monkeypatch.setattr(researcher, "complete", fake_complete)
    facts, queries = _run(researcher._extract("t", "http://x", "body", want_queries=False))
    assert facts == "- already a bullet"
    assert queries == []
