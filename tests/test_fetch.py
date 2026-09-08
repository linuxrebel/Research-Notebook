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


def tmp_write(text):
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".vtt")
    os.write(fd, text.encode())
    os.close(fd)
    return path
