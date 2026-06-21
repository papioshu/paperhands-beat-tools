"""Tests for tag_beats CLI arg parsing -> config wiring (no ffmpeg needed)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tag_beats  # noqa: E402


def test_defaults_map_to_config():
    args = tag_beats.parse_args([])
    cfg = tag_beats.config_from_args(args)
    assert cfg.interval_sec == 40.0
    assert cfg.tag_at_start is True
    assert cfg.before_drop is False
    assert cfg.bitrate == "320k"
    assert cfg.duck_db == 6.0
    assert cfg.detect is True


def test_flags_override_config():
    args = tag_beats.parse_args(
        ["--interval", "35", "--jitter", "4", "--no-start",
         "--before-drop", "--bpm", "140", "--key", "F#min",
         "--duck-db", "4", "--bitrate", "256k", "--seed", "7"]
    )
    cfg = tag_beats.config_from_args(args)
    assert cfg.interval_sec == 35.0
    assert cfg.jitter_sec == 4.0
    assert cfg.tag_at_start is False
    assert cfg.before_drop is True
    assert cfg.bpm_override == 140.0
    assert cfg.key_override == "F#min"
    assert cfg.duck_db == 4.0
    assert cfg.bitrate == "256k"
    assert cfg.seed == 7


def test_no_detect_disables_detection():
    args = tag_beats.parse_args(["--no-detect"])
    assert tag_beats.config_from_args(args).detect is False
