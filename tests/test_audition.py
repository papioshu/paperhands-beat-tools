"""Live tag audition + ducking + tag preview (offscreen)."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

pytest.importorskip("PySide6.QtMultimedia")

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.db import Database  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402
from app.ui.player import AudioPlayer  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


def _window(tmp_path):
    beat = tmp_path / "Night.mp3"
    beat.write_bytes(b"\x00")
    db = Database(str(tmp_path / "lib.db"))
    bid = db.add_beat(str(beat), "Night.mp3")
    db.update_beat(bid, analysis_status="done", duration_sec=100.0)
    db.close()
    app = _app()
    win = MainWindow(db_path=str(tmp_path / "lib.db"))
    app.processEvents()
    win.table.selectRow(0)
    app.processEvents()
    win._active_tag = "/tags/t.wav"
    return win


def test_placing_a_tag_auditions_it(tmp_path):
    win = _window(tmp_path)
    played = []
    win.player.play_tag = lambda path, volume=1.0: played.append(path)
    win._place_tag_at_fraction(0.25)
    assert played == ["/tags/t.wav"]
    win.close()


def test_double_click_row_starts_playback(tmp_path):
    beat = tmp_path / "Night.mp3"
    beat.write_bytes(b"\x00")
    db = Database(str(tmp_path / "lib.db"))
    db.add_beat(str(beat), "Night.mp3")
    db.update_beat(db.list_beats()[0]["id"], analysis_status="done", duration_sec=100.0)
    db.close()
    app = _app()
    win = MainWindow(db_path=str(tmp_path / "lib.db"))
    app.processEvents()
    win.table.selectRow(0)
    app.processEvents()

    played = []
    win.player.play = lambda: played.append(1)
    win._on_row_double_clicked(win.table.item(0, 0))
    assert played == [1]
    win.close()


def test_preview_button_plays_active_tag(tmp_path):
    win = _window(tmp_path)
    played = []
    win.player.play_tag = lambda path, volume=1.0: played.append(path)
    win._preview_active_tag()
    assert played == ["/tags/t.wav"]
    win.close()


def test_live_monitor_fires_tags_as_playhead_crosses(tmp_path):
    from core.models import Placement

    win = _window(tmp_path)
    fired = []
    win.player.play_tag = lambda path, volume=1.0: fired.append(path)
    win._placements = [Placement(10.0, "/t/a.wav"), Placement(50.0, "/t/b.wav")]

    # Step continuously like real playback (~0.4s updates, never a >1s jump).
    win._last_pos_sec = 0.0
    t = 0.0
    while t < 12.0:
        t = round(t + 0.4, 1)
        win._monitor_live_tags(t)
    assert fired == ["/t/a.wav"]           # only the 10s tag crossed
    while t < 51.0:
        t = round(t + 0.4, 1)
        win._monitor_live_tags(t)
    assert fired == ["/t/a.wav", "/t/b.wav"]
    win.close()


def test_live_monitor_resync_on_seek_does_not_fire(tmp_path):
    from core.models import Placement

    win = _window(tmp_path)
    fired = []
    win.player.play_tag = lambda path, volume=1.0: fired.append(path)
    win.player.duck = lambda db: None
    win._placements = [Placement(10.0, "/t/a.wav")]
    win._last_pos_sec = 0.0
    win._monitor_live_tags(60.0)       # big forward jump (seek) -> no fire
    assert fired == []
    win.close()
