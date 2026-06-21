"""A painted waveform: peaks + playhead + tag markers, with click-to-seek.

The widget is display-only state: give it a peaks array (0..1), a playback
position (0..1), and optional tag markers (each 0..1). Clicking anywhere emits
``seek_requested(fraction)``; the owner decides what to do with it. In Phase 5
the same surface is clicked to *place* a tag.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from app.theme import COLORS


class WaveformWidget(QWidget):
    seek_requested = Signal(float)   # 0..1
    marker_clicked = Signal(float)   # 0..1 (used by tagging in Phase 5)

    def __init__(self):
        super().__init__()
        self._peaks = None            # numpy array or None
        self._position = 0.0          # 0..1
        self._markers: List[float] = []
        self.setMinimumHeight(64)
        self.setCursor(Qt.PointingHandCursor)

    # -- state -------------------------------------------------------------

    def set_peaks(self, peaks) -> None:
        self._peaks = peaks
        self.update()

    def clear(self) -> None:
        self._peaks = None
        self._position = 0.0
        self._markers = []
        self.update()

    def set_position(self, fraction: float) -> None:
        self._position = max(0.0, min(1.0, fraction))
        self.update()

    def set_markers(self, fractions: List[float]) -> None:
        self._markers = [max(0.0, min(1.0, f)) for f in fractions]
        self.update()

    # -- interaction -------------------------------------------------------

    def _fraction_at(self, x: float) -> float:
        w = max(1, self.width())
        return max(0.0, min(1.0, x / w))

    def mousePressEvent(self, event):  # noqa: N802 - Qt override
        frac = self._fraction_at(event.position().x())
        self.seek_requested.emit(frac)
        self.marker_clicked.emit(frac)
        super().mousePressEvent(event)

    # -- painting ----------------------------------------------------------

    def paintEvent(self, event):  # noqa: N802 - Qt override
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing, False)
        w, h = self.width(), self.height()
        mid = h / 2

        p.fillRect(self.rect(), QColor(COLORS["panel"]))

        if self._peaks is None or len(self._peaks) == 0:
            p.setPen(QPen(QColor(COLORS["border"]), 1))
            p.drawLine(0, int(mid), w, int(mid))
            self._paint_markers(p, w, h)
            p.end()
            return

        n = len(self._peaks)
        played_x = self._position * w
        played = QColor(COLORS["lime_dim"])
        unplayed = QColor(COLORS["text_faint"])

        for i in range(n):
            x = (i / n) * w
            amp = float(self._peaks[i]) * (mid - 2)
            p.setPen(QPen(played if x <= played_x else unplayed, 1))
            p.drawLine(int(x), int(mid - amp), int(x), int(mid + amp))

        self._paint_markers(p, w, h)

        # Playhead
        p.setPen(QPen(QColor(COLORS["lime"]), 2))
        p.drawLine(int(played_x), 0, int(played_x), h)
        p.end()

    def _paint_markers(self, p: QPainter, w: int, h: int) -> None:
        pen = QPen(QColor(COLORS["violet"]), 2)
        p.setPen(pen)
        for frac in self._markers:
            x = int(frac * w)
            p.drawLine(x, 0, x, h)
            # little triangle flag at the top
            p.setBrush(QColor(COLORS["violet"]))
            p.drawPolygon([QPointF(x, 0), QPointF(x + 7, 0), QPointF(x, 7)])
