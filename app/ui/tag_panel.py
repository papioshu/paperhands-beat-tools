"""Tag library + placement controls.

Lists the producer tags in your tags folder. Pick one, toggle "Place on click",
then click anywhere on the waveform to drop that tag there (click a marker again
to remove it). Auto-place lays down default interval placements you can tweak,
and Export renders the tagged beat through the shared core engine.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from app import config
from app.services.importer import AUDIO_EXTS


class TagLibraryPanel(QFrame):
    active_tag_changed = Signal(str)     # path ("" if none)
    place_mode_changed = Signal(bool)
    crop_mode_changed = Signal(bool)
    autoplace_requested = Signal()
    clear_requested = Signal()
    export_tagged_preview_requested = Signal()
    export_clean_master_requested = Signal()
    export_tag_stem_requested = Signal()
    export_buyer_package_requested = Signal()

    def __init__(self):
        super().__init__()
        self.setObjectName("Panel")

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

        self.list = QListWidget()
        self.list.setMaximumHeight(140)
        layout.addWidget(self.list)

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
        self.list.currentItemChanged.connect(self._on_tag_changed)
        self.btn_place.toggled.connect(self._on_place_toggled)
        self.btn_crop.toggled.connect(self._on_crop_toggled)
        self.btn_auto.clicked.connect(self.autoplace_requested)
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
        self.list.clear()
        p = Path(folder)
        if p.is_dir():
            for f in sorted(p.iterdir()):
                if f.is_file() and f.suffix.lower() in AUDIO_EXTS:
                    item = QListWidgetItem(f.name)
                    item.setData(Qt.UserRole, str(f.resolve()))
                    self.list.addItem(item)
        if self.list.count():
            self.list.setCurrentRow(0)
        else:
            self.active_tag_changed.emit("")

    def active_tag(self) -> Optional[str]:
        item = self.list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def all_tag_paths(self) -> list:
        return [self.list.item(i).data(Qt.UserRole) for i in range(self.list.count())]

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

    def _on_place_toggled(self, on: bool) -> None:
        if on and self.btn_crop.isChecked():
            self.btn_crop.setChecked(False)  # mutually exclusive
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
        self.active_tag_changed.emit(current.data(Qt.UserRole) if current else "")
