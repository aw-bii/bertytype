from pathlib import Path


def save_transcript(text: str, source_path: Path) -> Path:
    out = source_path.with_suffix(".txt")
    try:
        out.write_text(text, encoding="utf-8")
    except OSError as e:
        raise RuntimeError(f"Could not save transcript to '{out}': {e}") from e
    return out
