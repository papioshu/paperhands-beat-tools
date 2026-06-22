"""Tag library + placement controls.

The tag library is DB-backed: tag files are grouped by category, each can be
enabled/disabled (checkbox), favorited (★), previewed, and selected as the active
tag to place. Folder changes re-sync new files into the library.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from app import config
from app.services import tag_library

_PATH_ROLE = Qt.UserRole
_ID_ROLE = Qt.UserRole + 1


class TagLibraryPanel(QFrame):
    active_tag_changed = Signal(str)     # path ("" if none)
    preview_tag_requested = Signal()
    place_mode_changed = Signal(bool)
    crop_mode_changed = Signal(bool)
    autoplace_requested = Signal()
    tag_at_drop_requested = Signal()
    tag_at_hook_requested = Signal()
    clear_requested = Signal()
    export_tagged_preview_requested = Signal()
    export_clean_master_requested = Signal()
    export_tag_stem_requested = Signal()
    export_buyer_package_requested = Signal()

    def __init__(self, db):
        super().__init__()
        self.db = db
        self.setObjectName("Panel")
        self._building = False

        layout = QVBoxLayout(self)
        heading = QLabel("Tag library")
        heading.setObjectName("Heading")
        layout.addWidget(heading)

        folder_row = QHBoxLayout()
        self.folder_label = QLabel("")
        self.folder_label.setObjectName("SubHeading")
        self.folder_label.setWordWrap(True)
        self.btn_folder = QPushButton("Folder…")
        self.btn_folder.setFixedWidth(80)
        folder_row.addWidget(self.folder_label, 1)
        folder_row.addWidget(self.btn_folder)
        layout.addLayout(folder_row)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setMaximumHeight(170)
        layout.addWidget(self.tree)

        tag_btns = QHBoxLayout()
        self.btn_preview = QPushButton("▶ Preview")
        self.btn_favorite = QPushButton("★ Favorite")
        self.btn_category = QPushButton("Category…")
        tag_btns.addWidget(self.btn_preview)
        tag_btns.addWidget(self.btn_favorite)
        tag_btns.addWidget(self.btn_category)
        layout.addLayout(tag_btns)

        mode_row = QHBoxLayout()
        self.btn_place = QPushButton("Place on click")
        self.btn_place.setObjectName("Accent")
        self.btn_place.setCheckable(True)
        self.btn_crop = QPushButton("Crop preview")
        self.btn_crop.setCheckable(True)
        mode_row.addWidget(self.btn_place)
        mode_row.addWidget(self.btn_crop)
        layout.addLayout(mode_row)

        action_row = QHBoxLayout()
        self.btn_auto = QPushButton("Auto-place")
        self.btn_clear = QPushButton("Clear")
        action_row.addWidget(self.btn_auto)
        action_row.addWidget(self.btn_clear)
        layout.addLayout(action_row)

        smart_row = QHBoxLayout()
        self.btn_tag_drop = QPushButton("Tag @ Drop")
        self.btn_tag_hook = QPushButton("Tag @ Hook")
        smart_row.addWidget(self.btn_tag_drop)
        smart_row.addWidget(self.btn_tag_hook)
        layout.addLayout(smart_row)

        self.count_label = QLabel("0 tags placed")
        self.count_label.setObjectName("AccentLime")
        layout.addWidget(self.count_label)

        self.btn_export_preview = QPushButton("Export Tagged Preview")
        self.btn_export_preview.setObjectName("Primary")
        layout.addWidget(self.btn_export_preview)
        self.btn_export_master = QPushButton("Export Clean Master")
        layout.addWidget(self.btn_export_master)
        self.btn_export_stem = QPushButton("Export Tag Stem")
        layout.addWidget(self.btn_export_stem)
        self.btn_export_package = QPushButton("Export Buyer Package")
        self.btn_export_package.setObjectName("Accent")
        layout.addWidget(self.btn_export_package)
        layout.addStretch(1)

        self._export_buttons = [
            self.btn_export_preview, self.btn_export_master,
            self.btn_export_stem, self.btn_export_package,
        ]

        # wiring
        self.btn_folder.clicked.connect(self._choose_folder)
        self.btn_preview.clicked.connect(self.preview_tag_requested)
        self.btn_favorite.clicked.connect(self._toggle_favorite)
        self.btn_category.clicked.connect(self._set_category)
        self.tree.currentItemChanged.connect(self._on_tag_changed)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.itemDoubleClicked.connect(lambda *_: self.preview_tag_requested.emit())
        self.btn_place.toggled.connect(self._on_place_toggled)
        self.btn_crop.toggled.connect(self._on_crop_toggled)
        self.btn_auto.clicked.connect(self.autoplace_requested)
        self.btn_tag_drop.clicked.connect(self.tag_at_drop_requested)
        self.btn_tag_hook.clicked.connect(self.tag_at_hook_requested)
        self.btn_clear.clicked.connect(self.clear_requested)
        self.btn_export_preview.clicked.connect(self.export_tagged_preview_requested)
        self.btn_export_master.clicked.connect(self.export_clean_master_requested)
        self.btn_export_stem.clicked.connect(self.export_tag_stem_requested)
        self.btn_export_package.clicked.connect(self.export_buyer_package_requested)

        self.refresh_tags()

    # -- public API --------------------------------------------------------

    def refresh_tags(self) -> None:
        folder = config.tags_folder()
        self.folder_label.setText(folder)
        tag_library.sync_folder(self.db, folder)

        self._building = True
        self.tree.clear()
        groups: dict = {}
        first_child = None
        for row in self.db.list_tag_files():
            cat = row["category"] or "Uncategorized"
            if cat not in groups:
                parent = QTreeWidgetItem([cat])
                parent.setFlags(parent.flags() & ~Qt.ItemIsSelectable)
                self.tree.addTopLevelItem(parent)
                parent.setExpanded(True)
                groups[cat] = parent
            label = ("★ " if row["favorite"] else "") + row["name"]
            child = QTreeWidgetItem([label])
            child.setData(0, _PATH_ROLE, row["path"])
            child.setData(0, _ID_ROLE, row["id"])
            child.setFlags(child.flags() | Qt.ItemIsUserCheckable)
            child.setCheckState(0, Qt.Checked if row["enabled"] else Qt.Unchecked)
            groups[cat].addChild(child)
            first_child = first_child or child
        self._building = False

        if first_child is not None:
            self.tree.setCurrentItem(first_child)
        else:
            self.active_tag_changed.emit("")

    def active_tag(self) -> Optional[str]:
        item = self.tree.currentItem()
        return item.data(0, _PATH_ROLE) if item else None

    def all_tag_paths(self) -> list:
        """Enabled tag paths (used for auto-place rotation)."""
        return [r["path"] for r in self.db.list_tag_files(enabled_only=True)]

    def set_placement_count(self, n: int) -> None:
        self.count_label.setText(f"{n} tag{'s' if n != 1 else ''} placed")

    def place_mode(self) -> bool:
        return self.btn_place.isChecked()

    def crop_mode(self) -> bool:
        return self.btn_crop.isChecked()

    def set_export_enabled(self, on: bool) -> None:
        for btn in self._export_buttons:
            btn.setEnabled(on)

    # -- internals ---------------------------------------------------------

    def _current_tag_id(self) -> Optional[int]:
        item = self.tree.currentItem()
        return item.data(0, _ID_ROLE) if item else None

    def _on_place_toggled(self, on: bool) -> None:
        if on and self.btn_crop.isChecked():
            self.btn_crop.setChecked(False)
        self.place_mode_changed.emit(on)

    def _on_crop_toggled(self, on: bool) -> None:
        if on and self.btn_place.isChecked():
            self.btn_place.setChecked(False)
        self.crop_mode_changed.emit(on)

    def _choose_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose tags folder")
        if folder:
            config.set_tags_folder(folder)
            self.refresh_tags()

    def _on_tag_changed(self, current, _previous) -> None:
        path = current.data(0, _PATH_ROLE) if current else None
        self.active_tag_changed.emit(path or "")

    def _on_item_changed(self, item, _column) -> None:
        if self._building:
            return
        tid = item.data(0, _ID_ROLE)
        if tid is not None:  # a tag row's checkbox toggled -> enable/disable
            self.db.update_tag_file(tid, enabled=1 if item.checkState(0) == Qt.Checked else 0)

    def _toggle_favorite(self) -> None:
        tid = self._current_tag_id()
        if tid is None:
            return
        row = self.db.get_tag_file(tid)
        self.db.update_tag_file(tid, favorite=0 if row["favorite"] else 1)
        self.refresh_tags()

    def _set_category(self) -> None:
        tid = self._current_tag_id()
        if tid is None:
            return
        row = self.db.get_tag_file(tid)
        text, ok = QInputDialog.getText(
            self, "Set category", "Category:", text=row["category"] or "")
        if ok:
            self.db.update_tag_file(tid, category=text.strip() or "Uncategorized")
            self.refresh_tags()
