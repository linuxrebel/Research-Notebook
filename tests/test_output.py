import json
import os

from agents.output import slugify, summary_md, write_outputs

RESULT = {
    "topic": "State of Rust Async in 2026!",
    "notes": "- fact one. Source: http://x",
    "summary": {
        "title": "Rust Async",
        "keyPoints": ["a", "b", "c"],
        "takeaway": "it's good",
    },
    "iterations": 1,
    "verdict": "APPROVED",
}


def test_slugify_basic():
    assert slugify("State of Rust Async in 2026!") == "state-of-rust-async-in-2026"


def test_slugify_collapses_and_strips():
    assert slugify("  Hello --- World!!  ") == "hello-world"


def test_slugify_empty_fallback():
    assert slugify("!!!") == "untitled"


def test_slugify_maxlen():
    assert len(slugify("a" * 200)) == 80


def test_summary_md_contains_sections():
    md = summary_md(RESULT)
    assert "# Rust Async" in md
    assert "## Key Points" in md
    assert "- a" in md
    assert "## Takeaway" in md
    assert "## Research Notes" in md


def test_write_outputs_creates_four_files(tmp_path):
    out = write_outputs(RESULT, base_dir=str(tmp_path))
    assert out == os.path.join(str(tmp_path), "state-of-rust-async-in-2026")
    for name in ("notes.md", "summary.json", "summary.md", "result.json"):
        assert os.path.isfile(os.path.join(out, name))


def test_write_outputs_content(tmp_path):
    out = write_outputs(RESULT, base_dir=str(tmp_path))
    with open(os.path.join(out, "summary.json")) as f:
        assert json.load(f) == RESULT["summary"]
    with open(os.path.join(out, "result.json")) as f:
        assert json.load(f)["verdict"] == "APPROVED"


def test_write_outputs_uses_env(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEARCH_DIR", str(tmp_path))
    out = write_outputs(RESULT)
    assert out.startswith(str(tmp_path))
