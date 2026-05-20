import numpy as np
import threading
from bertytype.audio import amplitude


def test_update_computes_rms_of_sine():
    amplitude.reset()
    chunk = (np.sin(np.linspace(0, 2 * np.pi, 1000)) * 32767).astype(np.int16)
    amplitude.update(chunk)
    val = amplitude.get()
    assert 0.65 < val < 0.75  # RMS of full-amplitude sine ~= 0.707


def test_reset_sets_zero():
    chunk = np.full(100, 16000, dtype=np.int16)
    amplitude.update(chunk)
    amplitude.reset()
    assert amplitude.get() == 0.0


def test_empty_chunk_does_not_raise():
    amplitude.reset()
    amplitude.update(np.array([], dtype=np.int16))
    assert amplitude.get() == 0.0


def test_amplitude_clamped_to_one():
    chunk = np.full(100, 32767, dtype=np.int16)
    amplitude.update(chunk)
    assert amplitude.get() <= 1.0


def test_thread_safety():
    amplitude.reset()
    chunk = np.full(1000, 16383, dtype=np.int16)
    errors = []

    def writer():
        try:
            for _ in range(200):
                amplitude.update(chunk)
        except Exception as e:
            errors.append(e)

    def reader():
        try:
            for _ in range(200):
                amplitude.get()
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
