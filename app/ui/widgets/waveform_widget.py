"""A painted waveform with three interaction modes.

* **seek**  — click anywhere to seek.
* **place** — click empty space to drop the active tag; click a marker to remove
  it; press-and-drag a marker to move it.
* **crop**  — drag to select a region (shaded band) for preview export.

The widget is pure display + interaction state. It emits intents and lets the
owner (MainWindow) decide what they mean against the real placement list.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from app.theme import COLORS

_MARKER_HIT_PX = 6        # how close a click must be to grab a marker
_DRAG_START_PX = 4        # movement before a press becomes a drag


class WaveformWidget(QWidget):
    seek_requested = Signal(float)        # 0..1
    tag_placed = Signal(float)            # 0..1
    marker_removed = Signal(int)          # marker index
    marker_moved = Signal(int, float)     # marker index, new 0..1
    crop_changed = Signal(float, float)   # start, end (0..1)

    def __init__(self):
        super().__init__()
        self._peaks = None
        self._position = 0.0
        self._markers: List[float] = []
        self._sections: List[float] = []     # structure boundaries (fractions)
        self._crop: Optional[Tuple[float, float]] = None
        self._mode = "seek"

        # transient drag state
        self._press_x = 0.0
        self._drag_marker: Optional[int] = None
        self._dragging = False
        self._crop_anchor: Optional[float] = None

        self.setMinimumHeight(64)
        self.setCursor(Qt.PointingHandCursor)

    # -- state -------------------------------------------------------------

    def set_mode(self, mode: str) -> None:
        assert mode in ("seek", "place", "crop")
        self._mode = mode
        self._reset_drag()
        self.update()

    def set_peaks(self, peaks) -> None:
        self._peaks = peaks
        self.update()

    def clear(self) -> None:
        self._peaks = None
        self._position = 0.0
        self._markers = []
        self._sections = []
        self._crop = None
        self._reset_drag()
        self.update()

    def set_position(self, fraction: float) -> None:
        self._position = max(0.0, min(1.0, fraction))
        self.update()

    def set_markers(self, fractions: List[float]) -> None:
        self._markers = [max(0.0, min(1.0, f)) for f in fractions]
        self.update()

    def set_sections(self, fractions: List[float]) -> None:
        self._sections = [max(0.0, min(1.0, f)) for f in fractions]
        self.update()

    def clear_crop(self) -> None:
        self._crop = None
        self.update()

    def crop_seconds(self, duration_sec: float) -> Optional[Tuple[float, float]]:
        """The current crop as ``(start_sec, end_sec)``, or None if unset/empty."""
        if not self._crop or duration_sec <= 0:
            return None
        a, b = self._crop
        if b - a < 1e-3:
            return None
        return (a * duration_sec, b * duration_sec)

    # -- hit testing -------------------------------------------------------

    def _fraction_at(self, x: float) -> float:
        return max(0.0, min(1.0, x / max(1, self.width())))

    def _marker_index_at(self, x: float) -> Optional[int]:
        w = max(1, self.width())
        for i, frac in enumerate(self._markers):
            if abs(frac * w - x) <= _MARKER_HIT_PX:
                return i
        return None

    def _reset_drag(self) -> None:
        self._drag_marker = None
        self._dragging = False
        self._crop_anchor = None

    # -- interaction -------------------------------------------------------

    def mousePressEvent(self, event):  # noqa: N802
        x = event.position().x()
        self._press_x = x
        self._dragging = False
        if self._mode == "place":
            self._drag_marker = self._marker_index_at(x)
        elif self._mode == "crop":
            self._crop_anchor = self._fraction_at(x)
            self._crop = (self._crop_anchor, self._crop_anchor)
            self.update()

    def mouseMoveEvent(self, event):  # noqa: N802
        x = event.position().x()
        frac = self._fraction_at(x)
        if abs(x - self._press_x) > _DRAG_START_PX:
            self._dragging = True

        if self._mode == "place" and self._drag_marker is not None and self._dragging:
            self._markers[self._drag_marker] = frac   # live feedback
            self.update()
        elif self._mode == "crop" and self._crop_anchor is not None:
            self._crop = (min(self._crop_anchor, frac), max(self._crop_anchor, frac))
            self.update()

    def mouseReleaseEvent(self, event):  # noqa: N802
        x = event.position().x()
        frac = self._fraction_at(x)
        mode = self._mode

        if mode == "seek":
            self.seek_requested.emit(frac)
        elif mode == "place":
            if self._dragging and self._drag_marker is not None:
                self.marker_moved.emit(self._drag_marker, frac)
            else:
                idx = self._marker_index_at(x)
                if idx is not None:
                    self.marker_removed.emit(idx)
                else:
                    self.tag_placed.emit(frac)
        elif mode == "crop" and self._crop is not None:
            self.crop_changed.emit(self._crop[0], self._crop[1])

        self._reset_drag()

    # -- painting ----------------------------------------------------------

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        w, h = self.width(), self.height()
        mid = h / 2
        p.fillRect(self.rect(), QColor(COLORS["panel"]))

        self._paint_crop(p, w, h)
        self._paint_sections(p, w, h)

        if self._peaks is None or len(self._peaks) == 0:
            p.setPen(QPen(QColor(COLORS["border"]), 1))
            p.drawLine(0, int(mid), w, int(mid))
        else:
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

        if self._peaks is not None and len(self._peaks):
            p.setPen(QPen(QColor(COLORS["lime"]), 2))
            px = int(self._position * w)
            p.drawLine(px, 0, px, h)
        p.end()

    def _paint_crop(self, p: QPainter, w: int, h: int) -> None:
        if not self._crop:
            return
        a, b = self._crop
        x0, x1 = int(a * w), int(b * w)
        band = QColor(COLORS["violet"])
        band.setAlpha(60)
        p.fillRect(x0, 0, max(1, x1 - x0), h, band)
        p.setPen(QPen(QColor(COLORS["violet"]), 1))
        p.drawLine(x0, 0, x0, h)
        p.drawLine(x1, 0, x1, h)

    def _paint_sections(self, p: QPainter, w: int, h: int) -> None:
        if not self._sections:
            return
        pen = QPen(QColor(COLORS["text_faint"]), 1, Qt.DashLine)
        p.setPen(pen)
        for frac in self._sections:
            x = int(frac * w)
            p.drawLine(x, 0, x, h)

    def _paint_markers(self, p: QPainter, w: int, h: int) -> None:
        p.setPen(QPen(QColor(COLORS["violet"]), 2))
        p.setBrush(QColor(COLORS["violet"]))
        for frac in self._markers:
            x = int(frac * w)
            p.drawLine(x, 0, x, h)
            p.drawPolygon([QPointF(x, 0), QPointF(x + 7, 0), QPointF(x, 7)])
