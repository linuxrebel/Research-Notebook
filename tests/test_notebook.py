import json
import os

from agents.notebook import Notebook, _source_slug


def test_source_slug_from_github_url():
    assert _source_slug("https://github.com/h4ckf0r0day/obscura", "h4ckf0r0day/obscura", 1) \
        == "github-com-h4ckf0r0day-obscura"


def test_source_slug_falls_back_to_index():
    assert _source_slug("", "", 2) == "source-2"


def _nb(tmp_path, monkeypatch):
    monkeypatch.delenv("OBSIDIAN_VAULT", raising=False)
    out = os.path.join(str(tmp_path), "run")
    os.makedirs(out, exist_ok=True)
    return Notebook(out, "Analyze obscura pros and cons", "run"), out


def test_init_writes_index(tmp_path, monkeypatch):
    _nb(tmp_path, monkeypatch)
    idx = (tmp_path / "run" / "index.md").read_text()
    assert "# Analyze obscura pros and cons" in idx
    assert "does not decide" in idx  # fact-gathering framing


def test_add_source_writes_note_and_links_index(tmp_path, monkeypatch):
    nb, out = _nb(tmp_path, monkeypatch)
    slug = nb.add_source("https://github.com/x/y", "- Written in [[Rust]].", title="x/y", via="github")
    note = (tmp_path / "run" / "sources" / f"{slug}.md").read_text()
    assert "[[Rust]]" in note
    assert 'source: "https://github.com/x/y"' in note
    assert "fetched_via: github" in note  # provenance recorded
    # index links the source with a wikilink Obsidian can graph
    assert f"[[sources/{slug}|x/y]]" in (tmp_path / "run" / "index.md").read_text()


def test_combined_notes_concatenates_sources(tmp_path, monkeypatch):
    nb, _ = _nb(tmp_path, monkeypatch)
    nb.add_source("http://a", "- fact A.", title="A")
    nb.add_source("http://b", "- fact B.", title="B")
    combined = nb.combined_notes()
    assert "fact A." in combined and "fact B." in combined


def test_finalize_writes_summary_and_result(tmp_path, monkeypatch):
    nb, out = _nb(tmp_path, monkeypatch)
    nb.add_source("http://a", "- fact A.", title="A")
    result = {
        "topic": "Analyze obscura pros and cons",
        "notes": "- fact A.",
        "summary": {"title": "Obscura", "keyPoints": ["Pro: x", "Con: y"], "takeaway": "findings only"},
        "iterations": 1,
        "verdict": "APPROVED",
    }
    d = nb.finalize(result)
    assert d == out
    summ = (tmp_path / "run" / "summary.md").read_text()
    assert "## Findings" in summ and "Pro: x" in summ and "[[sources/" in summ
    assert json.loads((tmp_path / "run" / "result.json").read_text())["verdict"] == "APPROVED"
    assert "See [[summary]]." in (tmp_path / "run" / "index.md").read_text()
