import pytest


@pytest.fixture(autouse=True)
def isolate_obsidian_config(tmp_path_factory, monkeypatch):
    """Point OBSIDIAN_CONFIG at a throwaway path for every test so
    register_vault() can never touch the real Obsidian config. Tests that need
    a working registry set OBSIDIAN_CONFIG themselves (this runs first)."""
    fake = tmp_path_factory.mktemp("obsidian") / "obsidian.json"
    monkeypatch.setenv("OBSIDIAN_CONFIG", str(fake))
