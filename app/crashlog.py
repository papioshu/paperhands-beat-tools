"""Crash logging + friendly error dialog (no stack traces shown to the user).

Uncaught exceptions are written in full to a timestamped file under the logs
directory (separate from user exports), and the user sees a calm, plain-language
message instead of a traceback or developer paths.
"""

from __future__ import annotations

import datetime
import sys
import traceback

from app.branding import APP_NAME
from app.paths import logs_dir


def _write_log(exc_type, exc, tb):
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    path = logs_dir() / f"crash_{ts}.log"
    path.write_text("".join(traceback.format_exception(exc_type, exc, tb)),
                    encoding="utf-8")
    return path


def install() -> None:
    """Route uncaught exceptions to a log file + a friendly dialog."""
    def handler(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc, tb)
            return
        log_path = None
        try:
            log_path = _write_log(exc_type, exc, tb)
        except Exception:  # noqa: BLE001 - logging must never raise
            pass
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox
            if QApplication.instance() is not None:
                box = QMessageBox()
                box.setIcon(QMessageBox.Warning)
                box.setWindowTitle(APP_NAME)
                box.setText("Something went wrong.")
                info = "The app ran into an unexpected problem."
                if log_path is not None:
                    info += f"\n\nA technical report was saved to:\n{log_path}"
                info += "\n\nYour work is auto-saved. You can keep going or restart."
                box.setInformativeText(info)
                box.exec()
        except Exception:  # noqa: BLE001
            pass
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = handler
