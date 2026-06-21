"""Progress panel + export-disable wiring (offscreen, no audio)."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.db import Database  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402
from app.ui.progress_panel import ProgressPanel  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


def test_progress_panel_lifecycle():
    _app()
    p = ProgressPanel()
    assert not p.isVisible()
    p.begin("Analyzing", total=5)
    assert p.isVisible()
    assert p.total.maximum() == 5

    p.update(2, 5, "Analyzing 2 of 5: Night.mp3")
    assert p.total.value() == 2
    assert "2 of 5" in p.status.text()

    p.log_line("✓ Night.mp3")
    p.log_line("✗ Bad.mp3: boom")
    assert "Night.mp3" in p.log.toPlainText()
    assert "boom" in p.log.toPlainText()

    p.end("Done", folder="C:/out")
    assert p.status.text() == "Done"
    assert "open output folder" in p.link.text()


def test_exporting_disables_then_enables_buttons(tmp_path):
    beat = tmp_path / "n.mp3"
    beat.write_bytes(b"\x00")
    db = Database(str(tmp_path / "lib.db"))
    db.add_beat(str(beat), "n.mp3")
    db.close()

    app = _app()
    win = MainWindow(db_path=str(tmp_path / "lib.db"))
    app.processEvents()

    win._set_exporting(True)
    assert not win.tag_panel.btn_export_preview.isEnabled()
    win._on_export_done(str(tmp_path / "out" / "n_TAGGED.mp3"))
    assert win.tag_panel.btn_export_preview.isEnabled()
    assert "open output folder" in win.progress.link.text()
    win.close()


def test_analysis_slots_update_panel(tmp_path):
    beat = tmp_path / "Night.mp3"
    beat.write_bytes(b"\x00")
    db = Database(str(tmp_path / "lib.db"))
    bid = db.add_beat(str(beat), "Night.mp3")
    db.close()

    app = _app()
    win = MainWindow(db_path=str(tmp_path / "lib.db"))
    app.processEvents()

    # Simulate the threaded analysis signal flow on one file.
    win._analysis_total = 1
    win._analysis_done = 0
    win.progress.begin("Analyzing", 1)
    win._on_analysis_started(bid)
    assert "1 of 1: Night.mp3" in win.progress.status.text()
    win._on_analyzed(bid, {"bpm": 140, "key": "F#min", "analysis_status": "done"})
    assert "Night.mp3" in win.progress.log.toPlainText()
    win._on_progress()
    assert win.progress.status.text() == "Analysis complete"
    win.close()
