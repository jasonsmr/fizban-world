import json
import os
import time
from typing import Any, Dict, Optional

from .config import EVENT_LOG_PATH, SNAPSHOT_PATH, DATA_DIR

def _ensure_dirs() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)

def append_event(event: Dict[str, Any]) -> None:
    _ensure_dirs()
    line = json.dumps(event, ensure_ascii=False)
    with open(EVENT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def save_snapshot(state: Dict[str, Any]) -> None:
    _ensure_dirs()
    tmp = SNAPSHOT_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, SNAPSHOT_PATH)

def load_snapshot() -> Optional[Dict[str, Any]]:
    try:
        with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None

def now_unix() -> float:
    return time.time()
