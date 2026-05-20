import pytest
from PySide6.QtGui import QKeySequence


def test_qks_round_trip_ctrl_shift_space():
    from bertytype.ui.settings import _qks_to_str, _str_to_qks
    assert _qks_to_str(_str_to_qks("ctrl+shift+space")) == "ctrl+shift+space"


def test_qks_round_trip_alt_f9():
    from bertytype.ui.settings import _qks_to_str, _str_to_qks
    assert _qks_to_str(_str_to_qks("alt+f9")) == "alt+f9"


def test_empty_sequence_returns_empty():
    from bertytype.ui.settings import _qks_to_str
    assert _qks_to_str(QKeySequence()) == ""


def test_output_is_lowercase():
    from bertytype.ui.settings import _qks_to_str, _str_to_qks
    result = _qks_to_str(_str_to_qks("ctrl+shift+space"))
    assert result == result.lower()


def test_dialog_opens_without_crash(qapp):
    from bertytype.ui.settings import _SettingsDialog
    from bertytype.config import Config
    cfg = Config()
    dlg = _SettingsDialog(cfg, on_save=lambda c: None)
    assert dlg is not None
    dlg.close()


def test_dialog_save_calls_on_save(qapp):
    from bertytype.ui.settings import _SettingsDialog
    from bertytype.config import Config
    saved = []
    cfg = Config()
    dlg = _SettingsDialog(cfg, on_save=saved.append)
    dlg._save()
    assert len(saved) == 1
    assert isinstance(saved[0], Config)


def test_dialog_save_rejects_empty_hotkey(qapp):
    from bertytype.ui.settings import _SettingsDialog
    from bertytype.config import Config
    from PySide6.QtGui import QKeySequence
    saved = []
    cfg = Config()
    dlg = _SettingsDialog(cfg, on_save=saved.append)
    dlg._hotkey_edit.setKeySequence(QKeySequence())
    dlg._save()
    assert saved == []
    assert dlg._error_lbl.text() != ""


def test_str_to_qks_not_empty_for_default_hotkeys():
    from bertytype.ui.settings import _str_to_qks
    assert not _str_to_qks("alt").isEmpty()
    assert not _str_to_qks("escape").isEmpty()
    assert not _str_to_qks("ctrl+shift+space").isEmpty()


def test_dialog_save_rejects_unsafe_model(qapp):
    from bertytype.ui.settings import _SettingsDialog
    from bertytype.config import Config
    saved = []
    cfg = Config()
    dlg = _SettingsDialog(cfg, on_save=saved.append)
    dlg._model_edit.setText("; rm -rf ~")
    dlg._save()
    assert saved == []
    assert dlg._error_lbl.text() != ""


def test_dialog_save_rejects_invalid_llm_timeout(qapp):
    from bertytype.ui.settings import _SettingsDialog
    from bertytype.config import Config
    saved = []
    cfg = Config()
    dlg = _SettingsDialog(cfg, on_save=saved.append)
    dlg._llm_to_edit.setText("999")
    dlg._save()
    assert saved == []
    assert dlg._error_lbl.text() != ""


def test_dialog_save_on_save_exception_shows_error(qapp):
    from bertytype.ui.settings import _SettingsDialog
    from bertytype.config import Config
    cfg = Config()

    def raising_save(_):
        raise OSError("disk full")

    dlg = _SettingsDialog(cfg, on_save=raising_save)
    dlg._save()
    assert "disk full" in dlg._error_lbl.text()
    assert dlg.result() != 1  # dialog did not accept


def test_dtw_row_hidden_in_ptt_mode(qapp):
    from bertytype.ui.settings import _SettingsDialog
    from bertytype.config import Config
    cfg = Config(hotkey_mode="ptt")
    dlg = _SettingsDialog(cfg, on_save=lambda c: None)
    # row 2 should be hidden
    assert not dlg._form.isRowVisible(2)
    dlg.close()


def test_dtw_row_visible_in_double_tap_mode(qapp):
    from bertytype.ui.settings import _SettingsDialog
    from bertytype.config import Config
    cfg = Config(hotkey_mode="double_tap_toggle")
    dlg = _SettingsDialog(cfg, on_save=lambda c: None)
    assert dlg._form.isRowVisible(2)
    dlg.close()


def test_save_button_is_default(qapp):
    from bertytype.ui.settings import _SettingsDialog
    from bertytype.config import Config
    from PySide6.QtWidgets import QPushButton
    cfg = Config()
    dlg = _SettingsDialog(cfg, on_save=lambda c: None)
    buttons = dlg.findChildren(QPushButton)
    default_buttons = [b for b in buttons if b.isDefault()]
    assert len(default_buttons) == 1
    assert default_buttons[0].text() == "SAVE SETTINGS"
    dlg.close()


def test_dialog_minimum_width_scales_with_dpi(qapp):
    from bertytype.ui.settings import _SettingsDialog
    from bertytype.config import Config
    from PySide6.QtWidgets import QApplication
    cfg = Config()
    dlg = _SettingsDialog(cfg, on_save=lambda c: None)
    dpi = QApplication.primaryScreen().logicalDotsPerInch()
    expected_min = int(480 * (dpi / 96.0))
    assert dlg.minimumWidth() >= expected_min - 1  # allow rounding
    dlg.close()


def test_invalid_hotkey_highlights_field(qapp):
    from bertytype.ui.settings import _SettingsDialog
    from bertytype.config import Config
    from PySide6.QtGui import QKeySequence
    cfg = Config()
    dlg = _SettingsDialog(cfg, on_save=lambda c: None)
    dlg._hotkey_edit.setKeySequence(QKeySequence())
    dlg._save()
    # The hotkey edit should have a red left-border applied
    style = dlg._hotkey_edit.styleSheet()
    assert "#f3727f" in style or "f3727f" in style.lower()
    dlg.close()


def test_error_highlight_clears_on_valid_save(qapp):
    from bertytype.ui.settings import _SettingsDialog
    from bertytype.config import Config
    from PySide6.QtGui import QKeySequence
    saved = []
    cfg = Config()
    dlg = _SettingsDialog(cfg, on_save=saved.append)
    # First: trigger error
    dlg._hotkey_edit.setKeySequence(QKeySequence())
    dlg._save()
    assert "#f3727f" in dlg._hotkey_edit.styleSheet()
    # Then: fix and save
    from bertytype.ui.settings import _str_to_qks
    dlg._hotkey_edit.setKeySequence(_str_to_qks("alt"))
    dlg._save()
    # Highlight should be cleared
    assert "#f3727f" not in dlg._hotkey_edit.styleSheet()
