"""Listens for Windows theme changes via WM_SETTINGCHANGE event filter."""
from __future__ import annotations
import sys

from PySide6.QtCore import QObject, QAbstractNativeEventFilter, Signal
from PySide6.QtWidgets import QApplication

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    WM_SETTINGCHANGE = 0x001A

    class _ThemeEventFilter(QAbstractNativeEventFilter):
        def __init__(self, watcher: ThemeWatcher) -> None:
            super().__init__()
            self._watcher = watcher

        def nativeEventFilter(self, eventType: bytes, message: int) -> object:
            if eventType == b"windows_generic_MSG":
                msg = wintypes.MSG.from_address(message)
                if msg.message == WM_SETTINGCHANGE and msg.lParam:
                    buf = ctypes.create_unicode_buffer(256)
                    atom_len = ctypes.windll.kernel32.GlobalGetAtomNameW(
                        msg.lParam, buf, 256
                    )
                    if atom_len and buf.value == "ImmersiveColorSet":
                        self._watcher._on_system_theme_change()
            return False, 0

    _HAS_NATIVE_EVENTS = True
else:
    _ThemeEventFilter = None
    _HAS_NATIVE_EVENTS = False


class ThemeWatcher(QObject):
    theme_changed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._current = self._read_theme()
        self._filter = (
            _ThemeEventFilter(self) if _HAS_NATIVE_EVENTS else None
        )
        if self._filter is not None:
            app = QApplication.instance()
            if app is not None:
                app.installNativeEventFilter(self._filter)

    @staticmethod
    def _read_theme() -> str:
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return "light" if value == 1 else "dark"
        except (OSError, ImportError):
            return "dark"

    def _on_system_theme_change(self) -> None:
        new = self._read_theme()
        if new != self._current:
            self._current = new
            self.theme_changed.emit(new)

    def current_theme(self) -> str:
        return self._current

    def stop(self) -> None:
        if self._filter is not None:
            app = QApplication.instance()
            if app is not None:
                app.removeNativeEventFilter(self._filter)
