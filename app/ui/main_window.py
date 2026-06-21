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

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThreadPool
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
from app.ui.player import AudioPlayer
from app.ui.settings_dialog import SettingsDialog
from app.ui.tag_panel import TagLibraryPanel
from app.ui.widgets import WaveformWidget
from app.workers import AnalysisRunnable, WorkerSignals
from core import pipeline
from core import placement as core_placement
from core import waveform as wf
from core.models import Placement, TaggingConfig

_COLUMNS = ["Title", "BPM", "Key", "Genre", "Mood", "Status"]


class MainWindow(QMainWindow):
    def __init__(self, db_path: str = "library.db"):
        super().__init__()
        self.db = Database(db_path)
        self.setWindowTitle("Paperhand's Beat Tools")
        self.resize(1180, 720)

        # Background analysis
        self.pool = QThreadPool.globalInstance()
        self.signals = WorkerSignals()
        self.signals.beat_analyzed.connect(self._on_analyzed)
        self.signals.error.connect(self._on_analysis_error)
        self.signals.progress.connect(self._on_progress)
        self._analysis_total = 0
        self._analysis_done = 0

        # Tag placement state (Phase 5)
        self._active_tag = None
        self._placements: list = []          # list[core.models.Placement]
        self._beat_duration_sec = 0.0
        self._current_path = None

        self._build_toolbar()
        self._build_body()
        self._build_player_bar()
        self.statusBar().showMessage("Ready")

        self.refresh_library()
        self.analyze_pending()

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

        self.tag_panel = TagLibraryPanel()
        self.tag_panel.active_tag_changed.connect(self._on_active_tag)
        self.tag_panel.place_mode_changed.connect(self._on_place_mode)
        self.tag_panel.autoplace_requested.connect(self._on_autoplace)
        self.tag_panel.clear_requested.connect(self._on_clear_tags)
        self.tag_panel.export_requested.connect(self._on_export)
        # The panel selects its first tag during construction (before we were
        # connected), so capture that initial selection now.
        self._active_tag = self.tag_panel.active_tag()

        right = QSplitter(Qt.Vertical)
        right.addWidget(self.detail)
        right.addWidget(self.tag_panel)
        right.setStretchFactor(0, 3)
        right.setStretchFactor(1, 2)
        self.split.addWidget(right)

        self.split.setStretchFactor(0, 3)
        self.split.setStretchFactor(1, 2)
        root.addWidget(self.split, 1)

        self._root_layout = root
        self.setCentralWidget(central)

    def _build_player_bar(self) -> None:
        bar = QFrame()
        bar.setObjectName("Panel")
        bar.setFixedHeight(108)
        layout = QHBoxLayout(bar)

        self.btn_play = QPushButton("Play")
        self.btn_play.setObjectName("Accent")
        self.btn_play.setFixedWidth(80)
        self.btn_play.setEnabled(False)
        layout.addWidget(self.btn_play)

        self.now_playing = QLabel("—")
        self.now_playing.setObjectName("AccentLime")
        self.now_playing.setFixedWidth(150)
        self.now_playing.setWordWrap(True)
        layout.addWidget(self.now_playing)

        self.waveform = WaveformWidget()
        layout.addWidget(self.waveform, 1)

        self.time_label = QLabel("0:00 / 0:00")
        self.time_label.setObjectName("SubHeading")
        self.time_label.setFixedWidth(90)
        self.time_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.time_label)

        self.seek = QSlider(Qt.Horizontal)
        self.seek.setEnabled(False)
        self.seek.setFixedWidth(150)
        layout.addWidget(self.seek)

        self._root_layout.addWidget(bar)

        # Player + transport wiring
        self.player = AudioPlayer()
        self._duration_ms = 0
        self.btn_play.clicked.connect(self.player.toggle)
        self.player.position_changed.connect(self._on_position)
        self.player.duration_changed.connect(self._on_duration)
        self.player.playing_changed.connect(
            lambda playing: self.btn_play.setText("Pause" if playing else "Play")
        )
        self.seek.sliderMoved.connect(self.player.set_position)
        self.waveform.seek_requested.connect(self._on_waveform_click)

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

    # -- background analysis ----------------------------------------------

    def _peaks_dir(self) -> Path:
        base = Path(self.db.path).resolve().parent if self.db.path != ":memory:" else Path.cwd()
        d = base / ".peaks"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def analyze_pending(self) -> None:
        """Queue background analysis for every un-analyzed, present beat."""
        pending = [
            b for b in self.db.list_beats()
            if (b["analysis_status"] in (None, "", "pending")) and not importer.is_missing(b)
        ]
        if not pending:
            return
        peaks_dir = self._peaks_dir()
        self._analysis_total += len(pending)
        for b in pending:
            task = AnalysisRunnable(
                b["id"], b["file_path"], str(peaks_dir / f"{b['id']}.npy"), self.signals
            )
            self.pool.start(task)
        self._update_progress_message()

    def _on_analyzed(self, beat_id: int, result: dict) -> None:
        self.db.update_beat(beat_id, **result)
        self._refresh_row_or_table(beat_id)

    def _on_analysis_error(self, beat_id: int, message: str) -> None:
        self.db.update_beat(beat_id, analysis_status="error")
        self._refresh_row_or_table(beat_id)

    def _on_progress(self) -> None:
        self._analysis_done += 1
        self._update_progress_message()
        if self._analysis_done >= self._analysis_total:
            self._analysis_total = self._analysis_done = 0
            self.statusBar().showMessage("Analysis complete", 3000)

    def _update_progress_message(self) -> None:
        if self._analysis_total:
            self.statusBar().showMessage(
                f"Analyzing {self._analysis_done}/{self._analysis_total}…"
            )

    def _refresh_row_or_table(self, beat_id: int) -> None:
        # Simple + correct: rebuild the table (selection preserved by id).
        self.refresh_library(self.search.text())
        if beat_id == self._selected_beat_id():
            self._on_selection()  # refresh detail panel's analysis line

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
        missing = importer.is_missing(row)
        self.detail.load_beat(row, self.db.get_tags(bid), missing=missing)
        self.now_playing.setText(row["title"] or row["filename"])
        self._load_into_player(row, missing)

    # -- playback ----------------------------------------------------------

    def _load_into_player(self, row, missing: bool) -> None:
        # New beat -> reset any in-progress tag placements.
        self._current_path = row["file_path"]
        self._beat_duration_sec = row["duration_sec"] or 0.0
        self._placements = []
        self._refresh_markers()

        # Waveform peaks (if analyzed)
        self.waveform.set_position(0.0)
        path = row["waveform_path"]
        if path and Path(path).exists():
            try:
                self.waveform.set_peaks(wf.load_peaks(path))
            except Exception:  # noqa: BLE001 - bad cache shouldn't break selection
                self.waveform.clear()
        else:
            self.waveform.clear()

        # Audio source
        playable = (not missing) and self.player.available
        if not missing:
            self.player.load(row["file_path"])
        else:
            self.player.stop()
        self.btn_play.setEnabled(playable)
        self.seek.setEnabled(playable)
        self.btn_play.setText("Play")

    def _on_duration(self, ms: int) -> None:
        self._duration_ms = ms
        self.seek.setRange(0, ms)
        self._update_time(0)

    def _on_position(self, ms: int) -> None:
        if not self.seek.isSliderDown():
            self.seek.blockSignals(True)
            self.seek.setValue(ms)
            self.seek.blockSignals(False)
        frac = (ms / self._duration_ms) if self._duration_ms else 0.0
        self.waveform.set_position(frac)
        self._update_time(ms)

    def _seek_fraction(self, fraction: float) -> None:
        if self._duration_ms:
            self.player.set_position(int(fraction * self._duration_ms))

    def _update_time(self, ms: int) -> None:
        self.time_label.setText(f"{self._fmt(ms)} / {self._fmt(self._duration_ms)}")

    @staticmethod
    def _fmt(ms: int) -> str:
        s = int(ms // 1000)
        return f"{s // 60}:{s % 60:02d}"

    # -- tagging (Phase 5) -------------------------------------------------

    def _on_active_tag(self, path: str) -> None:
        self._active_tag = path or None

    def _on_place_mode(self, on: bool) -> None:
        hint = ("Click the waveform to place the selected tag (click a marker to "
                "remove it)." if on else "Ready")
        self.statusBar().showMessage(hint)

    def _on_waveform_click(self, fraction: float) -> None:
        """In place-mode, drop/remove a tag; otherwise seek."""
        if not (self.tag_panel.place_mode() and self._active_tag
                and self._beat_duration_sec > 0):
            self._seek_fraction(fraction)
            return

        pos = fraction * self._beat_duration_sec
        threshold = max(0.5, 0.01 * self._beat_duration_sec)  # seconds
        for pl in list(self._placements):
            if pl.tag_path == self._active_tag and abs(pl.position_sec - pos) <= threshold:
                self._placements.remove(pl)  # toggle off
                self._refresh_markers()
                return
        self._placements.append(Placement(round(pos, 3), self._active_tag))
        self._placements.sort(key=lambda p: p.position_sec)
        self._refresh_markers()

    def _refresh_markers(self) -> None:
        dur = self._beat_duration_sec or 0.0
        fractions = [p.position_sec / dur for p in self._placements] if dur else []
        self.waveform.set_markers(fractions)
        self.tag_panel.set_placement_count(len(self._placements))

    def _on_autoplace(self) -> None:
        if self._beat_duration_sec <= 0:
            self.statusBar().showMessage("Analyze the beat first (no duration yet).", 3000)
            return
        tags = self.tag_panel.all_tag_paths()
        if not tags:
            self.statusBar().showMessage("No tags in the tag library.", 3000)
            return
        self._placements = core_placement.compute_placements(
            duration_sec=self._beat_duration_sec, tag_paths=tags, interval_sec=40.0,
        )
        self._refresh_markers()

    def _on_clear_tags(self) -> None:
        self._placements = []
        self._refresh_markers()

    def _on_export(self) -> None:
        if not self._current_path or not self._placements:
            self.statusBar().showMessage("Place at least one tag before exporting.", 3000)
            return
        bid = self._selected_beat_id()
        row = self.db.get_beat(bid) if bid is not None else None
        if row is None:
            return

        out_dir = Path(self.db.path).resolve().parent / "output" \
            if self.db.path != ":memory:" else Path.cwd() / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        from core.naming import build_output_stem
        out_stem = build_output_stem(Path(row["filename"]).stem, row["bpm"], row["key"])
        out_path = out_dir / f"{out_stem}.mp3"

        self.statusBar().showMessage("Exporting…")
        try:
            pipeline.export_with_placements(
                self._current_path, self._placements, str(out_path), TaggingConfig()
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Export failed", str(exc))
            self.statusBar().showMessage("Export failed", 3000)
            return
        self.statusBar().showMessage(f"Exported → {out_path.name}", 5000)

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
        self.analyze_pending()

    def _scan_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Scan a folder for beats")
        if not folder:
            return
        added = importer.scan_folder(self.db, folder)
        self.refresh_library(self.search.text())
        self.statusBar().showMessage(f"Scanned: {added} new beat(s)", 3000)
        self.analyze_pending()

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.db, self)
        dlg.exec()
        if dlg.added_count:
            self.refresh_library(self.search.text())
            self.analyze_pending()

    def closeEvent(self, event):  # noqa: N802 - Qt override
        self.db.close()
        super().closeEvent(event)
