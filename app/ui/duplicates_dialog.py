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
    QCheckBox,
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
        self.ignored = 0
        self.setWindowTitle(f"Duplicates — {len(groups)} group(s)")
        self.resize(760, 500)

        layout = QVBoxLayout(self)
        heading = QLabel("Duplicate beats")
        heading.setObjectName("Heading")
        layout.addWidget(heading)
        hint = QLabel("Matched by audio fingerprint. Check copies under "
                      "<b>Remove</b> to drop them from the library, or <b>Ignore</b> "
                      "to keep them and stop flagging them as duplicates. Files on "
                      "disk are never touched.")
        hint.setObjectName("SubHeading")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Beat", "BPM", "Key", "Ignore"])
        self.tree.setColumnWidth(0, 460)
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
                    "",
                ])
                child.setData(0, Qt.UserRole, row["id"])
                child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
                # Keep the first copy, pre-check the rest for removal.
                child.setCheckState(0, Qt.Checked if j > 0 else Qt.Unchecked)
                child.setCheckState(3, Qt.Unchecked)   # Ignore (opt-in)
                parent_item.addChild(child)

        row = QHBoxLayout()
        self.chk_all = QCheckBox("Select all")
        row.addWidget(self.chk_all)
        row.addStretch(1)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_remove = QPushButton("Apply (remove / ignore)")
        self.btn_remove.setObjectName("Primary")
        row.addWidget(self.btn_cancel)
        row.addWidget(self.btn_remove)
        layout.addLayout(row)

        self.chk_all.clicked.connect(self._toggle_all)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_remove.clicked.connect(self._remove)

    def _toggle_all(self, checked: bool) -> None:
        state = Qt.Checked if checked else Qt.Unchecked
        for i in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(i)
            for j in range(parent.childCount()):
                parent.child(j).setCheckState(0, state)

    def _ids_checked_in(self, col: int) -> list:
        ids = []
        for i in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(i)
            for j in range(parent.childCount()):
                child = parent.child(j)
                if child.checkState(col) == Qt.Checked:
                    ids.append(child.data(0, Qt.UserRole))
        return ids

    def _remove(self) -> None:
        remove = set(self._ids_checked_in(0))
        for bid in self._ids_checked_in(3):    # mark ignore (skip ones being removed)
            if bid not in remove:
                self.db.update_beat(bid, ignored=1)
                self.ignored += 1
        for bid in remove:
            self.db.delete_beat(bid)           # catalog row only; file stays on disk
            self.removed += 1
        self.accept()
