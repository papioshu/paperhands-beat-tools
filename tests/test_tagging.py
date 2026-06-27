"""Phase 5/6 placement + crop interactions, offscreen (no audio backend)."""

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
    win._active_tag = "/tags/myTag.wav"
    return win


def test_initial_tag_selection_is_captured(tmp_path):
    from app import config

    tagdir = tmp_path / "tags"
    tagdir.mkdir()
    (tagdir / "t.wav").write_bytes(b"\x00\x00")
    (tmp_path / "Night.mp3").write_bytes(b"\x00\x00")
    db_path = tmp_path / "lib.db"
    seed = Database(str(db_path))
    seed.add_beat(str(tmp_path / "Night.mp3"), "Night.mp3")
    seed.close()

    old = config.tags_folder()
    config.set_tags_folder(str(tagdir))
    try:
        # Build the window directly (the _window_with_beat helper forces a tag).
        app = _app()
        win = MainWindow(db_path=str(db_path))
        app.processEvents()
        assert win._active_tag and win._active_tag.endswith("t.wav")
        win.close()
    finally:
        config.set_tags_folder(old)


def test_remove_tag_file_hides_nondestructively(tmp_path, monkeypatch):
    from app import config
    from app.ui.tag_panel import TagLibraryPanel
    from PySide6.QtWidgets import QMessageBox

    tagdir = tmp_path / "tags"
    tagdir.mkdir()
    tagfile = tagdir / "drop.wav"
    tagfile.write_bytes(b"\x00\x00")
    db = Database(str(tmp_path / "lib.db"))

    old = config.tags_folder()
    config.set_tags_folder(str(tagdir))
    try:
        panel = TagLibraryPanel(db)          # refresh_tags syncs the folder -> 1 tag
        tid = panel._current_tag_id()
        assert tid is not None
        monkeypatch.setattr(QMessageBox, "question",
                            lambda *a, **k: QMessageBox.Yes)
        panel._remove_tag_file()
        assert tagfile.exists()                          # file untouched on disk
        assert db.list_tag_files() == []                 # hidden from the library
        panel.refresh_tags()                             # re-sync must not bring it back
        assert db.list_tag_files() == []
    finally:
        config.set_tags_folder(old)


def test_playable_tag_passthrough_and_fallback(tmp_path):
    win = _window_with_beat(tmp_path)
    # ratio ~1.0 -> play the raw file, no render.
    assert win._playable_tag("/x/a.wav", 1.0, True) == "/x/a.wav"
    # Non-trivial ratio but an unloadable file -> safe fallback to raw, no crash.
    assert win._playable_tag("/x/missing.wav", 1.5, True) == "/x/missing.wav"
    win.close()


def test_place_and_remove_tags(tmp_path):
    win = _window_with_beat(tmp_path)
    win._place_tag_at_fraction(0.10)   # 10s
    win._place_tag_at_fraction(0.50)   # 50s
    assert len(win._placements) == 2
    assert len(win.waveform._markers) == 2

    win._remove_marker(0)              # removes the earliest (10s)
    assert len(win._placements) == 1
    assert win._placements[0].position_sec == pytest.approx(50, abs=1)
    win.close()


def test_drag_to_move_marker(tmp_path):
    win = _window_with_beat(tmp_path)
    win._place_tag_at_fraction(0.20)   # 20s
    win._move_marker(0, 0.60)          # -> 60s
    assert win._placements[0].position_sec == pytest.approx(60, abs=1)
    win.close()


def test_place_requires_active_tag(tmp_path):
    win = _window_with_beat(tmp_path)
    win._active_tag = None
    win._place_tag_at_fraction(0.3)
    assert win._placements == []
    win.close()


def test_tag_at_drop_and_hook_place_at_detected_times(tmp_path):
    beat = tmp_path / "Night.mp3"
    beat.write_bytes(b"\x00\x00")
    db_path = tmp_path / "lib.db"
    seed = Database(str(db_path))
    bid = seed.add_beat(str(beat), "Night.mp3")
    seed.update_beat(bid, duration_sec=100.0, analysis_status="done",
                     drop_sec=30.0, hook_start=60.0, hook_end=75.0)
    seed.close()

    app = _app()
    win = MainWindow(db_path=str(db_path))
    app.processEvents()
    win.table.selectRow(0)
    app.processEvents()
    win._active_tag = "/tags/t.wav"

    # drop/hook shown on the waveform
    assert win.waveform._drop == pytest.approx(0.30)
    assert win.waveform._hook == pytest.approx((0.60, 0.75))

    win._tag_at_drop()
    win._tag_at_hook()
    assert sorted(round(p.position_sec) for p in win._placements) == [30, 60]
    win.close()


def test_autoplace_dialog_computes_and_applies(tmp_path):
    # Drive the auto-place dialog directly (no modal exec) and apply to the beat.
    from app.ui.autoplace_dialog import AutoPlaceDialog

    win = _window_with_beat(tmp_path)
    dlg = AutoPlaceDialog(["/tags/a.wav"], 100.0, [], None, None, 1, win)
    dlg.profile.setCurrentText("Custom")
    dlg.mode.setCurrentText("fixed")
    dlg.interval.setValue(40)
    dlg.min_spacing.setValue(10)
    win._placements = dlg.compute_for(100.0, [], None, None)
    win._refresh_markers(save=True)
    # First tag now lands 5-10s in (not at 0:00); spacing stays at the interval.
    pos = [round(p.position_sec) for p in win._placements]
    assert 5 <= pos[0] <= 10
    assert [b - a for a, b in zip(pos, pos[1:])] == [40, 40]
    win.close()


def test_batch_autoplace_applies_to_all_selected(tmp_path):
    import json

    from app.ui.autoplace_dialog import AutoPlaceDialog

    win = _window_with_beat(tmp_path)            # "Night" 100s, analyzed
    two = tmp_path / "Two.mp3"
    two.write_bytes(b"\x00")
    bid2 = win.db.add_beat(str(two), "Two.mp3")
    win.db.update_beat(bid2, duration_sec=200.0, analysis_status="done")
    win.refresh_library()

    ids = [b["id"] for b in win.db.list_beats()]
    dlg = AutoPlaceDialog(["/t/a.wav"], 100.0, [], None, None, len(ids), win)
    dlg.profile.setCurrentText("Custom")
    dlg.mode.setCurrentText("fixed")
    dlg.interval.setValue(40)
    dlg.min_spacing.setValue(10)
    win._batch_autoplace(dlg, ids)

    for bid in ids:
        saved = json.loads(win.db.get_beat(bid)["placements"])
        assert len(saved) >= 2                   # each beat got interval placements
    win.close()


def test_layers_created_and_persist(tmp_path):
    import json

    win = _window_with_beat(tmp_path)
    win._active_tag = "/tags/Oni.wav"
    win._place_tag_at_fraction(0.2)
    win._active_tag = "/tags/Paper.wav"
    win._place_tag_at_fraction(0.6)

    # one layer per distinct tag
    assert set(win._layers.keys()) == {"/tags/Oni.wav", "/tags/Paper.wav"}

    # mute one layer -> persisted, and reflected in audibility
    win._on_layer_changed("/tags/Oni.wav", {"enabled": True, "mute": True,
                                            "solo": False, "volume_db": 0.0, "pan": 0.0})
    assert not win._layer_active("/tags/Oni.wav")
    assert win._layer_active("/tags/Paper.wav")

    saved = json.loads(win.db.get_beat(win._current_beat_id)["layers"])
    assert saved["/tags/Oni.wav"]["mute"] is True
    win.close()


def test_clear_removes_all(tmp_path):
    win = _window_with_beat(tmp_path)
    win._place_tag_at_fraction(0.3)
    assert win._placements
    win._on_clear_tags()
    assert win._placements == []
    assert win.waveform._markers == []
    win.close()


def test_place_and_crop_are_mutually_exclusive(tmp_path):
    win = _window_with_beat(tmp_path)
    win.tag_panel.btn_place.setChecked(True)
    assert win.waveform._mode == "place"
    win.tag_panel.btn_crop.setChecked(True)        # turning crop on...
    assert not win.tag_panel.btn_place.isChecked()  # ...turns place off
    assert win.waveform._mode == "crop"
    win.close()


def test_crop_seconds_from_region(tmp_path):
    win = _window_with_beat(tmp_path)
    win.waveform._crop = (0.2, 0.6)
    assert win.waveform.crop_seconds(100.0) == pytest.approx((20.0, 60.0))
    win.close()


def test_placements_persist_across_reselection_and_reopen(tmp_path):
    beat2 = tmp_path / "Two.mp3"
    beat2.write_bytes(b"\x00\x00")
    win = _window_with_beat(tmp_path)
    bid = win._current_beat_id
    win.db.add_beat(str(beat2), "Two.mp3")
    win.db.update_beat(win.db.get_by_path(str(beat2))["id"], duration_sec=80.0)
    win.refresh_library()

    # place two tags on the first beat, then switch away and back
    win._place_tag_at_fraction(0.1)
    win._place_tag_at_fraction(0.5)
    db_path = win.db.path

    current = win._selected_beat_id()
    other_row = next(
        r for r in range(win.table.rowCount())
        if win.table.item(r, 0).data(Qt.UserRole) != current
    )
    win.table.selectRow(other_row)
    _app().processEvents()
    assert win._placements == []                 # other beat has none

    # back to the first beat -> markers restored from the DB
    back_row = next(
        r for r in range(win.table.rowCount())
        if win.table.item(r, 0).data(Qt.UserRole) == bid
    )
    win.table.selectRow(back_row)
    _app().processEvents()
    assert len(win._placements) == 2
    win.close()

    # and they survived to disk: reopen a fresh window on the same DB
    app = _app()
    win2 = MainWindow(db_path=str(db_path))
    app.processEvents()
    back_row = next(
        r for r in range(win2.table.rowCount())
        if win2.table.item(r, 0).data(Qt.UserRole) == bid
    )
    win2.table.selectRow(back_row)
    app.processEvents()
    assert len(win2._placements) == 2
    win2.close()


def test_selecting_another_beat_resets_placements(tmp_path):
    beat2 = tmp_path / "Two.mp3"
    beat2.write_bytes(b"\x00\x00")
    win = _window_with_beat(tmp_path)
    win.db.add_beat(str(beat2), "Two.mp3")
    win.db.update_beat(win.db.get_by_path(str(beat2))["id"], duration_sec=80.0)
    win.refresh_library()

    win._place_tag_at_fraction(0.2)
    assert win._placements

    current = win._selected_beat_id()
    other_row = next(
        r for r in range(win.table.rowCount())
        if win.table.item(r, 0).data(Qt.UserRole) != current
    )
    win.table.selectRow(other_row)
    _app().processEvents()
    assert win._placements == []
    win.close()
