"""Batch worker + batch export wiring (offscreen)."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtCore import QThreadPool  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.workers import BatchRunnable, BatchSignals  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


def test_batch_runnable_reports_ok_and_fail():
    app = _app()
    results, finished = [], []
    sig = BatchSignals()
    sig.result.connect(lambda ok, name, detail: results.append((ok, name)))
    sig.finished.connect(lambda ok, fail: finished.append((ok, fail)))

    items = [1, 2, 0, 3]   # treat 0 as a failure (division)

    def fn(x):
        return 10 / x      # x==0 raises -> counts as failure

    pool = QThreadPool.globalInstance()
    pool.start(BatchRunnable(items, fn, lambda x: f"item{x}", sig))
    pool.waitForDone(10_000)
    for _ in range(20):
        app.processEvents()

    assert finished == [(3, 1)]                 # 3 ok, 1 fail
    assert (False, "item0") in results


def test_progress_panel_eta_and_counts():
    from app.ui.progress_panel import ProgressPanel
    _app()
    p = ProgressPanel()
    p.begin("Exporting", total=10)
    p.update(2, 10, "Exporting 2 of 10")
    assert "left" in p.status.text() or "Exporting" in p.status.text()
    p.set_counts(2, 1)
    assert "2" in p.counts.text() and "1" in p.counts.text()
