# BertyType TODO Features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the setup wizard crash, add an undo injection hotkey, save transcription history to file, and support user-created named config profiles.

**Architecture:** Four independent features with minimal cross-cutting. Wizard fix is a rename + packaging change. Undo hotkey adds one config field and one pyautogui call. History is a new append-only JSONL module wired into the injection path. Profiles is a new JSON-directory module wired into the tray menu.

**Tech Stack:** Python, PySide6, pyautogui, JSON/JSONL for storage, pytest for tests.

---

## File Map

| Action | Path | Responsibility |
|--------|------|---------------|
| Rename | `src/bertytype/logging.py` → `src/bertytype/applog.py` | App-level loguru setup |
| Modify | `src/bertytype/config.py` | Add `undo_hotkey`, `active_profile` fields |
| Modify | `src/bertytype/__main__.py` | Undo handler, history writes, profile switching |
| Modify | `src/bertytype/ui/settings.py` | Add Undo Hotkey field |
| Modify | `src/bertytype/ui/tray.py` | Add View History + Profiles submenus |
| Create | `src/bertytype/injection/history.py` | JSONL append + time-range query |
| Create | `src/bertytype/profiles.py` | Profile list/load/save/delete |
| Modify | `pyproject.toml` | Add bertytype_setup to wheel, add entry point |
| Modify | `CLAUDE.md` | Fix launch invocation |
| Modify | `tests/test_logging.py` | Update to use applog |
| Modify | `tests/test_config.py` | Tests for new config fields |
| Create | `tests/test_history.py` | History module tests |
| Create | `tests/test_profiles.py` | Profiles module tests |

---

## Task 1: Rename bertytype/logging.py to applog.py

**Files:**
- Rename: `src/bertytype/logging.py` → `src/bertytype/applog.py`
- Modify: `src/bertytype/config.py:6`
- Modify: `src/bertytype/__main__.py:20`
- Modify: `tests/test_logging.py`

**Why:** `logging.py` shadows the Python stdlib `logging` module when the app is run via `python src/bertytype/__main__.py`, causing a circular import crash before Qt initializes.

- [ ] **Step 1: Create `src/bertytype/applog.py` with the same content as `logging.py`**

```python
import sys
from pathlib import Path
from loguru import logger

LOG_PATH = Path.home() / ".bertytype" / "logs"
LOG_FILE = "bertytype.log"

logger.remove()
if sys.stderr is not None:
    logger.add(
        sys.stderr,
        format="<level>{level}</level> <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        level="INFO",
    )


def init_file_logging() -> None:
    LOG_PATH.mkdir(parents=True, exist_ok=True)
    logger.add(
        LOG_PATH / LOG_FILE,
        rotation="10 MB",
        retention="7 days",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{function}:{line} - {message}",
    )
```

- [ ] **Step 2: Update import in `src/bertytype/config.py:6`**

Change:
```python
from bertytype import logging as log_module
```
To:
```python
from bertytype import applog as log_module
```

- [ ] **Step 3: Update import in `src/bertytype/__main__.py:20`**

Change:
```python
from bertytype import logging as log_module
```
To:
```python
from bertytype import applog as log_module
```

- [ ] **Step 4: Update `tests/test_logging.py` to reference applog**

Replace the entire file with:
```python
import sys
from unittest.mock import patch


def test_import_does_not_create_log_directory():
    """Importing bertytype.applog must not touch the filesystem."""
    for key in list(sys.modules):
        if "bertytype" in key:
            del sys.modules[key]

    with patch("pathlib.Path.mkdir") as mock_mkdir:
        import bertytype.applog  # noqa: F401
        mock_mkdir.assert_not_called()
```

- [ ] **Step 5: Delete `src/bertytype/logging.py`**

```bash
rm "src/bertytype/logging.py"
```

- [ ] **Step 6: Run tests to verify nothing broke**

```bash
.venv/Scripts/python.exe -m pytest tests/test_logging.py tests/test_config.py -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add src/bertytype/applog.py src/bertytype/config.py src/bertytype/__main__.py tests/test_logging.py
git rm src/bertytype/logging.py
git commit -m "fix: rename bertytype/logging.py to applog.py to avoid stdlib shadow"
```

---

## Task 2: Fix pyproject.toml packaging

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add `bertytype_setup` to wheel packages and add entry point**

In `pyproject.toml`, change:
```toml
[tool.hatch.build.targets.wheel]
packages = ["src/bertytype"]
```
To:
```toml
[tool.hatch.build.targets.wheel]
packages = ["src/bertytype", "src/bertytype_setup"]
```

And change:
```toml
[project.gui-scripts]
bertytype = "bertytype.__main__:main"
```
To:
```toml
[project.gui-scripts]
bertytype = "bertytype.__main__:main"
bertytype-setup = "bertytype_setup.__main__:main"
```

- [ ] **Step 2: Reinstall in editable mode so the new entry point is registered**

```bash
.venv/Scripts/pip.exe install -e .
```

Expected: output includes `Successfully installed bertytype-0.1.2`.

- [ ] **Step 3: Verify the new script exists**

```bash
ls .venv/Scripts/ | grep berty
```

Expected: both `bertytype.exe` and `bertytype-setup.exe` are listed.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "fix: add bertytype_setup to wheel packages and add bertytype-setup entry point"
```

---

## Task 3: Fix CLAUDE.md invocation

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update the launch command in CLAUDE.md**

Find the "Project Entry Point" section in `CLAUDE.md`. Change:
```
python src\bertytype\__main__.py
```
To:
```
python -m bertytype
```

- [ ] **Step 2: Verify the correct invocation works**

```bash
.venv/Scripts/python.exe -m bertytype --help 2>&1 | head -3
```

Expected: No `AttributeError` about circular imports (it may open a Qt window or exit cleanly).

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: fix CLAUDE.md launch invocation from direct script to python -m bertytype"
```

---

## Task 4: Add undo_hotkey to Config

**Files:**
- Modify: `src/bertytype/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write failing tests in `tests/test_config.py`**

Append to the file:
```python
def test_undo_hotkey_default():
    assert config.Config().undo_hotkey == "ctrl+z"


def test_undo_hotkey_round_trips(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    cfg = config.Config(undo_hotkey="ctrl+alt+z")
    config.save(cfg)
    loaded = config.load()
    assert loaded.undo_hotkey == "ctrl+alt+z"


def test_undo_hotkey_invalid_empty_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    (tmp_path / "config.json").write_text('{"undo_hotkey": ""}')
    loaded = config.load()
    assert loaded.undo_hotkey == "ctrl+z"
```

- [ ] **Step 2: Run to confirm they fail**

```bash
.venv/Scripts/python.exe -m pytest tests/test_config.py::test_undo_hotkey_default -v
```

Expected: FAIL with `AttributeError: 'Config' object has no attribute 'undo_hotkey'`.

- [ ] **Step 3: Add `undo_hotkey` to `Config` dataclass in `src/bertytype/config.py`**

In the `Config` dataclass, add after `show_completion_notification`:
```python
undo_hotkey: str = "ctrl+z"
```

- [ ] **Step 4: Add validation in `_validate_value()` in `src/bertytype/config.py`**

After the `elif key == "show_completion_notification":` block, add:
```python
    elif key == "undo_hotkey":
        if not isinstance(value, str) or not value.strip():
            logger.warning(f"Invalid {key}: {value!r}, using default {default!r}")
            return default
```

- [ ] **Step 5: Run tests to confirm they pass**

```bash
.venv/Scripts/python.exe -m pytest tests/test_config.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/bertytype/config.py tests/test_config.py
git commit -m "feat: add undo_hotkey config field (default ctrl+z)"
```

---

## Task 5: Add _on_undo() handler and preserve unmanaged config fields on settings save

**Files:**
- Modify: `src/bertytype/__main__.py`

- [ ] **Step 1: Add `pyautogui` import to `src/bertytype/__main__.py`**

At the top of `__main__.py`, after `import pyperclip`, add:
```python
import pyautogui
```

- [ ] **Step 2: Add `_on_undo()` function in `src/bertytype/__main__.py`**

After the `_on_cancel()` function (around line 50), add:
```python
def _on_undo() -> None:
    pyautogui.hotkey("ctrl", "z")
```

- [ ] **Step 3: Register the undo hotkey in `_register_hotkeys()`**

In `_register_hotkeys()`, after the line `hotkey_daemon.register(cfg.cancel_hotkey, _on_cancel)`, add:
```python
    hotkey_daemon.register(cfg.undo_hotkey, _on_undo)
```

The full `_register_hotkeys()` should end with:
```python
    hotkey_daemon.register(cfg.cancel_hotkey, _on_cancel)
    hotkey_daemon.register(cfg.undo_hotkey, _on_undo)
```

- [ ] **Step 4: Update `_save()` in `_on_open_settings()` to preserve `show_completion_notification`**

In `_on_open_settings()`, find the nested `_save()` function:

Current:
```python
    def _save(updated_cfg: cfg_module.Config) -> None:
        global _cfg
        with _cfg_lock:
            _cfg = updated_cfg
        cfg_module.save(updated_cfg)
        _register_hotkeys(updated_cfg)
```

Replace with:
```python
    def _save(updated_cfg: cfg_module.Config) -> None:
        import dataclasses
        global _cfg
        with _cfg_lock:
            current = _cfg
        # Preserve show_completion_notification which is not exposed in the settings dialog
        updated_cfg = dataclasses.replace(
            updated_cfg,
            show_completion_notification=current.show_completion_notification,
        )
        with _cfg_lock:
            _cfg = updated_cfg
        cfg_module.save(updated_cfg)
        _register_hotkeys(updated_cfg)
```

- [ ] **Step 5: Run tests**

```bash
.venv/Scripts/python.exe -m pytest tests/ -v -k "not test_setup_wizard and not test_setup_installers"
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/bertytype/__main__.py
git commit -m "feat: add _on_undo() handler, register undo_hotkey, preserve show_completion_notification on settings save"
```

---

## Task 6: Add Undo Hotkey field to Settings dialog

**Files:**
- Modify: `src/bertytype/ui/settings.py`

- [ ] **Step 1: Write a failing test in `tests/test_settings.py`**

Append to the file:
```python
def test_dialog_saves_undo_hotkey(qapp):
    from bertytype.ui.settings import _SettingsDialog, _str_to_qks
    from bertytype.config import Config
    saved = []
    cfg = Config(undo_hotkey="ctrl+z")
    dlg = _SettingsDialog(cfg, on_save=saved.append)
    dlg._undo_edit.setKeySequence(_str_to_qks("ctrl+alt+z"))
    dlg._save()
    assert len(saved) == 1
    assert saved[0].undo_hotkey == "ctrl+alt+z"
```

- [ ] **Step 2: Run to confirm it fails**

```bash
.venv/Scripts/python.exe -m pytest tests/test_settings.py::test_dialog_saves_undo_hotkey -v
```

Expected: FAIL with `AttributeError: '_SettingsDialog' object has no attribute '_undo_edit'`.

- [ ] **Step 3: Add `_undo_edit` widget in `_build_ui()` in `src/bertytype/ui/settings.py`**

After the `_cancel_edit` block (after `form.addRow("Cancel Hotkey", self._cancel_edit)`), add:
```python
        self._undo_edit = QKeySequenceEdit(_str_to_qks(cfg.undo_hotkey))
        self._undo_edit.setToolTip("Press the key combination to undo the last text injection in the target application")
        self._undo_edit.setAccessibleName("Undo Hotkey")
        self._undo_edit.setAccessibleDescription("Press the key combination to undo the last text injection in the target application")
        form.addRow("Undo Hotkey", self._undo_edit)
```

- [ ] **Step 4: Update `load_config()` to set the undo field**

In `load_config()`, after `self._cancel_edit.setKeySequence(_str_to_qks(cfg.cancel_hotkey))`, add:
```python
        self._undo_edit.setKeySequence(_str_to_qks(cfg.undo_hotkey))
```

- [ ] **Step 5: Update `_setup_tab_order()` to include `_undo_edit`**

In `_setup_tab_order()`, change the `widgets` list to insert `self._undo_edit` after `self._cancel_edit`:
```python
        widgets = [
            self._mode_combo,
            self._hotkey_edit,
            self._dtw_slider,
            self._cancel_edit,
            self._undo_edit,
            self._model_edit,
            self._refine_check,
            self._vad_slider,
            self._llm_to_edit,
            self._delay_edit,
            self._save_btn,
        ]
```

- [ ] **Step 6: Update `_save()` to read `undo_hotkey` and include it in Config**

In `_save()`, after reading `cancel_hotkey`, add:
```python
        undo_hotkey = _qks_to_str(self._undo_edit.keySequence())
        if not undo_hotkey:
            self._err("Undo Hotkey cannot be empty", self._undo_edit)
            return
```

Then in the `Config(...)` constructor call at the bottom of `_save()`, add `undo_hotkey=undo_hotkey`:
```python
        updated = Config(
            hotkey=hotkey,
            hotkey_mode=self._mode_combo.currentText(),
            cancel_hotkey=cancel_hotkey,
            undo_hotkey=undo_hotkey,
            model=model,
            refine=self._refine_check.isChecked(),
            vad_threshold=self._vad_slider.value() / 100,
            llm_timeout=llm_timeout,
            injection_delay=injection_delay,
            double_tap_window=self._dtw_slider.value() / 100,
        )
```

- [ ] **Step 7: Run tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_settings.py -v
```

Expected: all tests PASS.

- [ ] **Step 8: Commit**

```bash
git add src/bertytype/ui/settings.py tests/test_settings.py
git commit -m "feat: add Undo Hotkey field to settings dialog"
```

---

## Task 7: Create injection/history.py

**Files:**
- Create: `src/bertytype/injection/history.py`
- Create: `tests/test_history.py`

- [ ] **Step 1: Write failing tests in `tests/test_history.py`**

```python
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
```

- [ ] **Step 2: Run to confirm they fail**

```bash
.venv/Scripts/python.exe -m pytest tests/test_history.py -v
```

Expected: FAIL with `ImportError: cannot import name 'history' from 'bertytype.injection'`.

- [ ] **Step 3: Create `src/bertytype/injection/history.py`**

```python
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
    cutoff = since.timestamp()
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
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
.venv/Scripts/python.exe -m pytest tests/test_history.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bertytype/injection/history.py tests/test_history.py
git commit -m "feat: add injection/history.py with append and time-range query"
```

---

## Task 8: Wire history.append() into __main__.py

**Files:**
- Modify: `src/bertytype/__main__.py`

- [ ] **Step 1: Update the injection import at the top of `__main__.py`**

Change:
```python
from bertytype.injection import injector, exporter
```
To:
```python
from bertytype.injection import injector, exporter, history
```

- [ ] **Step 2: Call `history.append()` after successful injection in `_capture_and_process()`**

Find the block inside the `try` of `_capture_and_process()`:
```python
        try:
            injector.inject(text, cfg.injection_delay)
            if cfg.show_completion_notification:
                preview = text[:60] + ("..." if len(text) > 60 else "")
                tray.notify(preview)
        except Exception as e:
```

Change to:
```python
        try:
            injector.inject(text, cfg.injection_delay)
            history.append(text)
            if cfg.show_completion_notification:
                preview = text[:60] + ("..." if len(text) > 60 else "")
                tray.notify(preview)
        except Exception as e:
```

- [ ] **Step 3: Call `history.append()` after successful file transcription in `_do_file_transcription()`**

Find:
```python
        out_path = exporter.save_transcript(text, path)
        pyperclip.copy(text)
        tray.notify(messages.INFO_TRANSCRIPTION_COMPLETE.format(name=out_path.name))
```

Change to:
```python
        out_path = exporter.save_transcript(text, path)
        pyperclip.copy(text)
        history.append(text)
        tray.notify(messages.INFO_TRANSCRIPTION_COMPLETE.format(name=out_path.name))
```

- [ ] **Step 4: Run tests**

```bash
.venv/Scripts/python.exe -m pytest tests/ -v -k "not test_setup_wizard and not test_setup_installers"
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bertytype/__main__.py
git commit -m "feat: write transcription history after each successful injection"
```

---

## Task 9: Add View History tray submenu

**Files:**
- Modify: `src/bertytype/ui/tray.py`
- Modify: `src/bertytype/__main__.py`

- [ ] **Step 1: Add `_on_view_history()` handler in `__main__.py`**

After `_on_open_settings()`, add:
```python
def _on_view_history(range_key: str) -> None:
    import os
    from datetime import datetime, timedelta
    from bertytype.injection.history import EXPORT_PATH, query

    ranges = {
        "8h": timedelta(hours=8),
        "1d": timedelta(days=1),
        "7d": timedelta(days=7),
    }
    since = datetime.now() - ranges[range_key]
    entries = query(since)
    if not entries:
        tray.notify("No history in that range.")
        return
    lines = [
        f"[{datetime.fromtimestamp(e['ts']).strftime('%Y-%m-%d %H:%M:%S')}] {e['text']}"
        for e in entries
    ]
    EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    EXPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    os.startfile(str(EXPORT_PATH))
```

- [ ] **Step 2: Update `tray.start()` signature to accept `on_view_history`**

In `src/bertytype/ui/tray.py`, change the `start()` signature from:
```python
def start(
    cfg,
    on_transcribe_file: Callable[[], None],
    on_open_settings: Callable[[], None],
    on_quit: Callable[[], None],
) -> None:
```
To:
```python
def start(
    cfg,
    on_transcribe_file: Callable[[], None],
    on_open_settings: Callable[[], None],
    on_quit: Callable[[], None],
    on_view_history: Callable[[str], None] | None = None,
) -> None:
```

- [ ] **Step 3: Add the View History submenu in `start()` in `tray.py`**

In `start()`, after `menu.addAction("Settings", on_open_settings)`, add:
```python
    if on_view_history is not None:
        history_menu = menu.addMenu("View history")
        history_menu.addAction("Last 8 hours", lambda: on_view_history("8h"))
        history_menu.addAction("Last 24 hours", lambda: on_view_history("1d"))
        history_menu.addAction("Last 7 days", lambda: on_view_history("7d"))
```

- [ ] **Step 4: Pass `on_view_history` in the `tray.start()` call in `__main__.py`**

Find:
```python
    tray.start(
        cfg=cfg,
        on_transcribe_file=_on_transcribe_file,
        on_open_settings=_on_open_settings,
        on_quit=_on_quit,
    )
```

Change to:
```python
    tray.start(
        cfg=cfg,
        on_transcribe_file=_on_transcribe_file,
        on_open_settings=_on_open_settings,
        on_quit=_on_quit,
        on_view_history=_on_view_history,
    )
```

- [ ] **Step 5: Run tests**

```bash
.venv/Scripts/python.exe -m pytest tests/ -v -k "not test_setup_wizard and not test_setup_installers"
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/bertytype/ui/tray.py src/bertytype/__main__.py
git commit -m "feat: add View History tray submenu with 8h/1d/7d time ranges"
```

---

## Task 10: Add active_profile to Config

**Files:**
- Modify: `src/bertytype/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Write failing tests in `tests/test_config.py`**

Append:
```python
def test_active_profile_defaults_none():
    assert config.Config().active_profile is None


def test_active_profile_round_trips(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    cfg = config.Config(active_profile="Dictation")
    config.save(cfg)
    loaded = config.load()
    assert loaded.active_profile == "Dictation"


def test_active_profile_invalid_type_defaults_none(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    (tmp_path / "config.json").write_text('{"active_profile": 123}')
    loaded = config.load()
    assert loaded.active_profile is None
```

- [ ] **Step 2: Run to confirm they fail**

```bash
.venv/Scripts/python.exe -m pytest tests/test_config.py::test_active_profile_defaults_none -v
```

Expected: FAIL with `AttributeError`.

- [ ] **Step 3: Add `active_profile` to `Config` in `src/bertytype/config.py`**

In the `Config` dataclass, add after `undo_hotkey`:
```python
    active_profile: str | None = None
```

Also add the import at the top of the file if not already present:
```python
from typing import Any, Optional
```

(Note: `str | None` requires Python 3.10+, which matches `requires-python = ">=3.10"` in pyproject.toml.)

- [ ] **Step 4: Add validation in `_validate_value()`**

After the `elif key == "undo_hotkey":` block, add:
```python
    elif key == "active_profile":
        if value is not None and not isinstance(value, str):
            logger.warning(f"Invalid {key}: {value!r}, using default None")
            return None
```

- [ ] **Step 5: Run tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_config.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add src/bertytype/config.py tests/test_config.py
git commit -m "feat: add active_profile config field (default None)"
```

---

## Task 11: Create profiles.py

**Files:**
- Create: `src/bertytype/profiles.py`
- Create: `tests/test_profiles.py`

- [ ] **Step 1: Write failing tests in `tests/test_profiles.py`**

```python
import json
import pytest
from bertytype import profiles
from bertytype.config import Config


@pytest.fixture(autouse=True)
def tmp_profiles_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(profiles, "PROFILES_DIR", tmp_path / "profiles")


def test_list_profiles_empty_when_no_dir():
    result = profiles.list_profiles()
    assert result == []


def test_save_and_list():
    cfg = Config(hotkey="ctrl+r")
    profiles.save_profile("Work", cfg)
    assert profiles.list_profiles() == ["Work"]


def test_list_profiles_sorted():
    profiles.save_profile("Zebra", Config())
    profiles.save_profile("Alpha", Config())
    assert profiles.list_profiles() == ["Alpha", "Zebra"]


def test_load_profile_returns_config_with_active_set():
    cfg = Config(hotkey="ctrl+r")
    profiles.save_profile("Work", cfg)
    loaded = profiles.load_profile("Work")
    assert loaded.hotkey == "ctrl+r"
    assert loaded.active_profile == "Work"


def test_load_profile_missing_raises():
    with pytest.raises(FileNotFoundError):
        profiles.load_profile("nonexistent")


def test_save_creates_json_file():
    cfg = Config()
    profiles.save_profile("Test", cfg)
    path = profiles.PROFILES_DIR / "Test.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["hotkey"] == cfg.hotkey


def test_delete_profile_removes_file():
    profiles.save_profile("Temp", Config())
    profiles.delete_profile("Temp")
    assert profiles.list_profiles() == []


def test_delete_profile_missing_does_not_raise():
    profiles.delete_profile("does_not_exist")  # must not raise


def test_is_valid_name_accepts_valid():
    assert profiles.is_valid_name("My Profile") is True
    assert profiles.is_valid_name("code-mode") is True
    assert profiles.is_valid_name("profile_1") is True


def test_is_valid_name_rejects_empty():
    assert profiles.is_valid_name("") is False


def test_is_valid_name_rejects_too_long():
    assert profiles.is_valid_name("a" * 65) is False


def test_is_valid_name_rejects_special_chars():
    assert profiles.is_valid_name("bad/name") is False
    assert profiles.is_valid_name("bad;name") is False
```

- [ ] **Step 2: Run to confirm they fail**

```bash
.venv/Scripts/python.exe -m pytest tests/test_profiles.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'bertytype.profiles'`.

- [ ] **Step 3: Create `src/bertytype/profiles.py`**

```python
from __future__ import annotations
import dataclasses
import json
import re
from pathlib import Path

from bertytype import config as cfg_module
from bertytype.config import Config

PROFILES_DIR = Path.home() / ".bertytype" / "profiles"

_NAME_RE = re.compile(r'^[\w\s\-]+$')
_NAME_MAX_LEN = 64


def is_valid_name(name: str) -> bool:
    """Return True if name is a valid profile name."""
    return bool(name) and len(name) <= _NAME_MAX_LEN and bool(_NAME_RE.match(name))


def list_profiles() -> list[str]:
    """Return sorted profile names."""
    if not PROFILES_DIR.exists():
        return []
    return sorted(p.stem for p in PROFILES_DIR.glob("*.json"))


def load_profile(name: str) -> Config:
    """Load a profile by name. Raises FileNotFoundError if not found."""
    path = PROFILES_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Profile not found: {name!r}")
    data = json.loads(path.read_text(encoding="utf-8"))
    known_keys = set(dataclasses.asdict(Config()).keys())
    data = {k: v for k, v in data.items() if k in known_keys}
    cfg = cfg_module._validate(data)
    return dataclasses.replace(cfg, active_profile=name)


def save_profile(name: str, cfg: Config) -> None:
    """Save current config as a named profile."""
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    path = PROFILES_DIR / f"{name}.json"
    path.write_text(json.dumps(dataclasses.asdict(cfg), indent=2), encoding="utf-8")


def delete_profile(name: str) -> None:
    """Delete a profile by name. No-op if it does not exist."""
    path = PROFILES_DIR / f"{name}.json"
    path.unlink(missing_ok=True)
```

- [ ] **Step 4: Run tests**

```bash
.venv/Scripts/python.exe -m pytest tests/test_profiles.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/bertytype/profiles.py tests/test_profiles.py
git commit -m "feat: add profiles.py with list/load/save/delete and name validation"
```

---

## Task 12: Add Profiles tray submenu and wire profile switching

**Files:**
- Modify: `src/bertytype/ui/tray.py`
- Modify: `src/bertytype/__main__.py`

- [ ] **Step 1: Add module-level `_profiles_menu` state and `update_profiles_menu()` to `tray.py`**

At the top of `tray.py`, after the existing module-level globals, add:
```python
_profiles_menu: "QMenu | None" = None
```

After the `stop()` function, add:
```python
def update_profiles_menu(
    profile_names: list[str],
    active: str | None,
    on_switch: Callable[[str], None],
) -> None:
    """Rebuild the profiles submenu with current profile list."""
    if _profiles_menu is None:
        return
    # Remove all actions after the separator (the profile items)
    past_separator = False
    for action in list(_profiles_menu.actions()):
        if action.isSeparator():
            past_separator = True
        elif past_separator:
            _profiles_menu.removeAction(action)
    # Re-add profile items
    for name in profile_names:
        action = _profiles_menu.addAction(name, lambda n=name: on_switch(n))
        action.setCheckable(True)
        action.setChecked(name == active)
```

- [ ] **Step 2: Update `start()` signature in `tray.py` to accept profile callbacks**

Change the `start()` signature to:
```python
def start(
    cfg,
    on_transcribe_file: Callable[[], None],
    on_open_settings: Callable[[], None],
    on_quit: Callable[[], None],
    on_view_history: Callable[[str], None] | None = None,
    on_save_profile_as: Callable[[], None] | None = None,
) -> None:
```

- [ ] **Step 3: Add the Profiles submenu in `start()` in `tray.py`**

In `start()`, after the `if on_view_history` block and before `menu.addSeparator()`, add:

```python
    global _profiles_menu
    if on_save_profile_as is not None:
        _profiles_menu = menu.addMenu("Profiles")
        _profiles_menu.addAction("Save current as profile...", on_save_profile_as)
        _profiles_menu.addSeparator()
```

Also update the `stop()` function to reset `_profiles_menu`:
```python
def stop() -> None:
    global _tray_icon, _anim_timer, _error_timer, _profiles_menu
    _profiles_menu = None
    if _anim_timer is not None:
        ...
```

- [ ] **Step 4: Update `_save()` in `_on_open_settings()` to also preserve `active_profile`**

In `_on_open_settings()`, find the `dataclasses.replace(...)` call added in Task 5 and add `active_profile`:

Change:
```python
        updated_cfg = dataclasses.replace(
            updated_cfg,
            show_completion_notification=current.show_completion_notification,
        )
```
To:
```python
        updated_cfg = dataclasses.replace(
            updated_cfg,
            show_completion_notification=current.show_completion_notification,
            active_profile=current.active_profile,
        )
```

- [ ] **Step 5: Add profile handler functions in `__main__.py`**

After `_on_view_history()`, add:

```python
def _on_save_profile_as() -> None:
    import re
    from bertytype import profiles
    from PySide6.QtWidgets import QInputDialog
    name, ok = QInputDialog.getText(None, "Save Profile", "Profile name:")
    if not ok:
        return
    name = name.strip()
    if not profiles.is_valid_name(name):
        tray.notify("Invalid name. Use letters, digits, spaces, hyphens, or underscores (max 64 chars).")
        return
    with _cfg_lock:
        cfg = _cfg
    try:
        profiles.save_profile(name, cfg)
    except Exception as e:
        logger.warning(f"Failed to save profile {name!r}: {e}")
        tray.notify(f"Could not save profile '{name}'.")
        return
    _refresh_profiles_menu()
    tray.notify(f"Profile '{name}' saved.")


def _on_switch_profile(name: str) -> None:
    from bertytype import profiles
    import dataclasses
    try:
        new_cfg = profiles.load_profile(name)
    except Exception as e:
        logger.warning(f"Failed to load profile {name!r}: {e}")
        tray.notify(f"Could not load profile '{name}'.")
        return
    global _cfg
    with _cfg_lock:
        _cfg = new_cfg
    cfg_module.save(new_cfg)
    _register_hotkeys(new_cfg)
    _refresh_profiles_menu()
    tray.notify(f"Switched to '{name}'.")


def _refresh_profiles_menu() -> None:
    from bertytype import profiles
    with _cfg_lock:
        active = _cfg.active_profile
    tray.update_profiles_menu(
        profiles.list_profiles(),
        active,
        _on_switch_profile,
    )
```

- [ ] **Step 6: Pass `on_save_profile_as` in the `tray.start()` call and call `_refresh_profiles_menu()` after start**

Find the `tray.start(...)` call in `main()` and update it:
```python
    tray.start(
        cfg=cfg,
        on_transcribe_file=_on_transcribe_file,
        on_open_settings=_on_open_settings,
        on_quit=_on_quit,
        on_view_history=_on_view_history,
        on_save_profile_as=_on_save_profile_as,
    )
    _refresh_profiles_menu()
```

- [ ] **Step 7: Add a test for `update_profiles_menu` in `tests/test_tray.py`**

Append to `tests/test_tray.py`:
```python
def test_update_profiles_menu_no_crash_when_menu_is_none(qapp):
    import bertytype.ui.tray as t
    original = t._profiles_menu
    t._profiles_menu = None
    try:
        t.update_profiles_menu(["Work", "Personal"], "Work", lambda n: None)
        # Must not raise
    finally:
        t._profiles_menu = original
```

- [ ] **Step 8: Run all tests**

```bash
.venv/Scripts/python.exe -m pytest tests/ -v -k "not test_setup_wizard and not test_setup_installers"
```

Expected: all tests PASS.

- [ ] **Step 9: Commit**

```bash
git add src/bertytype/ui/tray.py src/bertytype/__main__.py tests/test_tray.py
git commit -m "feat: add Profiles tray submenu with save-as and switch"
```

---

## Task 13: Run the full test suite and clean up

- [ ] **Step 1: Run the complete test suite**

```bash
.venv/Scripts/python.exe -m pytest tests/ -v
```

Expected: all tests PASS (setup wizard and installer tests may be skipped if they require network access, that is acceptable).

- [ ] **Step 2: Remove the four items from TODO.md**

Replace the contents of `TODO.md` with:
```markdown
# TODO
```

(All four deferred features are now implemented.)

- [ ] **Step 3: Final commit**

```bash
git add TODO.md
git commit -m "docs: mark all deferred TODO features complete"
```
