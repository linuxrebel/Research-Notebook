"""Fetch and read primary sources — the difference between a research tool and
a search-snippet paraphraser.

Every URL that reaches the researcher is fetched and read here: GitHub repos via
the API (metadata + README + file tree), YouTube videos as their transcript (via
yt-dlp), any other URL as page text via an ordered backend chain (urllib, then
the obscura headless browser for JS/anti-bot walls). DDG (search.py) only
*discovers* links; this module reads what's behind them.

stdlib for the GitHub/urllib paths (urllib/re/html.parser); YouTube shells out
to yt-dlp and hard pages to obscura. Python-side like search.py, so it works
under any provider.
"""

import asyncio
import glob
import json
import os
import re
import shutil
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


# --- generic web page: ordered backend chain (urllib -> obscura) -------------
# urllib is free and reads most pages; a JS/anti-bot wall (Cloudflare, PyPI's
# "Client Challenge") returns a 200 with a challenge stub, not an error, so we
# escalate on *shape* (blocked/thin), not HTTP status. obscura is a local
# headless browser (V8) that runs the challenge and reads the real page.
_WEB_BACKENDS = ("urllib", "obscura")
_BLOCK_MARKERS = (
    "client challenge", "just a moment", "checking your browser",
    "verifying your browser", "verify you are human", "enable javascript",
    "cf-browser-verification", "captcha",
)


def _ordered_backends():
    """Backends in probe order, honoring FETCH_BACKEND (moves it to the front)."""
    order = list(_WEB_BACKENDS)
    pin = os.getenv("FETCH_BACKEND")
    if pin in order:
        order.insert(0, order.pop(order.index(pin)))
    return order


def _looks_blocked(text):
    """A page we didn't really get: empty, too thin, or a known challenge stub."""
    if not text or len(text.strip()) < 200:
        return True
    low = text[:2000].lower()
    return any(m in low for m in _BLOCK_MARKERS)


def _runs(*cmd):
    """True if the command runs and exits 0 — real probe, not just PATH presence."""
    try:
        return subprocess.run(cmd, capture_output=True, timeout=10).returncode == 0
    except Exception:
        return False


def _probe_obscura():
    return bool(shutil.which("obscura")) and _runs("obscura", "--version")


def _obscura_render(url):
    r = subprocess.run(
        ["obscura", "fetch", url, "--dump", "text", "--stealth", "--quiet",
         "--timeout", "45", "--wait-until", "networkidle0"],
        capture_output=True, text=True, timeout=90,
    )
    return r.stdout[:_MAX_CHARS]


_PROBES = {"urllib": lambda: True, "obscura": _probe_obscura}
_FETCHERS = {"urllib": _fetch_url_sync, "obscura": _obscura_render}


def _fetch_web(url):
    """Read a generic page, escalating urllib -> obscura on failure or a blocked
    shape. Returns the page text, or a note listing what each backend hit."""
    tried = []
    for name in _ordered_backends():
        if not _PROBES[name]():
            tried.append(f"{name}:absent")
            continue
        try:
            text = _FETCHERS[name](url)
        except Exception as e:
            tried.append(f"{name}:{str(e)[:40]}")
            continue
        if _looks_blocked(text):
            tried.append(f"{name}:blocked")
            continue
        return text
    return f"(no backend could read this page: {'; '.join(tried)})"


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
            return url, _fetch_web(url)
        except Exception as e:
            return url, f"(fetch failed: {str(e)[:150]})"

    return await asyncio.to_thread(_one)
