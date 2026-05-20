from __future__ import annotations
from typing import Callable
from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QScrollArea, QWidget, QVBoxLayout,
    QHBoxLayout, QLabel, QComboBox, QKeySequenceEdit, QCheckBox,
    QSlider, QLineEdit, QPushButton, QFrame,
)
from bertytype.config import Config, _is_safe_model_name, _VALID_HOTKEY_MODES
from bertytype.ui.tokens import TEXT_SECONDARY


def _qks_to_str(ks: QKeySequence) -> str:
    return ks.toString(QKeySequence.SequenceFormat.PortableText).lower()


def _str_to_qks(s: str) -> QKeySequence:
    return QKeySequence.fromString(s, QKeySequence.SequenceFormat.PortableText)


def open_settings(cfg: Config, on_save: Callable[[Config], None]) -> None:
    dlg = _SettingsDialog(cfg, on_save)
    dlg.exec()


class _SettingsDialog(QDialog):
    def __init__(self, cfg: Config, on_save: Callable[[Config], None]) -> None:
        super().__init__()
        self.setWindowTitle("BertyType Settings")
        self.setMinimumSize(480, 400)
        self._on_save = on_save
        self._build_ui(cfg)
        self._hotkey_edit.setFocus()

    def _build_ui(self, cfg: Config) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setContentsMargins(18, 12, 18, 12)
        form.setHorizontalSpacing(16)
        form.setVerticalSpacing(10)

        self._mode_combo = QComboBox()
        self._mode_combo.addItems(sorted(_VALID_HOTKEY_MODES))
        self._mode_combo.setCurrentText(cfg.hotkey_mode)
        self._mode_combo.setToolTip("ptt: hold to record / double_tap_toggle: tap twice to toggle recording")
        form.addRow("Recording Mode", self._mode_combo)

        self._hotkey_edit = QKeySequenceEdit(_str_to_qks(cfg.hotkey))
        self._hotkey_edit.setToolTip("Press the key combination to use as your push-to-talk hotkey")
        form.addRow("Hotkey", self._hotkey_edit)

        self._dtw_slider = QSlider(Qt.Orientation.Horizontal)
        self._dtw_slider.setRange(5, 200)
        self._dtw_slider.setValue(round(cfg.double_tap_window * 100))
        self._dtw_slider.setToolTip("Max time between two taps to trigger double-tap toggle (0.05 - 2.00s)")
        self._dtw_label = QLabel(f"{cfg.double_tap_window:.2f}s")
        self._dtw_slider.valueChanged.connect(
            lambda v: self._dtw_label.setText(f"{v / 100:.2f}s")
        )
        dtw_row = QWidget()
        dtw_layout = QHBoxLayout(dtw_row)
        dtw_layout.setContentsMargins(0, 0, 0, 0)
        dtw_layout.addWidget(self._dtw_slider)
        dtw_layout.addWidget(self._dtw_label)
        form.addRow("Double-tap Window", dtw_row)

        self._cancel_edit = QKeySequenceEdit(_str_to_qks(cfg.cancel_hotkey))
        self._cancel_edit.setToolTip("Press the key combination to cancel an in-progress recording")
        form.addRow("Cancel Hotkey", self._cancel_edit)

        self._model_edit = QLineEdit(cfg.model)
        self._model_edit.setToolTip("Ollama model name for LLM refinement (e.g. gemma4:e2b)")
        form.addRow("LLM Model", self._model_edit)

        self._refine_check = QCheckBox()
        self._refine_check.setChecked(cfg.refine)
        self._refine_check.setToolTip("Run transcribed text through the LLM to clean up filler words and punctuation")
        form.addRow("Refine with LLM", self._refine_check)

        self._vad_slider = QSlider(Qt.Orientation.Horizontal)
        self._vad_slider.setRange(0, 100)
        self._vad_slider.setValue(round(cfg.vad_threshold * 100))
        self._vad_slider.setToolTip("Silence threshold for voice activity detection (0.00 = very sensitive, 1.00 = least sensitive)")
        self._vad_label = QLabel(f"{cfg.vad_threshold:.2f}")
        self._vad_slider.valueChanged.connect(
            lambda v: self._vad_label.setText(f"{v / 100:.2f}")
        )
        vad_row = QWidget()
        vad_layout = QHBoxLayout(vad_row)
        vad_layout.setContentsMargins(0, 0, 0, 0)
        vad_layout.addWidget(self._vad_slider)
        vad_layout.addWidget(self._vad_label)
        form.addRow("VAD Threshold", vad_row)

        self._llm_to_edit = QLineEdit(str(cfg.llm_timeout))
        self._llm_to_edit.setToolTip("Seconds to wait for LLM response before timing out (1 - 600)")
        form.addRow("LLM Timeout", self._llm_to_edit)

        self._delay_edit = QLineEdit(str(cfg.injection_delay))
        self._delay_edit.setToolTip("Seconds to wait after focusing target window before injecting text (0.0 - 5.0)")
        form.addRow("Injection Delay", self._delay_edit)

        for row in range(form.rowCount()):
            lbl_item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            if lbl_item and lbl_item.widget():
                lbl_item.widget().setStyleSheet(f"color: {TEXT_SECONDARY}; font-size: 12px;")

        self._form = form
        self._mode_combo.currentTextChanged.connect(self._on_mode_changed)
        self._on_mode_changed(cfg.hotkey_mode)

        scroll.setWidget(form_widget)
        outer.addWidget(scroll, 1)

        footer = QWidget()
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(18, 10, 18, 10)
        self._error_lbl = QLabel()
        self._error_lbl.setObjectName("errorLabel")
        self._error_lbl.setStyleSheet("color: #e84040;")
        self._error_lbl.setFocusPolicy(Qt.FocusPolicy.TabFocus)
        self._error_lbl.setAccessibleName("Error")
        footer_layout.addWidget(self._error_lbl, 1)
        save_btn = QPushButton("SAVE SETTINGS")
        save_btn.setProperty("accent", True)
        save_btn.setDefault(True)
        save_btn.clicked.connect(self._save)
        footer_layout.addWidget(save_btn)
        outer.addWidget(footer)

    def _on_mode_changed(self, mode: str) -> None:
        self._form.setRowVisible(2, mode == "double_tap_toggle")

    def _err(self, msg: str) -> None:
        self._error_lbl.setText(msg)
        self._error_lbl.setFocus()

    def _save(self) -> None:
        self._error_lbl.setText("")

        hotkey = _qks_to_str(self._hotkey_edit.keySequence())
        if not hotkey:
            self._err("Hotkey must not be empty")
            return

        cancel_hotkey = _qks_to_str(self._cancel_edit.keySequence())
        if not cancel_hotkey:
            self._err("Cancel Hotkey must not be empty")
            return

        model = self._model_edit.text().strip()
        if not model:
            self._err("LLM Model must not be empty")
            return

        if not _is_safe_model_name(model):
            self._err("Model name contains invalid characters")
            return

        try:
            llm_timeout = int(self._llm_to_edit.text())
            if not (1 <= llm_timeout <= 600):
                raise ValueError
        except ValueError:
            self._err("LLM Timeout must be a whole number between 1 and 600")
            return

        try:
            injection_delay = float(self._delay_edit.text())
            if not (0.0 <= injection_delay <= 5.0):
                raise ValueError
        except ValueError:
            self._err("Injection Delay must be a number between 0.0 and 5.0")
            return

        updated = Config(
            hotkey=hotkey,
            hotkey_mode=self._mode_combo.currentText(),
            cancel_hotkey=cancel_hotkey,
            model=model,
            refine=self._refine_check.isChecked(),
            vad_threshold=self._vad_slider.value() / 100,
            llm_timeout=llm_timeout,
            injection_delay=injection_delay,
            double_tap_window=self._dtw_slider.value() / 100,
        )
        try:
            self._on_save(updated)
        except Exception as exc:
            self._err(f"Could not save settings: {exc}")
            return
        self.accept()
