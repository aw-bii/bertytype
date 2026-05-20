import io
import wave

import numpy as np
import pytest
from unittest.mock import patch, MagicMock

from bertytype.stt import vibevoice_local


def _make_pcm_bytes(duration_sec: float = 0.1, sample_rate: int = 16000) -> bytes:
    """Generate raw PCM int16 sine wave (matches capture.py output format)."""
    t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), endpoint=False)
    samples = (np.sin(2 * np.pi * 440 * t) * 32767 * 0.5).astype(np.int16)
    return samples.tobytes()


def test_is_available_returns_false_when_import_fails():
    with patch.dict("sys.modules", {"transformers": None}):
        result = vibevoice_local.is_available()
    assert result is False


def test_is_available_returns_true_when_transformers_importable():
    with patch.dict("sys.modules", {"transformers": MagicMock()}):
        result = vibevoice_local.is_available()
    assert result is True


def test_transcribe_rejects_empty_bytes():
    with pytest.raises(Exception):
        vibevoice_local.transcribe(b"")


def test_transcribe_does_not_crash_on_pcm_before_model_load():
    """Raw PCM is wrapped by _pcm_to_wav before model load, so wave.Error is avoided."""
    pcm = _make_pcm_bytes()
    with patch.object(vibevoice_local, "_get_model", side_effect=ImportError("no transformers")):
        with pytest.raises(ImportError):
            vibevoice_local.transcribe(pcm)


def test_pcm_to_wav_produces_valid_wav():
    pcm = _make_pcm_bytes()
    wav_bytes = vibevoice_local._pcm_to_wav(pcm)
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        assert wf.getnframes() == len(pcm) // 2
