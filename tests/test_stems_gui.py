"""Stem-split queue + DB save via a fake engine (offscreen, no Demucs)."""

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtCore import QThreadPool  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.db import Database  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


class _FakeEngine:
    name = "Fake"

    def available(self):
        return True

    def split(self, input_path, out_dir):
        os.makedirs(out_dir, exist_ok=True)
        out = {}
        for stem in ("vocals", "drums", "bass", "other"):
            p = os.path.join(out_dir, f"{stem}.wav")
            with open(p, "wb") as fh:
                fh.write(b"RIFF")
            out[stem] = p
        return out


def test_stem_split_saves_paths(tmp_path):
    beat = tmp_path / "Night.mp3"
    beat.write_bytes(b"\x00")
    db = Database(str(tmp_path / "lib.db"))
    bid = db.add_beat(str(beat), "Night.mp3")
    db.update_beat(bid, analysis_status="done", duration_sec=100.0)
    db.close()

    app = _app()
    win = MainWindow(db_path=str(tmp_path / "lib.db"))
    app.processEvents()
    win.stem_engine = _FakeEngine()
    win._run_stem_split([bid])
    QThreadPool.globalInstance().waitForDone(10_000)
    for _ in range(40):
        app.processEvents()

    saved = json.loads(win.db.get_beat(bid)["stems"])
    assert {"vocals", "drums", "bass", "other"} <= set(saved)
    assert win._stem_ok == 1 and win._stem_fail == 0
    win.close()
