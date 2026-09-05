from agents.search import format_results


def test_format_empty():
    assert format_results([]) == "(no search results)"


def test_format_single():
    results = [{"title": "T", "snippet": "S", "url": "http://x"}]
    out = format_results(results)
    assert "- T" in out
    assert "S" in out
    assert "Source: http://x" in out


def test_format_multiple_joined():
    results = [
        {"title": "A", "snippet": "a", "url": "http://a"},
        {"title": "B", "snippet": "b", "url": "http://b"},
    ]
    out = format_results(results)
    assert out.count("Source:") == 2
    assert "- A" in out and "- B" in out
