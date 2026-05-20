from __future__ import annotations
from typing import Callable
from PySide6.QtCore import QObject, QTimer, Signal, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap, QColor
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from bertytype.ui.tokens import STATUS_COLORS as _STATUS_COLORS

_BAR_HEIGHTS_BY_STATUS: dict[str, list[int]] = {
    "idle":       [16, 32, 48, 32, 16],
    "recording":  [52, 44, 52, 44, 52],
    "error":      [8,  8,  8,  8,  8],
}

# Animation frames for processing state - bars "cycle" left each tick
_PROCESSING_FRAMES: list[list[int]] = [
    [12, 44, 28, 52, 20],
    [20, 12, 44, 28, 52],
    [52, 20, 12, 44, 28],
    [28, 52, 20, 12, 44],
    [44, 28, 52, 20, 12],
]

_STATUS_LABELS: dict[str, str] = {
    "idle":       "Idle - hold hotkey to record",
    "recording":  "Recording...",
    "processing": "Processing...",
    "error":      "Error - check logs",
}

_BAR_WIDTH = 8
_BAR_GAP   = 4
_CANVAS    = 64
_ICON_CACHE: dict[tuple[str, float], QIcon] = {}


class _TraySignals(QObject):
    status_changed   = Signal(str)
    notify_requested = Signal(str)


_signals    = _TraySignals()
_tray_icon: QSystemTrayIcon | None = None
_status     = "idle"
_anim_frame = 0
_anim_timer: QTimer | None = None
_error_timer: QTimer | None = None


def _dpr() -> float:
    app = QApplication.instance()
    if app:
        screen = app.primaryScreen()
        if screen:
            return screen.devicePixelRatio()
    return 1.0


def _make_icon(status: str, frame: int = 0) -> QIcon:
    dpr = _dpr()
    cache_key = (f"{status}:{frame}", dpr)
    if cache_key in _ICON_CACHE:
        return _ICON_CACHE[cache_key]

    color_hex = _STATUS_COLORS.get(status, _STATUS_COLORS["error"])
    if status == "processing":
        bar_heights = _PROCESSING_FRAMES[frame % len(_PROCESSING_FRAMES)]
    else:
        bar_heights = _BAR_HEIGHTS_BY_STATUS.get(status, _BAR_HEIGHTS_BY_STATUS["idle"])

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
        x     = x_start + i * (_BAR_WIDTH + _BAR_GAP)
        y_top = (_CANVAS - bar_h) // 2
        painter.drawRoundedRect(x, y_top, _BAR_WIDTH, bar_h, 2, 2)
    painter.end()
    icon = QIcon(px)
    _ICON_CACHE[cache_key] = icon
    return icon


def _tick_animation() -> None:
    global _anim_frame
    if _tray_icon is None or _status != "processing":
        return
    _anim_frame = (_anim_frame + 1) % len(_PROCESSING_FRAMES)
    _tray_icon.setIcon(_make_icon("processing", _anim_frame))


def _recover_from_error() -> None:
    set_status("idle")


def _on_status_changed(status: str) -> None:
    global _status, _anim_frame
    _status = status
    _anim_frame = 0
    if _tray_icon is not None:
        _tray_icon.setIcon(_make_icon(status))
        _tray_icon.setToolTip(f"BertyType - {_STATUS_LABELS.get(status, status.capitalize())}")
    if _anim_timer is not None:
        if status == "processing":
            _anim_timer.start(200)
        else:
            _anim_timer.stop()
    if _error_timer is not None:
        if status == "error":
            _error_timer.start()
        else:
            _error_timer.stop()


def _on_notify_requested(msg: str) -> None:
    if _tray_icon is not None:
        _tray_icon.showMessage("BertyType", msg, QSystemTrayIcon.MessageIcon.NoIcon, 3000)


def set_status(status: str) -> None:
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
    """Register the tray icon and return immediately (non-blocking)."""
    global _tray_icon, _anim_timer, _error_timer
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
    icon.setIcon(_make_icon("idle"))
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
