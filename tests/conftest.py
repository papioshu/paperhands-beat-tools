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
