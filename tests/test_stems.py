"""Tests for core.stems pure parts (engine registry, collect, graceful)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import stems  # noqa: E402


def test_get_engine_default_is_demucs():
    eng = stems.get_engine()
    assert eng.name == "Demucs"
    assert eng.install_command()[-1] == "demucs"


def test_unknown_engine_falls_back_to_demucs():
    assert stems.get_engine("Nope").name == "Demucs"


def test_engine_uses_selected_model():
    assert stems.get_engine("Demucs", "htdemucs_ft").model_name == "htdemucs_ft"


def test_available_is_boolean():
    # Demucs likely not installed in the test env -> False, but must not raise.
    assert isinstance(stems.get_engine().available(), bool)
