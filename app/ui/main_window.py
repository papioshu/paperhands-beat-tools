"""The main application window: a three-pane shell.

    +------------------------------------------------------------+
    | Toolbar: [Import] [Scan]   [search...........]   [Settings]|
    +---------------------------+--------------------------------+
    | Library table             | Detail / tag panel (editable)  |
    +---------------------------+--------------------------------+
    | Player bar: waveform + transport (Phase 4)                 |
    +------------------------------------------------------------+
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.db import Database
from app.services import importer, renamer
from app.ui.detail_panel import DetailPanel
from app.ui.settings_dialog import SettingsDialog

_COLUMNS = ["Title", "BPM", "Key", "Genre", "Mood", "Status"]


class MainWindow(QMainWindow):
    def __init__(self, db_path: str = "library.db"):
        super().__init__()
        self.db = Database(db_path)
        self.setWindowTitle("Paperhand's Beat Tools")
        self.resize(1180, 720)

        self._build_toolbar()
        self._build_body()
        self._build_player_bar()
        self.statusBar().showMessage("Ready")

        self.refresh_library()

    # -- construction ------------------------------------------------------

    def _build_toolbar(self) -> None:
        tb = QToolBar()
        tb.setMovable(False)
        self.addToolBar(tb)

        self.btn_import = QPushButton("Import Beats")
        self.btn_import.setObjectName("Primary")
        self.btn_scan = QPushButton("Scan Folder")
        tb.addWidget(self.btn_import)
        tb.addWidget(self.btn_scan)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search title, genre, mood, key, tag…")
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(260)
        tb.addWidget(self.search)

        spacer = QWidget()
        spacer.setSizePolicy(spacer.sizePolicy().horizontalPolicy().Expanding,
                             spacer.sizePolicy().verticalPolicy().Preferred)
        tb.addWidget(spacer)

        self.btn_settings = QPushButton("Settings")
        tb.addWidget(self.btn_settings)

        self.btn_import.clicked.connect(self._import_files)
        self.btn_scan.clicked.connect(self._scan_folder)
        self.btn_settings.clicked.connect(self._open_settings)
        self.search.textChanged.connect(lambda t: self.refresh_library(t))

    def _build_body(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 6, 10, 10)
        root.setSpacing(8)

        self.split = QSplitter(Qt.Horizontal)

        self.table = QTableWidget(0, len(_COLUMNS))
        self.table.setHorizontalHeaderLabels(_COLUMNS)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, len(_COLUMNS)):
            hh.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._on_selection)
        self.split.addWidget(self.table)

        self.detail = DetailPanel()
        self.detail.saved.connect(self._on_save)
        self.detail.rename_requested.connect(self._on_rename)
        self.detail.relocate_requested.connect(self._on_relocate)
        self.split.addWidget(self.detail)

        self.split.setStretchFactor(0, 3)
        self.split.setStretchFactor(1, 2)
        root.addWidget(self.split, 1)

        self._root_layout = root
        self.setCentralWidget(central)

    def _build_player_bar(self) -> None:
        bar = QFrame()
        bar.setObjectName("Panel")
        bar.setFixedHeight(96)
        layout = QHBoxLayout(bar)

        self.btn_play = QPushButton("Play")
        self.btn_play.setObjectName("Accent")
        self.btn_play.setFixedWidth(80)
        self.btn_play.setEnabled(False)
        layout.addWidget(self.btn_play)

        self.waveform = QLabel("waveform appears here (Phase 4)")
        self.waveform.setObjectName("SubHeading")
        self.waveform.setAlignment(Qt.AlignCenter)
        self.waveform.setMinimumHeight(64)
        layout.addWidget(self.waveform, 1)

        self.seek = QSlider(Qt.Horizontal)
        self.seek.setEnabled(False)
        self.seek.setFixedWidth(160)
        layout.addWidget(self.seek)

        self.now_playing = QLabel("—")
        self.now_playing.setObjectName("AccentLime")
        self.now_playing.setFixedWidth(160)
        layout.addWidget(self.now_playing)

        self._root_layout.addWidget(bar)

    # -- data --------------------------------------------------------------

    def refresh_library(self, search: str = "") -> None:
        keep_id = self._selected_beat_id()
        beats = self.db.list_beats(search=search or None)
        self.table.blockSignals(True)
        self.table.setRowCount(len(beats))
        row_for_id = {}
        for r, b in enumerate(beats):
            missing = importer.is_missing(b)
            status = "missing" if missing else (b["analysis_status"] or "")
            values = [
                b["title"] or b["filename"],
                "" if b["bpm"] is None else f"{b['bpm']:g}",
                b["key"] or "",
                b["genre"] or "",
                b["mood"] or "",
                status,
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(str(val))
                item.setData(Qt.UserRole, b["id"])
                if missing and col == 5:
                    item.setForeground(Qt.yellow)
                self.table.setItem(r, col, item)
            row_for_id[b["id"]] = r
        self.table.blockSignals(False)
        self.statusBar().showMessage(f"{len(beats)} beat(s)")

        if keep_id in row_for_id:
            self.table.selectRow(row_for_id[keep_id])
        else:
            self.detail.clear()

    # -- selection / editing ----------------------------------------------

    def _selected_beat_id(self) -> Optional[int]:
        items = self.table.selectedItems()
        return items[0].data(Qt.UserRole) if items else None

    def _on_selection(self) -> None:
        bid = self._selected_beat_id()
        if bid is None:
            self.detail.clear()
            return
        row = self.db.get_beat(bid)
        if row is None:
            return
        self.detail.set_autocomplete(
            self.db.distinct_values("genre"),
            self.db.distinct_values("subgenre"),
            self.db.distinct_values("mood"),
            self.db.all_tag_names(),
        )
        self.detail.load_beat(row, self.db.get_tags(bid), missing=importer.is_missing(row))
        self.now_playing.setText(row["title"] or row["filename"])

    def _on_save(self, beat_id: int, fields: dict, tag_names: list) -> None:
        self.db.update_beat(beat_id, **fields)
        self.db.set_tags(beat_id, tag_names)
        self.refresh_library(self.search.text())
        self.statusBar().showMessage("Saved", 2000)

    def _on_rename(self, beat_id: int) -> None:
        row = self.db.get_beat(beat_id)
        if row is None:
            return
        pattern, ok = QInputDialog.getText(
            self, "Rename file", "Filename pattern:", text=renamer.DEFAULT_PATTERN
        )
        if not ok or not pattern.strip():
            return
        from pathlib import Path
        new_stem = renamer.build_basename(
            pattern,
            title=row["title"] or row["filename"],
            original_stem=Path(row["filename"]).stem,
            bpm=row["bpm"],
            key=row["key"],
        )
        try:
            renamer.rename_in_place(self.db, beat_id, new_stem)
        except FileExistsError:
            QMessageBox.warning(self, "Rename", "A file with that name already exists.")
            return
        except FileNotFoundError:
            QMessageBox.warning(self, "Rename", "The original file is missing.")
            return
        self.refresh_library(self.search.text())
        self.statusBar().showMessage(f"Renamed to {new_stem}", 3000)

    def _on_relocate(self, beat_id: int) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Locate the moved file", "",
            "Audio (*.mp3 *.wav *.aiff *.flac *.ogg *.m4a)"
        )
        if not path:
            return
        from pathlib import Path
        p = Path(path)
        self.db.update_beat(beat_id, file_path=str(p.resolve()), filename=p.name)
        self.refresh_library(self.search.text())
        self.statusBar().showMessage("Relocated", 2000)

    # -- import / scan / settings -----------------------------------------

    def _import_files(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Import beats", "",
            "Audio (*.mp3 *.wav *.aiff *.flac *.ogg *.m4a)"
        )
        if not paths:
            return
        added = importer.import_paths(self.db, paths)
        self.refresh_library(self.search.text())
        self.statusBar().showMessage(f"Imported {added} new beat(s)", 3000)

    def _scan_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Scan a folder for beats")
        if not folder:
            return
        added = importer.scan_folder(self.db, folder)
        self.refresh_library(self.search.text())
        self.statusBar().showMessage(f"Scanned: {added} new beat(s)", 3000)

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.db, self)
        dlg.exec()
        if dlg.added_count:
            self.refresh_library(self.search.text())

    def closeEvent(self, event):  # noqa: N802 - Qt override
        self.db.close()
        super().closeEvent(event)
