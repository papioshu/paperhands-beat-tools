"""Tests for the WaveformWidget (offscreen Qt; no audio backend needed)."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.ui.widgets import WaveformWidget  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


def _press(w, x):
    w.mousePressEvent(QMouseEvent(
        QEvent.MouseButtonPress, QPointF(x, 10), Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))


def _move(w, x):
    w.mouseMoveEvent(QMouseEvent(
        QEvent.MouseMove, QPointF(x, 10), Qt.NoButton, Qt.LeftButton, Qt.NoModifier))


def _release(w, x):
    w.mouseReleaseEvent(QMouseEvent(
        QEvent.MouseButtonRelease, QPointF(x, 10), Qt.LeftButton, Qt.NoButton, Qt.NoModifier))


def _widget():
    _app()
    w = WaveformWidget()
    w.resize(200, 64)
    return w


def test_fraction_at_maps_x_to_0_1():
    w = _widget()
    assert w._fraction_at(100) == pytest.approx(0.5)
    assert w._fraction_at(0) == 0.0
    assert w._fraction_at(10_000) == 1.0


def test_seek_mode_emits_seek_on_release():
    w = _widget()
    w.set_mode("seek")
    got = []
    w.seek_requested.connect(got.append)
    _press(w, 50)
    _release(w, 50)
    assert got and got[0] == pytest.approx(0.25)


def test_place_mode_empty_click_places_tag():
    w = _widget()
    w.set_mode("place")
    placed = []
    w.tag_placed.connect(placed.append)
    _press(w, 100)
    _release(w, 100)
    assert placed and placed[0] == pytest.approx(0.5)


def test_place_mode_click_on_marker_removes():
    w = _widget()
    w.set_markers([0.5])      # marker at x=100
    w.set_mode("place")
    removed = []
    w.marker_removed.connect(removed.append)
    _press(w, 100)
    _release(w, 100)
    assert removed == [0]


def test_place_mode_drag_moves_marker():
    w = _widget()
    w.set_markers([0.25])     # marker at x=50
    w.set_mode("place")
    moved = []
    w.marker_moved.connect(lambda i, f: moved.append((i, f)))
    _press(w, 50)
    _move(w, 150)
    _release(w, 150)
    assert moved and moved[0][0] == 0
    assert moved[0][1] == pytest.approx(0.75)


def test_crop_mode_drag_emits_region():
    w = _widget()
    w.set_mode("crop")
    regions = []
    w.crop_changed.connect(lambda a, b: regions.append((a, b)))
    _press(w, 40)
    _move(w, 160)
    _release(w, 160)
    assert regions and regions[0] == pytest.approx((0.2, 0.8))
    assert w.crop_seconds(100.0) == pytest.approx((20.0, 80.0))


def test_crop_seconds_none_when_empty_or_zero_duration():
    w = _widget()
    assert w.crop_seconds(100.0) is None      # no crop set
    w._crop = (0.3, 0.3)                       # zero-width
    assert w.crop_seconds(100.0) is None


def test_paints_with_peaks_markers_crop_position():
    w = _widget()
    w.resize(300, 64)
    w.set_peaks(np.linspace(0, 1, 500).astype("float32"))
    w.set_markers([0.25, 0.75])
    w._crop = (0.1, 0.4)
    w.set_position(0.5)
    assert w.grab().width() > 0


def test_clear_resets_state():
    w = _widget()
    w.set_peaks(np.ones(10, dtype="float32"))
    w.set_markers([0.5])
    w._crop = (0.1, 0.2)
    w.clear()
    assert w._peaks is None
    assert w._markers == []
    assert w._crop is None
    w.grab()
