import json
import pytest
from bertytype import profiles
from bertytype.config import Config


@pytest.fixture(autouse=True)
def tmp_profiles_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(profiles, "PROFILES_DIR", tmp_path / "profiles")


def test_list_profiles_empty_when_no_dir():
    result = profiles.list_profiles()
    assert result == []


def test_save_and_list():
    cfg = Config(hotkey="ctrl+r")
    profiles.save_profile("Work", cfg)
    assert profiles.list_profiles() == ["Work"]


def test_list_profiles_sorted():
    profiles.save_profile("Zebra", Config())
    profiles.save_profile("Alpha", Config())
    assert profiles.list_profiles() == ["Alpha", "Zebra"]


def test_load_profile_returns_config_with_active_set():
    cfg = Config(hotkey="ctrl+r")
    profiles.save_profile("Work", cfg)
    loaded = profiles.load_profile("Work")
    assert loaded.hotkey == "ctrl+r"
    assert loaded.active_profile == "Work"


def test_load_profile_missing_raises():
    with pytest.raises(FileNotFoundError):
        profiles.load_profile("nonexistent")


def test_save_creates_json_file():
    cfg = Config()
    profiles.save_profile("Test", cfg)
    path = profiles.PROFILES_DIR / "Test.json"
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["hotkey"] == cfg.hotkey


def test_delete_profile_removes_file():
    profiles.save_profile("Temp", Config())
    profiles.delete_profile("Temp")
    assert profiles.list_profiles() == []


def test_delete_profile_missing_does_not_raise():
    profiles.delete_profile("does_not_exist")  # must not raise


def test_is_valid_name_accepts_valid():
    assert profiles.is_valid_name("My Profile") is True
    assert profiles.is_valid_name("code-mode") is True
    assert profiles.is_valid_name("profile_1") is True


def test_is_valid_name_rejects_empty():
    assert profiles.is_valid_name("") is False


def test_is_valid_name_rejects_too_long():
    assert profiles.is_valid_name("a" * 65) is False


def test_is_valid_name_rejects_special_chars():
    assert profiles.is_valid_name("bad/name") is False
    assert profiles.is_valid_name("bad;name") is False
