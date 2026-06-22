"""Per-beat tag-layer mixer: one row per placed tag with M/S/volume/pan/enable.

Display-only state driven by the main window: ``set_layers`` rebuilds the rows
from the current beat's layers; any control change emits ``layer_changed`` with
the tag's full property dict.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class LayersPanel(QFrame):
    layer_changed = Signal(str, dict)   # tag_path, props

    def __init__(self):
        super().__init__()
        self.setObjectName("Panel")
        self._building = False

        outer = QVBoxLayout(self)
        heading = QLabel("Layers")
        heading.setObjectName("Heading")
        outer.addWidget(heading)
        self.empty = QLabel("Place tags to see their layers.")
        self.empty.setObjectName("SubHeading")
        outer.addWidget(self.empty)

        self.rows = QWidget()
        self._rows_layout = QVBoxLayout(self.rows)
        self._rows_layout.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(self.rows)
        outer.addStretch(1)

    def set_layers(self, layers: dict) -> None:
        """Rebuild rows from {tag_path: props}."""
        self._building = True
        while self._rows_layout.count():
            item = self._rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.empty.setVisible(not layers)

        for path, props in layers.items():
            self._rows_layout.addWidget(self._make_row(path, props))
        self._building = False

    def _make_row(self, path: str, props: dict) -> QWidget:
        row = QWidget()
        h = QHBoxLayout(row)
        h.setContentsMargins(0, 0, 0, 0)

        enable = QCheckBox()
        enable.setChecked(props.get("enabled", True))
        enable.setToolTip("Enable layer")
        h.addWidget(enable)

        name = QLabel(Path(path).stem)
        name.setMinimumWidth(80)
        h.addWidget(name, 1)

        mute = QPushButton("M")
        mute.setCheckable(True)
        mute.setChecked(props.get("mute", False))
        mute.setFixedWidth(26)
        solo = QPushButton("S")
        solo.setCheckable(True)
        solo.setChecked(props.get("solo", False))
        solo.setFixedWidth(26)
        h.addWidget(mute)
        h.addWidget(solo)

        vol = QSlider(Qt.Horizontal)
        vol.setRange(-24, 6)
        vol.setValue(int(props.get("volume_db", 0)))
        vol.setFixedWidth(80)
        vol.setToolTip("Volume (dB)")
        h.addWidget(vol)

        pan = QSlider(Qt.Horizontal)
        pan.setRange(-100, 100)
        pan.setValue(int(props.get("pan", 0.0) * 100))
        pan.setFixedWidth(70)
        pan.setToolTip("Pan (L–R)")
        h.addWidget(pan)

        def emit():
            if self._building:
                return
            self.layer_changed.emit(path, {
                "enabled": enable.isChecked(),
                "mute": mute.isChecked(),
                "solo": solo.isChecked(),
                "volume_db": float(vol.value()),
                "pan": pan.value() / 100.0,
            })

        enable.toggled.connect(emit)
        mute.toggled.connect(emit)
        solo.toggled.connect(emit)
        vol.valueChanged.connect(emit)
        pan.valueChanged.connect(emit)
        return row
