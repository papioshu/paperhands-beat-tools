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
        self._init_error = ""
        self._player = None
        self._out = None
        try:
            from PySide6.QtMultimedia import QAudioOutput, QMediaPlayer

            self._out = QAudioOutput()
            self._player = QMediaPlayer()
            self._player.setAudioOutput(self._out)
            # Forward via callables, NOT signal-to-signal: QMediaPlayer's
            # position/duration signals carry qlonglong (64-bit), which won't
            # connect to a Signal(int) and would disable the whole player.
            self._player.positionChanged.connect(self._emit_position)
            self._player.durationChanged.connect(self._emit_duration)
            self._player.playbackStateChanged.connect(self._on_state)
            self.available = True
        except Exception as exc:  # noqa: BLE001 - degrade, but remember why
            self._init_error = f"{type(exc).__name__}: {exc}"
            self.available = False

    def _emit_position(self, ms) -> None:
        self.position_changed.emit(int(ms))

    def _emit_duration(self, ms) -> None:
        self.duration_changed.emit(int(ms))

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
