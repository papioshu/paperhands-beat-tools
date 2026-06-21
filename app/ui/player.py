"""A thin wrapper over QMediaPlayer for auditioning beats.

Degrades gracefully: if the QtMultimedia module or an audio device is missing,
``available`` is False and the UI simply disables the transport instead of
crashing (useful for headless test environments).
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class AudioPlayer(QObject):
    position_changed = Signal(int)   # ms
    duration_changed = Signal(int)   # ms
    playing_changed = Signal(bool)

    def __init__(self):
        super().__init__()
        self.available = False
        self._player = None
        self._out = None
        try:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

            self._out = QAudioOutput()
            self._player = QMediaPlayer()
            self._player.setAudioOutput(self._out)
            self._player.positionChanged.connect(self.position_changed)
            self._player.durationChanged.connect(self.duration_changed)
            self._player.playbackStateChanged.connect(self._on_state)
            self.available = True
        except Exception:  # noqa: BLE001 - no multimedia backend; stay disabled
            self.available = False

    def _on_state(self, state) -> None:
        from PySide6.QtMultimedia import QMediaPlayer

        self.playing_changed.emit(state == QMediaPlayer.PlayingState)

    # -- controls (all no-ops when unavailable) ----------------------------

    def load(self, path: str) -> None:
        if not self.available:
            return
        from PySide6.QtCore import QUrl

        self._player.setSource(QUrl.fromLocalFile(path))

    def play(self) -> None:
        if self.available:
            self._player.play()

    def pause(self) -> None:
        if self.available:
            self._player.pause()

    def stop(self) -> None:
        if self.available:
            self._player.stop()

    def toggle(self) -> None:
        if not self.available:
            return
        from PySide6.QtMultimedia import QMediaPlayer

        if self._player.playbackState() == QMediaPlayer.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def set_position(self, ms: int) -> None:
        if self.available:
            self._player.setPosition(int(ms))

    def duration(self) -> int:
        return self._player.duration() if self.available else 0
