from agents.fetch import detect_urls, parse_github


def test_detect_urls_finds_url_in_topic():
    t = "analyze https://github.com/h4ckf0r0day/obscura for viability"
    assert detect_urls(t) == ["https://github.com/h4ckf0r0day/obscura"]


def test_detect_urls_none():
    assert detect_urls("no url in this topic") == []
    assert detect_urls("") == []


def test_parse_github_owner_repo():
    assert parse_github("https://github.com/h4ckf0r0day/obscura") == ("h4ckf0r0day", "obscura")


def test_parse_github_strips_git_suffix():
    assert parse_github("https://github.com/owner/repo.git") == ("owner", "repo")


def test_parse_github_ignores_deep_path():
    assert parse_github("https://github.com/owner/repo/tree/main") == ("owner", "repo")


def test_parse_github_rejects_non_repo_url():
    assert parse_github("https://example.com/owner/repo") is None
