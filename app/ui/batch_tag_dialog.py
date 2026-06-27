"""Batch Tag dialog: place tags at up to 4 manual times across many beats.

Time 1 is required; times 2-4 are opt-in. The chosen times are applied to every
selected beat (each clamped to its own duration), rotating through the enabled
producer tags — the same placement format Auto-Place produces.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

_DEFAULTS = [0.0, 30.0, 60.0, 90.0]


class BatchTagDialog(QDialog):
    def __init__(self, beat_count: int, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Batch Tag — manual times")
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f"Place tags at these times on {beat_count} beat(s). "
            "Time 1 is required; tick the others to use them."))
        form = QFormLayout()

        self.spins: list[QDoubleSpinBox] = []
        self.checks: list[QCheckBox | None] = []
        for i in range(4):
            spin = QDoubleSpinBox()
            spin.setRange(0, 3600)
            spin.setDecimals(1)
            spin.setSuffix(" s")
            spin.setValue(_DEFAULTS[i])
            self.spins.append(spin)
            if i == 0:
                form.addRow("Time 1 (required)", spin)
                self.checks.append(None)
            else:
                chk = QCheckBox(f"Time {i + 1}")
                spin.setEnabled(False)
                chk.toggled.connect(spin.setEnabled)
                roww = QWidget()
                h = QHBoxLayout(roww)
                h.setContentsMargins(0, 0, 0, 0)
                h.addWidget(chk)
                h.addWidget(spin, 1)
                form.addRow("", roww)
                self.checks.append(chk)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText(f"Tag {beat_count} beat(s)")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def times(self) -> list[float]:
        """Sorted, de-duplicated times: Time 1 plus any ticked optional times."""
        out = [self.spins[0].value()]
        for i in range(1, 4):
            if self.checks[i].isChecked():
                out.append(self.spins[i].value())
        return sorted(set(out))
