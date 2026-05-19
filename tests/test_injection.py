from pathlib import Path
from unittest.mock import patch, call, MagicMock
from bertytype.injection import injector
from bertytype.injection import exporter


def test_inject_copies_text_to_clipboard():
    with patch("pyperclip.copy") as mock_copy, \
         patch("pyautogui.hotkey"), \
         patch("time.sleep"):
        injector.inject("hello world")
    mock_copy.assert_called_once_with("hello world")


def test_inject_sends_ctrl_v():
    with patch("pyperclip.copy"), \
         patch("pyautogui.hotkey") as mock_hotkey, \
         patch("time.sleep"):
        injector.inject("hello world")
    mock_hotkey.assert_called_once_with("ctrl", "v")


def test_inject_sleeps_before_paste():
    sleep_calls = []
    with patch("pyperclip.copy"), \
         patch("pyautogui.hotkey"), \
         patch("time.sleep", side_effect=sleep_calls.append):
        injector.inject("text")
    assert len(sleep_calls) == 1
    assert sleep_calls[0] > 0


def test_inject_uses_custom_delay():
    sleep_calls = []
    with patch("pyperclip.copy"), \
         patch("pyautogui.hotkey"), \
         patch("time.sleep", side_effect=sleep_calls.append):
        injector.inject("text", delay=0.1)
    assert sleep_calls[0] == 0.1


def test_inject_empty_string():
    with patch("pyperclip.copy") as mock_copy, \
         patch("pyautogui.hotkey"), \
         patch("time.sleep"):
        injector.inject("")
    mock_copy.assert_called_once_with("")


def test_save_transcript_creates_txt_next_to_source(tmp_path):
    audio = tmp_path / "meeting.wav"
    audio.touch()
    out = exporter.save_transcript("hello world", audio)
    assert out == tmp_path / "meeting.txt"
    assert out.read_text(encoding="utf-8") == "hello world"


def test_save_transcript_returns_output_path(tmp_path):
    audio = tmp_path / "clip.mp3"
    audio.touch()
    result = exporter.save_transcript("transcript text", audio)
    assert isinstance(result, Path)
    assert result.suffix == ".txt"


def test_save_transcript_overwrites_existing(tmp_path):
    audio = tmp_path / "clip.wav"
    audio.touch()
    exporter.save_transcript("first", audio)
    exporter.save_transcript("second", audio)
    assert (tmp_path / "clip.txt").read_text(encoding="utf-8") == "second"


def test_save_transcript_raises_runtime_on_write_failure(tmp_path, mocker):
    import pytest
    from bertytype.injection.exporter import save_transcript
    mocker.patch("pathlib.Path.write_text", side_effect=PermissionError("read-only"))
    with pytest.raises(RuntimeError, match="Could not save transcript"):
        save_transcript("some text", tmp_path / "audio.wav")
