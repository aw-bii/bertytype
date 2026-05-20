import threading
from unittest.mock import patch
from bertytype import __main__ as app


def test_health_monitor_stops_when_quit_event_is_set():
    app._quit_event.clear()

    try:
        with patch.object(app, "_check_health", return_value={"vibevoice": False, "ollama": False}):
            thread = threading.Thread(
                target=app._periodic_health_check,
                args=(0,),
                daemon=True,
            )
            thread.start()
            app._quit_event.set()
            thread.join(timeout=2.0)

        assert not thread.is_alive(), "Health monitor did not stop after _quit_event was set"
    finally:
        app._quit_event.clear()


def test_cleanup_sets_quit_event():
    import bertytype.__main__ as main_mod
    from unittest.mock import patch, MagicMock
    with patch.object(main_mod, "llm_client") as mock_llm, \
         patch.object(main_mod, "hotkey_daemon") as mock_hk, \
         patch.object(main_mod, "tray") as mock_tray:
        main_mod._quit_event.clear()
        main_mod._cleanup()
        assert main_mod._quit_event.is_set()


def test_cleanup_stops_subsystems_in_order():
    import bertytype.__main__ as main_mod
    from unittest.mock import patch, MagicMock, call
    call_log = []
    with patch.object(main_mod, "llm_client") as m_llm, \
         patch.object(main_mod, "hotkey_daemon") as m_hk, \
         patch.object(main_mod, "tray") as m_tray:
        m_llm.shutdown.side_effect = lambda: call_log.append("llm")
        m_hk.stop.side_effect = lambda: call_log.append("hk")
        m_tray.stop.side_effect = lambda: call_log.append("tray")
        main_mod._cleanup()
    assert call_log == ["llm", "hk", "tray"]


def test_cleanup_survives_subsystem_exception():
    import bertytype.__main__ as main_mod
    from unittest.mock import patch
    with patch.object(main_mod, "llm_client") as m_llm, \
         patch.object(main_mod, "hotkey_daemon") as m_hk, \
         patch.object(main_mod, "tray") as m_tray:
        m_llm.shutdown.side_effect = RuntimeError("crash")
        main_mod._cleanup()  # must not raise
