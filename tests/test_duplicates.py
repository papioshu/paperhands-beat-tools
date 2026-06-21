"""Duplicate detection wiring + dialog (offscreen, no audio)."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.db import Database  # noqa: E402
from app.ui.duplicates_dialog import DuplicatesDialog  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


def test_dialog_removes_checked_from_library_only(tmp_path):
    f1 = tmp_path / "a.mp3"
    f1.write_bytes(b"\x00")
    f2 = tmp_path / "a_copy.mp3"
    f2.write_bytes(b"\x00")
    db = Database(str(tmp_path / "lib.db"))
    id1 = db.add_beat(str(f1), "a.mp3")
    id2 = db.add_beat(str(f2), "a_copy.mp3")
    # identical fingerprints
    db.update_beat(id1, fingerprint="ffff")
    db.update_beat(id2, fingerprint="ffff")

    _app()
    group = [db.get_beat(id1), db.get_beat(id2)]
    dlg = DuplicatesDialog(db, [group], None)
    # default: first kept, second checked for removal
    dlg._remove()

    assert dlg.removed == 1
    assert db.get_beat(id1) is not None      # kept
    assert db.get_beat(id2) is None          # removed from catalog
    assert f2.exists()                       # but the FILE is untouched
    db.close()


def test_no_groups_when_fingerprints_differ():
    from core import fingerprint as fp
    # 16 bits apart; with a tight threshold they are not duplicates.
    items = [(1, "ffff"), (2, "0000")]
    assert fp.group_duplicates(items, max_distance=4) == []
