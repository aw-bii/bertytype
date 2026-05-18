from pathlib import Path
import imageio_ffmpeg
from pydub import AudioSegment

AudioSegment.converter = imageio_ffmpeg.get_ffmpeg_exe()

SAMPLE_RATE = 16000


def read_file(path: Path) -> bytes:
    MAX_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB
    MAX_DURATION_MS = 600_000  # 10 minutes

    try:
        size = path.stat().st_size
    except OSError as e:
        raise ValueError(f"Cannot access audio file '{path.name}': {e}") from e

    if size > MAX_SIZE_BYTES:
        raise ValueError(
            f"Audio file too large ({size / 1024 / 1024:.0f} MB). Maximum is 500 MB."
        )

    try:
        audio = AudioSegment.from_file(str(path))
    except Exception as e:
        raise ValueError(f"Could not decode audio file '{path.name}': {e}") from e

    if len(audio) > MAX_DURATION_MS:
        raise ValueError(
            f"Audio file too long ({len(audio) / 1000:.0f}s). Maximum is 600s."
        )

    audio = audio.set_frame_rate(SAMPLE_RATE).set_channels(1).set_sample_width(2)
    return audio.raw_data
