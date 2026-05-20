from __future__ import annotations
import atexit
import threading
import time
from typing import Callable
import keyboard

_lock = threading.Lock()


@atexit.register
def _atexit_cleanup() -> None:
    # Non-blocking acquire: if a registration is in-progress we skip the lock
    # rather than risk deadlocking atexit against a hung daemon thread.
    acquired = _lock.acquire(blocking=False)
    try:
        keyboard.unhook_all()
    finally:
        if acquired:
            _lock.release()


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
    state: dict = {"last_tap": 0.0, "recording": False}

    def _handler(_event) -> None:
        now = time.monotonic()
        delta = now - state["last_tap"]
        if 0 < delta <= window:
            state["last_tap"] = 0.0  # reset so triple-tap isn't a second double-tap
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
