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
    # RMS computed outside the lock intentionally - numpy work is expensive and
    # chunk is a local, so only the float assignment needs protection.
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
