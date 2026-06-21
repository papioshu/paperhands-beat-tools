"""Batch rename dialog applied across multiple beats (offscreen, no audio)."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.db import Database  # noqa: E402
from app.ui.batch_rename_dialog import BatchRenameDialog  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


def test_batch_rename_applies_to_all(tmp_path):
    a = tmp_path / "raw1.mp3"
    a.write_bytes(b"\x00")
    b = tmp_path / "raw2.mp3"
    b.write_bytes(b"\x00")
    db = Database(str(tmp_path / "lib.db"))
    id_a = db.add_beat(str(a), "raw1.mp3", title="Night")
    db.update_beat(id_a, bpm=140, key="F#min")
    id_b = db.add_beat(str(b), "raw2.mp3", title="Sunrise")
    db.update_beat(id_b, bpm=92, key="Cmaj")

    _app()
    dlg = BatchRenameDialog(db, db.list_beats(), None)
    dlg.pattern.setText("{title} [{bpm} {key}]")
    dlg._apply()

    assert dlg.applied == 2
    assert (tmp_path / "Night [140BPM Fsharpmin].mp3").exists()
    assert (tmp_path / "Sunrise [92BPM Cmaj].mp3").exists()
    assert not a.exists() and not b.exists()
    # DB tracks the new names
    assert db.get_beat(id_a)["filename"] == "Night [140BPM Fsharpmin].mp3"
    db.close()


def test_batch_rename_skips_conflicts(tmp_path):
    a = tmp_path / "a.mp3"
    a.write_bytes(b"\x00")
    b = tmp_path / "b.mp3"
    b.write_bytes(b"\x00")
    db = Database(str(tmp_path / "lib.db"))
    db.add_beat(str(a), "a.mp3", title="Same")
    db.add_beat(str(b), "b.mp3", title="Same")

    _app()
    dlg = BatchRenameDialog(db, db.list_beats(), None)
    dlg.pattern.setText("{title}")     # both -> "Same.mp3" => conflict
    dlg._apply()

    assert dlg.applied == 0            # both skipped
    assert a.exists() and b.exists()   # untouched
    db.close()
