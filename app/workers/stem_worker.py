"""Background stem separation + one-click engine install (off the UI thread)."""

from __future__ import annotations

import os
import subprocess

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class StemSignals(QObject):
    started = Signal(int)            # beat_id
    done = Signal(int, dict)         # beat_id, {stem: path}
    error = Signal(int, str)         # beat_id, message


class StemRunnable(QRunnable):
    def __init__(self, beat_id: int, input_path: str, out_dir: str, engine,
                 signals: StemSignals):
        super().__init__()
        self.beat_id = beat_id
        self.input_path = input_path
        self.out_dir = out_dir
        self.engine = engine
        self.signals = signals

    @Slot()
    def run(self) -> None:
        self.signals.started.emit(self.beat_id)
        try:
            stems = self.engine.split(self.input_path, self.out_dir)
            try:
                from core.stems import build_instrumental
                inst = build_instrumental(
                    stems, os.path.join(self.out_dir, "instrumental.wav"))
                if inst:
                    stems["instrumental"] = inst
            except Exception:  # noqa: BLE001 - instrumental is optional
                pass
            self.signals.done.emit(self.beat_id, stems)
        except Exception as exc:  # noqa: BLE001
            self.signals.error.emit(self.beat_id, str(exc))


class InstallSignals(QObject):
    line = Signal(str)               # a line of installer output
    finished = Signal(bool, str)     # ok, message


class InstallRunnable(QRunnable):
    """Run a pip install command, streaming its output to the UI."""

    def __init__(self, command: list, signals: InstallSignals):
        super().__init__()
        self.command = command
        self.signals = signals

    @Slot()
    def run(self) -> None:
        try:
            proc = subprocess.Popen(
                self.command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1)
            for line in proc.stdout:
                self.signals.line.emit(line.rstrip())
            code = proc.wait()
            self.signals.finished.emit(code == 0,
                                       "" if code == 0 else f"pip exited {code}")
        except Exception as exc:  # noqa: BLE001
            self.signals.finished.emit(False, str(exc))
