"""DAW Mode — a lightweight multitrack stem workspace.

Preview, organize, tag, and export stems without a full DAW. Per-stem tracks
(mute/solo/volume/pan/color/waveform), a transport that plays the live *mixed*
render of the stems, a non-destructive tag timeline, and the five exports.

NOT a DAW: no MIDI/recording/VST/piano-roll/automation. Just beat prep + tagging
+ stem management + export.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from app.ui.player import AudioPlayer
from app.ui.widgets import WaveformWidget
from app.workers import ExportSignals, FunctionExportRunnable
from core import exports as core_exports
from core import mixer, pipeline
from core import waveform as wf
from core.models import Placement, TaggingConfig

# Stable display order + colors for the standard stems.
STEM_ORDER = ["drums", "bass", "vocals", "other", "instrumental", "tag_only"]
STEM_COLORS = {
    "drums": "#FF6B6B", "bass": "#5C9BFF", "vocals": "#6CE5A1",
    "other": "#8B5CF6", "instrumental": "#FFB454", "tag_only": "#B6F500",
}


class TrackRow(QFrame):
    """One stem track: color + name + M/S + volume + pan + waveform."""

    def __init__(self, track: dict):
        super().__init__()
        self.track = track
        self.setObjectName("Panel")
        h = QHBoxLayout(self)
        h.setContentsMargins(6, 2, 6, 2)

        swatch = QFrame()
        swatch.setFixedSize(10, 36)
        swatch.setStyleSheet(f"background:{track['color']}; border-radius:3px;")
        h.addWidget(swatch)

        name = QLabel(track["name"])
        name.setFixedWidth(90)
        h.addWidget(name)

        self.mute = QPushButton("M")
        self.mute.setCheckable(True)
        self.mute.setFixedWidth(26)
        self.solo = QPushButton("S")
        self.solo.setCheckable(True)
        self.solo.setFixedWidth(26)
        h.addWidget(self.mute)
        h.addWidget(self.solo)

        self.vol = QSlider(Qt.Horizontal)
        self.vol.setRange(-24, 6)
        self.vol.setValue(0)
        self.vol.setFixedWidth(80)
        h.addWidget(self.vol)
        self.pan = QSlider(Qt.Horizontal)
        self.pan.setRange(-100, 100)
        self.pan.setValue(0)
        self.pan.setFixedWidth(60)
        h.addWidget(self.pan)

        self.wave = WaveformWidget()
        self.wave.setMinimumHeight(36)
        h.addWidget(self.wave, 1)

        self.mute.toggled.connect(self._sync)
        self.solo.toggled.connect(self._sync)
        self.vol.valueChanged.connect(self._sync)
        self.pan.valueChanged.connect(self._sync)
        self._load_wave()

    def _load_wave(self) -> None:
        try:
            from core import audio
            seg = audio.load_audio(self.track["path"])
            samples, _ = audio.to_mono_float(seg)
            self.wave.set_peaks(wf.compute_peaks(samples, 600))
        except Exception:  # noqa: BLE001 - undecodable / missing stem -> flat
            pass

    def _sync(self) -> None:
        self.track.update({
            "mute": self.mute.isChecked(), "solo": self.solo.isChecked(),
            "volume_db": float(self.vol.value()), "pan": self.pan.value() / 100.0,
        })


class DawModeWindow(QMainWindow):
    def __init__(self, db, beat_id: int, parent=None):
        super().__init__(parent)
        self.db = db
        self.beat_id = beat_id
        self.row = db.get_beat(beat_id)
        self.stems = json.loads(self.row["stems"] or "{}")
        self._duration_ms = 0
        self._placements = self._load_placements()
        self._layers = json.loads(self.row["layers"] or "{}")

        name = Path(self.row["filename"]).stem
        self.setWindowTitle(f"DAW Mode — {name}")
        self.resize(960, 640)

        self.player = AudioPlayer()
        self.player.position_changed.connect(self._on_position)
        self.player.duration_changed.connect(self._on_duration)
        self.render_signals = ExportSignals()
        self.render_signals.done.connect(self._on_mix_ready)
        self.render_signals.error.connect(
            lambda m: self.status.setText(f"Mix render failed: {m}"))
        self.export_signals = ExportSignals()
        self.export_signals.done.connect(
            lambda p: self.status.setText(f"Exported → {Path(p).name}"))
        self.export_signals.error.connect(
            lambda m: QMessageBox.warning(self, "Export failed", m))

        self._build_ui()
        self._tracks = [r.track for r in self._rows]
        self._load_tag_timeline()

    # -- build -------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)

        # Transport
        bar = QHBoxLayout()
        self.btn_play = QPushButton("Play Mix")
        self.btn_play.setObjectName("Accent")
        self.btn_stop = QPushButton("Stop")
        self.btn_loop = QPushButton("Loop")
        self.btn_loop.setCheckable(True)
        self.seek = QSlider(Qt.Horizontal)
        self.time = QLabel("0:00 / 0:00")
        bar.addWidget(self.btn_play)
        bar.addWidget(self.btn_stop)
        bar.addWidget(self.btn_loop)
        bar.addWidget(self.seek, 1)
        bar.addWidget(self.time)
        root.addLayout(bar)

        # Tracks
        tracks_box = QVBoxLayout()
        self._rows = []
        for stem in STEM_ORDER:
            if stem in self.stems:
                tr = TrackRow({"name": stem, "path": self.stems[stem],
                               "color": STEM_COLORS.get(stem, "#9AA0AB"),
                               "mute": False, "solo": False,
                               "volume_db": 0.0, "pan": 0.0, "enabled": True})
                self._rows.append(tr)
                tracks_box.addWidget(tr)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        holder = QWidget()
        holder.setLayout(tracks_box)
        scroll.setWidget(holder)
        root.addWidget(scroll, 1)

        # Tag timeline
        tag_label = QLabel("Tag timeline (click to place · drag to move)")
        tag_label.setObjectName("SubHeading")
        root.addWidget(tag_label)
        self.tag_wave = WaveformWidget()
        self.tag_wave.setMinimumHeight(70)
        self.tag_wave.set_mode("place")
        self.tag_wave.tag_placed.connect(self._place_tag)
        self.tag_wave.marker_removed.connect(self._remove_marker)
        self.tag_wave.marker_moved.connect(self._move_marker)
        root.addWidget(self.tag_wave)

        controls = QHBoxLayout()
        self.btn_clear = QPushButton("Clear tags")
        self.btn_export = QPushButton("Export ▾")
        export_menu = QMenu(self.btn_export)
        export_menu.addAction("Tagged Preview MP3", self._export_tagged_preview)
        export_menu.addAction("Current Mix WAV", self._export_current_mix)
        export_menu.addAction("Clean Master WAV", self._export_clean_master)
        export_menu.addAction("Individual Stems", self._export_stems)
        export_menu.addAction("Buyer Package ZIP", self._export_buyer_package)
        self.btn_export.setMenu(export_menu)
        self.status = QLabel("")
        self.status.setObjectName("AccentLime")
        controls.addWidget(self.btn_clear)
        controls.addStretch(1)
        controls.addWidget(self.status)
        controls.addWidget(self.btn_export)
        root.addLayout(controls)

        self.setCentralWidget(central)

        self.btn_play.clicked.connect(self._play_mix)
        self.btn_stop.clicked.connect(self.player.stop)
        self.btn_loop.toggled.connect(self.player.set_loop)
        self.seek.sliderMoved.connect(self.player.set_position)
        self.btn_clear.clicked.connect(self._clear_tags)

    # -- tags --------------------------------------------------------------

    def _load_placements(self) -> list:
        raw = self.row["placements"]
        if not raw:
            return []
        try:
            return [Placement(float(d["pos"]), d["tag"]) for d in json.loads(raw)]
        except (ValueError, TypeError, KeyError):
            return []

    def _load_tag_timeline(self) -> None:
        path = self.row["waveform_path"]
        if path and Path(path).exists():
            try:
                self.tag_wave.set_peaks(wf.load_peaks(path))
            except Exception:  # noqa: BLE001
                pass
        self._refresh_markers()

    def _duration_sec(self) -> float:
        return self.row["duration_sec"] or 0.0

    def _refresh_markers(self) -> None:
        dur = self._duration_sec()
        self.tag_wave.set_markers(
            [p.position_sec / dur for p in self._placements] if dur else [])

    def _save_placements(self) -> None:
        self.db.update_beat(self.beat_id, placements=json.dumps(
            [{"pos": p.position_sec, "tag": p.tag_path} for p in self._placements]))

    def _place_tag(self, fraction: float) -> None:
        # Use the first available tag stem as the tag source, else skip.
        tag = self.stems.get("tag_only")
        if not tag or self._duration_sec() <= 0:
            self.status.setText("No tag stem available to place.")
            return
        self._placements.append(Placement(round(fraction * self._duration_sec(), 3), tag))
        self._placements.sort(key=lambda p: p.position_sec)
        self._refresh_markers()
        self._save_placements()

    def _remove_marker(self, index: int) -> None:
        if 0 <= index < len(self._placements):
            del self._placements[index]
            self._refresh_markers()
            self._save_placements()

    def _move_marker(self, index: int, fraction: float) -> None:
        if 0 <= index < len(self._placements) and self._duration_sec() > 0:
            pos = round(fraction * self._duration_sec(), 3)
            self._placements[index] = Placement(pos, self._placements[index].tag_path)
            self._placements.sort(key=lambda p: p.position_sec)
            self._refresh_markers()
            self._save_placements()

    def _clear_tags(self) -> None:
        self._placements = []
        self._refresh_markers()
        self._save_placements()

    # -- transport ---------------------------------------------------------

    def _play_mix(self) -> None:
        self.status.setText("Rendering mix…")
        tracks = [dict(t) for t in self._tracks]
        out = os.path.join(tempfile.gettempdir(),
                           f"daw_mix_{self.beat_id}.wav")

        def work():
            return mixer.mix_stem_tracks(tracks, out)

        self.pool_start(FunctionExportRunnable(work, self.render_signals))

    def pool_start(self, runnable):
        from PySide6.QtCore import QThreadPool
        QThreadPool.globalInstance().start(runnable)

    def _on_mix_ready(self, path: str) -> None:
        self.status.setText("Playing mix")
        self.player.load(path)
        self.player.play()

    def _on_duration(self, ms: int) -> None:
        self._duration_ms = ms
        self.seek.setRange(0, ms)

    def _on_position(self, ms: int) -> None:
        if not self.seek.isSliderDown():
            self.seek.blockSignals(True)
            self.seek.setValue(ms)
            self.seek.blockSignals(False)
        self.time.setText(f"{self._fmt(ms)} / {self._fmt(self._duration_ms)}")

    @staticmethod
    def _fmt(ms: int) -> str:
        s = int(ms // 1000)
        return f"{s // 60}:{s % 60:02d}"

    # -- exports -----------------------------------------------------------

    def _out_base(self) -> Path:
        base = (Path(self.db.path).resolve().parent
                if self.db.path != ":memory:" else Path.cwd())
        return base

    def _beat_name(self) -> str:
        from core.naming import build_output_stem
        return build_output_stem(Path(self.row["filename"]).stem,
                                 self.row["bpm"], self.row["key"], suffix="")

    def _run(self, fn, label: str) -> None:
        self.status.setText(f"{label}…")
        self.pool_start(FunctionExportRunnable(fn, self.export_signals))

    def _export_tagged_preview(self) -> None:
        out = self._out_base() / "previews" / f"{self._beat_name()}_TAGGED.mp3"
        out.parent.mkdir(parents=True, exist_ok=True)
        placements, layers = list(self._placements), dict(self._layers)
        src = self.row["file_path"]
        cfg = TaggingConfig()
        self._run(lambda: pipeline.export_with_placements(
            src, placements, str(out), cfg, layers=layers), "Exporting tagged preview")

    def _export_current_mix(self) -> None:
        out = self._out_base() / "mixes" / f"{self._beat_name()}_MIX.wav"
        out.parent.mkdir(parents=True, exist_ok=True)
        tracks = [dict(t) for t in self._tracks]
        self._run(lambda: mixer.mix_stem_tracks(tracks, str(out)), "Exporting mix")

    def _export_clean_master(self) -> None:
        out = self._out_base() / "masters" / f"{self._beat_name()}.wav"
        out.parent.mkdir(parents=True, exist_ok=True)
        src = self.row["file_path"]
        self._run(lambda: core_exports.export_clean_master(src, str(out), to_wav=True),
                  "Exporting clean master")

    def _export_stems(self) -> None:
        out_dir = self._out_base() / "stems_export" / self._beat_name()
        stems = dict(self.stems)

        def work():
            import shutil
            out_dir.mkdir(parents=True, exist_ok=True)
            for name, path in stems.items():
                if Path(path).exists():
                    shutil.copy2(path, out_dir / f"{name}.wav")
            return str(out_dir)

        self._run(work, "Exporting stems")

    def _export_buyer_package(self) -> None:
        beat_name = self._beat_name()
        master = self._out_base() / "masters" / f"{beat_name}.wav"
        manifest = self._out_base() / "metadata" / f"{beat_name}.json"
        zip_path = self._out_base() / "packages" / f"{beat_name}.zip"
        src = self.row["file_path"]
        stems = dict(self.stems)
        bpm, key = self.row["bpm"], self.row["key"]
        tag_times = sorted(round(p.position_sec, 3) for p in self._placements)

        def work():
            core_exports.export_clean_master(src, str(master), to_wav=True)
            core_exports.update_manifest(str(manifest), {
                "beat_name": beat_name, "bpm": bpm, "key": key,
                "tag_times": tag_times, "license": "All rights reserved (placeholder)",
                "stems": {k: Path(v).name for k, v in stems.items()},
            })
            import zipfile
            zip_path.parent.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(str(zip_path), "w", zipfile.ZIP_DEFLATED) as zf:
                if master.exists():
                    zf.write(str(master), master.name)
                if manifest.exists():
                    zf.write(str(manifest), manifest.name)
                for name, path in stems.items():          # optional stems
                    if Path(path).exists():
                        zf.write(path, f"stems/{name}.wav")
            return str(zip_path)

        self._run(work, "Building buyer package")

    def closeEvent(self, event):  # noqa: N802
        self.player.stop()
        super().closeEvent(event)
