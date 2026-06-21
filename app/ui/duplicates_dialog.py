"""Duplicate review dialog.

Shows groups of beats whose audio fingerprints match (same beat, even if renamed
or re-encoded). You pick which copies to drop. **Non-destructive:** removing a
copy here only deletes its *catalog entry* — the audio file on disk is never
touched.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)


class DuplicatesDialog(QDialog):
    def __init__(self, db, groups, parent=None):
        super().__init__(parent)
        self.db = db
        self.groups = groups          # list[list[row]]
        self.removed = 0
        self.setWindowTitle(f"Duplicates — {len(groups)} group(s)")
        self.resize(760, 500)

        layout = QVBoxLayout(self)
        heading = QLabel("Duplicate beats")
        heading.setObjectName("Heading")
        layout.addWidget(heading)
        hint = QLabel("Matched by audio fingerprint. Check the copies to remove. "
                      "This only removes them from the library — files on disk are "
                      "left untouched.")
        hint.setObjectName("SubHeading")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Beat", "BPM", "Key"])
        self.tree.setColumnWidth(0, 480)
        layout.addWidget(self.tree, 1)

        for i, group in enumerate(self.groups, start=1):
            parent_item = QTreeWidgetItem([f"Group {i} — {len(group)} copies", "", ""])
            parent_item.setFlags(parent_item.flags() & ~Qt.ItemIsSelectable)
            self.tree.addTopLevelItem(parent_item)
            parent_item.setExpanded(True)
            for j, row in enumerate(group):
                child = QTreeWidgetItem([
                    str(Path(row["file_path"])),
                    "" if row["bpm"] is None else f"{row['bpm']:g}",
                    row["key"] or "",
                ])
                child.setData(0, Qt.UserRole, row["id"])
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                # Keep the first copy, pre-check the rest for removal.
                child.setCheckState(0, Qt.Checked if j > 0 else Qt.Unchecked)
                parent_item.addChild(child)

        row = QHBoxLayout()
        row.addStretch(1)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_remove = QPushButton("Remove checked from library")
        self.btn_remove.setObjectName("Primary")
        row.addWidget(self.btn_cancel)
        row.addWidget(self.btn_remove)
        layout.addLayout(row)

        self.btn_cancel.clicked.connect(self.reject)
        self.btn_remove.clicked.connect(self._remove)

    def _checked_ids(self) -> list:
        ids = []
        for i in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(i)
            for j in range(parent.childCount()):
                child = parent.child(j)
                if child.checkState(0) == Qt.Checked:
                    ids.append(child.data(0, Qt.UserRole))
        return ids

    def _remove(self) -> None:
        for bid in self._checked_ids():
            self.db.delete_beat(bid)     # catalog row only; file stays on disk
            self.removed += 1
        self.accept()
