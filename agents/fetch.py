"""Fetch and read primary sources — the difference between a research tool and
a search-snippet paraphraser.

Every URL that reaches the researcher is fetched and read here: GitHub repos via
the API (metadata + README + file tree), any other URL as stripped page text.
DDG (search.py) only *discovers* links; this module reads what's behind them.

stdlib only (urllib/re/html.parser), Python-side like search.py, so it works
under any provider.
"""

import asyncio
import json
import re
import urllib.request
from html.parser import HTMLParser

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


def _fetch_one_sync(url):
    gh = parse_github(url)
    try:
        text = _fetch_github_sync(*gh) if gh else _fetch_url_sync(url)
    except Exception as e:
        return f"Source: {url}\n(fetch failed: {str(e)[:150]})"
    return f"Source: {url}\n{text}"


async def fetch_sources(urls):
    """Fetch and read each URL (github->API, else page text), off the event loop.

    Returns one formatted block of real document text, or "" for no urls.
    Duplicate URLs are read once, order preserved.
    """
    seen = list(dict.fromkeys(u for u in urls if u))
    if not seen:
        return ""
    blocks = await asyncio.to_thread(lambda: [_fetch_one_sync(u) for u in seen])
    return "\n\n---\n\n".join(blocks)
