"""Settings dialog: manage watched scan folders and trigger a rescan.

The "Scan directory" button the user asked for lives here. Watched folders
persist via app.config; "Scan now" rescans them all and reports how many new
beats were cataloged.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
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
