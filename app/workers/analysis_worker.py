"""Per-beat analysis task: detect BPM/key + cache waveform peaks, off-thread.

The runnable only *reads* the audio file and *writes* a peaks ``.npy`` cache; it
never touches the database. Results go back to the main thread via signals, so
the main thread alone owns the DB connection (no cross-thread SQLite writes).
"""

from __future__ import annotations

from PySide6.QtCore import QRunnable, Slot

from .signals import WorkerSignals


class AnalysisRunnable(QRunnable):
    def __init__(self, beat_id: int, file_path: str, peaks_path: str,
                 signals: WorkerSignals):
        super().__init__()
        self.beat_id = beat_id
        self.file_path = file_path
        self.peaks_path = peaks_path
        self.signals = signals

    @Slot()
    def run(self) -> None:
        try:
            from core import audio, detection, waveform

            seg = audio.load_audio(self.file_path)
            samples, sr = audio.to_mono_float(seg)

            det = detection.detect_bpm_key(samples, sr)
            saved = waveform.generate_peaks_file(samples, self.peaks_path)

            result = {
                "bpm": det.bpm,
                "key": det.key,
                "duration_sec": len(seg) / 1000.0,
                "waveform_path": saved,
                "analysis_status": "error" if det.error else "done",
            }
            self.signals.beat_analyzed.emit(self.beat_id, result)
        except Exception as exc:  # noqa: BLE001 - report, never crash the pool
            self.signals.error.emit(self.beat_id, str(exc))
        finally:
            self.signals.progress.emit()
