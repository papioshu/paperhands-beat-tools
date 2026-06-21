"""Tests for the WaveformWidget (offscreen Qt; no audio backend needed)."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.ui.widgets import WaveformWidget  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


def test_fraction_at_maps_x_to_0_1():
    _app()
    w = WaveformWidget()
    w.resize(200, 64)
    assert w._fraction_at(100) == pytest.approx(0.5)
    assert w._fraction_at(0) == 0.0
    assert w._fraction_at(10_000) == 1.0  # clamped


def test_seek_signal_emitted_on_click():
    from PySide6.QtCore import QEvent, QPointF, Qt
    from PySide6.QtGui import QMouseEvent

    _app()
    w = WaveformWidget()
    w.resize(200, 64)
    got = []
    w.seek_requested.connect(got.append)

    ev = QMouseEvent(
        QEvent.MouseButtonPress, QPointF(50.0, 10.0),
        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier,
    )
    w.mousePressEvent(ev)
    assert got and got[0] == pytest.approx(0.25)


def test_paints_with_peaks_markers_position():
    _app()
    w = WaveformWidget()
    w.resize(300, 64)
    w.set_peaks(np.linspace(0, 1, 500).astype("float32"))
    w.set_markers([0.25, 0.75])
    w.set_position(0.5)
    pm = w.grab()  # must not raise
    assert pm.width() > 0


def test_clear_resets_state():
    _app()
    w = WaveformWidget()
    w.set_peaks(np.ones(10, dtype="float32"))
    w.set_markers([0.5])
    w.clear()
    assert w._peaks is None
    assert w._markers == []
    w.grab()  # empty state still paints
