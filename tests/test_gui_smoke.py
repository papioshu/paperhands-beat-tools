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
