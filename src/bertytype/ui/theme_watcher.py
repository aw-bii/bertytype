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
