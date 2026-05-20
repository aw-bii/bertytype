from __future__ import annotations
import json
import time
from datetime import datetime
from pathlib import Path

HISTORY_PATH = Path.home() / ".bertytype" / "history.jsonl"
EXPORT_PATH = Path.home() / ".bertytype" / "history_export.txt"
_MAX_AGE_SECONDS = 7 * 24 * 3600


def append(text: str) -> None:
    """Append a transcription entry, pruning entries older than 7 days."""
    cutoff = time.time() - _MAX_AGE_SECONDS
    entry = {"ts": int(time.time()), "text": text}

    existing: list[dict] = []
    if HISTORY_PATH.exists():
        for line in HISTORY_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                if e.get("ts", 0) >= cutoff:
                    existing.append(e)
            except (json.JSONDecodeError, KeyError):
                pass

    existing.append(entry)
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_PATH.write_text(
        "\n".join(json.dumps(e) for e in existing) + "\n",
        encoding="utf-8",
    )


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
        except (json.JSONDecodeError, KeyError):
            pass
    return sorted(entries, key=lambda e: e["ts"])
