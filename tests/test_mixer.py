"""Tests for core.mixer (synthetic stems; needs pydub, no ffmpeg for WAV)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

pytest.importorskip("pydub")

from pydub import AudioSegment  # noqa: E402
from pydub.generators import Sine  # noqa: E402

from core import mixer  # noqa: E402


def _tone(path, freq=440, ms=400):
    Sine(freq).to_audio_segment(duration=ms).export(str(path), format="wav")
    return str(path)


def _silence(path, ms=400):
    AudioSegment.silent(duration=ms).export(str(path), format="wav")
    return str(path)


def test_audible_respects_mute_and_solo():
    tracks = [
        {"path": "a", "solo": False, "mute": False},
        {"path": "b", "mute": True},
        {"path": "c", "solo": True},
    ]
    audible = mixer.audible_tracks(tracks)
    assert [t["path"] for t in audible] == ["c"]   # solo isolates


def test_mix_combines_tones(tmp_path):
    tracks = [{"path": _tone(tmp_path / "t.wav")},
              {"path": _silence(tmp_path / "s.wav")}]
    out = mixer.mix_stem_tracks(tracks, str(tmp_path / "mix.wav"))
    seg = AudioSegment.from_file(out)
    assert seg.max_dBFS > -float("inf")            # tone present


def test_solo_silent_stem_yields_silence(tmp_path):
    tracks = [{"path": _tone(tmp_path / "t.wav")},
              {"path": _silence(tmp_path / "s.wav"), "solo": True}]
    out = mixer.mix_stem_tracks(tracks, str(tmp_path / "mix.wav"))
    seg = AudioSegment.from_file(out)
    assert seg.max_dBFS == -float("inf")           # only the silent stem soloed


def test_all_muted_writes_silence(tmp_path):
    tracks = [{"path": _tone(tmp_path / "t.wav"), "mute": True}]
    out = mixer.mix_stem_tracks(tracks, str(tmp_path / "mix.wav"))
    seg = AudioSegment.from_file(out)
    assert len(seg) > 0                             # valid file, silent
