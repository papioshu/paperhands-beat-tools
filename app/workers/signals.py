"""Qt signals emitted by background workers.

A QRunnable can't own signals, so they live on this QObject. It's created on the
main thread, so emissions from worker threads are delivered as queued calls —
which means the slots (and therefore all DB writes) run on the main thread.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class WorkerSignals(QObject):
    beat_analyzed = Signal(int, dict)   # beat_id, {bpm, key, duration_sec, ...}
    error = Signal(int, str)            # beat_id, message
    progress = Signal()                 # one unit finished (ok or error)
