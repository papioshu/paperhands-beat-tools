"""Per-placement stretch editor.

Lists the tags placed on the current beat and lets you tune each one's
time-stretch independently. Non-destructive: edits only change how the tag is
rendered at export — the original tag files and the clean master are untouched.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

_HELP = (
    "Adjust how each placed tag is time-stretched to lock it to the beat.\n"
    "• Stretch 1.00× = no change. Above 1 plays the tag faster (shorter); "
    "below 1 slower (longer).\n"
    "• Preserve pitch keeps the tag's tone while stretching. Uncheck it for a "
    "tape-style effect where pitch rises/falls with speed.\n"
    "• Changes apply only to this beat's preview/stem export — your tag files "
    "and clean master are never modified."
)


class StretchEditorDialog(QDialog):
    def __init__(self, placements, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Stretch Editor")
        self.resize(460, 360)
        self._placements = list(placements)

        layout = QVBoxLayout(self)
        help_label = QLabel(_HELP)
        help_label.setWordWrap(True)
        help_label.setObjectName("SubHeading")
        layout.addWidget(help_label)

        self.table = QTableWidget(len(self._placements), 4)
        self.table.setHorizontalHeaderLabels(["Time", "Tag", "Stretch", "Preserve pitch"])
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        layout.addWidget(self.table, 1)

        self._spins: list[QDoubleSpinBox] = []
        self._checks: list[QCheckBox] = []
        for r, p in enumerate(self._placements):
            t = QTableWidgetItem(f"{int(p.position_sec // 60)}:{int(p.position_sec % 60):02d}")
            self.table.setItem(r, 0, t)
            self.table.setItem(r, 1, QTableWidgetItem(Path(p.tag_path).stem))

            spin = QDoubleSpinBox()
            spin.setRange(0.25, 4.0)     # allow true half/double and beyond
            spin.setSingleStep(0.05)
            spin.setPrefix("×")
            spin.setValue(round(p.stretch_ratio, 4))
            self.table.setCellWidget(r, 2, spin)
            self._spins.append(spin)

            chk = QCheckBox()
            chk.setChecked(bool(p.preserve_pitch))
            self.table.setCellWidget(r, 3, chk)
            self._checks.append(chk)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def results(self) -> list:
        """One ``(ratio, preserve_pitch)`` per placement, in order."""
        return [(s.value(), c.isChecked())
                for s, c in zip(self._spins, self._checks)]
