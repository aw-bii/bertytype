from __future__ import annotations
import atexit
import sys
import threading
from pathlib import Path
import pyperclip
import requests

from PySide6.QtWidgets import QApplication, QFileDialog

from bertytype import config as cfg_module
from bertytype.audio import capture, vad, reader
from bertytype.stt import engine as stt_engine, vibevoice, vibevoice_local
from bertytype.llm import client as llm_client
from bertytype.injection import injector, exporter
from bertytype.hotkeys import daemon as hotkey_daemon
from bertytype.ui import tray, settings, tokens
from bertytype.ui.theme_watcher import ThemeWatcher
from bertytype import messages
from bertytype import logging as log_module

logger = log_module.logger

_cfg = cfg_module.Config()
_cfg_lock = threading.Lock()
_stop_event = threading.Event()
_cancel_event = threading.Event()
_quit_event = threading.Event()
_health = {"vibevoice": False, "ollama": False}
_health_lock = threading.Lock()
_theme_watcher: ThemeWatcher | None = None
_settings_dialog: "settings._SettingsDialog | None" = None


def _on_ptt_press() -> None:
    _cancel_event.clear()
    _stop_event.clear()
    tray.set_status("recording")
    thread = threading.Thread(target=_capture_and_process, daemon=True)
    thread.start()


def _on_ptt_release() -> None:
    _stop_event.set()


def _on_cancel() -> None:
    _cancel_event.set()
    _stop_event.set()


def _apply_llm_refinement(text: str, cfg, health: dict) -> str:
    """Returns LLM-refined text, or original text if refinement is disabled, unavailable, or fails."""
    if not cfg.refine:
        return text
    if not health["ollama"]:
        logger.info("Skipping refinement - Ollama unavailable")
        return text
    try:
        future = llm_client.refine_async(text, "clean_up", cfg.model, cfg.llm_timeout)
        return future.result(timeout=cfg.llm_timeout + 5)
    except Exception as e:
        logger.warning(f"LLM refinement failed: {e}")
        tray.notify(messages.ERROR_OLLAMA_UNAVAILABLE)
        return text


def _capture_and_process() -> None:
    with _health_lock:
        health = _health.copy()
    with _cfg_lock:
        cfg = _cfg
    try:
        audio = capture.start_recording(_stop_event, _cancel_event)
        if _cancel_event.is_set():
            tray.set_status("idle")
            return
        tray.set_status("processing")
        audio = vad.trim_silence(audio, threshold=cfg.vad_threshold)
        if not audio:
            tray.set_status("idle")
            return
        text = stt_engine.transcribe(audio)
        text = _apply_llm_refinement(text, cfg, health)
        try:
            injector.inject(text, cfg.injection_delay)
            if cfg.show_completion_notification:
                preview = text[:60] + ("..." if len(text) > 60 else "")
                tray.notify(preview)
        except Exception as e:
            logger.warning(f"Injection failed: {e}")
            pyperclip.copy(text)
            tray.notify(messages.ERROR_INJECTION_FAILED)
        tray.set_status("idle")
    except Exception as e:
        logger.exception(f"Transcription failed: {e}")
        tray.set_status("error")
        tray.notify(messages.ERROR_TRANSCRIPTION_FAILED)


def _on_transcribe_file() -> None:
    path_str, _ = QFileDialog.getOpenFileName(
        None,
        "Select audio file",
        "",
        "Audio files (*.wav *.mp3 *.m4a *.flac);;All files (*.*)",
    )
    if not path_str:
        return
    threading.Thread(
        target=_do_file_transcription, args=(Path(path_str),), daemon=True
    ).start()


def _do_file_transcription(path: Path) -> None:
    with _health_lock:
        health = _health.copy()
    with _cfg_lock:
        cfg = _cfg
    try:
        tray.set_status("processing")
        audio = reader.read_file(path)
        if not audio:
            tray.set_status("error")
            tray.notify(messages.ERROR_FILE_READ_FAILED)
            return
        text = stt_engine.transcribe(audio)
        text = _apply_llm_refinement(text, cfg, health)
        out_path = exporter.save_transcript(text, path)
        pyperclip.copy(text)
        tray.notify(messages.INFO_TRANSCRIPTION_COMPLETE.format(name=out_path.name))
        tray.set_status("idle")
    except Exception as e:
        logger.exception(f"File transcription failed: {e}")
        tray.set_status("error")
        tray.notify(messages.ERROR_TRANSCRIPTION_FAILED)


def _register_hotkeys(cfg: cfg_module.Config) -> None:
    _stop_event.set()   # signal any in-progress recording to stop cleanly
    # _stop_event is intentionally left set here; _on_ptt_press clears it on the next press.
    hotkey_daemon.stop()
    try:
        if cfg.hotkey_mode == "double_tap_toggle":
            hotkey_daemon.register_double_tap_toggle(
                cfg.hotkey,
                on_start=_on_ptt_press,
                on_stop=_on_ptt_release,
                window=cfg.double_tap_window,
            )
        else:
            hotkey_daemon.register_ptt(
                cfg.hotkey,
                on_press=_on_ptt_press,
                on_release=_on_ptt_release,
            )
        hotkey_daemon.register(cfg.cancel_hotkey, _on_cancel)
    except Exception:
        hotkey_daemon.stop()
        raise


def _on_open_settings() -> None:
    global _settings_dialog

    def _save(updated_cfg: cfg_module.Config) -> None:
        global _cfg
        with _cfg_lock:
            _cfg = updated_cfg
        cfg_module.save(updated_cfg)
        _register_hotkeys(updated_cfg)

    with _cfg_lock:
        current_cfg = _cfg

    if _settings_dialog is None:
        _settings_dialog = settings._SettingsDialog(current_cfg, on_save=_save)
        _settings_dialog._lazy_mode = True
    else:
        _settings_dialog._on_save = _save
        _settings_dialog.load_config(current_cfg)

    _settings_dialog.show()
    _settings_dialog.raise_()
    _settings_dialog.activateWindow()


def _cleanup() -> None:
    _quit_event.set()
    _stop_event.set()  # signal any in-progress recording to stop
    if _theme_watcher is not None:
        try:
            _theme_watcher.stop()
        except Exception as e:
            logger.warning(f"Cleanup error in theme_watcher: {e}")
    for fn, name in [
        (hotkey_daemon.stop, "hotkey_daemon"),
        (llm_client.shutdown, "llm_client"),
        (tray.stop, "tray"),
    ]:
        try:
            fn()
        except Exception as e:
            logger.warning(f"Cleanup error in {name}: {e}")


def _on_quit() -> None:
    _cleanup()
    app = QApplication.instance()
    if app is not None:
        app.quit()


def _check_health() -> dict[str, bool]:
    health = {"vibevoice": False, "ollama": False}
    try:
        with requests.get("http://localhost:11434/api/tags", timeout=5) as resp:
            health["ollama"] = resp.status_code == 200
    except (requests.ConnectionError, requests.Timeout):
        health["ollama"] = False
    if vibevoice_local.is_available():
        health["vibevoice"] = True
    else:
        try:
            with requests.get("http://localhost:8000/v1/models", timeout=5) as resp:
                health["vibevoice"] = resp.status_code == 200
        except (requests.ConnectionError, requests.Timeout):
            health["vibevoice"] = False
    return health


def _maybe_pull_model(model: str) -> None:
    import subprocess
    try:
        with requests.get("http://localhost:11434/api/tags", timeout=5) as resp:
            if resp.status_code != 200:
                return
            present = [m["name"] for m in resp.json().get("models", [])]
            if model in present:
                return
    except (requests.ConnectionError, requests.Timeout):
        return

    def _pull() -> None:
        tray.notify(f"Pulling {model} - this may take a few minutes...")
        logger.info(f"Pulling Ollama model: {model}")
        result = subprocess.run(["ollama", "pull", model], capture_output=True)
        if result.returncode == 0:
            tray.notify(f"{model} ready")
            logger.info(f"Model {model} pulled successfully")
        else:
            logger.warning(f"ollama pull failed: {result.stderr.decode('utf-8', errors='replace')}")

    threading.Thread(target=_pull, daemon=True).start()


def _periodic_health_check(interval: int = 60) -> None:
    global _health
    while not _quit_event.is_set():
        new_health = _check_health()
        logger.debug(f"Periodic health: vibevoice={new_health['vibevoice']}, ollama={new_health['ollama']}")
        with _health_lock:
            _health = new_health
        with _cfg_lock:
            cfg = _cfg
        if new_health["ollama"] and cfg.refine:
            _maybe_pull_model(cfg.model)
        _quit_event.wait(interval)


def _run_setup_if_needed() -> bool:
    try:
        from bertytype_setup.checks import check_all
        from bertytype_setup.wizard import SetupWizard
    except Exception:
        logger.exception("Failed to import bertytype_setup")
        return True
    try:
        check_results = check_all()
    except Exception:
        logger.exception("check_all() failed")
        check_results = {}
    logger.info(f"Setup checks: {check_results}")
    if all(check_results.values()) and check_results:
        return True
    wizard = SetupWizard()
    wizard.exec()
    return wizard.launch_requested


def main() -> None:
    atexit.register(_cleanup)
    log_module.init_file_logging()
    app = QApplication(sys.argv)
    global _theme_watcher
    _theme_watcher = ThemeWatcher()

    def _on_theme_changed(theme: str) -> None:
        app.setStyleSheet(tokens.build_qss(theme))

    _theme_watcher.theme_changed.connect(_on_theme_changed)
    app.setStyleSheet(tokens.build_qss(_theme_watcher.current_theme()))
    app.setQuitOnLastWindowClosed(False)
    global _cfg
    with _cfg_lock:
        _cfg = cfg_module.load()
    if not _run_setup_if_needed():
        return

    if vibevoice_local.is_available():
        stt_engine.set_backend(vibevoice_local.transcribe)
        logger.info("Using local VibeVoice (Transformers)")
    else:
        stt_engine.set_backend(vibevoice.transcribe)
        logger.info("Using HTTP VibeVoice (vLLM)")

    monitor_thread = threading.Thread(target=_periodic_health_check, daemon=True)
    monitor_thread.start()

    with _cfg_lock:
        cfg = _cfg
    _register_hotkeys(cfg)

    tray.start(
        cfg=cfg,
        on_transcribe_file=_on_transcribe_file,
        on_open_settings=_on_open_settings,
        on_quit=_on_quit,
    )
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
