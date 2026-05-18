"""Orchestration tests for _capture_and_process - the core mic-to-injection pipeline."""
from unittest.mock import patch, MagicMock, call
from bertytype import __main__ as app
from bertytype.config import Config


def _setup(health=None, cfg=None):
    """Reset shared state before each test."""
    app._cancel_event.clear()
    app._stop_event.clear()
    app._health = health or {"vibevoice": True, "ollama": True}
    if cfg is not None:
        app._cfg = cfg


def _make_future(value):
    f = MagicMock()
    f.result.return_value = value
    return f


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_happy_path_with_refinement():
    _setup()
    with patch.object(app.capture, "start_recording", return_value=b"audio"), \
         patch.object(app.vad, "trim_silence", return_value=b"trimmed"), \
         patch.object(app.stt_engine, "transcribe", return_value="raw text"), \
         patch.object(app.llm_client, "refine_async", return_value=_make_future("refined text")), \
         patch.object(app.injector, "inject") as mock_inject, \
         patch.object(app.tray, "set_status") as mock_status, \
         patch.object(app.tray, "notify"):
        app._capture_and_process()

    mock_inject.assert_called_once_with("refined text", app._cfg.injection_delay)
    assert mock_status.call_args_list[-1] == call("idle")


def test_happy_path_without_refinement():
    _setup(cfg=Config(refine=False))
    with patch.object(app.capture, "start_recording", return_value=b"audio"), \
         patch.object(app.vad, "trim_silence", return_value=b"trimmed"), \
         patch.object(app.stt_engine, "transcribe", return_value="raw text"), \
         patch.object(app.llm_client, "refine_async") as mock_refine, \
         patch.object(app.injector, "inject") as mock_inject, \
         patch.object(app.tray, "set_status"), \
         patch.object(app.tray, "notify"):
        app._capture_and_process()

    mock_refine.assert_not_called()
    mock_inject.assert_called_once_with("raw text", app._cfg.injection_delay)


def test_refinement_skipped_when_ollama_unhealthy():
    _setup(health={"vibevoice": True, "ollama": False})
    with patch.object(app.capture, "start_recording", return_value=b"audio"), \
         patch.object(app.vad, "trim_silence", return_value=b"trimmed"), \
         patch.object(app.stt_engine, "transcribe", return_value="raw text"), \
         patch.object(app.llm_client, "refine_async") as mock_refine, \
         patch.object(app.injector, "inject") as mock_inject, \
         patch.object(app.tray, "set_status"), \
         patch.object(app.tray, "notify"):
        app._capture_and_process()

    mock_refine.assert_not_called()
    mock_inject.assert_called_once_with("raw text", app._cfg.injection_delay)


# ---------------------------------------------------------------------------
# Cancel path
# ---------------------------------------------------------------------------

def test_cancel_during_recording_skips_processing():
    _setup()
    app._cancel_event.set()  # already set when start_recording returns

    with patch.object(app.capture, "start_recording", return_value=b"audio"), \
         patch.object(app.vad, "trim_silence") as mock_vad, \
         patch.object(app.stt_engine, "transcribe") as mock_stt, \
         patch.object(app.injector, "inject") as mock_inject, \
         patch.object(app.tray, "set_status") as mock_status, \
         patch.object(app.tray, "notify"):
        app._capture_and_process()

    mock_vad.assert_not_called()
    mock_stt.assert_not_called()
    mock_inject.assert_not_called()
    mock_status.assert_called_with("idle")


# ---------------------------------------------------------------------------
# Empty audio path
# ---------------------------------------------------------------------------

def test_empty_audio_after_vad_sets_idle_without_transcribing():
    _setup()
    with patch.object(app.capture, "start_recording", return_value=b"audio"), \
         patch.object(app.vad, "trim_silence", return_value=b""), \
         patch.object(app.stt_engine, "transcribe") as mock_stt, \
         patch.object(app.injector, "inject") as mock_inject, \
         patch.object(app.tray, "set_status") as mock_status, \
         patch.object(app.tray, "notify"):
        app._capture_and_process()

    mock_stt.assert_not_called()
    mock_inject.assert_not_called()
    mock_status.assert_called_with("idle")


# ---------------------------------------------------------------------------
# Injection failure falls back to clipboard
# ---------------------------------------------------------------------------

def test_injection_failure_copies_to_clipboard():
    _setup(cfg=Config(refine=False))
    with patch.object(app.capture, "start_recording", return_value=b"audio"), \
         patch.object(app.vad, "trim_silence", return_value=b"trimmed"), \
         patch.object(app.stt_engine, "transcribe", return_value="text"), \
         patch.object(app.injector, "inject", side_effect=Exception("inject failed")), \
         patch("bertytype.__main__.pyperclip") as mock_clip, \
         patch.object(app.tray, "set_status"), \
         patch.object(app.tray, "notify") as mock_notify:
        app._capture_and_process()

    mock_clip.copy.assert_called_once_with("text")
    mock_notify.assert_called_once()


# ---------------------------------------------------------------------------
# LLM refinement failure falls back to raw text
# ---------------------------------------------------------------------------

def test_llm_failure_falls_back_to_raw_text():
    _setup()
    bad_future = MagicMock()
    bad_future.result.side_effect = Exception("timeout")

    with patch.object(app.capture, "start_recording", return_value=b"audio"), \
         patch.object(app.vad, "trim_silence", return_value=b"trimmed"), \
         patch.object(app.stt_engine, "transcribe", return_value="raw text"), \
         patch.object(app.llm_client, "refine_async", return_value=bad_future), \
         patch.object(app.injector, "inject") as mock_inject, \
         patch.object(app.tray, "set_status"), \
         patch.object(app.tray, "notify"):
        app._capture_and_process()

    mock_inject.assert_called_once_with("raw text", app._cfg.injection_delay)


# ---------------------------------------------------------------------------
# LLM refinement failure notifies tray
# ---------------------------------------------------------------------------

def test_refinement_failure_notifies_tray(mocker):
    """LLM failure during PTT transcription shows tray notification."""
    from bertytype import __main__ as app
    mocker.patch.object(app.capture, "start_recording", return_value=b"\x00" * 3200)
    mocker.patch.object(app.vad, "trim_silence", return_value=b"\x00" * 3200)
    mocker.patch.object(app.stt_engine, "transcribe", return_value="raw text")
    mock_future = mocker.MagicMock()
    mock_future.result.side_effect = RuntimeError("ollama down")
    mocker.patch.object(app.llm_client, "refine_async", return_value=mock_future)
    mock_inject = mocker.patch.object(app.injector, "inject")
    mock_notify = mocker.patch.object(app.tray, "notify")
    mocker.patch.object(app.tray, "set_status")

    with app._cfg_lock:
        app._cfg = app.cfg_module.Config(refine=True)
    with app._health_lock:
        app._health = {"vibevoice": True, "ollama": True}

    app._capture_and_process()

    mock_notify.assert_any_call(app.messages.ERROR_OLLAMA_UNAVAILABLE)
    mock_inject.assert_called_once_with("raw text", app._cfg.injection_delay)


# ---------------------------------------------------------------------------
# STT failure surfaces as error status
# ---------------------------------------------------------------------------

def test_stt_failure_sets_error_status():
    _setup()
    with patch.object(app.capture, "start_recording", return_value=b"audio"), \
         patch.object(app.vad, "trim_silence", return_value=b"trimmed"), \
         patch.object(app.stt_engine, "transcribe", side_effect=RuntimeError("stt crash")), \
         patch.object(app.injector, "inject") as mock_inject, \
         patch.object(app.tray, "set_status") as mock_status, \
         patch.object(app.tray, "notify") as mock_notify:
        app._capture_and_process()

    mock_inject.assert_not_called()
    mock_status.assert_called_with("error")
    mock_notify.assert_called_once()
