from unittest.mock import patch, MagicMock
from bertytype.hotkeys import daemon


def test_register_calls_keyboard_add_hotkey():
    cb = MagicMock()
    with patch("keyboard.add_hotkey") as mock_add:
        daemon.register("ctrl+shift+space", cb)
    mock_add.assert_called_once_with("ctrl+shift+space", cb)


def test_register_ptt_hooks_press_and_release_with_full_combo():
    on_press = MagicMock()
    on_release = MagicMock()
    with patch("keyboard.add_hotkey") as mock_add:
        daemon.register_ptt("ctrl+shift+space", on_press, on_release)
    assert mock_add.call_count == 2
    calls = mock_add.call_args_list
    assert calls[0][0][0] == "ctrl+shift+space"
    assert calls[0][0][1] == on_press
    assert calls[0][1]["suppress"] is True
    assert calls[0][1]["trigger_on_release"] is False
    assert calls[1][0][0] == "ctrl+shift+space"
    assert calls[1][0][1] == on_release
    assert calls[1][1]["suppress"] is True
    assert calls[1][1]["trigger_on_release"] is True


def test_stop_unhooks_all():
    with patch("keyboard.unhook_all") as mock_unhook:
        daemon.stop()
    mock_unhook.assert_called_once()


def _get_double_tap_handler(key, on_start, on_stop, window=0.3):
    captured = []
    with patch("keyboard.on_press_key", side_effect=lambda k, h: captured.append(h)):
        daemon.register_double_tap_toggle(key, on_start, on_stop, window=window)
    return captured[0]


def test_double_tap_toggle_registers_on_press_key():
    on_start, on_stop = MagicMock(), MagicMock()
    with patch("keyboard.on_press_key") as mock_press:
        daemon.register_double_tap_toggle("alt", on_start, on_stop)
    mock_press.assert_called_once()
    assert mock_press.call_args[0][0] == "alt"


def test_single_tap_does_not_trigger():
    on_start, on_stop = MagicMock(), MagicMock()
    handler = _get_double_tap_handler("alt", on_start, on_stop, window=0.3)
    event = MagicMock()
    with patch("time.monotonic", return_value=1.0):
        handler(event)
    on_start.assert_not_called()
    on_stop.assert_not_called()


def test_double_tap_within_window_calls_on_start():
    on_start, on_stop = MagicMock(), MagicMock()
    handler = _get_double_tap_handler("alt", on_start, on_stop, window=0.3)
    event = MagicMock()
    times = iter([1.0, 1.2])
    with patch("time.monotonic", side_effect=times):
        handler(event)  # first tap
        handler(event)  # second tap 0.2s later - within 0.3s window
    on_start.assert_called_once()
    on_stop.assert_not_called()


def test_double_tap_outside_window_does_not_trigger():
    on_start, on_stop = MagicMock(), MagicMock()
    handler = _get_double_tap_handler("alt", on_start, on_stop, window=0.3)
    event = MagicMock()
    times = iter([1.0, 1.5])  # 0.5s apart, outside 0.3s window
    with patch("time.monotonic", side_effect=times):
        handler(event)
        handler(event)
    on_start.assert_not_called()


def test_second_double_tap_calls_on_stop():
    on_start, on_stop = MagicMock(), MagicMock()
    handler = _get_double_tap_handler("alt", on_start, on_stop, window=0.3)
    event = MagicMock()
    times = iter([1.0, 1.1, 2.0, 2.1])
    with patch("time.monotonic", side_effect=times):
        handler(event)  # tap 1
        handler(event)  # tap 2 - starts recording
        handler(event)  # tap 3
        handler(event)  # tap 4 - stops recording
    on_start.assert_called_once()
    on_stop.assert_called_once()


def test_triple_tap_does_not_double_trigger():
    """Third tap after a double-tap resets and does not immediately start again."""
    on_start, on_stop = MagicMock(), MagicMock()
    handler = _get_double_tap_handler("alt", on_start, on_stop, window=0.3)
    event = MagicMock()
    times = iter([1.0, 1.1, 1.15])
    with patch("time.monotonic", side_effect=times):
        handler(event)  # tap 1
        handler(event)  # tap 2 - starts (resets last_tap to 0)
        handler(event)  # tap 3 - last_tap is 0, delta = 1.15 > window: treated as first tap
    on_start.assert_called_once()
    on_stop.assert_not_called()


def test_stop_is_idempotent():
    """Calling stop() twice must not raise."""
    with patch("keyboard.unhook_all") as mock_unhook:
        daemon.stop()
        daemon.stop()
        assert mock_unhook.call_count == 2


def test_register_uses_lock():
    """Concurrent register calls must not interleave."""
    import threading
    import time as _time
    call_order = []

    def slow_add(hotkey, *args, **kwargs):
        call_order.append(f"start:{hotkey}")
        _time.sleep(0.01)
        call_order.append(f"end:{hotkey}")

    with patch("keyboard.add_hotkey", side_effect=slow_add):
        t1 = threading.Thread(target=daemon.register, args=("ctrl+a", lambda: None))
        t2 = threading.Thread(target=daemon.register, args=("ctrl+b", lambda: None))
        t1.start(); t2.start()
        t1.join(); t2.join()

    for idx in range(0, len(call_order) - 1, 2):
        key = call_order[idx].split(":")[1]
        assert call_order[idx + 1] == f"end:{key}"
