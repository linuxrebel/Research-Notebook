"""Fetch and read primary sources — the difference between a research tool and
a search-snippet paraphraser.

Every URL that reaches the researcher is fetched and read here: GitHub repos via
the API (metadata + README + file tree), YouTube videos as their transcript (via
yt-dlp), any other URL as stripped page text. DDG (search.py) only *discovers*
links; this module reads what's behind them.

stdlib for the web/GitHub paths (urllib/re/html.parser); YouTube shells out to
yt-dlp. Python-side like search.py, so it works under any provider.
"""

import asyncio
import glob
import json
import os
import re
import subprocess
import tempfile
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlparse

_URL = re.compile(r"https?://[^\s<>\")]+")
_GITHUB = re.compile(r"https?://github\.com/([^/\s]+)/([^/\s#?]+)")
_UA = {"User-Agent": "Notebook-research/1.0"}
_MAX_CHARS = 8000  # per-source cap; keep prompts bounded


def detect_urls(text):
    """URLs named in the topic string, in order."""
    return _URL.findall(text or "")


def parse_github(url):
    """(owner, repo) for a github.com repo URL, else None."""
    m = _GITHUB.match(url)
    if not m:
        return None
    return m.group(1), m.group(2).removesuffix(".git")


def is_youtube(url):
    """True for a YouTube video URL — read via yt-dlp transcript, not page text."""
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    return host in ("youtube.com", "m.youtube.com", "youtu.be")


def _get(url, accept=None):
    headers = dict(_UA)
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


class _Stripper(HTMLParser):
    """Collect visible text, dropping script/style content."""

    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            t = data.strip()
            if t:
                self.parts.append(t)


def _strip_html(html):
    p = _Stripper()
    p.feed(html)
    return "\n".join(p.parts)


def _fetch_github_sync(owner, repo):
    api = f"https://api.github.com/repos/{owner}/{repo}"
    meta = json.loads(_get(api, accept="application/vnd.github+json"))
    lines = [
        f"# GitHub repo: {owner}/{repo}",
        f"Description: {meta.get('description')}",
        f"Primary language: {meta.get('language')}  "
        f"Stars: {meta.get('stargazers_count')}  Forks: {meta.get('forks_count')}",
        f"License: {(meta.get('license') or {}).get('name')}",
        f"Topics: {', '.join(meta.get('topics') or []) or '(none)'}",
        f"Last push: {meta.get('pushed_at')}  Open issues: {meta.get('open_issues_count')}  "
        f"Archived: {meta.get('archived')}",
    ]
    try:
        readme = _get(f"{api}/readme", accept="application/vnd.github.raw")
        lines.append("\n## README\n" + readme[:_MAX_CHARS])
    except Exception as e:
        lines.append(f"(README unavailable: {str(e)[:120]})")
    try:
        contents = json.loads(_get(f"{api}/contents", accept="application/vnd.github+json"))
        names = [f"{c['name']}{'/' if c['type'] == 'dir' else ''}" for c in contents]
        lines.append("\n## Top-level contents\n" + ", ".join(names))
    except Exception:
        pass
    return "\n".join(lines)


def _fetch_url_sync(url):
    return _strip_html(_get(url))[:_MAX_CHARS]


def _vtt_to_text(path):
    """Plain caption text from a .vtt: drop timestamps/tags, dedupe roll-up lines."""
    raw = open(path, encoding="utf-8", errors="replace").read()
    out, seen = [], None
    for ln in raw.splitlines():
        if ("-->" in ln or ln.strip().isdigit()
                or ln.startswith(("WEBVTT", "Kind:", "Language:")) or not ln.strip()):
            continue
        ln = re.sub(r"<[^>]+>", "", ln).strip()
        if ln and ln != seen:
            out.append(ln)
            seen = ln
    return "\n".join(out)


def _ytdlp(args, timeout):
    return subprocess.run(
        ["yt-dlp", *args], capture_output=True, text=True, timeout=timeout
    )


def _fetch_youtube_sync(url):
    """Read a YouTube video as its transcript (English subs, auto or manual).

    Two yt-dlp calls: subtitle download (judged by files written, since a 429 on
    one language variant sets a nonzero exit even when subs land) and a
    best-effort title. No API key — yt-dlp is local.
    """
    with tempfile.TemporaryDirectory() as td:
        _ytdlp(
            ["--skip-download", "--write-auto-subs", "--write-subs",
             "--sub-langs", "en.*,en", "--sub-format", "vtt",
             "-o", os.path.join(td, "%(id)s.%(ext)s"), url],
            timeout=120,
        )
        vtts = sorted(glob.glob(os.path.join(td, "*.vtt")))
        try:
            t = _ytdlp(["--skip-download", "--print", "title", url], timeout=30)
            title = (t.stdout.strip().splitlines() or [""])[0] or url
        except Exception:
            title = url
        if not vtts:
            return title, f"# {title}\n\n(no transcript available for this video)"
        text = _vtt_to_text(vtts[0])[:_MAX_CHARS]
        return title, f"# {title}\n\n## Transcript\n{text}"


async def fetch_one(url):
    """Fetch and read one URL, off the event loop. Returns (title, text).

    title is "owner/repo" for a GitHub repo, else the URL. text is the repo
    metadata+README (GitHub) or stripped page text — one source's real content,
    for its own note.
    """

    def _one():
        try:
            if is_youtube(url):
                return _fetch_youtube_sync(url)
            gh = parse_github(url)
            if gh:
                return f"{gh[0]}/{gh[1]}", _fetch_github_sync(*gh)
            return url, _fetch_url_sync(url)
        except Exception as e:
            return url, f"(fetch failed: {str(e)[:150]})"

    return await asyncio.to_thread(_one)
