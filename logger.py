import json
import logging
import os
from datetime import datetime, timezone

# Progress goes to stdout (always). A debug file is opt-in via `Notebook --debug`
# and captures WARN/ERROR only. NullHandler keeps it silent until enabled.
_file_logger = logging.getLogger("notebook")
_file_logger.addHandler(logging.NullHandler())


def enable_debug_log(path):
    """Attach a WARN/ERROR file handler at `path` (called for `--debug`)."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        h = logging.FileHandler(path)
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        _file_logger.addHandler(h)
        _file_logger.setLevel(logging.WARNING)  # WARNING + ERROR only
    except OSError as e:
        print(f"(debug log unavailable: {e})")  # non-fatal


def log(stage, data):
    """Print one progress line to stdout."""
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[{ts}] [{stage}]", json.dumps(data, indent=2))


def warn(stage, data):
    log(stage, data)
    _file_logger.warning("[%s] %s", stage, json.dumps(data))


def error(stage, data):
    log(stage, data)
    _file_logger.error("[%s] %s", stage, json.dumps(data))
