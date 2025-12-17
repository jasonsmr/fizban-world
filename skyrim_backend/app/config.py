import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
EVENT_LOG_PATH = os.path.join(DATA_DIR, "events.jsonl")
SNAPSHOT_PATH = os.path.join(DATA_DIR, "snapshot.json")
API_TOKEN = os.environ.get("FIZBAN_API_TOKEN", "")  # optional shared secret

def require_token(token: str) -> bool:
    if not API_TOKEN:
        return True
    return token == API_TOKEN
