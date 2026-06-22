"""Tests for core.session (build/save/load/history, pure)."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import session  # noqa: E402


def test_build_session_has_all_fields():
    s = session.build_session("Beat_140BPM_Fmin", bpm=140, key="Fmin",
                              duration=180.0, source_master="masters/x.wav",
                              stems={"drums": "stems/drums.wav"})
    assert s["beat_name"] == "Beat_140BPM_Fmin"
    assert s["bpm"] == 140
    assert s["stems"]["drums"] == "stems/drums.wav"
    assert s["tag_placements"] == [] and s["tracks"] == {}
    assert s["export_history"] == []


def test_save_and_load_roundtrip(tmp_path):
    s = session.build_session(
        "Night", bpm=92, key="Cmaj",
        tracks={"vocals": {"mute": True, "solo": False, "volume_db": -3.0, "pan": 0.2}},
        tag_placements=[{"pos": 3.0, "tag": "tag.wav"}])
    path = session.session_path(str(tmp_path), "Night")
    session.save_session(path, s)
    assert Path(path).exists()
    assert path.endswith("Night.session.json")

    loaded = session.load_session(path)
    assert loaded["tracks"]["vocals"]["mute"] is True
    assert loaded["tag_placements"][0]["pos"] == 3.0


def test_load_missing_returns_empty(tmp_path):
    assert session.load_session(str(tmp_path / "nope.json")) == {}


def test_record_export_appends_history():
    s = session.build_session("X")
    session.record_export(s, "Tagged Preview", "previews/X_TAGGED.mp3")
    session.record_export(s, "Buyer Package", "packages/X.zip")
    assert [e["type"] for e in s["export_history"]] == ["Tagged Preview", "Buyer Package"]
    assert all("time" in e for e in s["export_history"])
