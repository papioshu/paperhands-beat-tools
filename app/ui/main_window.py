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

import json
import os
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
    QScrollArea,
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
from app.ui.autoplace_dialog import AutoPlaceDialog
from app.ui.batch_rename_dialog import BatchRenameDialog
from app.ui.detail_panel import DetailPanel
from app.ui.duplicates_dialog import DuplicatesDialog
from app.ui.progress_panel import ProgressPanel
from app.ui.player import AudioPlayer
from app.ui.settings_dialog import SettingsDialog
from app.ui.tag_panel import TagLibraryPanel
from app.ui.widgets import WaveformWidget
from app.workers import (
    AnalysisRunnable,
    ExportRunnable,
    ExportSignals,
    FunctionExportRunnable,
    UpdateChecker,
    WorkerSignals,
)
from app import config, updater
from app.version import __version__
from core import artwork as core_artwork
from core import exports as core_exports
from core import fingerprint as core_fingerprint
from core import metadata as core_metadata
from core import naming as core_naming
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
        self.signals.started.connect(self._on_analysis_started)
        self.signals.beat_analyzed.connect(self._on_analyzed)
        self.signals.error.connect(self._on_analysis_error)
        self.signals.progress.connect(self._on_progress)
        self._analysis_total = 0
        self._analysis_done = 0

        # Export worker
        self.export_signals = ExportSignals()
        self.export_signals.done.connect(self._on_export_done)
        self.export_signals.error.connect(self._on_export_error)
        self._exporting = False

        # Tag placement state (Phase 5)
        self._active_tag = None
        self._placements: list = []          # list[core.models.Placement]
        self._beat_duration_sec = 0.0
        self._current_path = None
        self._current_beat_id = None
        self._drop_sec = None
        self._hook_start = None
        # Live tag audition during playback
        self._fired_tags: set = set()
        self._last_pos_sec = 0.0
        self._live_duck_db = TaggingConfig().duck_db

        self._build_toolbar()
        self._build_body()
        self._build_player_bar()
        self.statusBar().showMessage("Ready")

        # Update checking (GitHub releases)
        self.update_checker = UpdateChecker()
        self.update_checker.checked.connect(self._on_update_checked)
        self._manual_update_check = False
        self.install_signals = ExportSignals()
        self.install_signals.done.connect(self._on_installer_ready)
        self.install_signals.error.connect(self._on_installer_error)

        self.refresh_library()
        self._startup_scan()          # auto-pick-up new files from watched folders
        self.analyze_pending()
        self._update_duplicate_indicator()

        repo = config.update_repo()
        # Silent startup check when configured; skipped under the offscreen test
        # platform so the suite never makes network calls.
        if repo and os.environ.get("QT_QPA_PLATFORM") != "offscreen":
            self.update_checker.check_async(repo, __version__)

    # -- construction ------------------------------------------------------

    def _build_toolbar(self) -> None:
        tb = QToolBar()
        tb.setMovable(False)
        self.addToolBar(tb)

        self.btn_import = QPushButton("Import Beats")
        self.btn_import.setObjectName("Primary")
        self.btn_scan = QPushButton("Scan Folder")
        self.btn_batch_rename = QPushButton("Batch Rename")
        self.btn_duplicates = QPushButton("Duplicates")
        tb.addWidget(self.btn_import)
        tb.addWidget(self.btn_scan)
        tb.addWidget(self.btn_batch_rename)
        tb.addWidget(self.btn_duplicates)

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
        self.btn_batch_rename.clicked.connect(self._batch_rename)
        self.btn_duplicates.clicked.connect(self._find_duplicates)
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
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Stretch)
        for i in range(1, len(_COLUMNS)):
            hh.setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._on_selection)
        self.table.itemDoubleClicked.connect(self._on_row_double_clicked)
        self.split.addWidget(self.table)

        self.detail = DetailPanel()
        self.detail.saved.connect(self._on_save)
        self.detail.rename_requested.connect(self._on_rename)
        self.detail.relocate_requested.connect(self._on_relocate)
        self.detail.set_artwork_requested.connect(self._set_artwork)
        self.detail.generate_artwork_requested.connect(self._generate_artwork)

        self.tag_panel = TagLibraryPanel(self.db)
        self.tag_panel.active_tag_changed.connect(self._on_active_tag)
        self.tag_panel.preview_tag_requested.connect(self._preview_active_tag)
        self.tag_panel.place_mode_changed.connect(self._on_place_mode)
        self.tag_panel.crop_mode_changed.connect(self._on_crop_mode)
        self.tag_panel.autoplace_requested.connect(self._on_autoplace)
        self.tag_panel.tag_at_drop_requested.connect(self._tag_at_drop)
        self.tag_panel.tag_at_hook_requested.connect(self._tag_at_hook)
        self.tag_panel.clear_requested.connect(self._on_clear_tags)
        self.tag_panel.export_tagged_preview_requested.connect(self._export_tagged_preview)
        self.tag_panel.export_clean_master_requested.connect(self._export_clean_master)
        self.tag_panel.export_tag_stem_requested.connect(self._export_tag_stem)
        self.tag_panel.export_buyer_package_requested.connect(self._export_buyer_package)
        # The panel selects its first tag during construction (before we were
        # connected), so capture that initial selection now.
        self._active_tag = self.tag_panel.active_tag()

        right = QSplitter(Qt.Vertical)
        right.addWidget(self.detail)
        right.addWidget(self.tag_panel)
        right.setStretchFactor(0, 3)
        right.setStretchFactor(1, 2)

        # Scroll the (tall) right pane so it can shrink — otherwise its large
        # minimum height overflows the window and clips the player bar / log.
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.NoFrame)
        right_scroll.setMinimumWidth(360)
        right_scroll.setWidget(right)
        self.split.addWidget(right_scroll)

        self.split.setStretchFactor(0, 3)
        self.split.setStretchFactor(1, 2)
        root.addWidget(self.split, 1)

        self.progress = ProgressPanel()
        root.addWidget(self.progress)

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
        self.player.tag_finished.connect(self.player.unduck)
        self.seek.sliderMoved.connect(self.player.set_position)
        self.waveform.seek_requested.connect(self._seek_fraction)
        self.waveform.tag_placed.connect(self._place_tag_at_fraction)
        self.waveform.marker_removed.connect(self._remove_marker)
        self.waveform.marker_moved.connect(self._move_marker)
        self.waveform.crop_changed.connect(self._on_crop_changed)

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
        first_batch = self._analysis_total == 0
        self._analysis_total += len(pending)
        if first_batch:
            self.progress.begin("Analyzing", self._analysis_total)
        for b in pending:
            task = AnalysisRunnable(
                b["id"], b["file_path"], str(peaks_dir / f"{b['id']}.npy"), self.signals
            )
            self.pool.start(task)
        self._update_progress_message()

    def _startup_scan(self) -> None:
        """Re-scan remembered folders on launch; dedupe skips already-cataloged."""
        folders = config.watched_folders()
        if not folders:
            return
        total = 0
        for folder in folders:
            try:
                total += importer.scan_folder(self.db, folder)
            except NotADirectoryError:
                continue
        if total:
            self.refresh_library(self.search.text())
            self.statusBar().showMessage(
                f"Startup scan: {total} new beat(s) added (existing skipped)", 4000)

    def _update_duplicate_indicator(self) -> None:
        """Light up the Duplicates button (orange + count) when dupes exist."""
        items = [(b["id"], b["fingerprint"]) for b in self.db.list_beats()
                 if b["fingerprint"]]
        groups = core_fingerprint.group_duplicates(items)
        if groups:
            self.btn_duplicates.setText(f"Duplicates ({len(groups)})")
            self.btn_duplicates.setStyleSheet(
                "background-color: #FFB454; color: #1A1A1A; font-weight: 600;")
        else:
            self.btn_duplicates.setText("Duplicates")
            self.btn_duplicates.setStyleSheet("")

    def _on_analysis_started(self, beat_id: int) -> None:
        row = self.db.get_beat(beat_id)
        name = row["filename"] if row else str(beat_id)
        n = min(self._analysis_done + 1, self._analysis_total)
        self.progress.update(self._analysis_done, self._analysis_total,
                             f"Analyzing {n} of {self._analysis_total}: {name}")

    def _on_analyzed(self, beat_id: int, result: dict) -> None:
        self.db.update_beat(beat_id, **result)
        row = self.db.get_beat(beat_id)
        extra = []
        if result.get("bpm") is not None:
            extra.append(f"{result['bpm']:g} BPM")
        if result.get("key"):
            extra.append(result["key"])
        tail = f"  ({', '.join(extra)})" if extra else ""
        self.progress.log_line(f"✓ {row['filename'] if row else beat_id}{tail}")
        self._refresh_row_or_table(beat_id)

    def _on_analysis_error(self, beat_id: int, message: str) -> None:
        self.db.update_beat(beat_id, analysis_status="error")
        row = self.db.get_beat(beat_id)
        self.progress.log_line(f"✗ {row['filename'] if row else beat_id}: {message}")
        self._refresh_row_or_table(beat_id)

    def _on_progress(self) -> None:
        self._analysis_done += 1
        self._update_progress_message()
        if self._analysis_done >= self._analysis_total:
            self._analysis_total = self._analysis_done = 0
            self.progress.end("Analysis complete")
            self.statusBar().showMessage("Analysis complete", 3000)
            self._update_duplicate_indicator()   # fingerprints now available

    def _update_progress_message(self) -> None:
        if self._analysis_total:
            self.progress.update(self._analysis_done, self._analysis_total)
            self.statusBar().showMessage(
                f"Analyzing {self._analysis_done}/{self._analysis_total}…"
            )

    def _refresh_row_or_table(self, beat_id: int) -> None:
        # Update only the affected row in place — rebuilding the whole table on
        # every per-file analysis completion is the main source of slowness.
        row = self.db.get_beat(beat_id)
        if row is not None:
            missing = importer.is_missing(row)
            status = "missing" if missing else (row["analysis_status"] or "")
            values = [
                row["title"] or row["filename"],
                "" if row["bpm"] is None else f"{row['bpm']:g}",
                row["key"] or "", row["genre"] or "", row["mood"] or "", status,
            ]
            for r in range(self.table.rowCount()):
                head = self.table.item(r, 0)
                if head and head.data(Qt.UserRole) == beat_id:
                    for col, val in enumerate(values):
                        cell = self.table.item(r, col)
                        if cell is not None:
                            cell.setText(str(val))
                    break
        if beat_id == self._selected_beat_id():
            self._on_selection()  # refresh detail panel's analysis line

    # -- selection / editing ----------------------------------------------

    def _selected_beat_id(self) -> Optional[int]:
        items = self.table.selectedItems()
        return items[0].data(Qt.UserRole) if items else None

    def _selected_beat_ids(self) -> list:
        ids = []
        for item in self.table.selectedItems():
            bid = item.data(Qt.UserRole)
            if bid not in ids:
                ids.append(bid)
        return ids

    def _batch_rename(self) -> None:
        ids = self._selected_beat_ids()
        if not ids:  # nothing selected -> offer the whole filtered view
            ids = [b["id"] for b in self.db.list_beats(search=self.search.text() or None)]
        rows = [self.db.get_beat(i) for i in ids]
        rows = [r for r in rows if r is not None and not importer.is_missing(r)]
        if not rows:
            self.statusBar().showMessage(
                "No present beats selected to rename.", 3000)
            return
        dlg = BatchRenameDialog(self.db, rows, self)
        dlg.exec()
        if dlg.applied:
            self.refresh_library(self.search.text())
            self.statusBar().showMessage(f"Renamed {dlg.applied} file(s)", 4000)

    def _find_duplicates(self) -> None:
        items = [(b["id"], b["fingerprint"]) for b in self.db.list_beats()
                 if b["fingerprint"]]
        groups_ids = core_fingerprint.group_duplicates(items)
        if not groups_ids:
            self.statusBar().showMessage(
                "No duplicates found (beats must be analyzed first).", 4000)
            return
        groups = [[self.db.get_beat(i) for i in g] for g in groups_ids]
        dlg = DuplicatesDialog(self.db, groups, self)
        dlg.exec()
        if dlg.removed:
            self.refresh_library(self.search.text())
            self._update_duplicate_indicator()
            self.statusBar().showMessage(
                f"Removed {dlg.removed} duplicate(s) from library", 4000)

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
        # New beat -> load its saved tag placements (persisted per beat).
        self._current_path = row["file_path"]
        self._current_beat_id = row["id"]
        self._beat_duration_sec = row["duration_sec"] or 0.0
        self._placements = self._load_placements(row)
        self._fired_tags = set()
        self._last_pos_sec = 0.0
        self.player.unduck()
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

        # Structure section dividers + detected drop/hook (if analyzed)
        dur = self._beat_duration_sec or 0.0
        sections = self._load_json_list(row["structure"]) if dur else []
        self.waveform.set_sections([t / dur for t in sections] if dur else [])

        self._drop_sec = row["drop_sec"]
        self._hook_start = row["hook_start"]
        self.waveform.set_drop((self._drop_sec / dur) if (self._drop_sec and dur) else None)
        hs, he = row["hook_start"], row["hook_end"]
        self.waveform.set_hook(
            (hs / dur, he / dur) if (hs is not None and he is not None and dur) else None)

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
        self._monitor_live_tags(ms / 1000.0)

    def _monitor_live_tags(self, pos_sec: float) -> None:
        """Fire each placed tag (ducking the beat) as the playhead reaches it."""
        delta = pos_sec - self._last_pos_sec
        # Seek / loop / big jump: re-sync without firing past tags.
        if delta < -0.2 or delta > 1.0:
            self._fired_tags = {i for i, p in enumerate(self._placements)
                               if p.position_sec <= pos_sec}
            self._last_pos_sec = pos_sec
            return
        for i, p in enumerate(self._placements):
            if i not in self._fired_tags and self._last_pos_sec < p.position_sec <= pos_sec:
                self._fired_tags.add(i)
                self.player.duck(self._live_duck_db)
                self.player.play_tag(p.tag_path)
        self._last_pos_sec = pos_sec

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

    def _on_row_double_clicked(self, _item) -> None:
        # Double-clicking a song starts playback (selection already loaded it).
        if self.btn_play.isEnabled():
            self.player.play()

    def _preview_active_tag(self) -> None:
        if self._active_tag:
            self.player.play_tag(self._active_tag)
        else:
            self.statusBar().showMessage("Select a tag to preview.", 2000)

    def _on_place_mode(self, on: bool) -> None:
        self.waveform.set_mode("place" if on else "seek")
        hint = ("Click the waveform to place the tag · drag a marker to move it · "
                "click a marker to remove it." if on else "Ready")
        self.statusBar().showMessage(hint)

    def _on_crop_mode(self, on: bool) -> None:
        if on:
            self.waveform.set_mode("crop")
            self.statusBar().showMessage(
                "Drag across the waveform to select the preview region.")
        else:
            self.waveform.clear_crop()
            self.waveform.set_mode("place" if self.tag_panel.place_mode() else "seek")
            self.statusBar().showMessage("Ready")

    def _place_tag_at_fraction(self, fraction: float) -> None:
        if not (self._active_tag and self._beat_duration_sec > 0):
            self.statusBar().showMessage("Select a tag in the tag library first.", 3000)
            return
        pos = round(fraction * self._beat_duration_sec, 3)
        self._placements.append(Placement(pos, self._active_tag))
        self._placements.sort(key=lambda p: p.position_sec)
        self._refresh_markers(save=True)
        self.player.play_tag(self._active_tag)   # instant audition on placement

    def _remove_marker(self, index: int) -> None:
        if 0 <= index < len(self._placements):
            del self._placements[index]
            self._refresh_markers(save=True)

    def _move_marker(self, index: int, fraction: float) -> None:
        if 0 <= index < len(self._placements) and self._beat_duration_sec > 0:
            pos = round(fraction * self._beat_duration_sec, 3)
            self._placements[index] = Placement(pos, self._placements[index].tag_path)
            self._placements.sort(key=lambda p: p.position_sec)
            self._refresh_markers(save=True)

    # -- placement persistence --------------------------------------------

    def _load_placements(self, row) -> list:
        raw = row["placements"]
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return []
        return [Placement(float(d["pos"]), d["tag"]) for d in data if "pos" in d and "tag" in d]

    @staticmethod
    def _load_json_list(raw) -> list:
        if not raw:
            return []
        try:
            data = json.loads(raw)
            return data if isinstance(data, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def _save_placements(self) -> None:
        if self._current_beat_id is None:
            return
        data = json.dumps([{"pos": p.position_sec, "tag": p.tag_path}
                           for p in self._placements])
        self.db.update_beat(self._current_beat_id, placements=data)

    def _on_crop_changed(self, start: float, end: float) -> None:
        if self._beat_duration_sec > 0:
            length = (end - start) * self._beat_duration_sec
            self.statusBar().showMessage(f"Preview region: {self._fmt(int(length*1000))}")

    def _refresh_markers(self, save: bool = False) -> None:
        dur = self._beat_duration_sec or 0.0
        fractions = [p.position_sec / dur for p in self._placements] if dur else []
        self.waveform.set_markers(fractions)
        self.tag_panel.set_placement_count(len(self._placements))
        if save:
            self._save_placements()

    def _beat_context(self, row):
        """(structure, drop, hook) for a beat row, for auto-placement."""
        structure = self._load_json_list(row["structure"]) if row else []
        drop = row["drop_sec"] if row else None
        hook = ((row["hook_start"], row["hook_end"])
                if row and row["hook_start"] is not None else None)
        return structure, drop, hook

    def _on_autoplace(self) -> None:
        tags = self.tag_panel.all_tag_paths()
        if not tags:
            self.statusBar().showMessage("No enabled tags in the library.", 3000)
            return
        selected = self._selected_beat_ids()
        if len(selected) <= 1 and self._beat_duration_sec <= 0:
            self.statusBar().showMessage("Analyze the beat first (no duration yet).", 3000)
            return

        row = self.db.get_beat(self._current_beat_id) if self._current_beat_id else None
        structure, drop, hook = self._beat_context(row)
        dlg = AutoPlaceDialog(tags, self._beat_duration_sec, structure, drop, hook,
                              len(selected), self)
        if not dlg.exec():
            return

        if len(selected) > 1:
            self._batch_autoplace(dlg, selected)
        else:
            self._placements = dlg.compute_for(
                self._beat_duration_sec, structure, drop, hook)
            self._refresh_markers(save=True)

    def _batch_autoplace(self, dlg, beat_ids: list) -> None:
        self.progress.begin("Auto-placing", len(beat_ids))
        done = applied = 0
        for bid in beat_ids:
            row = self.db.get_beat(bid)
            done += 1
            if row is None or not row["duration_sec"]:
                self.progress.log_line(
                    f"✗ {row['filename'] if row else bid}: not analyzed")
            else:
                structure, drop, hook = self._beat_context(row)
                placements = dlg.compute_for(row["duration_sec"], structure, drop, hook)
                self.db.update_beat(bid, placements=json.dumps(
                    [{"pos": p.position_sec, "tag": p.tag_path} for p in placements]))
                applied += 1
                self.progress.log_line(f"✓ {row['filename']}: {len(placements)} tags")
            self.progress.update(done, len(beat_ids),
                                 f"Auto-placing {done} of {len(beat_ids)}")
        self.progress.end(f"Auto-placed {applied} beat(s)")
        self._on_selection()   # reload the current beat's (possibly updated) markers

    def _tag_at_drop(self) -> None:
        if self._drop_sec and self._beat_duration_sec > 0:
            self._place_tag_at_fraction(self._drop_sec / self._beat_duration_sec)
        else:
            self.statusBar().showMessage("No drop detected for this beat.", 3000)

    def _tag_at_hook(self) -> None:
        if self._hook_start is not None and self._beat_duration_sec > 0:
            self._place_tag_at_fraction(self._hook_start / self._beat_duration_sec)
        else:
            self.statusBar().showMessage("No hook detected for this beat.", 3000)

    def _on_clear_tags(self) -> None:
        self._placements = []
        self._refresh_markers(save=True)

    # -- non-destructive export workflow ----------------------------------
    #
    # The cataloged file is the clean master and is never modified. Previews are
    # rendered from clean source + tag layer; the tag stem is silence + tags. The
    # buyer package ships the clean master + manifest, never a de-tagged file.

    def _export_base(self) -> Path:
        base = Path(self.db.path).resolve().parent if self.db.path != ":memory:" else Path.cwd()
        return base

    def _export_subdir(self, name: str) -> Path:
        d = self._export_base() / name
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _beat_name(self, row) -> str:
        return core_naming.build_output_stem(
            Path(row["filename"]).stem, row["bpm"], row["key"], suffix="")

    def _export_row(self):
        """Validate selection/readiness; return the beat row or None (with message)."""
        if self._exporting:
            return None
        if not self._current_path:
            self.statusBar().showMessage("Select a beat first.", 3000)
            return None
        row = self.db.get_beat(self._current_beat_id) if self._current_beat_id else None
        if row is None:
            return None
        if importer.is_missing(row):
            self.statusBar().showMessage("The clean master is missing — relocate it.", 3000)
            return None
        return row

    def _update_manifest(self, row, **paths) -> None:
        base = self._export_base()
        manifest = self._export_subdir("metadata") / f"{self._beat_name(row)}.json"
        rel = {k: os.path.relpath(v, base).replace("\\", "/")
               for k, v in paths.items() if v}
        core_exports.update_manifest(str(manifest), {
            "beat_name": self._beat_name(row),
            "tag_times": sorted(round(p.position_sec, 3) for p in self._placements),
            "bpm": row["bpm"],
            "key": row["key"],
            **rel,
        })

    def _start_export(self, fn, label: str) -> None:
        self._set_exporting(True)
        self.progress.begin(f"Exporting {label}", 1)
        self.statusBar().showMessage(f"Exporting {label}…")
        self.pool.start(FunctionExportRunnable(fn, self.export_signals))

    def _export_tagged_preview(self) -> None:
        row = self._export_row()
        if row is None:
            return
        if not self._placements:
            self.statusBar().showMessage("Place at least one tag first.", 3000)
            return
        crop = self.waveform.crop_seconds(self._beat_duration_sec)
        out_path = self._export_subdir("previews") / f"{self._beat_name(row)}_TAGGED.mp3"
        tags = core_metadata.build_id3_tags(
            config.producer(), title=row["title"] or Path(row["filename"]).stem,
            genre=row["genre"], bpm=row["bpm"], key=row["key"], mood=row["mood"],
            tags=self.db.get_tags(row["id"]),
        )
        cfg = TaggingConfig(producer=config.producer())
        placements = list(self._placements)
        src = self._current_path
        art = row["artwork_path"]
        cover = str(art) if art and Path(art).exists() else None

        def work():
            pipeline.export_with_placements(
                src, placements, str(out_path), cfg, crop=crop, tags=tags, cover=cover)
            return str(out_path)

        self._update_manifest(row, tagged_preview=str(out_path))
        self._start_export(work, "tagged preview")

    def _master_path(self, row) -> Path:
        to_wav = config.convert_master_to_wav()
        ext = ".wav" if to_wav else (Path(row["filename"]).suffix or ".wav")
        return self._export_subdir("masters") / f"{self._beat_name(row)}{ext}"

    def _export_clean_master(self) -> None:
        row = self._export_row()
        if row is None:
            return
        out_path = self._master_path(row)
        src = self._current_path
        to_wav = config.convert_master_to_wav()
        self._update_manifest(row, clean_master=str(out_path))
        self._start_export(
            lambda: core_exports.export_clean_master(src, str(out_path), to_wav=to_wav),
            "clean master")

    def _export_tag_stem(self) -> None:
        row = self._export_row()
        if row is None:
            return
        if not self._placements:
            self.statusBar().showMessage("Place at least one tag first.", 3000)
            return
        out_path = self._export_subdir("tag_stems") / f"{self._beat_name(row)}_TAGONLY.wav"
        placements = list(self._placements)
        src = self._current_path
        self._update_manifest(row, tag_stem=str(out_path))
        self._start_export(
            lambda: core_exports.export_tag_stem(src, placements, str(out_path)),
            "tag stem")

    def _export_buyer_package(self) -> None:
        row = self._export_row()
        if row is None:
            return
        beat_name = self._beat_name(row)
        master_path = self._master_path(row)
        manifest_path = self._export_subdir("metadata") / f"{beat_name}.json"
        zip_path = self._export_subdir("packages") / f"{beat_name}.zip"
        src = self._current_path
        to_wav = config.convert_master_to_wav()
        # Ensure the clean master + manifest exist before zipping.
        self._update_manifest(row, clean_master=str(master_path))

        def work():
            core_exports.export_clean_master(src, str(master_path), to_wav=to_wav)
            return core_exports.build_buyer_package(
                str(master_path), str(manifest_path), str(zip_path))

        self._start_export(work, "buyer package")

    def _set_exporting(self, on: bool) -> None:
        self._exporting = on
        self.tag_panel.set_export_enabled(not on)

    def _on_export_done(self, out_path: str) -> None:
        self._set_exporting(False)
        self.progress.update(1, 1)
        self.progress.log_line(f"✓ Exported → {Path(out_path).name}")
        self.progress.end("Export complete", folder=str(Path(out_path).parent))
        self.statusBar().showMessage(f"Exported → {Path(out_path).name}", 5000)

    def _on_export_error(self, message: str) -> None:
        self._set_exporting(False)
        self.progress.log_line(f"✗ Export failed: {message}")
        self.progress.end("Export failed")
        QMessageBox.warning(self, "Export failed", message)
        self.statusBar().showMessage("Export failed", 3000)

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

    def _set_artwork(self, beat_id: int) -> None:
        row = self.db.get_beat(beat_id)
        if row is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose artwork image (your own)", "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)")
        if not path:
            return
        ext = Path(path).suffix or ".png"
        dst = self._export_subdir("artwork") / f"{self._beat_name(row)}{ext}"
        try:
            core_artwork.import_artwork(path, str(dst))
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Artwork", str(exc))
            return
        self.db.update_beat(beat_id, artwork_path=str(dst))
        if beat_id == self._selected_beat_id():
            self.detail.set_artwork_thumb(str(dst))
        self.statusBar().showMessage("Artwork set", 2000)

    def _generate_artwork(self, beat_id: int) -> None:
        row = self.db.get_beat(beat_id)
        if row is None:
            return
        dst = self._export_subdir("artwork") / f"{self._beat_name(row)}.png"
        try:
            core_artwork.generate_artwork(
                str(dst), title=row["title"] or Path(row["filename"]).stem,
                bpm=row["bpm"], key=row["key"], mood=row["mood"])
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Artwork", str(exc))
            return
        self.db.update_beat(beat_id, artwork_path=str(dst))
        if beat_id == self._selected_beat_id():
            self.detail.set_artwork_thumb(str(dst))
        self.statusBar().showMessage("Artwork generated", 2000)

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
        self.progress.begin("Importing", 1)
        added = importer.import_paths(self.db, paths)
        self.progress.log_line(
            f"Imported {added} new beat(s) from {len(paths)} selected file(s)")
        self.progress.end(f"Imported {added} beat(s)")
        self.refresh_library(self.search.text())
        self.statusBar().showMessage(f"Imported {added} new beat(s)", 3000)
        self.analyze_pending()

    def _scan_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Scan a folder for beats")
        if not folder:
            return
        self.progress.begin("Scanning", 1)
        added = importer.scan_folder(self.db, folder)
        self.progress.log_line(f"Scanned {folder}: {added} new beat(s)")
        self.progress.end(f"Scanned {added} beat(s)")
        self.refresh_library(self.search.text())
        self.statusBar().showMessage(f"Scanned: {added} new beat(s)", 3000)
        self.analyze_pending()

    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.db, self)
        dlg.exec()
        if dlg.added_count or dlg.catalog_changed:
            self.refresh_library(self.search.text())
            self.analyze_pending()
            self._update_duplicate_indicator()
        if dlg.tags_changed:
            self.tag_panel.refresh_tags()
        if dlg.check_updates:
            self._manual_update_check = True
            self.update_checker.check_async(config.update_repo(), __version__)

    def _on_update_checked(self, available: bool, version: str, url: str, error: str) -> None:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        if available and url:
            self.statusBar().showMessage(f"Update available: {version}", 8000)
            box = QMessageBox(self)
            box.setWindowTitle("Update available")
            box.setText(f"A new version ({version}) is available.")
            box.setInformativeText("Download and install it now?")
            btn_install = box.addButton("Download && Install", QMessageBox.AcceptRole)
            btn_page = box.addButton("Open page", QMessageBox.ActionRole)
            box.addButton("Later", QMessageBox.RejectRole)
            box.exec()
            clicked = box.clickedButton()
            if clicked is btn_install:
                self._download_and_install(config.update_repo())
            elif clicked is btn_page:
                QDesktopServices.openUrl(QUrl(url))
        elif self._manual_update_check:
            if error:
                QMessageBox.information(self, "Updates", f"Couldn't check: {error}")
            else:
                QMessageBox.information(self, "Updates",
                                        f"You're on the latest version ({__version__}).")
        self._manual_update_check = False

    def _download_and_install(self, repo: str) -> None:
        import tempfile

        dest = str(Path(tempfile.gettempdir()) / "PaperhandsBeatTools-setup.exe")
        self.progress.begin("Downloading update", 1)

        def work():
            url = updater.latest_installer_url(repo)
            if not url:
                raise RuntimeError("The latest release has no installer (.exe) asset.")
            return updater.download(url, dest)

        self.pool.start(FunctionExportRunnable(work, self.install_signals))

    def _on_installer_ready(self, path: str) -> None:
        self.progress.end("Downloaded — launching installer…")
        try:
            os.startfile(path)  # noqa: S606 - launch the trusted, just-downloaded installer
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Update", f"Couldn't launch installer: {exc}")
            return
        from PySide6.QtWidgets import QApplication
        QApplication.instance().quit()   # close so the installer can replace files

    def _on_installer_error(self, message: str) -> None:
        self.progress.end("Update download failed")
        QMessageBox.warning(self, "Update", message)

    def closeEvent(self, event):  # noqa: N802 - Qt override
        self.db.close()
        super().closeEvent(event)
