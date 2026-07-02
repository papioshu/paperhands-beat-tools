"""A progress + log panel shown during long jobs (analysis, export, batch).

Keeps the user informed instead of a frozen window: a busy bar for the current
file, a determinate bar for the whole batch, a status line, a toggleable log of
per-file successes/errors, and a clickable link to the output folder on
completion. It only *displays* state — the actual work runs on worker threads.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)


class ProgressPanel(QFrame):
    cancelled = Signal()   # user asked to stop the current batch

    def __init__(self):
        super().__init__()
        self.setObjectName("Panel")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(10, 6, 10, 6)
        outer.setSpacing(4)

        top = QHBoxLayout()
        self.status = QLabel("")
        self.status.setObjectName("AccentLime")
        top.addWidget(self.status, 1)
        self.counts = QLabel("")
        self.counts.setObjectName("SubHeading")
        top.addWidget(self.counts)
        self.link = QLabel("")
        self.link.setTextFormat(Qt.RichText)
        self.link.setOpenExternalLinks(False)
        self.link.linkActivated.connect(self._open_link)
        top.addWidget(self.link)
        self.btn_log = QPushButton("Log")
        self.btn_log.setCheckable(True)
        self.btn_log.setFixedWidth(60)
        self.btn_log.toggled.connect(self._toggle_log)
        top.addWidget(self.btn_log)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFixedWidth(70)
        self.btn_cancel.setToolTip("Stop queuing the rest of this batch")
        self.btn_cancel.clicked.connect(self.cancelled)
        self.btn_cancel.hide()
        top.addWidget(self.btn_cancel)
        outer.addLayout(top)

        bars = QHBoxLayout()
        self.busy = QProgressBar()          # current file (indeterminate while active)
        self.busy.setFixedWidth(120)
        self.busy.setTextVisible(False)
        self.total = QProgressBar()          # whole batch
        bars.addWidget(self.busy)
        bars.addWidget(self.total, 1)
        outer.addLayout(bars)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setFixedHeight(120)
        self.log.hide()
        outer.addWidget(self.log)

        self.hide()

    # -- lifecycle ---------------------------------------------------------

    def begin(self, verb: str, total: int = 1) -> None:
        self.status.setText(f"{verb}…")
        self.counts.clear()
        self.link.clear()
        self.busy.setRange(0, 0)            # indeterminate = "working"
        self.total.setRange(0, max(1, total))
        self.total.setValue(0)
        self._t0 = time.monotonic()
        self.btn_cancel.show()
        self.show()

    def update(self, done: int, total: int, current_text: Optional[str] = None) -> None:
        self.total.setRange(0, max(1, total))
        self.total.setValue(min(done, total))
        if current_text:
            text = current_text
            if done > 0 and total > 1 and getattr(self, "_t0", None):
                elapsed = time.monotonic() - self._t0
                eta = elapsed / done * (total - done)
                text = f"{current_text}  ·  ~{self._fmt_eta(eta)} left"
            self.status.setText(text)

    def set_counts(self, ok: int, fail: int) -> None:
        parts = [f"✓ {ok}"]
        if fail:
            parts.append(f"✗ {fail}")
        self.counts.setText("   ".join(parts))

    @staticmethod
    def _fmt_eta(seconds: float) -> str:
        s = int(seconds)
        return f"{s // 60}m{s % 60:02d}s" if s >= 60 else f"{s}s"

    def log_line(self, text: str) -> None:
        self.log.appendPlainText(text)

    def end(self, message: str, folder: Optional[str] = None) -> None:
        self.btn_cancel.hide()
        self.busy.setRange(0, 1)
        self.busy.setValue(1)
        self.status.setText(message)
        if folder:
            url = QUrl.fromLocalFile(str(folder)).toString()
            self.link.setText(f'<a href="{url}">open output folder</a>')

    # -- internals ---------------------------------------------------------

    def _toggle_log(self, on: bool) -> None:
        self.log.setVisible(on)

    def _open_link(self, href: str) -> None:
        QDesktopServices.openUrl(QUrl(href))
