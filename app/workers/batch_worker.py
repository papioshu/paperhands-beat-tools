"""Run a per-item action over a list of jobs on one background thread.

Jobs are self-contained (gathered on the main thread) so the worker never
touches the DB. Emits progress (for the bar + ETA), per-item results (for the
log + counts), and a final summary. Sequential — one item at a time — which is
right for CPU/ffmpeg-heavy work and gives a meaningful ETA.
"""

from __future__ import annotations

from typing import Callable, Sequence

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class BatchSignals(QObject):
    progress = Signal(int, int, str)   # done, total, current name
    result = Signal(bool, str, str)    # ok, name, detail/error
    finished = Signal(int, int)        # ok_count, fail_count


class BatchRunnable(QRunnable):
    def __init__(self, items: Sequence, fn: Callable, namer: Callable,
                 signals: BatchSignals):
        super().__init__()
        self.items = list(items)
        self.fn = fn          # fn(item) -> detail str; raises on failure
        self.namer = namer    # item -> display name
        self.signals = signals

    @Slot()
    def run(self) -> None:
        total = len(self.items)
        ok = fail = 0
        for i, item in enumerate(self.items):
            name = self.namer(item)
            self.signals.progress.emit(i, total, name)
            try:
                detail = self.fn(item) or ""
                ok += 1
                self.signals.result.emit(True, name, str(detail))
            except Exception as exc:  # noqa: BLE001 - per-item failure, keep going
                fail += 1
                self.signals.result.emit(False, name, str(exc))
            self.signals.progress.emit(i + 1, total, name)
        self.signals.finished.emit(ok, fail)
