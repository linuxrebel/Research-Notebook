import asyncio
import os

from agents import fetch
from agents.fetch import detect_urls, is_youtube, parse_github


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


def test_is_youtube_matches_video_hosts():
    assert is_youtube("https://youtu.be/9EAzI4NSvP8")
    assert is_youtube("https://www.youtube.com/watch?v=abc")
    assert is_youtube("https://m.youtube.com/watch?v=abc")
    assert not is_youtube("https://github.com/owner/repo")
    assert not is_youtube("https://example.com/youtu.be")


def test_vtt_to_text_strips_timestamps_and_dedupes():
    vtt = (
        "WEBVTT\nKind: captions\nLanguage: en\n\n"
        "00:00:01.000 --> 00:00:02.000\nhello <c>world</c>\n\n"
        "00:00:02.000 --> 00:00:03.000\nhello world\n\n"  # rollup dup -> collapsed
        "00:00:03.000 --> 00:00:04.000\nnext line\n"
    )
    p = tmp_write(vtt)
    assert fetch._vtt_to_text(p) == "hello world\nnext line"


def test_fetch_one_youtube_branch_uses_transcript(monkeypatch, tmp_path):
    """youtube URL -> yt-dlp transcript path, no network. subs judged by files."""
    vtt = tmp_path / "vid.en.vtt"
    vtt.write_text("WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nthe transcript\n")

    def fake_ytdlp(args, timeout):
        class R:
            stdout = "My Video Title\n" if "--print" in args else ""
        return R()

    monkeypatch.setattr(fetch, "_ytdlp", fake_ytdlp)
    monkeypatch.setattr(fetch, "glob", type("G", (), {
        "glob": staticmethod(lambda pat: [str(vtt)])})())

    title, text = asyncio.run(fetch.fetch_one("https://youtu.be/xyz"))
    assert title == "My Video Title"
    assert "## Transcript" in text and "the transcript" in text


def test_fetch_one_youtube_no_subs_reports_gracefully(monkeypatch):
    def fake_ytdlp(args, timeout):
        class R:
            stdout = "Silent Video\n" if "--print" in args else ""
        return R()

    monkeypatch.setattr(fetch, "_ytdlp", fake_ytdlp)
    monkeypatch.setattr(fetch, "glob", type("G", (), {
        "glob": staticmethod(lambda pat: [])})())

    title, text = asyncio.run(fetch.fetch_one("https://youtu.be/xyz"))
    assert title == "Silent Video"
    assert "no transcript available" in text


def test_looks_blocked_catches_stub_and_challenge():
    assert fetch._looks_blocked("")
    assert fetch._looks_blocked("   ")
    assert fetch._looks_blocked("too short")
    assert fetch._looks_blocked("<div>Client Challenge</div>" + " " * 300)
    assert fetch._looks_blocked("Fastly is verifying your browser..." + " " * 300)
    assert not fetch._looks_blocked("real page content, " * 40)


def test_ordered_backends_default_and_pin(monkeypatch):
    monkeypatch.delenv("FETCH_BACKEND", raising=False)
    assert fetch._ordered_backends() == ["urllib", "obscura"]
    monkeypatch.setenv("FETCH_BACKEND", "obscura")
    assert fetch._ordered_backends() == ["obscura", "urllib"]
    monkeypatch.setenv("FETCH_BACKEND", "bogus")  # unknown ignored
    assert fetch._ordered_backends() == ["urllib", "obscura"]


def test_fetch_web_escalates_past_blocked_urllib(monkeypatch):
    """urllib returns a challenge stub -> escalate to obscura, which reads it."""
    good = "the real rendered page content " * 20
    monkeypatch.setattr(fetch, "_PROBES", {"urllib": lambda: True, "obscura": lambda: True})
    monkeypatch.setattr(fetch, "_FETCHERS", {
        "urllib": lambda u: "Client Challenge" + " " * 300,
        "obscura": lambda u: good,
    })
    assert fetch._fetch_web("https://pypi.org/x") == good


def test_fetch_web_urllib_wins_when_unblocked(monkeypatch):
    calls = []
    monkeypatch.setattr(fetch, "_PROBES", {"urllib": lambda: True, "obscura": lambda: True})
    monkeypatch.setattr(fetch, "_FETCHERS", {
        "urllib": lambda u: "plenty of real content " * 20,
        "obscura": lambda u: calls.append(u) or "should not run",
    })
    out = fetch._fetch_web("https://example.com")
    assert "real content" in out and calls == []  # obscura never invoked


def test_fetch_web_reports_when_all_fail(monkeypatch):
    monkeypatch.setattr(fetch, "_PROBES", {"urllib": lambda: True, "obscura": lambda: False})
    monkeypatch.setattr(fetch, "_FETCHERS", {
        "urllib": lambda u: "captcha" + " " * 300,
        "obscura": lambda u: "unused",
    })
    out = fetch._fetch_web("https://x")
    assert out.startswith("(no backend could read this page")
    assert "urllib:blocked" in out and "obscura:absent" in out


def tmp_write(text):
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".vtt")
    os.write(fd, text.encode())
    os.close(fd)
    return path
