"""Auto-place dialog: pick a profile/mode + smart-spacing, preview, then apply.

Approve-before-apply: the live preview shows how many tags will land on the
current beat before you commit. The chosen settings are reused to apply the same
profile across many selected beats (each computed from its own duration).
"""

from __future__ import annotations

import random

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from core import autoplace


class AutoPlaceDialog(QDialog):
    def __init__(self, tags, duration, structure, drop, hook, selected_count, parent=None):
        super().__init__(parent)
        self.tags = list(tags)
        self._ctx = (duration, structure, drop, hook)
        self.selected_count = selected_count
        self.setWindowTitle("Auto-Place Tags")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.profile = QComboBox()
        self.profile.addItem("Custom")
        self.profile.addItems(list(autoplace.PROFILES.keys()))
        form.addRow("Profile", self.profile)

        self.mode = QComboBox()
        self.mode.addItems(autoplace.MODES)
        form.addRow("Mode", self.mode)

        self.interval = QDoubleSpinBox()
        self.interval.setRange(5, 600)
        self.interval.setValue(40)
        self.interval.setSuffix(" s")
        form.addRow("Interval", self.interval)

        self.jitter = QDoubleSpinBox()
        self.jitter.setRange(0, 60)
        self.jitter.setValue(0)
        self.jitter.setSuffix(" s")
        form.addRow("Random ±", self.jitter)

        self.min_spacing = QDoubleSpinBox()
        self.min_spacing.setRange(0, 300)
        self.min_spacing.setValue(30)
        self.min_spacing.setSuffix(" s")
        form.addRow("Min spacing", self.min_spacing)

        self.outro = QCheckBox("Add an outro tag near the end")
        form.addRow("", self.outro)
        layout.addLayout(form)

        self.preview = QLabel("")
        self.preview.setObjectName("AccentLime")
        layout.addWidget(self.preview)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        ok_text = (f"Apply to {selected_count} beats" if selected_count > 1
                   else "Apply")
        self.buttons.button(QDialogButtonBox.Ok).setText(ok_text)
        layout.addWidget(self.buttons)

        self.profile.currentTextChanged.connect(self._load_profile)
        for w in (self.mode, self.interval, self.jitter, self.min_spacing):
            (w.currentTextChanged if isinstance(w, QComboBox)
             else w.valueChanged).connect(self._update_preview)
        self.outro.toggled.connect(self._update_preview)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        self._update_preview()

    # -- settings ----------------------------------------------------------

    def _load_profile(self, name: str) -> None:
        if name in autoplace.PROFILES:
            d = dict(autoplace.PROFILES[name])
            self.mode.setCurrentText(d.get("mode", "fixed"))
            if "interval" in d:
                self.interval.setValue(d["interval"])
            if "jitter" in d:
                self.jitter.setValue(d["jitter"])
            self.outro.setChecked(bool(d.get("include_outro", False)))
        self._update_preview()

    def settings(self):
        """Return (mode, params, min_spacing) for suggest_placements."""
        prof = self.profile.currentText()
        if prof in autoplace.PROFILES:
            d = dict(autoplace.PROFILES[prof])
            mode = d.pop("mode", "fixed")
            params = d
        else:
            mode = self.mode.currentText()
            params = {}
            if mode in ("fixed", "random"):
                params["interval"] = self.interval.value()
            if mode == "random":
                params["jitter"] = self.jitter.value()
                params["include_outro"] = self.outro.isChecked()
        return mode, params, self.min_spacing.value()

    def compute_for(self, duration, structure, drop, hook):
        mode, params, min_spacing = self.settings()
        return autoplace.suggest_placements(
            mode, duration, self.tags, structure=structure, drop=drop, hook=hook,
            min_spacing=min_spacing, rng=random.Random(), **params)

    def _update_preview(self) -> None:
        duration, structure, drop, hook = self._ctx
        if not self.tags:
            self.preview.setText("No enabled tags in the library.")
            return
        n = len(self.compute_for(duration, structure, drop, hook))
        self.preview.setText(f"{n} tag(s) on the current beat")
