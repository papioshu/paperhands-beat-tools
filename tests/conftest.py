"""Shared test fixtures.

Isolate app settings from the real machine: the GUI reads watched folders,
producer name, stem model, etc. from QSettings (the Windows registry in normal
mode). Without isolation a test that constructs MainWindow would scan the user's
real watched folders and import their whole music library into the test db. Each
test gets a fresh, throwaway settings file instead.
"""

import pytest


@pytest.fixture(autouse=True)
def _isolate_settings(tmp_path_factory, monkeypatch):
    try:
        from PySide6.QtCore import QSettings
    except Exception:        # no Qt in this env -> pure tests, nothing to isolate
        return
    ini = tmp_path_factory.mktemp("settings") / "app.ini"
    store = QSettings(str(ini), QSettings.IniFormat)
    monkeypatch.setattr("app.config._settings", lambda: store, raising=False)


@pytest.fixture(autouse=True)
def _mute_audio(monkeypatch):
    """Keep the test suite silent. Qt's audio output still plays under the
    offscreen platform, so GUI tests that hit play()/play_tag() would blast
    real tag/beat audio out the default device. Mute every player's output."""
    try:
        from app.ui import player as player_mod
    except Exception:        # no Qt -> pure tests, nothing to mute
        return
    orig_init = player_mod.AudioPlayer.__init__

    def muted_init(self, *args, **kwargs):
        orig_init(self, *args, **kwargs)
        if getattr(self, "available", False):
            try:
                self._out.setMuted(True)
                self._tag_out.setMuted(True)
            except Exception:
                pass

    monkeypatch.setattr(player_mod.AudioPlayer, "__init__", muted_init)
