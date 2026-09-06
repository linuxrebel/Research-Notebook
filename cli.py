"""Notebook — interactive research launcher.

Interactive by design: it forces a human in the loop to limit guessing. For a
non-interactive/machine entry point, use server.py (the API).
"""

import asyncio
import json
import os
import readline
import sys
import urllib.request

from dotenv import load_dotenv

load_dotenv()

from agents.coordinator import run_pipeline
from agents.llm import _ollama_native_base, resolve_provider
from agents.output import slugify


def preflight():
    """Fail fast with a friendly message if the local model server is down."""
    if resolve_provider() != "ollama":
        return
    try:
        with urllib.request.urlopen(_ollama_native_base() + "/api/tags", timeout=3) as r:
            up = r.status == 200
    except Exception:
        up = False
    if not up:
        print("Ollama does not appear to be running.")
        print("Start it, then re-run Notebook.")
        sys.exit(1)


def edit_input(prompt, prefill=""):
    """input() with an editable pre-filled line (readline)."""
    readline.set_startup_hook(lambda: readline.insert_text(prefill))
    try:
        return input(prompt).strip()
    finally:
        readline.set_startup_hook()


def research_base():
    return os.environ.get("RESEARCH_DIR") or os.path.expanduser("~/research")


def choose_dir_name(topic):
    """Suggest a slug, let the user edit it, resolve collisions."""
    base = research_base()
    name = edit_input("Directory name: ", slugify(topic))
    while True:
        if not name:
            name = edit_input("Directory name (cannot be empty): ", slugify(topic))
            continue
        target = os.path.join(base, name)
        if not os.path.exists(target):
            return name
        print(f'\n"{target}" already exists.')
        choice = input("[r]euse it / [n]ew name / [a]bort? ").strip().lower()
        if choice in ("r", "reuse"):
            return name
        if choice in ("a", "abort"):
            print("Aborted.")
            sys.exit(0)
        name = edit_input("New directory name: ", name)


def gather_request():
    topic = input("What do you want to investigate? ").strip()
    if not topic:
        print("No topic given. Aborting.")
        sys.exit(1)
    topic = edit_input("Edit if needed (Enter to accept): ", topic)
    if not topic:
        print("No topic given. Aborting.")
        sys.exit(1)

    name = choose_dir_name(topic)

    print("\n--- Research request ---")
    print(f'  Topic:      "{topic}"')
    print(f"  Output dir: {os.path.join(research_base(), name)}")
    if input("Start? [y/N] ").strip().lower() not in ("y", "yes"):
        print("Aborted.")
        sys.exit(0)
    return topic, name


async def main():
    preflight()
    topic, name = gather_request()
    result = await run_pipeline(topic, dir_name=name)
    print("\n=== FINAL RESULT ===")
    print(json.dumps(result, indent=2))


asyncio.run(main())
