"""Settings dialog: manage watched scan folders and trigger a rescan.

The "Scan directory" button the user asked for lives here. Watched folders
persist via app.config; "Scan now" rescans them all and reports how many new
beats were cataloged.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from app import config
from app.services import catalog_io, importer


class SettingsDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Settings — Watched Folders")
        self.resize(560, 360)

        layout = QVBoxLayout(self)

        # Producer name (embedded as the ID3 artist on exports)
        prod_heading = QLabel("Producer name")
        prod_heading.setObjectName("Heading")
        layout.addWidget(prod_heading)
        prod_hint = QLabel("Embedded as the artist tag on every exported MP3.")
        prod_hint.setObjectName("SubHeading")
        layout.addWidget(prod_hint)
        self.producer_edit = QLineEdit(config.producer())
        self.producer_edit.setPlaceholderText("paperhand")
        layout.addWidget(self.producer_edit)
        self.producer_edit.editingFinished.connect(
            lambda: config.set_producer(self.producer_edit.text())
        )

        # Tag library folder (also changeable from the tag panel)
        tags_heading = QLabel("Tag library folder")
        tags_heading.setObjectName("Heading")
        layout.addWidget(tags_heading)
        tags_row = QHBoxLayout()
        self.tags_label = QLabel(config.tags_folder())
        self.tags_label.setObjectName("SubHeading")
        self.tags_label.setWordWrap(True)
        self.btn_tags_folder = QPushButton("Change…")
        self.btn_tags_folder.setFixedWidth(90)
        tags_row.addWidget(self.tags_label, 1)
        tags_row.addWidget(self.btn_tags_folder)
        layout.addLayout(tags_row)
        self.btn_tags_folder.clicked.connect(self._choose_tags_folder)

        heading = QLabel("Watched folders")
        heading.setObjectName("Heading")
        layout.addWidget(heading)
        hint = QLabel("Folders scanned for new beats. Use “Scan now” to catalog "
                      "any new files found in them.")
        hint.setObjectName("SubHeading")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.list = QListWidget()
        self.list.addItems(config.watched_folders())
        layout.addWidget(self.list, 1)

        row = QHBoxLayout()
        self.btn_add = QPushButton("Add folder…")
        self.btn_remove = QPushButton("Remove")
        self.btn_scan = QPushButton("Scan now")
        self.btn_scan.setObjectName("Accent")
        row.addWidget(self.btn_add)
        row.addWidget(self.btn_remove)
        row.addStretch(1)
        row.addWidget(self.btn_scan)
        layout.addLayout(row)

        # Catalog backup (export / import metadata)
        backup_heading = QLabel("Catalog backup")
        backup_heading.setObjectName("Heading")
        layout.addWidget(backup_heading)
        backup_hint = QLabel("Export all beats + tags to CSV/JSON, or restore a "
                             "previously exported catalog.")
        backup_hint.setObjectName("SubHeading")
        backup_hint.setWordWrap(True)
        layout.addWidget(backup_hint)
        backup_row = QHBoxLayout()
        self.btn_export_catalog = QPushButton("Export catalog…")
        self.btn_import_catalog = QPushButton("Import catalog…")
        backup_row.addWidget(self.btn_export_catalog)
        backup_row.addWidget(self.btn_import_catalog)
        backup_row.addStretch(1)
        layout.addLayout(backup_row)

        # Stem separation model
        model_heading = QLabel("Stem separation model")
        model_heading.setObjectName("Heading")
        layout.addWidget(model_heading)
        model_hint = QLabel("Model used by Split Stems / DAW Mode. Picking a new "
                            "one downloads it in the background on first use.")
        model_hint.setObjectName("SubHeading")
        model_hint.setWordWrap(True)
        layout.addWidget(model_hint)
        self.model_combo = QComboBox()
        for key, desc in config.DEMUCS_MODELS.items():
            self.model_combo.addItem(f"{key} — {desc}", key)
        cur = config.demucs_model()
        self.model_combo.setCurrentIndex(max(0, self.model_combo.findData(cur)))
        self.model_combo.setToolTip("Demucs model for stem separation")
        layout.addWidget(self.model_combo)
        self.model_combo.currentIndexChanged.connect(self._on_model_changed)

        # Audio output device (where playback is heard)
        audio_heading = QLabel("Audio output")
        audio_heading.setObjectName("Heading")
        layout.addWidget(audio_heading)
        audio_hint = QLabel("Device used for beat/tag playback. "
                            "“System default” follows your Windows default.")
        audio_hint.setObjectName("SubHeading")
        audio_hint.setWordWrap(True)
        layout.addWidget(audio_hint)
        self.audio_combo = QComboBox()
        self.audio_combo.addItem("System default", "")
        from app.ui.player import AudioPlayer
        for desc in AudioPlayer.output_devices():
            self.audio_combo.addItem(desc, desc)
        cur_audio = config.audio_output()
        self.audio_combo.setCurrentIndex(max(0, self.audio_combo.findData(cur_audio)))
        layout.addWidget(self.audio_combo)
        self.audio_combo.currentIndexChanged.connect(self._on_audio_changed)

        # Export options
        self.chk_master_wav = QCheckBox(
            "Convert clean master to WAV on export (default: copy verbatim)")
        self.chk_master_wav.setChecked(config.convert_master_to_wav())
        self.chk_master_wav.toggled.connect(config.set_convert_master_to_wav)
        layout.addWidget(self.chk_master_wav)

        # Updates (GitHub releases)
        from app.version import __version__
        upd_heading = QLabel(f"Updates  —  current version {__version__}")
        upd_heading.setObjectName("Heading")
        layout.addWidget(upd_heading)
        upd_hint = QLabel("Check GitHub for a newer release.")
        upd_hint.setObjectName("SubHeading")
        layout.addWidget(upd_hint)
        self.btn_check_updates = QPushButton("Check for updates")
        layout.addWidget(self.btn_check_updates)
        self.btn_check_updates.clicked.connect(self._check_updates)

        close_row = QHBoxLayout()
        close_row.addStretch(1)
        self.btn_close = QPushButton("Close")
        self.btn_close.setObjectName("Primary")
        close_row.addWidget(self.btn_close)
        layout.addLayout(close_row)

        self.btn_add.clicked.connect(self._add)
        self.btn_remove.clicked.connect(self._remove)
        self.btn_scan.clicked.connect(self._scan)
        self.btn_export_catalog.clicked.connect(self._export_catalog)
        self.btn_import_catalog.clicked.connect(self._import_catalog)
        self.btn_close.clicked.connect(self.accept)

        self.added_count = 0       # new beats from scans this session
        self.catalog_changed = False  # whether an import altered the library
        self.tags_changed = False     # whether the tag library folder changed
        self.check_updates = False    # whether the user asked to check for updates
        self.model_changed = False    # whether the stem model selection changed
        self.audio_changed = False    # whether the output device selection changed

    def _on_audio_changed(self) -> None:
        config.set_audio_output(self.audio_combo.currentData())
        self.audio_changed = True

    def _on_model_changed(self) -> None:
        name = self.model_combo.currentData()
        if name and name != config.demucs_model():
            config.set_demucs_model(name)
            self.model_changed = True

    def _add(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Add a folder to watch")
        if folder:
            config.add_watched_folder(folder)
            self.list.clear()
            self.list.addItems(config.watched_folders())

    def _remove(self) -> None:
        item = self.list.currentItem()
        if item:
            config.remove_watched_folder(item.text())
            self.list.takeItem(self.list.row(item))

    def _check_updates(self) -> None:
        self.check_updates = True
        self.accept()       # main window runs the check after the dialog closes

    def _choose_tags_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Choose tag library folder")
        if folder:
            config.set_tags_folder(folder)
            self.tags_label.setText(folder)
            self.tags_changed = True

    def _export_catalog(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Export catalog", "catalog.csv",
            "CSV (*.csv);;JSON (*.json)")
        if not path:
            return
        try:
            n = catalog_io.export_catalog(self.db, path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Export failed", str(exc))
            return
        QMessageBox.information(self, "Catalog exported", f"Wrote {n} beat(s).")

    def _import_catalog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Import catalog", "", "Catalog (*.csv *.json)")
        if not path:
            return
        try:
            added, updated = catalog_io.import_catalog(self.db, path)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.warning(self, "Import failed", str(exc))
            return
        self.catalog_changed = True
        QMessageBox.information(self, "Catalog imported",
                                f"Added {added}, updated {updated} beat(s).")

    def _scan(self) -> None:
        folders = config.watched_folders()
        if not folders:
            QMessageBox.information(self, "Scan", "Add at least one folder first.")
            return
        total = 0
        for folder in folders:
            try:
                total += importer.scan_folder(self.db, folder)
            except NotADirectoryError:
                continue  # folder went away; skip quietly
        self.added_count += total
        QMessageBox.information(self, "Scan complete",
                                f"Cataloged {total} new beat(s).")
