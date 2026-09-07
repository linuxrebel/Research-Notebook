import json
import os
import subprocess

from agents.output import (
    hook_obsidian_dir,
    register_vault,
    research_base,
    slugify,
)


def _make_run_dir(base, name="state-of-rust-async-in-2026"):
    """A minimal finished research folder to hook into a vault."""
    out = os.path.join(str(base), name)
    os.makedirs(os.path.join(out, "sources"), exist_ok=True)
    with open(os.path.join(out, "index.md"), "w") as f:
        f.write("# topic\n")
    return out


def test_slugify_basic():
    assert slugify("State of Rust Async in 2026!") == "state-of-rust-async-in-2026"


def test_slugify_collapses_and_strips():
    assert slugify("  Hello --- World!!  ") == "hello-world"


def test_slugify_empty_fallback():
    assert slugify("!!!") == "untitled"


def test_slugify_maxlen():
    assert len(slugify("a" * 200)) == 80


def test_research_base_env(monkeypatch, tmp_path):
    monkeypatch.setenv("RESEARCH_DIR", str(tmp_path))
    assert research_base() == str(tmp_path)


def test_hook_noop_without_vault(tmp_path, monkeypatch):
    monkeypatch.delenv("OBSIDIAN_VAULT", raising=False)
    out = _make_run_dir(tmp_path)
    assert hook_obsidian_dir(out, "state-of-rust-async-in-2026") is None
    assert not os.path.exists(os.path.join(out, "unhook.sh"))


def test_hook_symlinks_folder_and_unhook(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    monkeypatch.setenv("OBSIDIAN_VAULT", str(vault))
    out = _make_run_dir(tmp_path / "research")

    link = hook_obsidian_dir(out, "state-of-rust-async-in-2026")
    assert os.path.islink(link)
    assert os.path.realpath(link) == os.path.realpath(out)
    # a note inside the linked folder is reachable through the vault
    assert os.path.isfile(os.path.join(link, "index.md"))

    unhook = os.path.join(out, "unhook.sh")
    assert os.access(unhook, os.X_OK)
    subprocess.run(["bash", unhook], check=True)
    assert not os.path.lexists(link)
    assert os.path.isfile(os.path.join(out, "index.md"))  # source folder intact


def test_hook_name_sets_vault_folder_name(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    monkeypatch.setenv("OBSIDIAN_VAULT", str(vault))
    out = _make_run_dir(tmp_path / "research", name="my-custom-dir")
    hook_obsidian_dir(out, "my-custom-dir")
    assert os.path.islink(vault / "Research" / "my-custom-dir")


def test_hook_auto_provisions_new_vault(tmp_path, monkeypatch):
    vault = tmp_path / "Obsidian_Vaults" / "notebook"  # does not exist yet
    monkeypatch.setenv("OBSIDIAN_VAULT", str(vault))
    out = _make_run_dir(tmp_path / "research")
    hook_obsidian_dir(out, "state-of-rust-async-in-2026")
    assert (vault / ".obsidian" / "app.json").is_file()
    assert os.path.islink(vault / "Research" / "state-of-rust-async-in-2026")


def test_hook_preserves_existing_obsidian_config(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    (vault / ".obsidian").mkdir(parents=True)
    (vault / ".obsidian" / "app.json").write_text('{"mine": true}')
    monkeypatch.setenv("OBSIDIAN_VAULT", str(vault))
    out = _make_run_dir(tmp_path / "research")
    hook_obsidian_dir(out, "state-of-rust-async-in-2026")
    assert (vault / ".obsidian" / "app.json").read_text() == '{"mine": true}'


def test_hook_does_not_clobber_real_path(tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    (vault / "Research").mkdir(parents=True)
    real = vault / "Research" / "state-of-rust-async-in-2026"
    real.write_text("my own note")
    monkeypatch.setenv("OBSIDIAN_VAULT", str(vault))
    out = _make_run_dir(tmp_path / "research")
    assert hook_obsidian_dir(out, "state-of-rust-async-in-2026") is None
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
