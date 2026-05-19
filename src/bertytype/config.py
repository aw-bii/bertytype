import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

from bertytype import logging as log_module

CONFIG_PATH = Path.home() / ".bertytype" / "config.json"

logger = log_module.logger

_VALID_HOTKEY_MODES = {"ptt", "double_tap_toggle"}


def _is_safe_model_name(model: str) -> bool:
    dangerous = {"../", ";", "$", "|", ">", "<", "`", "&&", "||"}
    return not any(pattern in model for pattern in dangerous)


@dataclass
class Config:
    hotkey: str = "alt"
    cancel_hotkey: str = "escape"
    model: str = "gemma4:e2b"
    refine: bool = True
    vad_threshold: float = 0.02
    hotkey_mode: str = "double_tap_toggle"
    double_tap_window: float = 0.3
    llm_timeout: int = 30
    injection_delay: float = 0.05


def _validate_value(key: str, value: Any, default: Any) -> Any:
    if key in ("hotkey", "cancel_hotkey"):
        if not isinstance(value, str) or not value.strip():
            logger.warning(f"Invalid {key}: {value!r}, using default {default!r}")
            return default
    elif key == "model":
        if not isinstance(value, str) or not value.strip():
            logger.warning(f"Invalid model: {value!r}, using default {default!r}")
            return default
        if not _is_safe_model_name(value):
            logger.warning(f"Suspicious model name: {value!r}, using default {default!r}")
            return default
    elif key == "refine":
        if not isinstance(value, bool):
            logger.warning(f"Invalid refine: {value!r}, using default {default!r}")
            return default
    elif key == "vad_threshold":
        if not isinstance(value, (int, float)) or not (0.0 <= value <= 1.0):
            logger.warning(f"Invalid vad_threshold: {value!r}, using default {default!r}")
            return default
    elif key == "hotkey_mode":
        if value not in _VALID_HOTKEY_MODES:
            logger.warning(f"Invalid hotkey_mode: {value!r}, using default {default!r}")
            return default
    elif key == "double_tap_window":
        if not isinstance(value, (int, float)) or not (0.05 <= value <= 2.0):
            logger.warning(f"Invalid double_tap_window: {value!r}, using default {default!r}")
            return default
    elif key == "llm_timeout":
        if not isinstance(value, int) or value <= 0:
            logger.warning(f"Invalid {key}: {value!r}, using default {default!r}")
            return default
    elif key == "injection_delay":
        if not isinstance(value, (int, float)) or value < 0:
            logger.warning(f"Invalid {key}: {value!r}, using default {default!r}")
            return default
    return value


def _validate(data: dict) -> Config:
    defaults = Config()
    defaults_dict = asdict(defaults)
    validated = {}
    for key, default in defaults_dict.items():
        validated[key] = _validate_value(key, data.get(key, default), default)
    return Config(**validated)


def load() -> Config:
    if CONFIG_PATH.exists():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            # Silently drop unknown/removed keys (e.g. stt_timeout from old configs)
            known_keys = set(asdict(Config()).keys())
            data = {k: v for k, v in data.items() if k in known_keys}
            return _validate(data)
        except (json.JSONDecodeError, TypeError, KeyError) as e:
            logger.warning(f"Config load failed: {e}, using defaults")
    return Config()


def save(cfg: Config) -> None:
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")
