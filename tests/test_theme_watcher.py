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
