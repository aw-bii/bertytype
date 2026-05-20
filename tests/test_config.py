import json
from pathlib import Path
import pytest
from bertytype import config


def test_defaults():
    cfg = config.Config()
    assert cfg.hotkey == "alt"
    assert cfg.model == "gemma4:e2b"
    assert cfg.refine is True
    assert cfg.vad_threshold == 0.02
    assert cfg.hotkey_mode == "double_tap_toggle"
    assert cfg.double_tap_window == 0.3
    assert not hasattr(cfg, "stt_timeout")


def test_save_and_load(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    cfg = config.Config(hotkey="ctrl+r", model="gemma4:e2b", refine=False, vad_threshold=0.05)
    config.save(cfg)
    loaded = config.load()
    assert loaded.hotkey == "ctrl+r"
    assert loaded.refine is False
    assert loaded.vad_threshold == 0.05


def test_load_missing_returns_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "nonexistent.json")
    cfg = config.load()
    assert cfg == config.Config()


def test_save_creates_parent_dir(tmp_path, monkeypatch):
    target = tmp_path / "nested" / "dir" / "config.json"
    monkeypatch.setattr(config, "CONFIG_PATH", target)
    config.save(config.Config())
    assert target.exists()


def test_default_cancel_hotkey():
    cfg = config.Config()
    assert cfg.cancel_hotkey == "escape"


def test_cancel_hotkey_round_trips(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    cfg = config.Config(cancel_hotkey="ctrl+z")
    config.save(cfg)
    loaded = config.load()
    assert loaded.cancel_hotkey == "ctrl+z"


def test_load_invalid_hotkey_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    (tmp_path / "config.json").write_text('{"hotkey": ""}')
    loaded = config.load()
    assert loaded.hotkey == "alt"


def test_load_invalid_vad_threshold_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    (tmp_path / "config.json").write_text('{"vad_threshold": 2.0}')
    loaded = config.load()
    assert loaded.vad_threshold == 0.02


def test_load_invalid_vad_threshold_negative(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    (tmp_path / "config.json").write_text('{"vad_threshold": -0.5}')
    loaded = config.load()
    assert loaded.vad_threshold == 0.02


def test_load_invalid_refine_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    (tmp_path / "config.json").write_text('{"refine": "yes"}')
    loaded = config.load()
    assert loaded.refine is True


def test_load_invalid_json_returns_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    (tmp_path / "config.json").write_text("not valid json")
    loaded = config.load()
    assert loaded == config.Config()


def test_load_partial_valid_data(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    (tmp_path / "config.json").write_text('{"hotkey": "ctrl+b"}')
    loaded = config.load()
    assert loaded.hotkey == "ctrl+b"
    assert loaded.model == "gemma4:e2b"


def test_hotkey_mode_round_trips(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    cfg = config.Config(hotkey_mode="ptt")
    config.save(cfg)
    loaded = config.load()
    assert loaded.hotkey_mode == "ptt"


def test_invalid_hotkey_mode_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    (tmp_path / "config.json").write_text('{"hotkey_mode": "bogus"}')
    loaded = config.load()
    assert loaded.hotkey_mode == "double_tap_toggle"


def test_double_tap_window_round_trips(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    cfg = config.Config(double_tap_window=0.5)
    config.save(cfg)
    loaded = config.load()
    assert loaded.double_tap_window == 0.5


def test_old_config_with_stt_timeout_loads_without_error(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    (tmp_path / "config.json").write_text('{"stt_timeout": 60, "hotkey": "alt"}')
    loaded = config.load()
    assert loaded.hotkey == "alt"


@pytest.mark.parametrize("model_name", [
    "../etc/passwd",
    "model;rm -rf",
    "model$shell",
    "model|grep",
    "model>out",
    "model<in",
    "model`cmd`",
    "model&&cmd",
    "model||cmd",
])
def test_model_name_rejects_dangerous_patterns(tmp_path, monkeypatch, model_name):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    (tmp_path / "config.json").write_text(f'{{"model": "{model_name}"}}')
    loaded = config.load()
    assert loaded.model == "gemma4:e2b"


def test_model_name_accepts_valid_names(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    (tmp_path / "config.json").write_text('{"model": "llama3:8b"}')
    loaded = config.load()
    assert loaded.model == "llama3:8b"


def test_model_name_accepts_ollama_default(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    (tmp_path / "config.json").write_text('{"model": "gemma4:e2b"}')
    loaded = config.load()
    assert loaded.model == "gemma4:e2b"


def test_model_name_accepts_custom_model(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_PATH", tmp_path / "config.json")
    (tmp_path / "config.json").write_text('{"model": "my-custom-model:latest"}')
    loaded = config.load()
    assert loaded.model == "my-custom-model:latest"


def test_show_completion_notification_defaults_true():
    from bertytype.config import Config
    assert Config().show_completion_notification is True


def test_show_completion_notification_round_trips():
    from bertytype.config import Config, save, load
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "config.json"
        with patch("bertytype.config.CONFIG_PATH", path):
            cfg = Config(show_completion_notification=False)
            save(cfg)
            loaded = load()
            assert loaded.show_completion_notification is False
