import io
import wave
from typing import Any, Optional

import numpy as np

_MODEL_ID = "microsoft/VibeVoice-ASR-HF"
_processor: Optional[Any] = None
_model: Optional[Any] = None


def _get_model():
    global _processor, _model
    if _processor is None:
        from transformers import AutoProcessor, VibeVoiceAsrForConditionalGeneration

        _processor = AutoProcessor.from_pretrained(_MODEL_ID)
        _model = VibeVoiceAsrForConditionalGeneration.from_pretrained(
            _MODEL_ID, device_map="auto"
        )
    return _processor, _model


def _pcm_to_wav(pcm_bytes: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


def transcribe(audio_bytes: bytes) -> str:
    wav_bytes = _pcm_to_wav(audio_bytes)
    processor, model = _get_model()

    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        if wf.getnchannels() != 1:
            raise ValueError("Audio must be mono")
        audio_data = wf.readframes(wf.getnframes())

    audio = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0

    inputs = processor.apply_transcription_request(
        audio=audio, return_format="transcription_only"
    ).to(model.device)

    output_ids = model.generate(**inputs)
    return processor.decode(output_ids[0], skip_special_tokens=True)


def is_available() -> bool:
    try:
        import transformers  # noqa: F401
        return True
    except ImportError:
        return False
