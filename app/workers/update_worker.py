"""Run the GitHub update check off the UI thread."""

from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot

from app import updater


class UpdateChecker(QObject):
    # available, latest_version, release_url, error
    checked = Signal(bool, str, str, str)

    def check_async(self, repo: str, current: str) -> None:
        signals = self

        class _Runnable(QRunnable):
            @Slot()
            def run(self_inner):
                result = updater.check_for_update(current, repo)
                signals.checked.emit(*result)

        QThreadPool.globalInstance().start(_Runnable())
