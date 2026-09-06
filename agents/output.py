"""Persist pipeline results as documents under $HOME/research/<topic-slug>/.

Writes four files per run:
    notes.md      raw research notes (markdown)
    summary.json  the structured summary object
    summary.md    human-readable summary (title, key points, takeaway, notes)
    result.json   the full run_pipeline() result

Destination base is RESEARCH_DIR if set, else ~/research.
"""

import json
import os
import re


def slugify(topic, maxlen=80):
    """Filesystem-safe directory name from a topic string."""
    s = re.sub(r"[^a-z0-9]+", "-", topic.lower()).strip("-")
    return s[:maxlen].strip("-") or "untitled"


def summary_md(result):
    s = result["summary"]
    key_points = "\n".join(f"- {p}" for p in s.get("keyPoints", []))
    return (
        f"# {s.get('title', '(untitled)')}\n\n"
        f"**Topic:** {result['topic']}\n\n"
        f"## Key Points\n\n{key_points}\n\n"
        f"## Takeaway\n\n{s.get('takeaway', '')}\n\n"
        f"## Research Notes\n\n{result['notes']}\n"
    )


def write_outputs(result, base_dir=None):
    """Write the four documents; return the topic directory path."""
    base = base_dir or os.environ.get("RESEARCH_DIR") or os.path.expanduser("~/research")
    out_dir = os.path.join(base, slugify(result["topic"]))
    os.makedirs(out_dir, exist_ok=True)

    with open(os.path.join(out_dir, "notes.md"), "w") as f:
        f.write(f"# {result['topic']}\n\n{result['notes']}\n")
    with open(os.path.join(out_dir, "summary.json"), "w") as f:
        json.dump(result["summary"], f, indent=2)
    with open(os.path.join(out_dir, "summary.md"), "w") as f:
        f.write(summary_md(result))
    with open(os.path.join(out_dir, "result.json"), "w") as f:
        json.dump(result, f, indent=2)

    return out_dir
