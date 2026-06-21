"""The main application window: a three-pane shell.

    +------------------------------------------------------+
    | Toolbar:  [Import Beats] [Scan Folder]      [Settings]|
    +---------------------------+--------------------------+
    | Library table             | Detail / tag panel       |
    | (title, bpm, key, genre,  | (edit title/genre/mood/  |
    |  mood, status)            |  tags/notes)             |
    +---------------------------+--------------------------+
    | Player bar: waveform + transport (play/pause/seek)   |
    +------------------------------------------------------+

Phase 1 wires the layout, the DB, and library refresh. Editing, analysis, the
real waveform, and tagging arrive in later phases.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
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

        spacer = QWidget()
        spacer.setSizePolicy(spacer.sizePolicy().horizontalPolicy().Expanding,
                             spacer.sizePolicy().verticalPolicy().Preferred)
        tb.addWidget(spacer)

        self.btn_settings = QPushButton("Settings")
        tb.addWidget(self.btn_settings)

    def _build_body(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 6, 10, 10)
        root.setSpacing(8)

        self.split = QSplitter(Qt.Horizontal)

        # Library table
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
        self.split.addWidget(self.table)

        # Detail panel (placeholder content; populated in Phase 2)
        self.detail = QFrame()
        self.detail.setObjectName("Panel")
        dl = QVBoxLayout(self.detail)
        title = QLabel("Beat details")
        title.setObjectName("Heading")
        hint = QLabel("Select a beat to edit its tags, genre, mood, and notes.")
        hint.setObjectName("SubHeading")
        hint.setWordWrap(True)
        dl.addWidget(title)
        dl.addWidget(hint)
        dl.addStretch(1)
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

        self.waveform = QLabel("waveform appears here")
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
        """Reload the table from the database."""
        beats = self.db.list_beats(search=search or None)
        self.table.setRowCount(len(beats))
        for r, b in enumerate(beats):
            values = [
                b["title"] or b["filename"],
                "" if b["bpm"] is None else f"{b['bpm']:g}",
                b["key"] or "",
                b["genre"] or "",
                b["mood"] or "",
                b["analysis_status"] or "",
            ]
            for col, val in enumerate(values):
                item = QTableWidgetItem(str(val))
                item.setData(Qt.UserRole, b["id"])
                self.table.setItem(r, col, item)
        self.statusBar().showMessage(f"{len(beats)} beat(s)")

    def closeEvent(self, event):  # noqa: N802 - Qt override
        self.db.close()
        super().closeEvent(event)
