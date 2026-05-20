import bertytype.ui.tray as tray_module


def test_notify_emits_signal(qapp):
    received = []
    tray_module._signals.notify_requested.connect(received.append)
    try:
        tray_module.notify("Done - saved to foo.txt")
        assert "Done - saved to foo.txt" in received
    finally:
        tray_module._signals.notify_requested.disconnect(received.append)


def test_set_status_emits_signal(qapp):
    received = []
    tray_module._signals.status_changed.connect(received.append)
    try:
        original = tray_module._status
        tray_module._status = "idle"
        tray_module.set_status("recording")
        assert "recording" in received
    finally:
        tray_module._status = original
        tray_module._signals.status_changed.disconnect(received.append)


def test_set_status_dedup_does_not_emit(qapp):
    received = []
    tray_module._signals.status_changed.connect(received.append)
    try:
        tray_module._status = "idle"
        tray_module.set_status("idle")
        assert received == []
    finally:
        tray_module._signals.status_changed.disconnect(received.append)


def test_notify_no_crash_without_tray_icon(qapp):
    original = tray_module._tray_icon
    tray_module._tray_icon = None
    try:
        tray_module.notify("any message")  # must not raise
    finally:
        tray_module._tray_icon = original


def test_set_status_no_crash_without_tray_icon(qapp):
    from bertytype.ui import tray as tray_module_local
    from PySide6.QtCore import QCoreApplication
    original = tray_module_local._status
    try:
        tray_module_local._status = "idle"
        tray_module_local.set_status("recording")  # must not raise
        QCoreApplication.processEvents()
    finally:
        tray_module_local._status = original


def test_error_timer_starts_on_error_status(qapp):
    import bertytype.ui.tray as tray_module
    original_status = tray_module._status
    tray_module._status = "idle"
    try:
        tray_module._error_timer = __import__("PySide6.QtCore", fromlist=["QTimer"]).QTimer()
        tray_module._error_timer.setSingleShot(True)
        tray_module._error_timer.setInterval(30_000)
        tray_module._on_status_changed("error")
        assert tray_module._error_timer.isActive()
    finally:
        tray_module._error_timer.stop()
        tray_module._error_timer = None
        tray_module._status = original_status


def test_error_timer_stops_on_non_error_status(qapp):
    import bertytype.ui.tray as tray_module
    original_status = tray_module._status
    from PySide6.QtCore import QTimer
    timer = QTimer()
    timer.setSingleShot(True)
    timer.start(30_000)
    tray_module._error_timer = timer
    tray_module._status = "error"
    try:
        tray_module._on_status_changed("idle")
        assert not tray_module._error_timer.isActive()
    finally:
        tray_module._error_timer = None
        tray_module._status = original_status


def test_current_heights_initialized_to_idle(qapp):
    import bertytype.ui.tray as t
    assert len(t._current_heights) == 5
    assert t._current_heights[2] > t._current_heights[0]  # center taller than edge


def test_tick_lerps_heights_toward_target(qapp):
    import bertytype.ui.tray as t
    from bertytype.ui.tray import _get_target_heights
    # Force all current heights to 0
    original_heights = t._current_heights[:]
    t._current_heights = [0.0] * 5
    t._status = "idle"
    targets = _get_target_heights("idle", 0, 0.0)
    t._tick_animation()
    # After one lerp step, heights should have moved toward target
    for i in range(5):
        assert t._current_heights[i] > 0.0
        assert t._current_heights[i] < targets[i]
    # Restore
    t._current_heights[:] = original_heights


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
