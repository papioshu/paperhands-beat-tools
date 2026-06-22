"""DAW Mode window construction + tag timeline + mix render (offscreen)."""

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

pytest.importorskip("PySide6")
pytest.importorskip("pydub")

from PySide6.QtCore import QThreadPool  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.db import Database  # noqa: E402
from app.ui.daw_window import DawModeWindow  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


def _stem(path, freq=220):
    from pydub.generators import Sine
    Sine(freq).to_audio_segment(duration=500).export(str(path), format="wav")
    return str(path)


def _beat_with_stems(tmp_path):
    beat = tmp_path / "Night.mp3"
    beat.write_bytes(b"\x00")
    stems = {
        "drums": _stem(tmp_path / "drums.wav", 110),
        "bass": _stem(tmp_path / "bass.wav", 80),
        "vocals": _stem(tmp_path / "vocals.wav", 440),
        "other": _stem(tmp_path / "other.wav", 330),
        "tag_only": _stem(tmp_path / "tag.wav", 880),
    }
    db = Database(str(tmp_path / "lib.db"))
    bid = db.add_beat(str(beat), "Night.mp3")
    db.update_beat(bid, analysis_status="done", duration_sec=20.0,
                   stems=json.dumps(stems))
    db.close()
    return bid


def test_daw_window_builds_track_rows(tmp_path):
    bid = _beat_with_stems(tmp_path)
    _app()
    db = Database(str(tmp_path / "lib.db"))
    win = DawModeWindow(db, bid)
    # one row per stem (5)
    assert len(win._rows) == 5
    names = [r.track["name"] for r in win._rows]
    assert names[:4] == ["drums", "bass", "vocals", "other"]
    win.close()
    db.close()


def test_daw_tag_place_and_clear(tmp_path):
    bid = _beat_with_stems(tmp_path)
    _app()
    db = Database(str(tmp_path / "lib.db"))
    win = DawModeWindow(db, bid)

    win._place_tag(0.25)               # -> 5s (20s * 0.25), uses tag_only stem
    win._place_tag(0.75)
    assert len(win._placements) == 2
    saved = json.loads(db.get_beat(bid)["placements"])
    assert len(saved) == 2

    win._clear_tags()
    assert win._placements == []
    win.close()
    db.close()


def test_daw_mute_solo_reflected_in_tracks(tmp_path):
    bid = _beat_with_stems(tmp_path)
    _app()
    db = Database(str(tmp_path / "lib.db"))
    win = DawModeWindow(db, bid)
    win._rows[0].solo.setChecked(True)
    win._rows[1].mute.setChecked(True)
    from core import mixer
    audible = [t["name"] for t in mixer.audible_tracks(win._tracks)]
    assert audible == ["drums"]        # only the soloed track
    win.close()
    db.close()
