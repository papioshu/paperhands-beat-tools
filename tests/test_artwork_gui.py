"""Artwork set/generate wiring in the app (offscreen; needs PySide6 + Pillow)."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

pytest.importorskip("PySide6")
pytest.importorskip("PIL")

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.db import Database  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


def _window(tmp_path):
    beat = tmp_path / "Night.mp3"
    beat.write_bytes(b"\x00")
    db = Database(str(tmp_path / "lib.db"))
    bid = db.add_beat(str(beat), "Night.mp3", title="Night")
    db.update_beat(bid, bpm=140, key="F#min", analysis_status="done", duration_sec=100.0)
    db.close()
    app = _app()
    win = MainWindow(db_path=str(tmp_path / "lib.db"))
    app.processEvents()
    win.table.selectRow(0)
    app.processEvents()
    return win, bid


def test_generate_artwork_sets_path_and_thumb(tmp_path):
    win, bid = _window(tmp_path)
    win._generate_artwork(bid)
    path = win.db.get_beat(bid)["artwork_path"]
    assert path and Path(path).exists()
    assert Path(path).parent.name == "artwork"
    assert not win.detail.artwork_thumb.pixmap().isNull()   # thumbnail shown
    win.close()


def test_set_artwork_imports_local_image(tmp_path):
    # Make a small valid PNG to "upload".
    from PIL import Image
    src = tmp_path / "mine.png"
    Image.new("RGB", (64, 64), (10, 200, 100)).save(src)

    win, bid = _window(tmp_path)
    # Drive the import directly (bypass the file dialog).
    from core import artwork
    dst = win._export_subdir("artwork") / f"{win._beat_name(win.db.get_beat(bid))}.png"
    artwork.import_artwork(str(src), str(dst))
    win.db.update_beat(bid, artwork_path=str(dst))
    assert Path(win.db.get_beat(bid)["artwork_path"]).exists()
    win.close()
