"""Headless smoke test: the main window constructs, themes, and refreshes.

Runs under Qt's 'offscreen' platform so it needs no display. Skipped cleanly if
PySide6 isn't installed.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.db import Database  # noqa: E402
from app.theme import apply_theme, build_stylesheet  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def test_stylesheet_builds():
    qss = build_stylesheet()
    assert "QPushButton" in qss and "#8B5CF6" in qss  # violet present


def test_main_window_constructs_and_shows(tmp_path):
    app = _app()
    apply_theme(app)
    win = MainWindow(db_path=str(tmp_path / "lib.db"))
    win.show()
    app.processEvents()
    assert win.windowTitle() == "Paperhand's Beat Tools"
    assert win.table.columnCount() == 6
    win.close()


def test_window_lists_existing_beats(tmp_path):
    # Seed a DB, then confirm the table renders the row.
    db_path = tmp_path / "lib.db"
    seed = Database(str(db_path))
    bid = seed.add_beat("/m/Night.mp3", "Night.mp3")
    seed.update_beat(bid, bpm=140, key="F#min", genre="Trap", analysis_status="done")
    seed.close()

    app = _app()
    win = MainWindow(db_path=str(db_path))
    app.processEvents()
    assert win.table.rowCount() == 1
    assert win.table.item(0, 0).text() == "Night.mp3"   # title falls back to filename
    assert win.table.item(0, 1).text() == "140"
    assert win.table.item(0, 2).text() == "F#min"
    win.close()


def test_edit_via_detail_panel_persists(tmp_path):
    db_path = tmp_path / "lib.db"
    seed = Database(str(db_path))
    bid = seed.add_beat("/m/N.mp3", "N.mp3")
    seed.close()

    app = _app()
    win = MainWindow(db_path=str(db_path))
    app.processEvents()
    win.table.selectRow(0)
    app.processEvents()

    win.detail.title.setText("Night Drive")
    win.detail.genre.setCurrentText("Trap")
    win.detail.mood.setCurrentText("Dark")
    win.detail.tags.setText("dark, melodic, dark")  # dup should collapse
    win.detail._emit_save()
    app.processEvents()

    row = win.db.get_beat(bid)
    assert row["title"] == "Night Drive"
    assert row["genre"] == "Trap"
    assert row["mood"] == "Dark"
    assert set(win.db.get_tags(bid)) == {"dark", "melodic"}
    win.close()


def test_selecting_analyzed_beat_loads_waveform(tmp_path):
    import numpy as np
    from core import waveform as wf

    # A real (empty) audio file so the beat isn't "missing", plus a peaks cache.
    beat_file = tmp_path / "Night.mp3"
    beat_file.write_bytes(b"\x00\x00")
    peaks_path = wf.generate_peaks_file(
        np.linspace(0, 1, 5000).astype("float32"), str(tmp_path / "1"), buckets=300
    )

    db_path = tmp_path / "lib.db"
    seed = Database(str(db_path))
    bid = seed.add_beat(str(beat_file), "Night.mp3")
    seed.update_beat(bid, bpm=140, key="F#min", analysis_status="done",
                     waveform_path=peaks_path, duration_sec=12.0)
    seed.close()

    app = _app()
    win = MainWindow(db_path=str(db_path))
    app.processEvents()
    win.table.selectRow(0)
    app.processEvents()

    assert win.waveform._peaks is not None
    assert len(win.waveform._peaks) == 300
    win.close()


def test_search_filters_table(tmp_path):
    db_path = tmp_path / "lib.db"
    seed = Database(str(db_path))
    b1 = seed.add_beat("/m/Night.mp3", "Night.mp3")
    seed.update_beat(b1, genre="Trap")
    b2 = seed.add_beat("/m/Sun.mp3", "Sun.mp3")
    seed.update_beat(b2, genre="Soul")
    seed.close()

    app = _app()
    win = MainWindow(db_path=str(db_path))
    app.processEvents()
    assert win.table.rowCount() == 2
    win.search.setText("trap")
    app.processEvents()
    assert win.table.rowCount() == 1
    assert win.table.item(0, 0).text() == "Night.mp3"
    win.close()
