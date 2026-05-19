from __future__ import annotations
import base64
import io
import json
import wave

import requests

VIBEVOICE_URL = "http://localhost:8000/v1/chat/completions"
_MODEL = "vibevoice"
_SAMPLE_RATE = 16000
_CHANNELS = 1
_SAMPLE_WIDTH = 2  # int16


def _pcm_to_wav(pcm_bytes: bytes) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(_CHANNELS)
        wf.setsampwidth(_SAMPLE_WIDTH)
        wf.setframerate(_SAMPLE_RATE)
        wf.writeframes(pcm_bytes)
    return buf.getvalue()


def transcribe(audio: bytes, timeout: int = 60) -> str:
    wav_bytes = _pcm_to_wav(audio)
    audio_b64 = base64.b64encode(wav_bytes).decode("utf-8")
    payload = {
        "model": _MODEL,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant that transcribes audio input"
                    " into text output in JSON format."
                ),
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "audio_url",
                        "audio_url": {"url": f"data:audio/wav;base64,{audio_b64}"},
                    },
                    {"type": "text", "text": "Transcribe the audio."},
                ],
            },
        ],
        "max_tokens": 32768,
        "temperature": 0.0,
        "stream": True,
        "top_p": 1.0,
    }
    # connect_timeout=10, read_timeout=timeout: prevents silent hangs if the
    # server stops streaming mid-response after the connection is established.
    resp = requests.post(VIBEVOICE_URL, json=payload, stream=True, timeout=(10, timeout))
    try:
        resp.raise_for_status()
        accumulated = ""
        for line in resp.iter_lines():
            if not line:
                continue
            decoded = line.decode("utf-8")
            if not decoded.startswith("data: "):
                continue
            json_str = decoded[6:]
            if json_str.strip() == "[DONE]":
                break
            try:
                data = json.loads(json_str)
                content = data["choices"][0]["delta"].get("content", "")
                if content:
                    # vLLM may send full accumulated text instead of incremental chunks
                    if content.startswith(accumulated):
                        accumulated = content
                    else:
                        accumulated += content
            except (json.JSONDecodeError, KeyError, IndexError):
                pass
    finally:
        resp.close()
    return accumulated.strip()
