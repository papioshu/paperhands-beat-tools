"""The detail / tag-editing panel for the selected beat.

Shows read-only analysis (filename, BPM, key, status) and editable metadata
(title, genre, sub-genre, mood, free-form tags, notes). Emits intents; it never
touches the database itself — the main window owns persistence.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
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
    set_artwork_requested = Signal(int)    # beat_id (pick a local image)
    generate_artwork_requested = Signal(int)  # beat_id (Pillow)

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

        self.confidence = QLabel("")
        self.confidence.setObjectName("SubHeading")
        self.confidence.setWordWrap(True)
        outer.addWidget(self.confidence)

        # Artwork: thumbnail + set-your-own / generate
        art_row = QHBoxLayout()
        self.artwork_thumb = QLabel("no\nartwork")
        self.artwork_thumb.setObjectName("SubHeading")
        self.artwork_thumb.setAlignment(Qt.AlignCenter)
        self.artwork_thumb.setFixedSize(88, 88)
        self.artwork_thumb.setStyleSheet(
            "border: 1px solid #3D434F; border-radius: 6px;")
        art_row.addWidget(self.artwork_thumb)
        art_btns = QVBoxLayout()
        self.btn_set_art = QPushButton("Set image…")
        self.btn_gen_art = QPushButton("Generate")
        art_btns.addWidget(self.btn_set_art)
        art_btns.addWidget(self.btn_gen_art)
        art_btns.addStretch(1)
        art_row.addLayout(art_btns)
        art_row.addStretch(1)
        outer.addLayout(art_row)

        self.btn_set_art.clicked.connect(
            lambda: self._beat_id is not None and self.set_artwork_requested.emit(self._beat_id))
        self.btn_gen_art.clicked.connect(
            lambda: self._beat_id is not None and self.generate_artwork_requested.emit(self._beat_id))

        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        self.title = QLineEdit()
        self.bpm = QComboBox()        # editable: detected value + candidates
        self.bpm.setEditable(True)
        self.key = QComboBox()
        self.key.setEditable(True)
        self.genre = _editable_combo([])
        self.subgenre = _editable_combo([])
        self.mood = _editable_combo([])
        self.tags = QLineEdit()
        self.tags.setPlaceholderText("comma-separated, e.g. dark, melodic, leased")
        self.notes = QPlainTextEdit()
        self.notes.setFixedHeight(90)
        form.addRow("Title", self.title)
        form.addRow("BPM", self.bpm)
        form.addRow("Key", self.key)
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
        self.analysis.setText(f"{row['filename']}   ({row['analysis_status'] or '—'})")

        self.title.setText(row["title"] or "")
        bpm_current = "" if row["bpm"] is None else f"{row['bpm']:g}"
        self._fill_combo(self.bpm, bpm_current,
                         [f"{c:g}" for c in _parse_list(row["bpm_candidates"])])
        self._fill_combo(self.key, row["key"] or "", _parse_list(row["key_candidates"]))
        self._show_confidence(row["bpm_confidence"], row["key_confidence"])

        self.genre.setCurrentText(row["genre"] or "")
        self.subgenre.setCurrentText(row["subgenre"] or "")
        # Pre-fill an empty mood with the detected suggestion (user can override).
        mood_val = row["mood"] or ""
        suggested = _row_get(row, "mood_suggested")
        if not mood_val and suggested:
            mood_val = suggested
            self.confidence.setText(
                (self.confidence.text() + "  ·  " if self.confidence.text() else "")
                + f"mood suggested: {suggested}")
        self.mood.setCurrentText(mood_val)
        self.tags.setText(", ".join(tag_names))
        self.notes.setPlainText(row["notes"] or "")

        self.set_artwork_thumb(_row_get(row, "artwork_path"))
        self.missing_banner.setVisible(missing)
        self.btn_relocate.setVisible(missing)
        self.btn_rename.setDisabled(missing)
        self.set_enabled(True)

    def set_artwork_thumb(self, path) -> None:
        if path and Path(path).exists():
            pm = QPixmap(str(path))
            if not pm.isNull():
                self.artwork_thumb.setPixmap(pm.scaled(
                    86, 86, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                return
        self.artwork_thumb.setPixmap(QPixmap())
        self.artwork_thumb.setText("no\nartwork")

    def clear(self) -> None:
        self._beat_id = None
        self.analysis.setText("Select a beat to edit.")
        self.confidence.setText("")
        self.set_artwork_thumb(None)
        for w in (self.title, self.tags):
            w.clear()
        for c in (self.bpm, self.key, self.genre, self.subgenre, self.mood):
            c.setCurrentText("")
        self.notes.clear()
        self.missing_banner.hide()
        self.btn_relocate.hide()
        self.set_enabled(False)

    def set_enabled(self, on: bool) -> None:
        for w in (self.title, self.bpm, self.key, self.genre, self.subgenre,
                  self.mood, self.tags, self.notes, self.btn_save, self.btn_rename,
                  self.btn_set_art, self.btn_gen_art):
            w.setEnabled(on)

    # -- internals ---------------------------------------------------------

    @staticmethod
    def _fill_combo(combo, current: str, candidates) -> None:
        combo.blockSignals(True)
        combo.clear()
        items = []
        for c in [current, *candidates]:
            s = str(c)
            if s and s not in items:
                items.append(s)
        combo.addItems(items)
        combo.setCurrentText(str(current))
        combo.blockSignals(False)

    def _show_confidence(self, bpm_conf, key_conf) -> None:
        parts = []
        if bpm_conf is not None:
            parts.append(f"BPM {int(round(bpm_conf * 100))}%")
        if key_conf is not None:
            parts.append(f"Key {int(round(key_conf * 100))}%")
        self.confidence.setText(
            ("Detection confidence — " + " · ".join(parts)) if parts else "")

    def _emit_save(self) -> None:
        if self._beat_id is None:
            return
        fields = {
            "title": self.title.text().strip(),
            "bpm": _parse_bpm(self.bpm.currentText()),
            "key": self.key.currentText().strip() or None,
            "genre": self.genre.currentText().strip(),
            "subgenre": self.subgenre.currentText().strip(),
            "mood": self.mood.currentText().strip(),
            "notes": self.notes.toPlainText().strip(),
        }
        tag_names = [t.strip() for t in self.tags.text().split(",") if t.strip()]
        self.saved.emit(self._beat_id, fields, tag_names)


def _row_get(row, column):
    """Read a column from a sqlite3.Row, tolerating its absence (older rows)."""
    try:
        return row[column]
    except (IndexError, KeyError):
        return None


def _parse_list(raw):
    """Parse a JSON list stored in the DB; tolerate empty/garbage."""
    if not raw:
        return []
    try:
        import json

        data = json.loads(raw)
        return data if isinstance(data, list) else []
    except (ValueError, TypeError):
        return []


def _parse_bpm(text: str):
    text = text.strip()
    try:
        return float(text) if text else None
    except ValueError:
        return None
