"""Notebook — an interlinked note-set written incrementally to disk.

A research run is a human-style notebook, not one blob built in memory: each
source is read and its facts written to their own note as they're gathered, the
index is updated after every source, and the synthesis comes last. Facts survive
an interrupt because they're already on disk, and each note carries [[wikilinks]]
so Obsidian draws the graph across them.

    <dir>/index.md            map of content: link to every source + the synthesis
    <dir>/sources/<slug>.md   facts from one source (frontmatter: url, date)
    <dir>/summary.md          synthesis of the gathered facts (links the sources)
    <dir>/result.json         full run result
"""

import datetime
import json
import os
import re

from agents.output import hook_obsidian_dir, slugify


def _source_slug(url, title, i):
    """Short, stable slug for a source note. Prefer the URL's tail, fall back to
    the title, then an index — always unique-ish and filesystem-safe."""
    tail = re.sub(r"^https?://(www\.)?", "", url or "").strip("/")
    base = tail or title or f"source-{i}"
    return slugify(base, maxlen=60) or f"source-{i}"


class Notebook:
    def __init__(self, out_dir, topic, name):
        self.dir = out_dir
        self.topic = topic
        self.name = name
        self.sources = []  # list of {slug, title, url}
        os.makedirs(os.path.join(out_dir, "sources"), exist_ok=True)
        self._write_index()

    def add_source(self, url, facts, title=None):
        """Write one source note and link it from the index. Returns its slug."""
        title = title or url or "source"
        slug = _source_slug(url, title, len(self.sources) + 1)
        note = (
            "---\n"
            f'source: "{url}"\n'
            f"fetched: {datetime.date.today().isoformat()}\n"
            "tags: [source]\n"
            "---\n\n"
            f"# {title}\n\n"
            f"Source: {url}\n\n"
            f"{facts.strip()}\n"
        )
        with open(os.path.join(self.dir, "sources", f"{slug}.md"), "w") as f:
            f.write(note)
        self.sources.append({"slug": slug, "title": title, "url": url})
        self._write_index()  # refresh after every source: durable, resumable
        return slug

    def _index_md(self, with_summary=False):
        lines = [
            "---",
            f'topic: "{self.topic}"',
            f"date: {datetime.date.today().isoformat()}",
            "tags: [research, notebook]",
            "---",
            "",
            f"# {self.topic}",
            "",
            "Research notebook: gathered facts, one note per source. This collects "
            "what the sources say; it does not decide the question.",
            "",
            "## Sources",
            "",
        ]
        if self.sources:
            lines += [f"- [[sources/{s['slug']}|{s['title']}]] — {s['url']}" for s in self.sources]
        else:
            lines.append("_(none yet)_")
        if with_summary:
            lines += ["", "## Synthesis", "", "See [[summary]]."]
        return "\n".join(lines) + "\n"

    def _write_index(self, with_summary=False):
        with open(os.path.join(self.dir, "index.md"), "w") as f:
            f.write(self._index_md(with_summary))

    def combined_notes(self):
        """All gathered source facts concatenated — the summarizer's input."""
        blocks = []
        for s in self.sources:
            path = os.path.join(self.dir, "sources", f"{s['slug']}.md")
            with open(path) as f:
                blocks.append(f.read())
        return "\n\n---\n\n".join(blocks)

    def _summary_md(self, summary):
        key_points = "\n".join(f"- {p}" for p in summary.get("keyPoints", []))
        source_links = "\n".join(
            f"- [[sources/{s['slug']}|{s['title']}]]" for s in self.sources
        )
        return (
            "---\n"
            f'topic: "{self.topic}"\n'
            f"date: {datetime.date.today().isoformat()}\n"
            "tags: [research, synthesis]\n"
            "---\n\n"
            f"# {summary.get('title', '(untitled)')}\n\n"
            f"**Topic:** {self.topic}\n\n"
            f"## Findings\n\n{key_points}\n\n"
            f"## Notes\n\n{summary.get('takeaway', '')}\n\n"
            f"## Sources\n\n{source_links}\n"
        )

    def finalize(self, result):
        """Write summary.md + result.json, link the synthesis from the index, and
        hook the whole folder into the Obsidian vault. Returns the folder path."""
        with open(os.path.join(self.dir, "summary.md"), "w") as f:
            f.write(self._summary_md(result["summary"]))
        with open(os.path.join(self.dir, "result.json"), "w") as f:
            json.dump(result, f, indent=2)
        self._write_index(with_summary=True)
        hook_obsidian_dir(self.dir, self.name)
        return self.dir
