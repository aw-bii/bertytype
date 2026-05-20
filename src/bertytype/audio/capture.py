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
