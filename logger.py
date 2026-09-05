import json
import os
import time
from datetime import datetime, timezone

os.makedirs("logs", exist_ok=True)
LOG_FILE = os.path.join("logs", f"run-{int(time.time() * 1000)}.log")


def log(stage, data):
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stage": stage,
        "data": data,
    }
    print(f"[{entry['timestamp']}] [{stage}]", json.dumps(data, indent=2))
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")
