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
_profiles_menu: "QMenu | None" = None
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

    if _tray_icon is not None:
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
    on_view_history: Callable[[str], None] | None = None,
    on_save_profile_as: Callable[[], None] | None = None,
) -> None:
    global _tray_icon, _anim_timer, _error_timer, _profiles_menu, _llm_model
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
    if on_view_history is not None:
        history_menu = menu.addMenu("View history")
        history_menu.addAction("Last 8 hours", lambda: on_view_history("8h"))
        history_menu.addAction("Last 24 hours", lambda: on_view_history("1d"))
        history_menu.addAction("Last 7 days", lambda: on_view_history("7d"))
    if on_save_profile_as is not None:
        _profiles_menu = menu.addMenu("Profiles")
        _profiles_menu.addAction("Save current as profile...", on_save_profile_as)
        _profiles_menu.addSeparator()
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
    global _tray_icon, _anim_timer, _error_timer, _profiles_menu
    _profiles_menu = None
    if _anim_timer is not None:
        _anim_timer.stop()
        _anim_timer = None
    if _error_timer is not None:
        _error_timer.stop()
        _error_timer = None
    if _tray_icon is not None:
        _tray_icon.hide()
        _tray_icon = None


def update_profiles_menu(
    profile_names: list[str],
    active: str | None,
    on_switch: Callable[[str], None],
) -> None:
    """Rebuild the profiles submenu with current profile list."""
    if _profiles_menu is None:
        return
    past_separator = False
    for action in list(_profiles_menu.actions()):
        if action.isSeparator():
            past_separator = True
        elif past_separator:
            _profiles_menu.removeAction(action)
            action.deleteLater()
    for name in profile_names:
        action = _profiles_menu.addAction(name, lambda n=name: on_switch(n))
        action.setCheckable(True)
        action.setChecked(name == active)
