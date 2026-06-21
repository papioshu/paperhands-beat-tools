"""Startup auto-scan + duplicate indicator (offscreen, no audio)."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from app import config  # noqa: E402
from app.db import Database  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


def test_startup_scans_watched_folder_and_skips_existing(tmp_path):
    beats = tmp_path / "beats"
    beats.mkdir()
    (beats / "a.mp3").write_bytes(b"\x00")
    (beats / "b.mp3").write_bytes(b"\x00")
    db_path = tmp_path / "lib.db"
    Database(str(db_path)).close()

    old = config.watched_folders()
    config.set_watched_folders([str(beats)])
    try:
        app = _app()
        win = MainWindow(db_path=str(db_path))   # startup scan runs in __init__
        app.processEvents()
        assert win.table.rowCount() == 2          # picked up without manual scan

        # Add one more file, reopen -> only the new one is added (existing skipped)
        (beats / "c.mp3").write_bytes(b"\x00")
        win.close()
        win2 = MainWindow(db_path=str(db_path))
        app.processEvents()
        assert win2.table.rowCount() == 3
        assert len(win2.db.list_beats()) == 3     # no duplicate rows for a/b
        win2.close()
    finally:
        config.set_watched_folders(old)


def test_duplicate_indicator_lights_up(tmp_path):
    f1 = tmp_path / "a.mp3"
    f1.write_bytes(b"\x00")
    f2 = tmp_path / "a_copy.mp3"
    f2.write_bytes(b"\x00")
    db = Database(str(tmp_path / "lib.db"))
    i1 = db.add_beat(str(f1), "a.mp3")
    i2 = db.add_beat(str(f2), "a_copy.mp3")
    # Realistic 512-bit (128 hex) fingerprints: identical = duplicate.
    db.update_beat(i1, fingerprint="ff" * 64)
    db.update_beat(i2, fingerprint="ff" * 64)
    db.close()

    app = _app()
    win = MainWindow(db_path=str(tmp_path / "lib.db"))
    app.processEvents()
    win._update_duplicate_indicator()
    assert "(" in win.btn_duplicates.text()       # shows a count
    assert win.btn_duplicates.styleSheet() != ""  # highlighted

    # No dupes -> back to normal (all 512 bits differ)
    win.db.update_beat(i2, fingerprint="00" * 64)
    win._update_duplicate_indicator()
    assert win.btn_duplicates.text() == "Duplicates"
    assert win.btn_duplicates.styleSheet() == ""
    win.close()
