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


def test_collect_stems_finds_and_copies(tmp_path):
    # Simulate a demucs output tree: <search>/htdemucs/track/<stem>.wav
    src = tmp_path / "out" / "htdemucs" / "track"
    src.mkdir(parents=True)
    for stem in stems.DEFAULT_STEMS:
        (src / f"{stem}.wav").write_bytes(b"RIFF")
    out = tmp_path / "stems" / "BeatName"

    found = stems._collect_stems(str(tmp_path / "out"), str(out))
    assert set(found.keys()) == set(stems.DEFAULT_STEMS)
    for stem in stems.DEFAULT_STEMS:
        assert (out / f"{stem}.wav").exists()


def test_collect_stems_empty_when_nothing_found(tmp_path):
    assert stems._collect_stems(str(tmp_path), str(tmp_path / "o")) == {}


def test_available_is_boolean():
    # Demucs likely not installed in the test env -> False, but must not raise.
    assert isinstance(stems.get_engine().available(), bool)
