"""The detail / tag-editing panel for the selected beat.

Shows read-only analysis (filename, BPM, key, status) and editable metadata
(title, genre, sub-genre, mood, free-form tags, notes). Emits intents; it never
touches the database itself — the main window owns persistence.
"""

from __future__ import annotations

from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QCompleter,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def _editable_combo(values: List[str]) -> QComboBox:
    combo = QComboBox()
    combo.setEditable(True)
    combo.addItem("")
    combo.addItems(values)
    combo.setCurrentText("")
    completer = QCompleter(values)
    completer.setCaseSensitivity(Qt.CaseInsensitive)
    completer.setCompletionMode(QCompleter.PopupCompletion)
    combo.setCompleter(completer)
    return combo


class DetailPanel(QFrame):
    saved = Signal(int, dict, list)        # beat_id, fields, tag_names
    rename_requested = Signal(int)         # beat_id
    relocate_requested = Signal(int)       # beat_id

    def __init__(self):
        super().__init__()
        self.setObjectName("Panel")
        self._beat_id: Optional[int] = None

        outer = QVBoxLayout(self)

        self.heading = QLabel("Beat details")
        self.heading.setObjectName("Heading")
        outer.addWidget(self.heading)

        self.analysis = QLabel("Select a beat to edit.")
        self.analysis.setObjectName("AccentLime")
        self.analysis.setWordWrap(True)
        outer.addWidget(self.analysis)

        self.missing_banner = QLabel("⚠ File missing — relocate it to play or rename.")
        self.missing_banner.setStyleSheet("color: #FFB454;")
        self.missing_banner.setWordWrap(True)
        self.missing_banner.hide()
        outer.addWidget(self.missing_banner)

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        self.title = QLineEdit()
        self.genre = _editable_combo([])
        self.subgenre = _editable_combo([])
        self.mood = _editable_combo([])
        self.tags = QLineEdit()
        self.tags.setPlaceholderText("comma-separated, e.g. dark, melodic, leased")
        self.notes = QPlainTextEdit()
        self.notes.setFixedHeight(90)
        form.addRow("Title", self.title)
        form.addRow("Genre", self.genre)
        form.addRow("Sub-genre", self.subgenre)
        form.addRow("Mood", self.mood)
        form.addRow("Tags", self.tags)
        form.addRow("Notes", self.notes)
        outer.addLayout(form)

        buttons = QHBoxLayout()
        self.btn_save = QPushButton("Save")
        self.btn_save.setObjectName("Primary")
        self.btn_rename = QPushButton("Rename file…")
        self.btn_relocate = QPushButton("Relocate…")
        self.btn_relocate.hide()
        buttons.addWidget(self.btn_save)
        buttons.addWidget(self.btn_rename)
        buttons.addWidget(self.btn_relocate)
        buttons.addStretch(1)
        outer.addLayout(buttons)
        outer.addStretch(1)

        self.btn_save.clicked.connect(self._emit_save)
        self.btn_rename.clicked.connect(
            lambda: self._beat_id is not None and self.rename_requested.emit(self._beat_id)
        )
        self.btn_relocate.clicked.connect(
            lambda: self._beat_id is not None and self.relocate_requested.emit(self._beat_id)
        )

        self.set_enabled(False)

    # -- public API --------------------------------------------------------

    def set_autocomplete(self, genres, subgenres, moods, tag_names) -> None:
        """Refresh dropdown suggestions from the DB's distinct values."""
        for combo, vals in ((self.genre, genres), (self.subgenre, subgenres),
                            (self.mood, moods)):
            current = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("")
            combo.addItems(vals)
            combo.setCurrentText(current)
            combo.blockSignals(False)
        completer = QCompleter(list(tag_names))
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        self.tags.setCompleter(completer)

    def load_beat(self, row, tag_names: List[str], missing: bool = False) -> None:
        self._beat_id = row["id"]
        bpm = "" if row["bpm"] is None else f"{row['bpm']:g} BPM"
        key = row["key"] or ""
        sep = " · " if bpm and key else ""
        self.analysis.setText(
            f"{row['filename']}\n{bpm}{sep}{key}   ({row['analysis_status'] or '—'})"
        )
        self.title.setText(row["title"] or "")
        self.genre.setCurrentText(row["genre"] or "")
        self.subgenre.setCurrentText(row["subgenre"] or "")
        self.mood.setCurrentText(row["mood"] or "")
        self.tags.setText(", ".join(tag_names))
        self.notes.setPlainText(row["notes"] or "")

        self.missing_banner.setVisible(missing)
        self.btn_relocate.setVisible(missing)
        self.btn_rename.setDisabled(missing)
        self.set_enabled(True)

    def clear(self) -> None:
        self._beat_id = None
        self.analysis.setText("Select a beat to edit.")
        for w in (self.title, self.tags):
            w.clear()
        for c in (self.genre, self.subgenre, self.mood):
            c.setCurrentText("")
        self.notes.clear()
        self.missing_banner.hide()
        self.btn_relocate.hide()
        self.set_enabled(False)

    def set_enabled(self, on: bool) -> None:
        for w in (self.title, self.genre, self.subgenre, self.mood, self.tags,
                  self.notes, self.btn_save, self.btn_rename):
            w.setEnabled(on)

    # -- internals ---------------------------------------------------------

    def _emit_save(self) -> None:
        if self._beat_id is None:
            return
        fields = {
            "title": self.title.text().strip(),
            "genre": self.genre.currentText().strip(),
            "subgenre": self.subgenre.currentText().strip(),
            "mood": self.mood.currentText().strip(),
            "notes": self.notes.toPlainText().strip(),
        }
        tag_names = [t.strip() for t in self.tags.text().split(",") if t.strip()]
        self.saved.emit(self._beat_id, fields, tag_names)
