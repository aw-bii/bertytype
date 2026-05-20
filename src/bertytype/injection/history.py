from __future__ import annotations
import json
import time
from datetime import datetime
from pathlib import Path

HISTORY_PATH = Path.home() / ".bertytype" / "history.jsonl"
EXPORT_PATH = Path.home() / ".bertytype" / "history_export.txt"
_MAX_AGE_SECONDS = 7 * 24 * 3600


_COMPACTION_THRESHOLD = 100


def append(text: str) -> None:
    entry = json.dumps({"ts": int(time.time()), "text": text}, separators=(",", ":"))
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(HISTORY_PATH, "a", encoding="utf-8") as f:
        f.write(entry + "\n")
    _maybe_compact()


def _maybe_compact() -> None:
    if not HISTORY_PATH.exists():
        return
    cutoff = time.time() - _MAX_AGE_SECONDS
    with open(HISTORY_PATH, "r", encoding="utf-8") as f:
        lines = f.readlines()
    line_count = sum(1 for line in lines if line.strip())
    if line_count <= _COMPACTION_THRESHOLD:
        return
    surviving = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
            if e.get("ts", 0) >= cutoff:
                surviving.append(line)
        except json.JSONDecodeError:
            continue
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(surviving) + "\n")


def query(since: datetime) -> list[dict]:
    """Return entries at or after `since`, sorted oldest-first."""
    try:
        cutoff = since.timestamp()
    except (OSError, ValueError):
        cutoff = 0
    if not HISTORY_PATH.exists():
        return []
    entries: list[dict] = []
    for line in HISTORY_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
            if e.get("ts", 0) >= cutoff:
                entries.append(e)
        except json.JSONDecodeError:
            pass
    return sorted(entries, key=lambda e: e["ts"])
