"""Off-thread export so the UI stays responsive while ffmpeg re-encodes.

Mirrors the analysis worker: a QObject holds the signals, the QRunnable does the
work and emits results that are delivered to the main thread.
"""

from __future__ import annotations

from typing import Dict, Optional, Sequence

from PySide6.QtCore import QObject, QRunnable, Signal, Slot

from core import pipeline
from core.models import TaggingConfig


class ExportSignals(QObject):
    done = Signal(str)     # output path
    error = Signal(str)    # message


class ExportRunnable(QRunnable):
    def __init__(
        self,
        input_path: str,
        placements: Sequence,
        out_path: str,
        config: TaggingConfig,
        signals: ExportSignals,
        crop: Optional[tuple] = None,
        tags: Optional[Dict[str, str]] = None,
    ):
        super().__init__()
        self.input_path = input_path
        self.placements = list(placements)   # snapshot; main thread may mutate
        self.out_path = out_path
        self.config = config
        self.signals = signals
        self.crop = crop
        self.tags = tags

    @Slot()
    def run(self) -> None:
        try:
            pipeline.export_with_placements(
                self.input_path, self.placements, self.out_path, self.config,
                crop=self.crop, tags=self.tags,
            )
            self.signals.done.emit(self.out_path)
        except Exception as exc:  # noqa: BLE001 - report to the UI thread
            self.signals.error.emit(str(exc))
