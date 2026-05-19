from __future__ import annotations
import queue
import threading
from typing import Callable

from PySide6.QtCore import QObject, QThread, Signal, Qt
from PySide6.QtWidgets import (
    QWizard, QWizardPage, QLabel, QVBoxLayout, QHBoxLayout,
    QWidget, QProgressBar, QPlainTextEdit, QCheckBox,
)

from bertytype_setup import checks, installers
from bertytype_setup.constants import MODEL

TITLE = "BertyType Setup"

DEPS = [
    ("ollama",    "Ollama",              "~90 MB"),
    ("model",     f"{MODEL} model",      "~2 GB"),
    ("vibevoice", "VibeVoice ASR model", "~1.5 GB"),
    ("ffmpeg",    "ffmpeg",              "Bundled"),
]

_PAGE_WELCOME = 0
_PAGE_CHECK   = 1
_PAGE_INSTALL = 2
_PAGE_FINISH  = 3


class _CheckWorker(QThread):
    check_done = Signal(dict)

    def run(self) -> None:
        result = checks.check_all()
        self.check_done.emit(result)


class _InstallWorker(QThread):
    log_msg       = Signal(str)
    step_started  = Signal(str)
    step_done     = Signal(str)
    step_failed   = Signal(str)
    step_skipped  = Signal(str)
    step_progress = Signal(str, float)
    all_done      = Signal(list)

    def __init__(self, steps: list[str], cancel: threading.Event) -> None:
        super().__init__()
        self._steps  = steps
        self._cancel = cancel

    def run(self) -> None:
        q = queue.Queue()
        t = threading.Thread(
            target=installers.run_all_installs,
            args=(q, self._cancel, self._steps),
            daemon=True,
        )
        t.start()
        failures: list[str] = []
        _dispatch: dict[str, Callable] = {
            "log":           lambda *a: self.log_msg.emit(a[0]),
            "step_start":    lambda *a: self.step_started.emit(a[0]),
            "step_done":     lambda *a: self.step_done.emit(a[0]),
            "step_failed":   lambda *a: self.step_failed.emit(a[0]),
            "step_skipped":  lambda *a: self.step_skipped.emit(a[0]),
            "step_progress": lambda *a: self.step_progress.emit(a[0], a[1]),
        }
        while True:
            try:
                item = q.get(timeout=0.05)
            except queue.Empty:
                if not t.is_alive():
                    # drain any remaining items the thread may have put in after is_alive() returned False
                    while True:
                        try:
                            item = q.get_nowait()
                        except queue.Empty:
                            break
                        event, *args = item
                        if event in _dispatch:
                            _dispatch[event](*args)
                        if event == "step_failed":
                            failures.append(args[0])
                        if event == "all_done":
                            break
                    break
                continue
            event, *args = item
            if event in _dispatch:
                _dispatch[event](*args)
            if event == "step_failed":
                failures.append(args[0])
            if event == "all_done":
                break
        t.join()
        self.all_done.emit(failures)


class WelcomePage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle(TITLE)
        layout = QVBoxLayout(self)
        desc = QLabel(
            "This wizard will download and install all required\n"
            "components for BertyType. An internet connection is required."
        )
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)
        layout.addSpacing(8)
        layout.addWidget(QLabel("The following will be installed:"))
        for _, name, size in DEPS:
            layout.addWidget(QLabel(f"  {name}  ({size})"))


class CheckPage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Checking dependencies...")
        self._badges: dict[str, QLabel] = {}
        self._steps: list[str] = []
        self._complete = False
        layout = QVBoxLayout(self)
        for key, name, _ in DEPS:
            row = QWidget()
            row_l = QHBoxLayout(row)
            row_l.setContentsMargins(0, 0, 0, 0)
            row_l.addWidget(QLabel(name), 1)
            badge = QLabel("Checking...")
            self._badges[key] = badge
            row_l.addWidget(badge)
            layout.addWidget(row)
        self._worker: _CheckWorker | None = None

    def initializePage(self) -> None:
        self._complete = False
        self._worker = _CheckWorker()
        self._worker.check_done.connect(self._on_check_done)
        self._worker.start()

    def _on_check_done(self, result: dict) -> None:
        all_ok = True
        for key, _, _ in DEPS:
            if key == "ffmpeg":
                self._badges[key].setText("Included")
                continue
            if result.get(key, False):
                self._badges[key].setText("Already installed")
            else:
                self._badges[key].setText("Will be downloaded")
                all_ok = False
        self._steps = [] if all_ok else [
            k for k in ("ollama", "model", "vibevoice")
            if not result.get(k, False)
        ]
        self._complete = True
        self.completeChanged.emit()

    def isComplete(self) -> bool:
        return self._complete

    def steps_to_install(self) -> list[str]:
        return self._steps


class InstallPage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Installing...")
        self.setCommitPage(True)
        self._indicators: dict[str, QLabel] = {}
        self._pbars: dict[str, QProgressBar] = {}
        self._cancel_event = threading.Event()
        self._failures: list[str] = []
        self._complete = False
        layout = QVBoxLayout(self)
        for key, name, _ in DEPS:
            if key == "ffmpeg":
                continue
            row = QWidget()
            row_l = QHBoxLayout(row)
            row_l.setContentsMargins(0, 0, 0, 0)
            row_l.addWidget(QLabel(name), 1)
            ind = QLabel("Pending")
            self._indicators[key] = ind
            row_l.addWidget(ind)
            pb = QProgressBar()
            pb.setRange(0, 100)
            pb.setValue(0)
            pb.setMaximumWidth(130)
            self._pbars[key] = pb
            row_l.addWidget(pb)
            layout.addWidget(row)
        self._log = QPlainTextEdit()
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(120)
        layout.addWidget(self._log)
        self._overall = QProgressBar()
        self._overall.setRange(0, 100)
        layout.addWidget(self._overall)
        self._worker: _InstallWorker | None = None

    def initializePage(self) -> None:
        check_page = self.wizard().page(_PAGE_CHECK) if self.wizard() else None
        steps = check_page.steps_to_install() if check_page else []
        if not steps:
            self._complete = True
            self.completeChanged.emit()
            return
        self._cancel_event.clear()
        self._failures = []
        self._complete = False
        self._worker = _InstallWorker(steps, self._cancel_event)
        self._worker.log_msg.connect(self._log.appendPlainText)
        self._worker.step_started.connect(
            lambda k: self._indicators[k].setText("|") if k in self._indicators else None
        )
        self._worker.step_done.connect(self._on_step_done)
        self._worker.step_failed.connect(self._on_step_failed)
        self._worker.step_skipped.connect(
            lambda k: self._indicators[k].setText("Skipped") if k in self._indicators else None
        )
        self._worker.step_progress.connect(self._on_step_progress)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.start()

    def _on_step_done(self, key: str) -> None:
        if key in self._indicators:
            self._indicators[key].setText("Done")
        if key in self._pbars:
            self._pbars[key].setValue(100)
        self._advance_overall()

    def _on_step_failed(self, key: str) -> None:
        if key in self._indicators:
            self._indicators[key].setText("Failed")
        self._advance_overall()

    def _on_step_progress(self, key: str, fraction: float) -> None:
        if key in self._pbars:
            self._pbars[key].setValue(int(fraction * 100))

    def _on_all_done(self, failures: list[str]) -> None:
        self._failures = failures
        self._complete = True
        self.completeChanged.emit()

    def _advance_overall(self) -> None:
        done = sum(
            1 for ind in self._indicators.values()
            if ind.text() in ("Done", "Failed", "Skipped")
        )
        total = len(self._indicators)
        self._overall.setValue(int(done / total * 100) if total else 100)

    def isComplete(self) -> bool:
        return self._complete

    def cancel(self) -> None:
        self._cancel_event.set()

    def failures(self) -> list[str]:
        return self._failures


class FinishPage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Setup complete!")
        layout = QVBoxLayout(self)
        self._status_lbl = QLabel()
        layout.addWidget(self._status_lbl)
        self._launch_check = QCheckBox("Launch BertyType now")
        self._launch_check.setChecked(True)
        layout.addWidget(self._launch_check)
        self._failure_lbl = QLabel()
        self._failure_lbl.hide()
        layout.addWidget(self._failure_lbl)

    def initializePage(self) -> None:
        install_page = self.wizard().page(_PAGE_INSTALL) if self.wizard() else None
        failures = install_page.failures() if install_page else []
        if not failures:
            self.setTitle("Setup complete!")
            self._status_lbl.setText("All components installed successfully.")
            self._launch_check.show()
            self._failure_lbl.hide()
        else:
            self.setTitle("Setup finished with errors")
            self._failure_lbl.setText("Failed:\n" + "\n".join(failures))
            self._launch_check.hide()
            self._failure_lbl.show()

    def launch_requested(self) -> bool:
        return self._launch_check.isChecked() and self._launch_check.isVisible()


class SetupWizard(QWizard):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(TITLE)
        self.setMinimumSize(540, 440)
        self.addPage(WelcomePage())
        self.addPage(CheckPage())
        self.addPage(InstallPage())
        self.addPage(FinishPage())
        self.setOption(QWizard.WizardOption.NoBackButtonOnLastPage)
        self.button(QWizard.WizardButton.CancelButton).clicked.connect(
            self._on_cancel_clicked
        )

    def _on_cancel_clicked(self) -> None:
        if self.currentId() == _PAGE_INSTALL:
            install_page = self.page(_PAGE_INSTALL)
            if install_page:
                install_page.cancel()

    @property
    def launch_requested(self) -> bool:
        finish_page = self.page(_PAGE_FINISH)
        return finish_page.launch_requested() if finish_page else False
