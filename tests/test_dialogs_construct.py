"""Every dialog + the DAW window must construct cleanly.

Constructing a Qt window evaluates every ``.clicked.connect(self._handler)`` at
init time, so a button wired to a missing/renamed handler raises AttributeError
here. This is the cheap guarantee that no front-end control is dead. The main
window is already covered by test_gui_smoke; these are the ones it never builds.
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
from core.models import Placement  # noqa: E402


def _app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _seed(tmp_path):
    beat = tmp_path / "Night.mp3"
    beat.write_bytes(b"\x00\x00")
    db = Database(str(tmp_path / "lib.db"))
    bid = db.add_beat(str(beat), "Night.mp3")
    db.update_beat(bid, bpm=140, key="F#min", duration_sec=120.0,
                   analysis_status="done")
    return db, bid


def test_all_dialogs_construct(tmp_path):
    app = _app()
    db, bid = _seed(tmp_path)
    row = db.get_beat(bid)

    from app.ui.autoplace_dialog import AutoPlaceDialog
    from app.ui.batch_rename_dialog import BatchRenameDialog
    from app.ui.batch_tag_dialog import BatchTagDialog
    from app.ui.duplicates_dialog import DuplicatesDialog
    from app.ui.settings_dialog import SettingsDialog
    from app.ui.stretch_editor_dialog import StretchEditorDialog

    dialogs = [
        AutoPlaceDialog(["/tags/a.wav"], 120.0, None, None, None, 1),
        BatchRenameDialog(db, [row]),
        BatchTagDialog(3),
        DuplicatesDialog(db, [[row, row]]),
        SettingsDialog(db),
        StretchEditorDialog([Placement(10.0, "/tags/a.wav")]),
    ]
    for d in dialogs:
        d.close()
    app.processEvents()


def test_daw_window_constructs(tmp_path):
    app = _app()
    db, bid = _seed(tmp_path)

    from app.ui.daw_window import DawModeWindow

    win = DawModeWindow(db, bid)
    app.processEvents()
    # Transport + clear + the five export menu actions are present.
    assert win.btn_play is not None and win.btn_export.menu() is not None
    assert len(win.btn_export.menu().actions()) == 5
    win.close()
