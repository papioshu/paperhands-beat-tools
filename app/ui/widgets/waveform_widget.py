"""A painted waveform with three interaction modes + scroll-wheel zoom.

* **seek**  — click anywhere to seek.
* **place** — click empty space to drop the active tag; click a marker to remove
  it; press-and-drag a marker to move it.
* **crop**  — drag to select a region (shaded band) for preview export.

Scroll the wheel over the waveform to zoom in/out (centered on the cursor);
Shift+wheel pans when zoomed. All positions (markers, crop, playhead, clicks)
are stored as *global* fractions of the whole track and mapped to the visible
window, so zooming never desyncs them.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from app.theme import COLORS

_MARKER_HIT_PX = 6
_DRAG_START_PX = 4
_MAX_ZOOM = 40.0


class WaveformWidget(QWidget):
    seek_requested = Signal(float)        # 0..1 (global)
    tag_placed = Signal(float)            # 0..1 (global)
    marker_removed = Signal(int)          # marker index
    marker_moved = Signal(int, float)     # marker index, new 0..1 (global)
    crop_changed = Signal(float, float)   # start, end (0..1 global)

    def __init__(self):
        super().__init__()
        self._peaks = None
        self._position = 0.0
        self._markers: List[float] = []
        self._sections: List[float] = []
        self._drop: Optional[float] = None
        self._hook: Optional[Tuple[float, float]] = None
        self._crop: Optional[Tuple[float, float]] = None
        self._mode = "seek"

        self._zoom = 1.0          # 1.0 = whole track; >1 = zoomed in
        self._view_start = 0.0    # global fraction at the left edge

        self._press_x = 0.0
        self._drag_marker: Optional[int] = None
        self._dragging = False
        self._crop_anchor: Optional[float] = None

        self.setMinimumHeight(64)
        self.setCursor(Qt.PointingHandCursor)
        self.setMouseTracking(True)

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
        self._drop = None
        self._hook = None
        self._crop = None
        self._zoom = 1.0
        self._view_start = 0.0
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

    def set_drop(self, fraction: Optional[float]) -> None:
        self._drop = None if fraction is None else max(0.0, min(1.0, fraction))
        self.update()

    def set_hook(self, span: Optional[Tuple[float, float]]) -> None:
        self._hook = span
        self.update()

    def clear_crop(self) -> None:
        self._crop = None
        self.update()

    def crop_seconds(self, duration_sec: float) -> Optional[Tuple[float, float]]:
        if not self._crop or duration_sec <= 0:
            return None
        a, b = self._crop
        if b - a < 1e-3:
            return None
        return (a * duration_sec, b * duration_sec)

    # -- zoom mapping ------------------------------------------------------

    def _window(self) -> float:
        return 1.0 / self._zoom

    def _global_at(self, x: float) -> float:
        w = max(1, self.width())
        return max(0.0, min(1.0, self._view_start + (x / w) * self._window()))

    def _screen_x(self, g: float) -> float:
        return ((g - self._view_start) / self._window()) * max(1, self.width())

    # Kept for tests/back-compat: at zoom 1 this is x/width (a global fraction).
    def _fraction_at(self, x: float) -> float:
        return self._global_at(x)

    def _clamp_view(self) -> None:
        self._zoom = max(1.0, min(_MAX_ZOOM, self._zoom))
        self._view_start = max(0.0, min(1.0 - self._window(), self._view_start))

    def wheelEvent(self, event):  # noqa: N802
        steps = event.angleDelta().y() / 120.0
        if event.modifiers() & Qt.ShiftModifier:
            self._view_start += -steps * 0.08 * self._window()  # pan
        else:
            cursor_g = self._global_at(event.position().x())
            cx = event.position().x() / max(1, self.width())
            self._zoom *= 1.25 ** steps
            self._zoom = max(1.0, min(_MAX_ZOOM, self._zoom))
            self._view_start = cursor_g - cx * self._window()   # keep cursor fixed
        self._clamp_view()
        self.update()

    # -- hit testing -------------------------------------------------------

    def _marker_index_at(self, x: float) -> Optional[int]:
        for i, frac in enumerate(self._markers):
            if abs(self._screen_x(frac) - x) <= _MARKER_HIT_PX:
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
            self._crop_anchor = self._global_at(x)
            self._crop = (self._crop_anchor, self._crop_anchor)
            self.update()

    def mouseMoveEvent(self, event):  # noqa: N802
        if not (event.buttons() & Qt.LeftButton):
            return
        x = event.position().x()
        g = self._global_at(x)
        if abs(x - self._press_x) > _DRAG_START_PX:
            self._dragging = True

        if self._mode == "place" and self._drag_marker is not None and self._dragging:
            self._markers[self._drag_marker] = g
            self.update()
        elif self._mode == "crop" and self._crop_anchor is not None:
            self._crop = (min(self._crop_anchor, g), max(self._crop_anchor, g))
            self.update()

    def mouseReleaseEvent(self, event):  # noqa: N802
        x = event.position().x()
        g = self._global_at(x)
        mode = self._mode

        if mode == "seek":
            self.seek_requested.emit(g)
        elif mode == "place":
            if self._dragging and self._drag_marker is not None:
                self.marker_moved.emit(self._drag_marker, g)
            else:
                idx = self._marker_index_at(x)
                if idx is not None:
                    self.marker_removed.emit(idx)
                else:
                    self.tag_placed.emit(g)
        elif mode == "crop" and self._crop is not None:
            self.crop_changed.emit(self._crop[0], self._crop[1])

        self._reset_drag()

    # -- painting ----------------------------------------------------------

    def paintEvent(self, event):  # noqa: N802
        p = QPainter(self)
        w, h = self.width(), self.height()
        mid = h / 2
        p.fillRect(self.rect(), QColor(COLORS["panel"]))

        self._paint_hook(p, w, h)
        self._paint_crop(p, w, h)
        self._paint_sections(p, w, h)

        if self._peaks is None or len(self._peaks) == 0:
            p.setPen(QPen(QColor(COLORS["border"]), 1))
            p.drawLine(0, int(mid), w, int(mid))
        else:
            n = len(self._peaks)
            lo = max(0, int(self._view_start * n))
            hi = min(n, int((self._view_start + self._window()) * n) + 1)
            played = QColor(COLORS["lime_dim"])
            unplayed = QColor(COLORS["text_faint"])
            played_x = self._screen_x(self._position)
            for j in range(lo, hi):
                x = self._screen_x(j / n)
                amp = float(self._peaks[j]) * (mid - 2)
                p.setPen(QPen(played if x <= played_x else unplayed, 1))
                p.drawLine(int(x), int(mid - amp), int(x), int(mid + amp))

        self._paint_drop(p, w, h)
        self._paint_markers(p, w, h)

        if self._peaks is not None and len(self._peaks):
            p.setPen(QPen(QColor(COLORS["lime"]), 2))
            px = int(self._screen_x(self._position))
            p.drawLine(px, 0, px, h)

        if self._zoom > 1.0:
            p.setPen(QPen(QColor(COLORS["text_dim"]), 1))
            p.drawText(6, 14, f"{self._zoom:.1f}x")
        p.end()

    def _paint_hook(self, p: QPainter, w: int, h: int) -> None:
        if not self._hook:
            return
        x0, x1 = int(self._screen_x(self._hook[0])), int(self._screen_x(self._hook[1]))
        band = QColor(COLORS["lime"])
        band.setAlpha(28)
        p.fillRect(x0, 0, max(1, x1 - x0), h, band)

    def _paint_drop(self, p: QPainter, w: int, h: int) -> None:
        if self._drop is None:
            return
        x = int(self._screen_x(self._drop))
        p.setPen(QPen(QColor(COLORS["warn"]), 2, Qt.DotLine))
        p.drawLine(x, 0, x, h)

    def _paint_crop(self, p: QPainter, w: int, h: int) -> None:
        if not self._crop:
            return
        x0, x1 = int(self._screen_x(self._crop[0])), int(self._screen_x(self._crop[1]))
        band = QColor(COLORS["violet"])
        band.setAlpha(60)
        p.fillRect(x0, 0, max(1, x1 - x0), h, band)
        p.setPen(QPen(QColor(COLORS["violet"]), 1))
        p.drawLine(x0, 0, x0, h)
        p.drawLine(x1, 0, x1, h)

    def _paint_sections(self, p: QPainter, w: int, h: int) -> None:
        if not self._sections:
            return
        p.setPen(QPen(QColor(COLORS["text_faint"]), 1, Qt.DashLine))
        for frac in self._sections:
            x = int(self._screen_x(frac))
            p.drawLine(x, 0, x, h)

    def _paint_markers(self, p: QPainter, w: int, h: int) -> None:
        p.setPen(QPen(QColor(COLORS["violet"]), 2))
        p.setBrush(QColor(COLORS["violet"]))
        for frac in self._markers:
            x = int(self._screen_x(frac))
            p.drawLine(x, 0, x, h)
            p.drawPolygon([QPointF(x, 0), QPointF(x + 7, 0), QPointF(x, 7)])
