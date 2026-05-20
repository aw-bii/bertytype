# UI Polish, Audio-Reactive Waveform, and Bug Fixes - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship audio-reactive tray waveform, Windows dark/light theme switching, easing animations, settings polish, and a set of reliability bug fixes - all without touching deferred features.

**Architecture:** Foundation-first: Task 1 builds the audio amplitude pipeline, Task 2-3 build the dark/light theme system. Tasks 4-6 layer animation and visual feedback on top. Tasks 7-10 fix bugs and add performance improvements. Each task is independently testable.

**Tech Stack:** Python, PySide6, `winreg` (Windows registry), `numpy`, `sounddevice`, `keyboard`

**Spec:** `docs/specs/2026-05-20-ui-polish-and-bug-fixes-design.md`

---

## File Map

| Action | Path | Responsibility |
| ------ | ---- | -------------- |
| Create | `src/bertytype/audio/amplitude.py` | Shared float for mic amplitude; written by capture thread, read by tray |
| Create | `src/bertytype/ui/theme_watcher.py` | Polls Windows registry for light/dark preference, emits Qt signal |
| Create | `tests/test_amplitude.py` | Tests for amplitude module |
| Create | `tests/test_theme_watcher.py` | Tests for ThemeWatcher |
| Modify | `src/bertytype/audio/capture.py` | Call `amplitude.update()` per chunk, `amplitude.reset()` after stop |
| Modify | `src/bertytype/ui/tokens.py` | Add light palette, refactor `build_qss(theme)`, fill QSS gaps, add `:pressed` states |
| Modify | `src/bertytype/ui/tray.py` | Per-bar easing, audio-reactive waveform, `set_status(reason)`, processing tooltip, completion notification |
| Modify | `src/bertytype/ui/settings.py` | Spacing constants, field error highlight, DPI-aware size, lazy load support, debounce, tab order |
| Modify | `src/bertytype/config.py` | Add `show_completion_notification: bool = True` |
| Modify | `src/bertytype/hotkeys/daemon.py` | `atexit` cleanup, registration lock, try/finally on re-register |
| Modify | `src/bertytype/__main__.py` | Wire ThemeWatcher, lazy settings dialog, atexit cleanup, completion notify |
| Modify | `tests/test_tokens.py` | Update calls to `build_qss()` to pass `"dark"` |
| Modify | `tests/test_tray.py` | Tests for easing state, reason param, amplitude |

---

## Task 1: Audio Amplitude Pipeline

**Files:**

- Create: `src/bertytype/audio/amplitude.py`
- Modify: `src/bertytype/audio/capture.py`
- Create: `tests/test_amplitude.py`

- [ ] **Step 1.1: Write failing tests**

```python
# tests/test_amplitude.py
import numpy as np
import threading
from bertytype.audio import amplitude


def test_update_computes_rms_of_sine():
    amplitude.reset()
    chunk = (np.sin(np.linspace(0, 2 * np.pi, 1000)) * 32767).astype(np.int16)
    amplitude.update(chunk)
    val = amplitude.get()
    assert 0.65 < val < 0.75  # RMS of full-amplitude sine ~= 0.707


def test_reset_sets_zero():
    chunk = np.full(100, 16000, dtype=np.int16)
    amplitude.update(chunk)
    amplitude.reset()
    assert amplitude.get() == 0.0


def test_empty_chunk_does_not_raise():
    amplitude.reset()
    amplitude.update(np.array([], dtype=np.int16))
    assert amplitude.get() == 0.0


def test_amplitude_clamped_to_one():
    chunk = np.full(100, 32767, dtype=np.int16)
    amplitude.update(chunk)
    assert amplitude.get() <= 1.0


def test_thread_safety():
    amplitude.reset()
    chunk = np.full(1000, 16383, dtype=np.int16)
    errors = []

    def writer():
        try:
            for _ in range(200):
                amplitude.update(chunk)
        except Exception as e:
            errors.append(e)

    def reader():
        try:
            for _ in range(200):
                amplitude.get()
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
```

- [ ] **Step 1.2: Run tests - expect failures**

```
.venv\Scripts\python.exe -m pytest tests/test_amplitude.py -v
```

Expected: `ModuleNotFoundError` or `ImportError` - module does not exist yet.

- [ ] **Step 1.3: Create `src/bertytype/audio/amplitude.py`**

```python
"""Shared mic amplitude state. Written by capture thread, read by tray on each tick."""
from __future__ import annotations
import threading
import numpy as np

_lock = threading.Lock()
_value: float = 0.0


def update(chunk: np.ndarray) -> None:
    """Compute RMS of int16 numpy chunk and store normalized 0.0-1.0 value."""
    if chunk.size == 0:
        return
    rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2))) / 32768.0
    global _value
    with _lock:
        _value = min(1.0, rms)


def get() -> float:
    """Return the most recently computed amplitude (0.0-1.0)."""
    with _lock:
        return _value


def reset() -> None:
    """Reset amplitude to 0.0. Call when recording stops."""
    global _value
    with _lock:
        _value = 0.0
```

- [ ] **Step 1.4: Run tests - expect all pass**

```
.venv\Scripts\python.exe -m pytest tests/test_amplitude.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 1.5: Modify `src/bertytype/audio/capture.py` to write amplitude**

Replace the entire file:

```python
import threading
import numpy as np
import sounddevice as sd
from bertytype.audio import amplitude

SAMPLE_RATE = 16000
CHANNELS = 1


def start_recording(stop_event: threading.Event, cancel_event: threading.Event | None = None) -> bytes:
    if cancel_event is not None and cancel_event.is_set():
        return b""

    frames: list[np.ndarray] = []

    def _callback(indata: np.ndarray, frame_count: int, time_info, status) -> None:
        frames.append(indata.copy())
        amplitude.update(indata)

    def _cancel_watcher() -> None:
        if cancel_event is not None:
            while not cancel_event.wait(timeout=0.05):
                pass
            stop_event.set()

    watcher = None
    if cancel_event is not None:
        watcher = threading.Thread(target=_cancel_watcher, daemon=True)
        watcher.start()

    with sd.InputStream(
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
        callback=_callback,
    ):
        stop_event.wait()

    amplitude.reset()

    if not frames:
        return b""
    return np.concatenate(frames, axis=0).tobytes()
```

- [ ] **Step 1.6: Run full test suite - no regressions**

```
.venv\Scripts\python.exe -m pytest tests/ -v
```

Expected: all existing tests pass.

- [ ] **Step 1.7: Commit**

```bash
git add src/bertytype/audio/amplitude.py src/bertytype/audio/capture.py tests/test_amplitude.py
git commit -m "feat: add audio amplitude pipeline for tray waveform"
```

---

## Task 2: Tokens - Light Palette and build_qss(theme)

**Files:**

- Modify: `src/bertytype/ui/tokens.py`
- Modify: `tests/test_tokens.py`

- [ ] **Step 2.1: Write failing tests**

Add to `tests/test_tokens.py`:

```python
def test_build_qss_dark_returns_nonempty():
    from bertytype.ui.tokens import build_qss
    result = build_qss("dark")
    assert isinstance(result, str) and len(result) > 100


def test_build_qss_light_returns_nonempty():
    from bertytype.ui.tokens import build_qss
    result = build_qss("light")
    assert isinstance(result, str) and len(result) > 100


def test_build_qss_light_contains_light_bg():
    from bertytype.ui.tokens import build_qss
    result = build_qss("light")
    assert "#f5f5f5" in result  # light background token


def test_build_qss_dark_contains_dark_bg():
    from bertytype.ui.tokens import build_qss, BG
    result = build_qss("dark")
    assert BG in result


def test_build_qss_default_is_dark():
    from bertytype.ui.tokens import build_qss, BG
    assert BG in build_qss()
```

- [ ] **Step 2.2: Run new tests - expect failures**

```
.venv\Scripts\python.exe -m pytest tests/test_tokens.py -v
```

Expected: the 5 new tests fail (signature mismatch / missing light bg token).

- [ ] **Step 2.3: Rewrite `src/bertytype/ui/tokens.py`**

```python
"""Shared color and typography tokens for the BertyType UI."""
from __future__ import annotations

# --- Dark palette constants (module-level for backward compat) ---
BG           = "#121212"
BG_ELEVATED  = "#181818"
BG_MID       = "#1f1f1f"
BORDER       = "#4d4d4d"
BORDER_LIGHT = "#7c7c7c"
TEXT           = "#ffffff"
TEXT_SECONDARY = "#b3b3b3"
TEXT_DIM       = "#909090"   # lightened from #888 for better AA margin
ACCENT       = "#1ed760"
ACCENT_HVR   = "#22e865"
DESTRUCTIVE  = "#f3727f"
WARNING      = "#ffa42b"
ANNOUNCEMENT = "#539df5"
SWITCH_TRACK = "#4d4d4d"

STATUS_COLORS: dict[str, str] = {
    "idle":       ACCENT,
    "recording":  DESTRUCTIVE,
    "processing": WARNING,
    "error":      TEXT_DIM,
}

FONT_FAMILY = "Segoe UI"
FONT = ("Segoe UI", 11)


def _dark_palette() -> dict:
    return dict(
        bg=BG, bg_elevated=BG_ELEVATED, bg_mid=BG_MID,
        border=BORDER, border_light=BORDER_LIGHT,
        text=TEXT, text_secondary=TEXT_SECONDARY, text_dim=TEXT_DIM,
        accent=ACCENT, accent_hvr=ACCENT_HVR, accent_pressed="#18a348",
        destructive=DESTRUCTIVE, switch_track=SWITCH_TRACK,
        font_family=FONT_FAMILY,
    )


def _light_palette() -> dict:
    return dict(
        bg="#f5f5f5", bg_elevated="#ffffff", bg_mid="#ebebeb",
        border="#d4d4d4", border_light="#999999",
        text="#121212", text_secondary="#555555", text_dim="#6b6b6b",
        accent=ACCENT, accent_hvr=ACCENT_HVR, accent_pressed="#18a348",
        destructive=DESTRUCTIVE, switch_track="#c7c7c7",
        font_family=FONT_FAMILY,
    )


def build_qss(theme: str = "dark") -> str:
    p = _light_palette() if theme == "light" else _dark_palette()
    return f"""
    * {{
        font-family: "{p['font_family']}";
    }}
    QDialog, QWizard {{
        background: {p['bg']};
        color: {p['text']};
        font-size: 13px;
    }}
    QLabel {{
        color: {p['text']};
        background: transparent;
    }}
    QToolTip {{
        background: {p['bg_elevated']};
        color: {p['text']};
        border: 1px solid {p['border']};
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 12px;
    }}
    QLineEdit, QKeySequenceEdit {{
        background: {p['bg_mid']};
        border: 1px solid {p['border']};
        border-radius: 500px;
        padding: 6px 14px;
        color: {p['text']};
        font-size: 13px;
    }}
    QLineEdit:focus, QKeySequenceEdit:focus {{
        border-color: {p['border_light']};
    }}
    QComboBox {{
        background: {p['bg_mid']};
        border: 1px solid {p['border']};
        border-radius: 500px;
        padding: 6px 14px;
        color: {p['text']};
        font-size: 13px;
    }}
    QComboBox:hover {{
        border-color: {p['border_light']};
    }}
    QComboBox:focus {{
        border-color: {p['accent']};
    }}
    QComboBox::drop-down {{
        border: none;
        padding-right: 10px;
    }}
    QComboBox QAbstractItemView {{
        background: {p['bg_elevated']};
        border: 1px solid {p['border']};
        color: {p['text']};
        selection-background-color: {p['bg_mid']};
    }}
    QComboBox QAbstractItemView::item:hover {{
        background: {p['bg_mid']};
    }}
    QSlider::groove:horizontal {{
        background: {p['bg_mid']};
        height: 4px;
        border-radius: 2px;
    }}
    QSlider::handle:horizontal {{
        background: {p['accent']};
        width: 11px;
        height: 11px;
        margin: -4px 0;
        border-radius: 5px;
    }}
    QSlider::handle:horizontal:pressed {{
        background: {p['accent_hvr']};
        width: 14px;
        height: 14px;
        margin: -5px 0;
    }}
    QSlider::sub-page:horizontal {{
        background: {p['accent']};
        border-radius: 2px;
    }}
    QPushButton {{
        background: {p['bg_mid']};
        border: 1px solid {p['border']};
        border-radius: 9999px;
        padding: 8px 20px;
        color: {p['text']};
        font-size: 13px;
        font-weight: 700;
    }}
    QPushButton:hover {{
        border-color: {p['text']};
    }}
    QPushButton:focus {{
        border-color: {p['accent']};
        outline: none;
    }}
    QPushButton:pressed {{
        background: {p['bg']};
    }}
    QPushButton[accent="true"] {{
        background: {p['accent']};
        border: none;
        color: {p['bg']};
        font-weight: 700;
    }}
    QPushButton[accent="true"]:hover {{
        background: {p['accent_hvr']};
    }}
    QPushButton[accent="true"]:pressed {{
        background: {p['accent_pressed']};
    }}
    QCheckBox {{
        color: {p['text']};
        spacing: 8px;
    }}
    QCheckBox::indicator {{
        width: 38px;
        height: 20px;
        border-radius: 10px;
    }}
    QCheckBox::indicator:unchecked {{
        background: {p['switch_track']};
    }}
    QCheckBox::indicator:checked {{
        background: {p['accent']};
    }}
    QCheckBox:focus {{
        outline: 1px dotted {p['accent']};
    }}
    QScrollArea, QScrollArea > QWidget > QWidget {{
        background: {p['bg']};
        border: none;
    }}
    QScrollBar:vertical {{
        background: {p['bg']};
        width: 8px;
    }}
    QScrollBar::handle:vertical {{
        background: {p['border']};
        border-radius: 4px;
        min-height: 20px;
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0;
    }}
    QScrollBar:horizontal {{
        background: {p['bg']};
        height: 8px;
    }}
    QScrollBar::handle:horizontal {{
        background: {p['border']};
        border-radius: 4px;
        min-width: 20px;
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0;
    }}
    QPlainTextEdit {{
        background: {p['bg_elevated']};
        border: 1px solid {p['border']};
        border-radius: 6px;
        color: {p['text_secondary']};
        font-size: 12px;
    }}
    QProgressBar {{
        background: {p['bg_elevated']};
        border: none;
        border-radius: 4px;
        height: 8px;
        color: transparent;
    }}
    QProgressBar::chunk {{
        background: {p['accent']};
        border-radius: 4px;
    }}
    QWizard QPushButton {{
        min-width: 80px;
    }}
    """
```

- [ ] **Step 2.4: Update existing token tests to pass `"dark"` explicitly**

In `tests/test_tokens.py`, update the original 5 tests:

```python
def test_build_qss_returns_nonempty_string():
    from bertytype.ui.tokens import build_qss
    result = build_qss("dark")
    assert isinstance(result, str)
    assert len(result) > 100


def test_build_qss_contains_bg_token():
    from bertytype.ui.tokens import build_qss, BG
    assert BG in build_qss("dark")


def test_build_qss_contains_accent_token():
    from bertytype.ui.tokens import build_qss, ACCENT
    assert ACCENT in build_qss("dark")


def test_build_qss_contains_border_token():
    from bertytype.ui.tokens import build_qss, BORDER
    assert BORDER in build_qss("dark")


def test_build_qss_contains_text_token():
    from bertytype.ui.tokens import build_qss, TEXT
    assert TEXT in build_qss("dark")
```

- [ ] **Step 2.5: Run all token tests**

```
.venv\Scripts\python.exe -m pytest tests/test_tokens.py -v
```

Expected: all 10 tests PASS.

- [ ] **Step 2.6: Update `__main__.py` line 254 to pass theme**

In `src/bertytype/__main__.py`, find:

```python
    app.setStyleSheet(tokens.build_qss())
```

Replace with:

```python
    app.setStyleSheet(tokens.build_qss("dark"))
```

(ThemeWatcher in Task 3 will update this dynamically.)

- [ ] **Step 2.7: Run full test suite - no regressions**

```
.venv\Scripts\python.exe -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 2.8: Commit**

```bash
git add src/bertytype/ui/tokens.py tests/test_tokens.py src/bertytype/__main__.py
git commit -m "feat: add light palette and build_qss(theme) with QSS gap fill"
```

---

## Task 3: ThemeWatcher

**Files:**

- Create: `src/bertytype/ui/theme_watcher.py`
- Modify: `src/bertytype/__main__.py`
- Create: `tests/test_theme_watcher.py`

- [ ] **Step 3.1: Write failing tests**

```python
# tests/test_theme_watcher.py
from unittest.mock import patch


def test_current_theme_defaults_to_dark_on_registry_error(qapp):
    from bertytype.ui.theme_watcher import ThemeWatcher
    with patch.object(ThemeWatcher, "_read_theme", return_value="dark"):
        watcher = ThemeWatcher()
        assert watcher.current_theme() == "dark"
        watcher.stop()


def test_current_theme_returns_light_when_set(qapp):
    from bertytype.ui.theme_watcher import ThemeWatcher
    with patch.object(ThemeWatcher, "_read_theme", return_value="light"):
        watcher = ThemeWatcher()
        assert watcher.current_theme() == "light"
        watcher.stop()


def test_theme_changed_emits_on_switch(qapp):
    from bertytype.ui.theme_watcher import ThemeWatcher
    from PySide6.QtCore import QCoreApplication

    # Starts dark, then _check sees light
    call_seq = ["dark", "light"]
    call_iter = iter(call_seq)
    with patch.object(ThemeWatcher, "_read_theme", side_effect=lambda: next(call_iter)):
        watcher = ThemeWatcher()
        received = []
        watcher.theme_changed.connect(received.append)
        watcher._check()
        QCoreApplication.processEvents()
        assert received == ["light"]
        watcher.stop()


def test_theme_changed_does_not_emit_when_unchanged(qapp):
    from bertytype.ui.theme_watcher import ThemeWatcher
    from PySide6.QtCore import QCoreApplication
    with patch.object(ThemeWatcher, "_read_theme", return_value="dark"):
        watcher = ThemeWatcher()
        received = []
        watcher.theme_changed.connect(received.append)
        watcher._check()
        QCoreApplication.processEvents()
        assert received == []
        watcher.stop()


def test_stop_stops_timer(qapp):
    from bertytype.ui.theme_watcher import ThemeWatcher
    with patch.object(ThemeWatcher, "_read_theme", return_value="dark"):
        watcher = ThemeWatcher()
        watcher.stop()
        assert not watcher._timer.isActive()
```

- [ ] **Step 3.2: Run tests - expect failures**

```
.venv\Scripts\python.exe -m pytest tests/test_theme_watcher.py -v
```

Expected: `ModuleNotFoundError` - module does not exist yet.

- [ ] **Step 3.3: Create `src/bertytype/ui/theme_watcher.py`**

```python
"""Polls the Windows registry for light/dark theme preference every 2 seconds."""
from __future__ import annotations
from PySide6.QtCore import QObject, QTimer, Signal

try:
    import winreg
    _HAS_WINREG = True
except ImportError:
    _HAS_WINREG = False


class ThemeWatcher(QObject):
    theme_changed = Signal(str)  # emits "dark" or "light"

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current = self._read_theme()
        self._timer = QTimer(self)
        self._timer.setInterval(2000)
        self._timer.timeout.connect(self._check)
        self._timer.start()

    @staticmethod
    def _read_theme() -> str:
        if not _HAS_WINREG:
            return "dark"
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return "light" if value == 1 else "dark"
        except OSError:
            return "dark"

    def _check(self) -> None:
        new = self._read_theme()
        if new != self._current:
            self._current = new
            self.theme_changed.emit(new)

    def current_theme(self) -> str:
        return self._current

    def stop(self) -> None:
        self._timer.stop()
```

- [ ] **Step 3.4: Run ThemeWatcher tests**

```
.venv\Scripts\python.exe -m pytest tests/test_theme_watcher.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 3.5: Wire ThemeWatcher into `__main__.py`**

In `src/bertytype/__main__.py`, add import at top with other ui imports:

```python
from bertytype.ui import tray, settings, tokens
from bertytype.ui.theme_watcher import ThemeWatcher
```

Add module-level variable after `_health_lock`:

```python
_theme_watcher: ThemeWatcher | None = None
```

In the `main()` function, after `app.setStyleSheet(tokens.build_qss("dark"))`, add:

```python
    global _theme_watcher
    _theme_watcher = ThemeWatcher()

    def _on_theme_changed(theme: str) -> None:
        app.setStyleSheet(tokens.build_qss(theme))

    _theme_watcher.theme_changed.connect(_on_theme_changed)
    app.setStyleSheet(tokens.build_qss(_theme_watcher.current_theme()))
```

Also update `_on_quit()` to stop the watcher:

```python
def _on_quit() -> None:
    _quit_event.set()
    if _theme_watcher is not None:
        _theme_watcher.stop()
    llm_client.shutdown()
    hotkey_daemon.stop()
    tray.stop()
    app = QApplication.instance()
    if app is not None:
        app.quit()
```

- [ ] **Step 3.6: Run full test suite**

```
.venv\Scripts\python.exe -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 3.7: Commit**

```bash
git add src/bertytype/ui/theme_watcher.py tests/test_theme_watcher.py src/bertytype/__main__.py
git commit -m "feat: add ThemeWatcher for Windows dark/light system theme switching"
```

---

## Task 4: Tray - Easing Curves and Audio-Reactive Waveform

**Files:**

- Modify: `src/bertytype/ui/tray.py`
- Modify: `tests/test_tray.py`

- [ ] **Step 4.1: Write failing tests**

Add to `tests/test_tray.py`:

```python
def test_current_heights_initialized_to_idle(qapp):
    import bertytype.ui.tray as t
    assert len(t._current_heights) == 5
    assert t._current_heights[2] > t._current_heights[0]  # center taller than edge


def test_tick_lerps_heights_toward_target(qapp):
    import bertytype.ui.tray as t
    from bertytype.ui.tray import _get_target_heights
    # Force all current heights to 0
    t._current_heights = [0.0] * 5
    t._status = "idle"
    targets = _get_target_heights("idle", 0, 0.0)
    t._tick_animation()
    # After one lerp step, heights should have moved toward target
    for i in range(5):
        assert t._current_heights[i] > 0.0
        assert t._current_heights[i] < targets[i]


def test_recording_targets_use_amplitude(qapp):
    from bertytype.ui.tray import _get_target_heights
    targets_loud = _get_target_heights("recording", 0, 1.0)
    targets_quiet = _get_target_heights("recording", 0, 0.0)
    # Loud recording should produce taller bars than quiet
    assert sum(targets_loud) > sum(targets_quiet)


def test_error_targets_are_flat(qapp):
    from bertytype.ui.tray import _get_target_heights
    targets = _get_target_heights("error", 0, 0.0)
    assert all(h == targets[0] for h in targets)
    assert targets[0] < 15  # flat and short
```

- [ ] **Step 4.2: Run new tests - expect failures**

```
.venv\Scripts\python.exe -m pytest tests/test_tray.py -v -k "heights or lerps or amplitude or flat"
```

Expected: failures - `_current_heights`, `_get_target_heights` do not exist yet.

- [ ] **Step 4.3: Rewrite `src/bertytype/ui/tray.py`**

Replace the entire file:

```python
from __future__ import annotations
from typing import Callable
from PySide6.QtCore import QObject, QTimer, Signal, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap, QColor
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from bertytype.ui.tokens import STATUS_COLORS as _STATUS_COLORS

_PROCESSING_FRAMES: list[list[int]] = [
    [12, 44, 28, 52, 20],
    [20, 12, 44, 28, 52],
    [52, 20, 12, 44, 28],
    [28, 52, 20, 12, 44],
    [44, 28, 52, 20, 12],
]

_BAR_WIDTH = 8
_BAR_GAP   = 4
_CANVAS    = 64
_LERP_FACTOR = 0.35
_BAR_FLOOR   = 10.0
_BAR_CEILING = 58.0
_BAR_MULTIPLIERS = [0.6, 0.85, 1.0, 0.85, 0.6]
_NOISE_PRIMES    = [17, 19, 23, 29, 31]

_STATUS_LABELS: dict[str, str] = {
    "idle":       "Idle - hold hotkey to record",
    "recording":  "Recording...",
    "processing": "Processing...",
    "error":      "Error - check logs",
}


class _TraySignals(QObject):
    status_changed   = Signal(str)
    notify_requested = Signal(str)


_signals    = _TraySignals()
_tray_icon: QSystemTrayIcon | None = None
_status     = "idle"
_anim_frame = 0
_anim_timer: QTimer | None = None
_error_timer: QTimer | None = None
_last_error: str = ""
_llm_model: str = ""
_current_heights: list[float] = [16.0, 32.0, 48.0, 32.0, 16.0]


def _dpr() -> float:
    app = QApplication.instance()
    if app:
        screen = app.primaryScreen()
        if screen:
            return screen.devicePixelRatio()
    return 1.0


def _make_icon(bar_heights: list[float], color_hex: str) -> QIcon:
    dpr = _dpr()
    size = int(_CANVAS * dpr)
    px = QPixmap(size, size)
    px.setDevicePixelRatio(dpr)
    px.fill(Qt.GlobalColor.transparent)
    painter = QPainter(px)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(color_hex))
    painter.setPen(Qt.PenStyle.NoPen)
    total_w = len(bar_heights) * _BAR_WIDTH + (len(bar_heights) - 1) * _BAR_GAP
    x_start = (_CANVAS - total_w) // 2
    for i, bar_h in enumerate(bar_heights):
        h = max(2, round(bar_h))
        x = x_start + i * (_BAR_WIDTH + _BAR_GAP)
        y_top = (_CANVAS - h) // 2
        painter.drawRoundedRect(x, y_top, _BAR_WIDTH, h, 2, 2)
    painter.end()
    return QIcon(px)


def _get_target_heights(status: str, frame: int, amplitude: float) -> list[float]:
    if status == "recording":
        heights = []
        for i in range(5):
            noise = (frame * _NOISE_PRIMES[i]) % 7 - 3
            h = _BAR_FLOOR + (_BAR_CEILING - _BAR_FLOOR) * amplitude * _BAR_MULTIPLIERS[i] + noise
            heights.append(max(_BAR_FLOOR, min(_BAR_CEILING, h)))
        return heights
    if status == "processing":
        return [float(h) for h in _PROCESSING_FRAMES[frame % len(_PROCESSING_FRAMES)]]
    if status == "error":
        return [8.0] * 5
    return [16.0, 32.0, 48.0, 32.0, 16.0]  # idle


def _tick_animation() -> None:
    global _anim_frame, _current_heights
    if _tray_icon is None:
        return
    if _status == "processing":
        _anim_frame = (_anim_frame + 1) % len(_PROCESSING_FRAMES)

    from bertytype.audio import amplitude as amp_module
    amp = amp_module.get() if _status == "recording" else 0.0
    targets = _get_target_heights(_status, _anim_frame, amp)

    settled = True
    for i in range(5):
        diff = targets[i] - _current_heights[i]
        _current_heights[i] += diff * _LERP_FACTOR
        if abs(diff) > 0.5:
            settled = False

    color_hex = _STATUS_COLORS.get(_status, _STATUS_COLORS["error"])
    _tray_icon.setIcon(_make_icon(_current_heights, color_hex))

    if settled and _status not in ("processing", "recording"):
        if _anim_timer is not None:
            _anim_timer.stop()


def _recover_from_error() -> None:
    set_status("idle")


def _on_status_changed(status: str) -> None:
    global _status, _anim_frame
    _status = status
    _anim_frame = 0
    if _tray_icon is not None:
        if status == "processing" and _llm_model:
            label = f"Processing with {_llm_model}..."
        elif status == "error":
            label = f"Error - {_last_error}" if _last_error else _STATUS_LABELS["error"]
        else:
            label = _STATUS_LABELS.get(status, status.capitalize())
        _tray_icon.setToolTip(f"BertyType - {label}")
    if _anim_timer is not None:
        _anim_timer.start(200)  # always restart for easing
    if _error_timer is not None:
        if status == "error":
            _error_timer.start()
        else:
            _error_timer.stop()


def _on_notify_requested(msg: str) -> None:
    if _tray_icon is not None:
        _tray_icon.showMessage("BertyType", msg, QSystemTrayIcon.MessageIcon.NoIcon, 3000)


def set_status(status: str, *, reason: str = "") -> None:
    global _last_error
    if status == "error" and reason:
        _last_error = reason
    if status != _status:
        _signals.status_changed.emit(status)


def notify(msg: str) -> None:
    _signals.notify_requested.emit(msg)


def start(
    cfg,
    on_transcribe_file: Callable[[], None],
    on_open_settings: Callable[[], None],
    on_quit: Callable[[], None],
) -> None:
    global _tray_icon, _anim_timer, _error_timer, _llm_model
    _llm_model = cfg.model
    _signals.status_changed.connect(
        _on_status_changed, Qt.ConnectionType.QueuedConnection | Qt.ConnectionType.UniqueConnection
    )
    _signals.notify_requested.connect(
        _on_notify_requested, Qt.ConnectionType.QueuedConnection | Qt.ConnectionType.UniqueConnection
    )
    menu = QMenu()
    menu.addAction("Transcribe file...", on_transcribe_file)
    menu.addAction("Settings", on_open_settings)
    menu.addSeparator()
    menu.addAction("Quit", on_quit)
    icon = QSystemTrayIcon()
    color_hex = _STATUS_COLORS["idle"]
    icon.setIcon(_make_icon(_current_heights, color_hex))
    icon.setToolTip(f"BertyType - {_STATUS_LABELS['idle']}")
    icon.setContextMenu(menu)
    icon.show()
    _tray_icon = icon
    _anim_timer = QTimer()
    _anim_timer.setInterval(200)
    _anim_timer.timeout.connect(_tick_animation)
    _error_timer = QTimer()
    _error_timer.setSingleShot(True)
    _error_timer.setInterval(30_000)
    _error_timer.timeout.connect(_recover_from_error)


def stop() -> None:
    global _tray_icon, _anim_timer, _error_timer
    if _anim_timer is not None:
        _anim_timer.stop()
        _anim_timer = None
    if _error_timer is not None:
        _error_timer.stop()
        _error_timer = None
    if _tray_icon is not None:
        _tray_icon.hide()
        _tray_icon = None
```

- [ ] **Step 4.4: Run all tray tests**

```
.venv\Scripts\python.exe -m pytest tests/test_tray.py -v
```

Expected: all tests pass (new and existing).

- [ ] **Step 4.5: Run full test suite**

```
.venv\Scripts\python.exe -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 4.6: Commit**

```bash
git add src/bertytype/ui/tray.py tests/test_tray.py
git commit -m "feat: add easing curves and audio-reactive waveform to tray icon"
```

---

## Task 5: Tray - Completion Notification and Processing Tooltip

**Files:**

- Modify: `src/bertytype/config.py`
- Modify: `src/bertytype/__main__.py`

- [ ] **Step 5.1: Write failing tests**

Add to `tests/test_tray.py`:

```python
def test_set_status_stores_error_reason(qapp):
    import bertytype.ui.tray as t
    original_last = t._last_error
    original_status = t._status
    try:
        t._status = "idle"
        t.set_status("error", reason="mic disconnected")
        assert t._last_error == "mic disconnected"
    finally:
        t._last_error = original_last
        t._status = original_status


def test_set_status_reason_only_stored_for_error(qapp):
    import bertytype.ui.tray as t
    original_last = t._last_error
    original_status = t._status
    try:
        t._last_error = "old"
        t._status = "error"
        t.set_status("idle", reason="should be ignored")
        assert t._last_error == "old"
    finally:
        t._last_error = original_last
        t._status = original_status
```

Add to `tests/test_config.py` (or a new block at the end of the existing file):

```python
def test_show_completion_notification_defaults_true():
    from bertytype.config import Config
    assert Config().show_completion_notification is True


def test_show_completion_notification_round_trips():
    from bertytype.config import Config, save, load
    import tempfile, os
    from unittest.mock import patch
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "config.json")
        with patch("bertytype.config.CONFIG_PATH", __import__("pathlib").Path(path)):
            cfg = Config(show_completion_notification=False)
            save(cfg)
            loaded = load()
            assert loaded.show_completion_notification is False
```

- [ ] **Step 5.2: Run new tests - expect failures**

```
.venv\Scripts\python.exe -m pytest tests/test_tray.py -v -k "reason" && .venv\Scripts\python.exe -m pytest tests/test_config.py -v -k "notification"
```

Expected: failures - `reason` kwarg not accepted / `show_completion_notification` not on Config.

- [ ] **Step 5.3: Add `show_completion_notification` to `src/bertytype/config.py`**

In the `Config` dataclass, add the new field after `injection_delay`:

```python
@dataclass
class Config:
    hotkey: str = "alt"
    cancel_hotkey: str = "escape"
    model: str = "gemma4:e2b"
    refine: bool = True
    vad_threshold: float = 0.02
    hotkey_mode: str = "double_tap_toggle"
    double_tap_window: float = 0.3
    llm_timeout: int = 30
    injection_delay: float = 0.05
    show_completion_notification: bool = True
```

In `_validate_value()`, add handling for the new key after the `injection_delay` branch:

```python
    elif key == "show_completion_notification":
        if not isinstance(value, bool):
            logger.warning(f"Invalid show_completion_notification: {value!r}, using default {default!r}")
            return default
```

- [ ] **Step 5.4: Add completion notify call in `__main__.py`**

In `_capture_and_process()`, find the injection block and add the notify call:

```python
        try:
            injector.inject(text, cfg.injection_delay)
            if cfg.show_completion_notification:
                preview = text[:60] + ("..." if len(text) > 60 else "")
                tray.notify(f"Typed: {preview}")
        except Exception as e:
            logger.warning(f"Injection failed: {e}")
            pyperclip.copy(text)
            tray.notify(messages.ERROR_INJECTION_FAILED)
        tray.set_status("idle")
```

- [ ] **Step 5.5: Run all tests**

```
.venv\Scripts\python.exe -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 5.6: Commit**

```bash
git add src/bertytype/config.py src/bertytype/__main__.py tests/test_tray.py tests/test_config.py
git commit -m "feat: add completion notification and error-reason tooltip to tray"
```

---

## Task 6: Hotkey Registration Bug Fix

**Files:**

- Modify: `src/bertytype/hotkeys/daemon.py`
- Modify: `src/bertytype/__main__.py`

- [ ] **Step 6.1: Write failing tests**

Add to `tests/test_hotkeys.py` (read it first to avoid duplicates, then add):

```python
def test_stop_is_idempotent():
    """Calling stop() twice must not raise."""
    from bertytype.hotkeys import daemon
    from unittest.mock import patch
    with patch("keyboard.unhook_all") as mock_unhook:
        daemon.stop()
        daemon.stop()
        assert mock_unhook.call_count == 2


def test_register_uses_lock():
    """Concurrent register calls must not interleave."""
    from bertytype.hotkeys import daemon
    from unittest.mock import patch
    import threading
    call_order = []
    original_add = __import__("keyboard").add_hotkey

    def slow_add(hotkey, *args, **kwargs):
        call_order.append(f"start:{hotkey}")
        __import__("time").sleep(0.01)
        call_order.append(f"end:{hotkey}")

    with patch("keyboard.add_hotkey", side_effect=slow_add):
        t1 = threading.Thread(target=daemon.register, args=("ctrl+a", lambda: None))
        t2 = threading.Thread(target=daemon.register, args=("ctrl+b", lambda: None))
        t1.start(); t2.start()
        t1.join(); t2.join()

    # Each start should be immediately followed by its own end (no interleaving)
    for idx in range(0, len(call_order) - 1, 2):
        key = call_order[idx].split(":")[1]
        assert call_order[idx + 1] == f"end:{key}"
```

- [ ] **Step 6.2: Run new tests - expect failures**

```
.venv\Scripts\python.exe -m pytest tests/test_hotkeys.py -v -k "idempotent or lock"
```

Expected: test_register_uses_lock fails (no lock exists yet).

- [ ] **Step 6.3: Rewrite `src/bertytype/hotkeys/daemon.py`**

```python
from __future__ import annotations
import atexit
import threading
from typing import Callable
import keyboard

_lock = threading.Lock()


@atexit.register
def _atexit_cleanup() -> None:
    keyboard.unhook_all()


def register(hotkey: str, callback: Callable[[], None]) -> None:
    with _lock:
        keyboard.add_hotkey(hotkey, callback)


def register_ptt(
    hotkey: str,
    on_press: Callable[[], None],
    on_release: Callable[[], None],
) -> None:
    with _lock:
        keyboard.add_hotkey(hotkey, on_press, suppress=True, trigger_on_release=False)
        keyboard.add_hotkey(hotkey, on_release, suppress=True, trigger_on_release=True)


def register_double_tap_toggle(
    key: str,
    on_start: Callable[[], None],
    on_stop: Callable[[], None],
    window: float = 0.3,
) -> None:
    import time
    state: dict = {"last_tap": 0.0, "recording": False}

    def _handler(_event) -> None:
        now = time.monotonic()
        delta = now - state["last_tap"]
        if 0 < delta <= window:
            state["last_tap"] = 0.0
            if not state["recording"]:
                state["recording"] = True
                on_start()
            else:
                state["recording"] = False
                on_stop()
        else:
            state["last_tap"] = now

    with _lock:
        keyboard.on_press_key(key, _handler)


def stop() -> None:
    with _lock:
        keyboard.unhook_all()
```

- [ ] **Step 6.4: Add try/finally to `_register_hotkeys` in `__main__.py`**

Find `_register_hotkeys` and replace:

```python
def _register_hotkeys(cfg: cfg_module.Config) -> None:
    _stop_event.set()
    hotkey_daemon.stop()
    try:
        if cfg.hotkey_mode == "double_tap_toggle":
            hotkey_daemon.register_double_tap_toggle(
                cfg.hotkey,
                on_start=_on_ptt_press,
                on_stop=_on_ptt_release,
                window=cfg.double_tap_window,
            )
        else:
            hotkey_daemon.register_ptt(
                cfg.hotkey,
                on_press=_on_ptt_press,
                on_release=_on_ptt_release,
            )
        hotkey_daemon.register(cfg.cancel_hotkey, _on_cancel)
    except Exception:
        hotkey_daemon.stop()
        raise
```

- [ ] **Step 6.5: Run all tests**

```
.venv\Scripts\python.exe -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 6.6: Commit**

```bash
git add src/bertytype/hotkeys/daemon.py src/bertytype/__main__.py tests/test_hotkeys.py
git commit -m "fix: add atexit cleanup and lock to hotkey daemon"
```

---

## Task 7: Memory Leaks and Unified Exit Cleanup

**Files:**

- Modify: `src/bertytype/__main__.py`

- [ ] **Step 7.1: Write failing tests**

Add to `tests/test_main_shutdown.py` (read existing file first, then add):

```python
def test_cleanup_sets_quit_event():
    import importlib
    import bertytype.__main__ as main_mod
    from unittest.mock import patch, MagicMock
    with patch.object(main_mod, "llm_client") as mock_llm, \
         patch.object(main_mod, "hotkey_daemon") as mock_hk, \
         patch.object(main_mod, "tray") as mock_tray:
        main_mod._quit_event.clear()
        main_mod._cleanup()
        assert main_mod._quit_event.is_set()


def test_cleanup_stops_subsystems_in_order():
    import bertytype.__main__ as main_mod
    from unittest.mock import patch, MagicMock, call
    call_log = []
    with patch.object(main_mod, "llm_client") as m_llm, \
         patch.object(main_mod, "hotkey_daemon") as m_hk, \
         patch.object(main_mod, "tray") as m_tray:
        m_llm.shutdown.side_effect = lambda: call_log.append("llm")
        m_hk.stop.side_effect = lambda: call_log.append("hk")
        m_tray.stop.side_effect = lambda: call_log.append("tray")
        main_mod._cleanup()
    assert call_log == ["llm", "hk", "tray"]


def test_cleanup_survives_subsystem_exception():
    import bertytype.__main__ as main_mod
    from unittest.mock import patch
    with patch.object(main_mod, "llm_client") as m_llm, \
         patch.object(main_mod, "hotkey_daemon") as m_hk, \
         patch.object(main_mod, "tray") as m_tray:
        m_llm.shutdown.side_effect = RuntimeError("crash")
        main_mod._cleanup()  # must not raise
```

- [ ] **Step 7.2: Run new tests - expect failures**

```
.venv\Scripts\python.exe -m pytest tests/test_main_shutdown.py -v -k "cleanup"
```

Expected: `AttributeError` - `_cleanup` does not exist yet.

- [ ] **Step 7.3: Add `_cleanup` to `__main__.py`**

Add this function before `_on_quit`:

```python
import atexit

def _cleanup() -> None:
    _quit_event.set()
    for fn, name in [
        (llm_client.shutdown, "llm_client"),
        (hotkey_daemon.stop, "hotkey_daemon"),
        (tray.stop, "tray"),
    ]:
        try:
            fn()
        except Exception as e:
            logger.warning(f"Cleanup error in {name}: {e}")

atexit.register(_cleanup)
```

Update `_on_quit()` to call `_cleanup()` instead of repeating the logic:

```python
def _on_quit() -> None:
    if _theme_watcher is not None:
        _theme_watcher.stop()
    _cleanup()
    app = QApplication.instance()
    if app is not None:
        app.quit()
```

- [ ] **Step 7.4: Run all tests**

```
.venv\Scripts\python.exe -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 7.5: Commit**

```bash
git add src/bertytype/__main__.py tests/test_main_shutdown.py
git commit -m "fix: add unified _cleanup() with atexit registration and subsystem ordering"
```

---

## Task 8: Settings - Spacing, Error Field Highlighting, DPI Scaling

**Files:**

- Modify: `src/bertytype/ui/settings.py`
- Modify: `tests/test_settings.py`

- [ ] **Step 8.1: Write failing tests**

Add to `tests/test_settings.py`:

```python
def test_dialog_minimum_width_scales_with_dpi(qapp):
    from bertytype.ui.settings import _SettingsDialog
    from bertytype.config import Config
    from PySide6.QtWidgets import QApplication
    cfg = Config()
    dlg = _SettingsDialog(cfg, on_save=lambda c: None)
    dpi = QApplication.primaryScreen().logicalDotsPerInch()
    expected_min = int(480 * (dpi / 96.0))
    assert dlg.minimumWidth() >= expected_min - 1  # allow rounding
    dlg.close()


def test_invalid_hotkey_highlights_field(qapp):
    from bertytype.ui.settings import _SettingsDialog
    from bertytype.config import Config
    from PySide6.QtGui import QKeySequence
    cfg = Config()
    dlg = _SettingsDialog(cfg, on_save=lambda c: None)
    dlg._hotkey_edit.setKeySequence(QKeySequence())
    dlg._save()
    # The hotkey edit should have a red left-border applied
    style = dlg._hotkey_edit.styleSheet()
    assert "#f3727f" in style or "f3727f" in style.lower()
    dlg.close()


def test_error_highlight_clears_on_valid_save(qapp):
    from bertytype.ui.settings import _SettingsDialog
    from bertytype.config import Config
    from PySide6.QtGui import QKeySequence
    saved = []
    cfg = Config()
    dlg = _SettingsDialog(cfg, on_save=saved.append)
    # First: trigger error
    dlg._hotkey_edit.setKeySequence(QKeySequence())
    dlg._save()
    assert "#f3727f" in dlg._hotkey_edit.styleSheet()
    # Then: fix and save
    from bertytype.ui.settings import _str_to_qks
    dlg._hotkey_edit.setKeySequence(_str_to_qks("alt"))
    dlg._save()
    # Highlight should be cleared
    assert "#f3727f" not in dlg._hotkey_edit.styleSheet()
```

- [ ] **Step 8.2: Run new tests - expect failures**

```
.venv\Scripts\python.exe -m pytest tests/test_settings.py -v -k "dpi or highlight or clear"
```

Expected: failures - DPI scaling not implemented, field highlighting not implemented.

- [ ] **Step 8.3: Rewrite `src/bertytype/ui/settings.py`**

Replace the entire file:

```python
from __future__ import annotations
from typing import Callable
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QApplication, QDialog, QFormLayout, QScrollArea, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QComboBox, QKeySequenceEdit, QCheckBox,
    QSlider, QLineEdit, QPushButton, QFrame,
)
from bertytype.config import Config, _is_safe_model_name, _VALID_HOTKEY_MODES
from bertytype.ui.tokens import TEXT_SECONDARY, DESTRUCTIVE

_FORM_H_MARGIN = 18
_FORM_V_MARGIN = 20
_FORM_ROW_SPACING = 12
_BASE_MIN_WIDTH = 480


def _qks_to_str(ks: QKeySequence) -> str:
    return ks.toString(QKeySequence.SequenceFormat.PortableText).lower()


def _str_to_qks(s: str) -> QKeySequence:
    return QKeySequence.fromString(s, QKeySequence.SequenceFormat.PortableText)


def open_settings(cfg: Config, on_save: Callable[[Config], None]) -> None:
    dlg = _SettingsDialog(cfg, on_save)
    dlg.exec()


class _SettingsDialog(QDialog):
    def __init__(self, cfg: Config, on_save: Callable[[Config], None]) -> None:
        super().__init__()
        self.setWindowTitle("BertyType Settings")
        dpi = QApplication.primaryScreen().logicalDotsPerInch()
        min_w = int(_BASE_MIN_WIDTH * (dpi / 96.0))
        self.setMinimumSize(min_w, 400)
        self._on_save = on_save
        self._error_fields: list[QWidget] = []
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(150)
        self._build_ui(cfg)
        self._setup_tab_order()
        self._hotkey_edit.setFocus()

    def _build_ui(self, cfg: Config) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setContentsMargins(_FORM_H_MARGIN, _FORM_V_MARGIN, _FORM_H_MARGIN, _FORM_V_MARGIN)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(_FORM_ROW_SPACING)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(sorted(_VALID_HOTKEY_MODES))
        self._mode_combo.setCurrentText(cfg.hotkey_mode)
        self._mode_combo.setToolTip("ptt: hold to record / double_tap_toggle: tap twice to toggle recording")
        form.addRow("Recording Mode", self._mode_combo)

        self._hotkey_edit = QKeySequenceEdit(_str_to_qks(cfg.hotkey))
        self._hotkey_edit.setToolTip("Press the key combination to use as your push-to-talk hotkey")
        form.addRow("Hotkey", self._hotkey_edit)

        self._dtw_slider = QSlider(Qt.Orientation.Horizontal)
        self._dtw_slider.setRange(5, 200)
        self._dtw_slider.setValue(round(cfg.double_tap_window * 100))
        self._dtw_slider.setToolTip("Max time between two taps to trigger double-tap toggle (0.05 - 2.00s)")
        self._dtw_label = QLabel(f"{cfg.double_tap_window:.2f}s")
        self._dtw_slider.valueChanged.connect(
            lambda v: (self._dtw_label.setText(f"{v / 100:.2f}s"), self._debounce.start())
        )
        dtw_row = QWidget()
        dtw_layout = QHBoxLayout(dtw_row)
        dtw_layout.setContentsMargins(0, 0, 0, 0)
        dtw_layout.addWidget(self._dtw_slider)
        dtw_layout.addWidget(self._dtw_label)
        form.addRow("Double-tap Window", dtw_row)

        self._cancel_edit = QKeySequenceEdit(_str_to_qks(cfg.cancel_hotkey))
        self._cancel_edit.setToolTip("Press the key combination to cancel an in-progress recording")
        form.addRow("Cancel Hotkey", self._cancel_edit)

        self._model_edit = QLineEdit(cfg.model)
        self._model_edit.setToolTip("Ollama model name for LLM refinement (e.g. gemma4:e2b)")
        form.addRow("LLM Model", self._model_edit)

        self._refine_check = QCheckBox()
        self._refine_check.setChecked(cfg.refine)
        self._refine_check.setToolTip("Run transcribed text through the LLM to clean up filler words and punctuation")
        form.addRow("Refine with LLM", self._refine_check)

        self._vad_slider = QSlider(Qt.Orientation.Horizontal)
        self._vad_slider.setRange(0, 100)
        self._vad_slider.setValue(round(cfg.vad_threshold * 100))
        self._vad_slider.setToolTip("Silence threshold for voice activity detection (0.00 = very sensitive, 1.00 = least sensitive)")
        self._vad_label = QLabel(f"{cfg.vad_threshold:.2f}")
        self._vad_slider.valueChanged.connect(
            lambda v: (self._vad_label.setText(f"{v / 100:.2f}"), self._debounce.start())
        )
        vad_row = QWidget()
        vad_layout = QHBoxLayout(vad_row)
        vad_layout.setContentsMargins(0, 0, 0, 0)
        vad_layout.addWidget(self._vad_slider)
        vad_layout.addWidget(self._vad_label)
        form.addRow("VAD Threshold", vad_row)

        self._llm_to_edit = QLineEdit(str(cfg.llm_timeout))
        self._llm_to_edit.setToolTip("Seconds to wait for LLM response before timing out (1 - 600)")
        form.addRow("LLM Timeout", self._llm_to_edit)

        self._delay_edit = QLineEdit(str(cfg.injection_delay))
        self._delay_edit.setToolTip("Seconds to wait after focusing target window before injecting text (0.0 - 5.0)")
        form.addRow("Injection Delay", self._delay_edit)

        for row in range(form.rowCount()):
            lbl_item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            if lbl_item and lbl_item.widget():
                lbl_item.widget().setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")

        self._form = form
        self._mode_combo.currentTextChanged.connect(self._on_mode_changed)
        self._on_mode_changed(cfg.hotkey_mode)

        scroll.setWidget(form_widget)
        outer.addWidget(scroll, 1)

        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(_FORM_H_MARGIN, 10, _FORM_H_MARGIN, 10)
        self._error_lbl = QLabel()
        self._error_lbl.setObjectName("errorLabel")
        self._error_lbl.setStyleSheet("color: #e84040;")
        self._error_lbl.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self._error_lbl.setAccessibleName("Error")
        footer_layout.addWidget(self._error_lbl, 1)
        self._save_btn = QPushButton("SAVE SETTINGS")
        self._save_btn.setProperty("accent", True)
        self._save_btn.setDefault(True)
        self._save_btn.clicked.connect(self._save)
        footer_layout.addWidget(self._save_btn)
        outer.addWidget(footer)

    def _setup_tab_order(self) -> None:
        widgets = [
            self._mode_combo,
            self._hotkey_edit,
            self._dtw_slider,
            self._cancel_edit,
            self._model_edit,
            self._refine_check,
            self._vad_slider,
            self._llm_to_edit,
            self._delay_edit,
            self._save_btn,
        ]
        for i in range(len(widgets) - 1):
            self.setTabOrder(widgets[i], widgets[i + 1])

    def _on_mode_changed(self, mode: str) -> None:
        self._form.setRowVisible(2, mode == "double_tap_toggle")

    def _set_field_error(self, widget: QWidget) -> None:
        widget.setStyleSheet(f"border-left: 2px solid {DESTRUCTIVE};")
        self._error_fields.append(widget)

    def _clear_field_errors(self) -> None:
        for w in self._error_fields:
            w.setStyleSheet("")
        self._error_fields.clear()

    def _err(self, msg: str, field: QWidget | None = None) -> None:
        self._error_lbl.setText(msg)
        if field is not None:
            self._set_field_error(field)
        self._error_lbl.setFocus()

    def _save(self) -> None:
        self._error_lbl.setText("")
        self._clear_field_errors()

        hotkey = _qks_to_str(self._hotkey_edit.keySequence())
        if not hotkey:
            self._err("Hotkey cannot be empty", self._hotkey_edit)
            return

        cancel_hotkey = _qks_to_str(self._cancel_edit.keySequence())
        if not cancel_hotkey:
            self._err("Cancel Hotkey cannot be empty", self._cancel_edit)
            return

        model = self._model_edit.text().strip()
        if not model:
            self._err("LLM Model cannot be empty", self._model_edit)
            return

        if not _is_safe_model_name(model):
            self._err("Model name contains invalid characters", self._model_edit)
            return

        try:
            llm_timeout = int(self._llm_to_edit.text())
            if not (1 <= llm_timeout <= 600):
                raise ValueError
        except ValueError:
            self._err("LLM Timeout must be a whole number between 1 and 600", self._llm_to_edit)
            return

        try:
            injection_delay = float(self._delay_edit.text())
            if not (0.0 <= injection_delay <= 5.0):
                raise ValueError
        except ValueError:
            self._err("Injection Delay must be a number between 0.0 and 5.0", self._delay_edit)
            return

        updated = Config(
            hotkey=hotkey,
            hotkey_mode=self._mode_combo.currentText(),
            cancel_hotkey=cancel_hotkey,
            model=model,
            refine=self._refine_check.isChecked(),
            vad_threshold=self._vad_slider.value() / 100,
            llm_timeout=llm_timeout,
            injection_delay=injection_delay,
            double_tap_window=self._dtw_slider.value() / 100,
        )
        try:
            self._on_save(updated)
        except Exception as exc:
            self._err(f"Could not save settings: {exc}")
            return
        self.accept()
```

- [ ] **Step 8.4: Run all settings tests**

```
.venv\Scripts\python.exe -m pytest tests/test_settings.py -v
```

Expected: all tests pass.

- [ ] **Step 8.5: Run full test suite**

```
.venv\Scripts\python.exe -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 8.6: Commit**

```bash
git add src/bertytype/ui/settings.py tests/test_settings.py
git commit -m "feat: add settings spacing constants, field error highlighting, DPI scaling, tab order"
```

---

## Task 9: Settings - Lazy Loading

**Files:**

- Modify: `src/bertytype/ui/settings.py`
- Modify: `src/bertytype/__main__.py`
- Modify: `tests/test_settings.py`

- [ ] **Step 9.1: Write failing tests**

Add to `tests/test_settings.py`:

```python
def test_settings_dialog_can_be_shown_and_hidden(qapp):
    from bertytype.ui.settings import _SettingsDialog
    from bertytype.config import Config
    cfg = Config()
    dlg = _SettingsDialog(cfg, on_save=lambda c: None)
    dlg.show()
    assert dlg.isVisible()
    dlg.hide()
    assert not dlg.isVisible()
    dlg.close()


def test_settings_dialog_load_config_refreshes_fields(qapp):
    from bertytype.ui.settings import _SettingsDialog
    from bertytype.config import Config
    cfg1 = Config(model="gemma4:e2b")
    cfg2 = Config(model="llama3:8b")
    dlg = _SettingsDialog(cfg1, on_save=lambda c: None)
    assert dlg._model_edit.text() == "gemma4:e2b"
    dlg.load_config(cfg2)
    assert dlg._model_edit.text() == "llama3:8b"
    dlg.close()
```

- [ ] **Step 9.2: Run new tests - expect failures**

```
.venv\Scripts\python.exe -m pytest tests/test_settings.py -v -k "hidden or load_config"
```

Expected: `load_config` method does not exist yet.

- [ ] **Step 9.3: Add `load_config` to `_SettingsDialog` in `settings.py`**

Add this method to the `_SettingsDialog` class (after `_setup_tab_order`):

```python
    def load_config(self, cfg: Config) -> None:
        """Refresh all fields from a new config. Used by lazy-loading in __main__."""
        self._mode_combo.setCurrentText(cfg.hotkey_mode)
        from bertytype.ui.settings import _str_to_qks
        self._hotkey_edit.setKeySequence(_str_to_qks(cfg.hotkey))
        self._dtw_slider.setValue(round(cfg.double_tap_window * 100))
        self._cancel_edit.setKeySequence(_str_to_qks(cfg.cancel_hotkey))
        self._model_edit.setText(cfg.model)
        self._refine_check.setChecked(cfg.refine)
        self._vad_slider.setValue(round(cfg.vad_threshold * 100))
        self._llm_to_edit.setText(str(cfg.llm_timeout))
        self._delay_edit.setText(str(cfg.injection_delay))
        self._error_lbl.setText("")
        self._clear_field_errors()
```

Also override `closeEvent` so the dialog hides instead of being destroyed when used in lazy mode:

```python
    def closeEvent(self, event) -> None:
        if self._lazy_mode:
            event.ignore()
            self.hide()
        else:
            super().closeEvent(event)
```

Add `self._lazy_mode = False` in `__init__` after `self._error_fields = []`.

- [ ] **Step 9.4: Wire lazy loading in `__main__.py`**

Add module-level variable after `_theme_watcher`:

```python
_settings_dialog: "settings._SettingsDialog | None" = None
```

Replace `_on_open_settings` with:

```python
def _on_open_settings() -> None:
    global _settings_dialog

    def _save(updated_cfg: cfg_module.Config) -> None:
        global _cfg
        with _cfg_lock:
            _cfg = updated_cfg
        cfg_module.save(updated_cfg)
        _register_hotkeys(updated_cfg)

    with _cfg_lock:
        current_cfg = _cfg

    if _settings_dialog is None:
        _settings_dialog = settings._SettingsDialog(current_cfg, on_save=_save)
        _settings_dialog._lazy_mode = True
    else:
        _settings_dialog._on_save = _save
        _settings_dialog.load_config(current_cfg)

    _settings_dialog.show()
    _settings_dialog.raise_()
    _settings_dialog.activateWindow()
```

- [ ] **Step 9.5: Run all tests**

```
.venv\Scripts\python.exe -m pytest tests/ -v
```

Expected: all tests pass.

- [ ] **Step 9.6: Commit**

```bash
git add src/bertytype/ui/settings.py src/bertytype/__main__.py tests/test_settings.py
git commit -m "feat: lazy-load settings dialog, add load_config for re-use"
```

---

## Task 10: Final Integration Check and TODO Cleanup

**Files:**

- Modify: `TODO.md`

- [ ] **Step 10.1: Run the full test suite one final time**

```
.venv\Scripts\python.exe -m pytest tests/ -v --tb=short
```

Expected: all tests pass with no failures or errors.

- [ ] **Step 10.2: Verify the app starts without crash**

```
.venv\Scripts\python.exe src\bertytype\__main__.py &
```

Check: tray icon appears, no Python traceback in terminal. Quit via tray menu.

- [ ] **Step 10.3: Update TODO.md - remove completed items**

Remove all items that are now implemented:

- Motion/Interaction: animation curves, micro-interactions, button states
- Component: dark mode adaptations
- Performance: debouncing, lazy loading, resource cleanup on exit
- Bug fixes: hotkey registration, memory leaks, responsive/DPI scaling, error state handling
- Implementation phases: Phase 2, 3, 4 items covered
- Success metrics: zero regressions and maintained performance (verified by test suite)

Keep items that remain out of scope per the spec.

- [ ] **Step 10.4: Final commit**

```bash
git add TODO.md
git commit -m "chore: update TODO to reflect completed UI polish and bug fix tasks"
```

---

## Self-Review Checklist

**Spec coverage:**

| Spec section | Task |
| --- | --- |
| 1A Dark mode system | Task 2 + Task 3 |
| 1B Audio amplitude pipeline | Task 1 |
| 2A Easing curves | Task 4 |
| 2B Audio-reactive waveform | Task 4 |
| 2C Button states / micro-interactions | Task 2 (QSS `:pressed` states) |
| 2D LLM processing tooltip + completion notify | Task 5 |
| 3A Settings spacing + container cleanup | Task 8 |
| 3B Error state field highlight | Task 8 |
| 3C Hotkey bug fix | Task 6 |
| 3D Memory leaks | Task 7 |
| 3E DPI/responsive scaling | Task 8 |
| 4A Slider debounce | Task 8 |
| 4B Lazy loading settings | Task 9 |
| 4C Unified exit cleanup | Task 7 |
| 4D Keyboard navigation (tab order) | Task 8 |
| 4E Contrast audit | Verified inline in Task 2 (dark palette `TEXT_DIM` lightened to `#909090`) |
