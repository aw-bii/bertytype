from typing import Callable

# Set once in main() before worker threads start. Not safe to reassign after threads launch.
_backend: Callable[[bytes], str] | None = None


def set_backend(fn: Callable[[bytes], str] | None) -> None:
    global _backend
    _backend = fn


def transcribe(audio: bytes) -> str:
    if _backend is None:
        raise RuntimeError(
            "STT backend not configured. Call set_backend() with a VibeVoice callable."
        )
    return _backend(audio)
