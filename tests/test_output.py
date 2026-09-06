import json
import os
import subprocess

from agents.output import (
    hook_obsidian,
    register_vault,
    slugify,
    summary_md,
    write_outputs,
)

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


def test_summary_md_has_frontmatter():
    md = summary_md(RESULT)
    assert md.startswith("---\n")
    assert 'topic: "State of Rust Async in 2026!"' in md
    assert "verdict: APPROVED" in md
    assert "tags: [research, multi-agent-101]" in md


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


def test_write_outputs_name_overrides_slug(tmp_path, monkeypatch):
    monkeypatch.delenv("OBSIDIAN_VAULT", raising=False)
    out = write_outputs(RESULT, base_dir=str(tmp_path), name="my-custom-dir")
    assert out == os.path.join(str(tmp_path), "my-custom-dir")
    assert os.path.isfile(os.path.join(out, "summary.md"))


def test_hook_name_sets_vault_note_filename(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    monkeypatch.setenv("OBSIDIAN_VAULT", str(vault))
    write_outputs(RESULT, base_dir=str(tmp_path / "research"), name="my-custom-dir")
    assert os.path.islink(vault / "Research" / "my-custom-dir.md")
    # the slug-named note must NOT be created when an explicit name is given
    assert not os.path.lexists(vault / "Research" / "state-of-rust-async-in-2026.md")


def test_write_outputs_uses_env(tmp_path, monkeypatch):
    monkeypatch.setenv("RESEARCH_DIR", str(tmp_path))
    monkeypatch.delenv("OBSIDIAN_VAULT", raising=False)
    out = write_outputs(RESULT)
    assert out.startswith(str(tmp_path))


def test_hook_noop_without_vault(tmp_path, monkeypatch):
    monkeypatch.delenv("OBSIDIAN_VAULT", raising=False)
    out = write_outputs(RESULT, base_dir=str(tmp_path))
    assert hook_obsidian(RESULT, out) is None
    assert not os.path.exists(os.path.join(out, "unhook.sh"))


def test_hook_creates_symlink_and_unhook(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    monkeypatch.setenv("OBSIDIAN_VAULT", str(vault))
    out = write_outputs(RESULT, base_dir=str(tmp_path / "research"))

    link = vault / "Research" / "state-of-rust-async-in-2026.md"
    assert os.path.islink(link)
    assert os.path.realpath(link) == os.path.realpath(os.path.join(out, "summary.md"))

    unhook = os.path.join(out, "unhook.sh")
    assert os.path.isfile(unhook)
    assert os.access(unhook, os.X_OK)

    # running unhook removes the symlink, leaves the source intact
    subprocess.run(["bash", unhook], check=True)
    assert not os.path.lexists(link)
    assert os.path.isfile(os.path.join(out, "summary.md"))


def test_hook_auto_provisions_new_vault(tmp_path, monkeypatch):
    vault = tmp_path / "Obsidian_Vaults" / "multi-agent-101"  # does not exist yet
    monkeypatch.setenv("OBSIDIAN_VAULT", str(vault))
    write_outputs(RESULT, base_dir=str(tmp_path / "research"))

    assert (vault / ".obsidian" / "app.json").is_file()
    assert os.path.islink(vault / "Research" / "state-of-rust-async-in-2026.md")


def test_hook_preserves_existing_obsidian_config(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / ".obsidian" / "app.json").write_text('{"mine": true}')
    monkeypatch.setenv("OBSIDIAN_VAULT", str(vault))

    write_outputs(RESULT, base_dir=str(tmp_path / "research"))
    assert (vault / ".obsidian" / "app.json").read_text() == '{"mine": true}'


def test_hook_does_not_clobber_real_file(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    (vault / "Research").mkdir(parents=True)
    real = vault / "Research" / "state-of-rust-async-in-2026.md"
    real.write_text("my own note")
    monkeypatch.setenv("OBSIDIAN_VAULT", str(vault))

    out = write_outputs(RESULT, base_dir=str(tmp_path / "research"))
    assert not os.path.islink(real)
    assert real.read_text() == "my own note"
    assert not os.path.exists(os.path.join(out, "unhook.sh"))


def test_register_vault_no_config(tmp_path, monkeypatch):
    monkeypatch.setenv("OBSIDIAN_CONFIG", str(tmp_path / "nonexistent.json"))
    assert register_vault(str(tmp_path / "vault")) is False


def test_register_vault_adds_entry(tmp_path, monkeypatch):
    cfg = tmp_path / "obsidian.json"
    cfg.write_text(json.dumps({"vaults": {"abc": {"path": "/other", "ts": 1, "open": True}}}))
    monkeypatch.setenv("OBSIDIAN_CONFIG", str(cfg))
    vault = str(tmp_path / "myvault")

    assert register_vault(vault) is True
    data = json.loads(cfg.read_text())
    paths = [v["path"] for v in data["vaults"].values()]
    assert os.path.abspath(vault) in paths
    assert "/other" in paths  # existing entry preserved


def test_register_vault_idempotent(tmp_path, monkeypatch):
    cfg = tmp_path / "obsidian.json"
    cfg.write_text(json.dumps({"vaults": {}}))
    monkeypatch.setenv("OBSIDIAN_CONFIG", str(cfg))
    vault = str(tmp_path / "v")

    register_vault(vault)
    register_vault(vault)  # second call must not duplicate
    data = json.loads(cfg.read_text())
    matches = [v for v in data["vaults"].values() if v["path"] == os.path.abspath(vault)]
    assert len(matches) == 1


def test_register_vault_creates_vaults_key(tmp_path, monkeypatch):
    cfg = tmp_path / "obsidian.json"
    cfg.write_text("{}")  # no "vaults" key
    monkeypatch.setenv("OBSIDIAN_CONFIG", str(cfg))
    assert register_vault(str(tmp_path / "v")) is True
    assert "vaults" in json.loads(cfg.read_text())
