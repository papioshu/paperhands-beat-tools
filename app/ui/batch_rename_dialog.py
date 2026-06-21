"""Batch rename dialog: apply a filename pattern across many beats at once.

Live preview of current -> new for every selected beat, with collision warnings.
Applies through the same collision-safe ``renamer.rename_in_place`` used for
single renames, so files on disk and the DB stay in sync.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.services import renamer
from app.theme import COLORS


class BatchRenameDialog(QDialog):
    def __init__(self, db, rows, parent=None):
        super().__init__(parent)
        self.db = db
        self.rows = list(rows)
        self.applied = 0
        self.setWindowTitle(f"Batch Rename — {len(self.rows)} beat(s)")
        self.resize(720, 460)

        layout = QVBoxLayout(self)

        heading = QLabel("Filename pattern")
        heading.setObjectName("Heading")
        layout.addWidget(heading)
        hint = QLabel("Tokens: {title} {bpm} {key} {name}. Empty values collapse "
                      "cleanly. Beats that would collide are skipped.")
        hint.setObjectName("SubHeading")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.pattern = QLineEdit(renamer.DEFAULT_PATTERN)
        layout.addWidget(self.pattern)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Current", "New name", "Status"])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        layout.addWidget(self.table, 1)

        row = QHBoxLayout()
        self.summary = QLabel("")
        self.summary.setObjectName("SubHeading")
        row.addWidget(self.summary)
        row.addStretch(1)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_apply = QPushButton("Apply rename")
        self.btn_apply.setObjectName("Primary")
        row.addWidget(self.btn_cancel)
        row.addWidget(self.btn_apply)
        layout.addLayout(row)

        self.pattern.textChanged.connect(self._refresh)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_apply.clicked.connect(self._apply)

        self._plans = []
        self._refresh()

    def _refresh(self) -> None:
        self._plans = renamer.plan_batch_rename(self.rows, self.pattern.text())
        self.table.setRowCount(len(self._plans))
        will_rename = 0
        for r, p in enumerate(self._plans):
            if p["conflict"]:
                status, color = "conflict", QColor(COLORS["error"])
            elif not p["changed"]:
                status, color = "unchanged", QColor(COLORS["text_faint"])
            else:
                status, color = "rename", QColor(COLORS["lime"])
                will_rename += 1
            for c, text in enumerate((p["current"], p["new_name"], status)):
                item = QTableWidgetItem(text)
                if c == 2:
                    item.setForeground(color)
                self.table.setItem(r, c, item)
        self.summary.setText(f"{will_rename} of {len(self._plans)} will be renamed")
        self.btn_apply.setEnabled(will_rename > 0)

    def _apply(self) -> None:
        applied = 0
        for p in self._plans:
            if not p["changed"] or p["conflict"]:
                continue
            try:
                renamer.rename_in_place(self.db, p["beat_id"], p["new_stem"])
                applied += 1
            except (FileExistsError, FileNotFoundError):
                continue   # skip problem files; others still proceed
        self.applied = applied
        self.accept()
