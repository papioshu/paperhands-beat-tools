"""Tag library + placement controls.

The tag library is DB-backed: tag files are grouped by category, each can be
enabled/disabled (checkbox), favorited (★), previewed, and selected as the active
tag to place. Folder changes re-sync new files into the library.
"""

from __future__ import annotations

import os
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QMessageBox,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

_MODE_LABELS = {"Normal": "normal", "Half-Time": "half",
                "Double-Time": "double", "Manual": "manual"}

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
    stretch_changed = Signal()              # tempo-match settings changed
    preview_stretch_requested = Signal()    # audition the active tag stretched
    stretch_editor_requested = Signal()     # open the per-placement stretch editor
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

        # -- Tempo match (per-placement tag stretching) --
        tempo_hdr = QLabel("Tempo match")
        tempo_hdr.setObjectName("SubHeading")
        layout.addWidget(tempo_hdr)

        t1 = QHBoxLayout()
        t1.addWidget(QLabel("Tag BPM"))
        self.native_bpm = QDoubleSpinBox()
        self.native_bpm.setRange(0, 300)
        self.native_bpm.setDecimals(1)
        self.native_bpm.setSpecialValueText("—")     # 0 shows as "not set"
        t1.addWidget(self.native_bpm)
        self.match_toggle = QCheckBox("Match beat")
        self.match_toggle.setChecked(True)   # auto-match each selected beat's tempo
        t1.addWidget(self.match_toggle)
        layout.addLayout(t1)

        t2 = QHBoxLayout()
        self.match_mode = QComboBox()
        self.match_mode.addItems(list(_MODE_LABELS.keys()))
        t2.addWidget(self.match_mode, 1)
        self.preserve_pitch = QCheckBox("Preserve pitch")
        self.preserve_pitch.setChecked(True)
        t2.addWidget(self.preserve_pitch)
        layout.addLayout(t2)

        t3 = QHBoxLayout()
        self.manual_ratio = QDoubleSpinBox()
        self.manual_ratio.setRange(0.25, 4.0)   # allow true half/double and beyond
        self.manual_ratio.setSingleStep(0.05)
        self.manual_ratio.setValue(1.0)
        self.manual_ratio.setPrefix("×")
        self.manual_ratio.setEnabled(False)          # only in Manual mode
        t3.addWidget(self.manual_ratio)
        self.stretch_label = QLabel("Stretch: 1.00×")
        self.stretch_label.setObjectName("AccentLime")
        t3.addWidget(self.stretch_label, 1)
        self.btn_preview_stretch = QPushButton("▶ Preview")
        t3.addWidget(self.btn_preview_stretch)
        layout.addLayout(t3)

        self.btn_stretch_editor = QPushButton("Stretch editor…")
        self.btn_stretch_editor.setToolTip(
            "Fine-tune the time-stretch of each placed tag on this beat")
        layout.addWidget(self.btn_stretch_editor)

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
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._tree_context_menu)
        self.btn_place.toggled.connect(self._on_place_toggled)
        self.btn_crop.toggled.connect(self._on_crop_toggled)
        self.btn_auto.clicked.connect(self.autoplace_requested)
        self.btn_tag_drop.clicked.connect(self.tag_at_drop_requested)
        self.btn_tag_hook.clicked.connect(self.tag_at_hook_requested)
        self.btn_clear.clicked.connect(self.clear_requested)
        self.native_bpm.valueChanged.connect(self._on_native_bpm_changed)
        self.match_toggle.toggled.connect(lambda *_: self.stretch_changed.emit())
        self.preserve_pitch.toggled.connect(lambda *_: self.stretch_changed.emit())
        self.match_mode.currentTextChanged.connect(self._on_mode_changed)
        self.manual_ratio.valueChanged.connect(lambda *_: self.stretch_changed.emit())
        self.btn_preview_stretch.clicked.connect(self.preview_stretch_requested)
        self.btn_stretch_editor.clicked.connect(self.stretch_editor_requested)
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
        self._load_native_bpm()
        self.active_tag_changed.emit(path or "")

    # -- tempo match -------------------------------------------------------

    def _load_native_bpm(self) -> None:
        """Show the selected tag's stored native BPM (0 = not set)."""
        tid = self._current_tag_id()
        row = self.db.get_tag_file(tid) if tid is not None else None
        self.native_bpm.blockSignals(True)
        self.native_bpm.setValue((row["native_bpm"] or 0.0) if row else 0.0)
        self.native_bpm.blockSignals(False)
        self.stretch_changed.emit()

    def _on_native_bpm_changed(self, value: float) -> None:
        tid = self._current_tag_id()
        if tid is not None:
            self.db.update_tag_file(tid, native_bpm=value or None)
        self.stretch_changed.emit()

    def _on_mode_changed(self, label: str) -> None:
        self.manual_ratio.setEnabled(_MODE_LABELS.get(label) == "manual")
        self.stretch_changed.emit()

    def stretch_settings(self) -> dict:
        """Current tempo-match settings (consumed when a tag is placed)."""
        return {
            "match": self.match_toggle.isChecked(),
            "mode": _MODE_LABELS.get(self.match_mode.currentText(), "normal"),
            "native_bpm": self.native_bpm.value() or None,
            "preserve_pitch": self.preserve_pitch.isChecked(),
            "manual_ratio": self.manual_ratio.value(),
        }

    def set_stretch_display(self, text: str) -> None:
        self.stretch_label.setText(text)

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

    def _tree_context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
        if item is None or item.data(0, _ID_ROLE) is None:
            return                                  # header/category row, not a tag
        self.tree.setCurrentItem(item)
        menu = QMenu(self)
        menu.addAction("Preview", self.preview_tag_requested.emit)
        menu.addAction("Toggle favorite", self._toggle_favorite)
        menu.addAction("Set category…", self._set_category)
        menu.addSeparator()
        menu.addAction("Remove from library", self._remove_tag_file)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _remove_tag_file(self) -> None:
        tid = self._current_tag_id()
        if tid is None:
            return
        row = self.db.get_tag_file(tid)
        # The library re-syncs from the folder, so removal must delete the file
        # too or it reappears on the next refresh. Destructive -> confirm first.
        resp = QMessageBox.question(
            self, "Remove tag",
            f"Remove “{row['name']}” from the library?\n\n"
            f"This permanently deletes the file from disk:\n{row['path']}",
            QMessageBox.Yes | QMessageBox.Cancel, QMessageBox.Cancel)
        if resp != QMessageBox.Yes:
            return
        try:
            os.remove(row["path"])
        except OSError:
            pass                                    # already gone; still drop the row
        self.db.remove_tag_file(tid)
        self.refresh_tags()
