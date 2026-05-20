from __future__ import annotations
import dataclasses
import json
import re
from pathlib import Path

from bertytype import config as cfg_module
from bertytype.config import Config

PROFILES_DIR = Path.home() / ".bertytype" / "profiles"

_NAME_RE = re.compile(r'^[\w\s\-]+$')
_NAME_MAX_LEN = 64


def is_valid_name(name: str) -> bool:
    """Return True if name is a valid profile name."""
    return bool(name) and len(name) <= _NAME_MAX_LEN and bool(_NAME_RE.match(name))


def list_profiles() -> list[str]:
    """Return sorted profile names."""
    if not PROFILES_DIR.exists():
        return []
    return sorted(p.stem for p in PROFILES_DIR.glob("*.json"))


def load_profile(name: str) -> Config:
    """Load a profile by name. Raises FileNotFoundError if not found."""
    path = PROFILES_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"Profile not found: {name!r}")
    data = json.loads(path.read_text(encoding="utf-8"))
    known_keys = set(dataclasses.asdict(Config()).keys())
    data = {k: v for k, v in data.items() if k in known_keys}
    cfg = cfg_module._validate(data)
    return dataclasses.replace(cfg, active_profile=name)


def save_profile(name: str, cfg: Config) -> None:
    """Save current config as a named profile."""
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    path = PROFILES_DIR / f"{name}.json"
    path.write_text(json.dumps(dataclasses.asdict(cfg), indent=2), encoding="utf-8")


def delete_profile(name: str) -> None:
    """Delete a profile by name. No-op if it does not exist."""
    path = PROFILES_DIR / f"{name}.json"
    path.unlink(missing_ok=True)
