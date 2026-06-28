"""AudioPlayer availability + signal forwarding (regression for the play bug).

The 64-bit position/duration signals from QMediaPlayer must connect without
error, or the player silently disables itself and the Play button does nothing.
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

pytest.importorskip("PySide6.QtMultimedia")

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.ui.player import AudioPlayer  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


def test_player_is_available():
    _app()
    p = AudioPlayer()
    assert p.available, f"player unavailable: {getattr(p, '_init_error', '')}"


def test_outputs_muted_during_tests():
    # The conftest _mute_audio fixture must silence every player, or test runs
    # blast real tag/beat audio out the default device.
    _app()
    p = AudioPlayer()
    assert p._out.isMuted() and p._tag_out.isMuted()


def test_position_and_duration_forward_as_ints():
    _app()
    p = AudioPlayer()
    pos, dur = [], []
    p.position_changed.connect(pos.append)
    p.duration_changed.connect(dur.append)
    p._emit_position(1234567)      # > 32-bit-ish value still forwards
    p._emit_duration(7654321)
    assert pos == [1234567]
    assert dur == [7654321]
