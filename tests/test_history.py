import json
import time
from datetime import datetime, timedelta
import pytest
from bertytype.injection import history


@pytest.fixture(autouse=True)
def tmp_history(tmp_path, monkeypatch):
    monkeypatch.setattr(history, "HISTORY_PATH", tmp_path / "history.jsonl")
    monkeypatch.setattr(history, "EXPORT_PATH", tmp_path / "history_export.txt")


def test_append_creates_file():
    history.append("hello world")
    assert history.HISTORY_PATH.exists()


def test_append_stores_text():
    history.append("test text")
    entries = history.query(datetime.fromtimestamp(0))
    assert any(e["text"] == "test text" for e in entries)


def test_append_stores_timestamp():
    before = int(time.time())
    history.append("ts test")
    after = int(time.time())
    entries = history.query(datetime.fromtimestamp(0))
    assert any(before <= e["ts"] <= after for e in entries if e["text"] == "ts test")


def test_query_empty_returns_empty_list():
    result = history.query(datetime.now() - timedelta(hours=1))
    assert result == []


def test_query_filters_by_since():
    old_ts = int(time.time()) - 9 * 3600
    recent_ts = int(time.time()) - 3600
    history.HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    history.HISTORY_PATH.write_text(
        f'{{"ts": {old_ts}, "text": "old"}}\n{{"ts": {recent_ts}, "text": "recent"}}\n',
        encoding="utf-8",
    )
    result = history.query(datetime.now() - timedelta(hours=8))
    assert len(result) == 1
    assert result[0]["text"] == "recent"


def test_query_returns_sorted_oldest_first():
    t1 = int(time.time()) - 300
    t2 = int(time.time()) - 100
    history.HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    history.HISTORY_PATH.write_text(
        f'{{"ts": {t2}, "text": "second"}}\n{{"ts": {t1}, "text": "first"}}\n',
        encoding="utf-8",
    )
    result = history.query(datetime.fromtimestamp(0))
    assert result[0]["text"] == "first"
    assert result[1]["text"] == "second"


def test_append_prunes_entries_older_than_7_days():
    old_ts = int(time.time()) - 8 * 24 * 3600
    history.HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    history.HISTORY_PATH.write_text(
        f'{{"ts": {old_ts}, "text": "ancient"}}\n',
        encoding="utf-8",
    )
    history.append("new entry")
    entries = history.query(datetime.fromtimestamp(0))
    texts = [e["text"] for e in entries]
    assert "ancient" not in texts
    assert "new entry" in texts


def test_append_multiple_entries():
    history.append("first")
    history.append("second")
    entries = history.query(datetime.now() - timedelta(minutes=1))
    texts = [e["text"] for e in entries]
    assert "first" in texts
    assert "second" in texts


def test_query_missing_file_returns_empty():
    assert not history.HISTORY_PATH.exists()
    result = history.query(datetime.now() - timedelta(hours=1))
    assert result == []
