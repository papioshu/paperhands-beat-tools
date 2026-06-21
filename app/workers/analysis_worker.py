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
        self.signals.started.emit(self.beat_id)
        try:
            import json

            from core import audio, detection, fingerprint, mood, structure, waveform

            seg = audio.load_audio(self.file_path)
            samples, sr = audio.to_mono_float(seg)
            duration_sec = len(seg) / 1000.0

            # Downsample for feature extraction: CQT/STFT cost scales with sample
            # count, so halving the rate roughly halves analysis time. Results are
            # in seconds/pitch classes, so accuracy impact is negligible.
            try:
                import librosa
                if sr > 22050:
                    samples = librosa.resample(samples, orig_sr=sr, target_sr=22050)
                    sr = 22050
            except Exception:  # noqa: BLE001 - fall back to full-rate analysis
                pass

            det = detection.detect_bpm_key(samples, sr)
            saved = waveform.generate_peaks_file(samples, self.peaks_path)
            try:
                fp = fingerprint.compute_fingerprint(samples, sr)
            except Exception:  # noqa: BLE001 - fingerprint is best-effort
                fp = ""
            try:
                sections = structure.detect_structure(samples, sr)
                drop = structure.detect_drop(samples, sr, sections)
                hook = structure.detect_hook(samples, sr, sections)
            except Exception:  # noqa: BLE001 - structure is best-effort
                sections, drop, hook = [], None, None
            try:
                mood_suggested, _ = mood.detect_mood(samples, sr, det.key, det.bpm)
            except Exception:  # noqa: BLE001 - mood is best-effort
                mood_suggested = None

            result = {
                "bpm": det.bpm,
                "key": det.key,
                "duration_sec": duration_sec,
                "waveform_path": saved,
                "analysis_status": "error" if det.error else "done",
                "bpm_confidence": det.bpm_confidence,
                "key_confidence": det.key_confidence,
                "bpm_candidates": json.dumps(list(det.bpm_candidates)),
                "key_candidates": json.dumps(list(det.key_candidates)),
                "fingerprint": fp,
                "structure": json.dumps(sections),
                "drop_sec": drop,
                "hook_start": hook[0] if hook else None,
                "hook_end": hook[1] if hook else None,
                "mood_suggested": mood_suggested,
            }
            self.signals.beat_analyzed.emit(self.beat_id, result)
        except Exception as exc:  # noqa: BLE001 - report, never crash the pool
            self.signals.error.emit(self.beat_id, str(exc))
        finally:
            self.signals.progress.emit()
