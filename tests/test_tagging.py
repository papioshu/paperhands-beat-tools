"""Phase 5 placement interactions, offscreen (no audio backend needed)."""

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


def _app():
    return QApplication.instance() or QApplication([])


def _window_with_beat(tmp_path):
    beat = tmp_path / "Night.mp3"
    beat.write_bytes(b"\x00\x00")
    db_path = tmp_path / "lib.db"
    seed = Database(str(db_path))
    bid = seed.add_beat(str(beat), "Night.mp3")
    seed.update_beat(bid, duration_sec=100.0, analysis_status="done", bpm=140, key="F#min")
    seed.close()

    app = _app()
    win = MainWindow(db_path=str(db_path))
    app.processEvents()
    win.table.selectRow(0)
    app.processEvents()
    return win


def test_initial_tag_selection_is_captured(tmp_path):
    from app import config

    tagdir = tmp_path / "tags"
    tagdir.mkdir()
    (tagdir / "t.wav").write_bytes(b"\x00\x00")
    old = config.tags_folder()
    config.set_tags_folder(str(tagdir))
    try:
        win = _window_with_beat(tmp_path)
        assert win._active_tag and win._active_tag.endswith("t.wav")
        win.close()
    finally:
        config.set_tags_folder(old)


def test_click_places_and_toggles_tags(tmp_path):
    win = _window_with_beat(tmp_path)
    win._active_tag = "/tags/myTag.wav"
    win.tag_panel.btn_place.setChecked(True)

    win._on_waveform_click(0.10)   # -> 10s
    win._on_waveform_click(0.50)   # -> 50s
    assert len(win._placements) == 2
    assert len(win.waveform._markers) == 2

    # clicking near the 10s marker again removes it
    win._on_waveform_click(0.10)
    assert len(win._placements) == 1
    assert win._placements[0].position_sec == pytest.approx(50, abs=1)
    win.close()


def test_no_placement_when_not_in_place_mode(tmp_path):
    win = _window_with_beat(tmp_path)
    win._active_tag = "/tags/myTag.wav"
    win.tag_panel.btn_place.setChecked(False)  # seek mode
    win._on_waveform_click(0.25)
    assert win._placements == []
    win.close()


def test_autoplace_lays_down_interval_tags(tmp_path):
    win = _window_with_beat(tmp_path)
    win.tag_panel.all_tag_paths = lambda: ["/tags/a.wav"]  # pretend the library
    win._on_autoplace()
    # duration 100s, interval 40, start at 0 -> 0, 40, 80
    assert [round(p.position_sec) for p in win._placements] == [0, 40, 80]
    assert len(win.waveform._markers) == 3
    win.close()


def test_clear_removes_all(tmp_path):
    win = _window_with_beat(tmp_path)
    win._active_tag = "/tags/myTag.wav"
    win.tag_panel.btn_place.setChecked(True)
    win._on_waveform_click(0.3)
    assert win._placements
    win._on_clear_tags()
    assert win._placements == []
    assert win.waveform._markers == []
    win.close()


def test_selecting_another_beat_resets_placements(tmp_path):
    beat2 = tmp_path / "Two.mp3"
    beat2.write_bytes(b"\x00\x00")
    win = _window_with_beat(tmp_path)
    win.db.add_beat(str(beat2), "Two.mp3")
    win.db.update_beat(win.db.get_by_path(str(beat2))["id"], duration_sec=80.0)
    win.refresh_library()

    win._active_tag = "/tags/myTag.wav"
    win.tag_panel.btn_place.setChecked(True)
    win._on_waveform_click(0.2)
    assert win._placements

    win.table.selectRow(1)  # switch beats
    _app().processEvents()
    assert win._placements == []  # reset for the new beat
    win.close()
