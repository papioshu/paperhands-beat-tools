"""Unit tests for core.naming — pure logic, no ffmpeg/librosa needed."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import naming  # noqa: E402


# --- format_key_for_filename ------------------------------------------------

def test_sharp_key_becomes_word():
    assert naming.format_key_for_filename("F#min") == "Fsharpmin"


def test_flat_key_becomes_word():
    assert naming.format_key_for_filename("Bbmaj") == "Bflatmaj"


def test_flat_b_does_not_eat_the_note_b():
    # "Bmin" -> note B, no accidental, minor
    assert naming.format_key_for_filename("Bmin") == "Bmin"


def test_spelled_out_quality_is_shortened():
    assert naming.format_key_for_filename("A minor") == "Amin"
    assert naming.format_key_for_filename("G major") == "Gmaj"


def test_empty_key_is_empty():
    assert naming.format_key_for_filename("") == ""


# --- token detection --------------------------------------------------------

def test_detects_existing_bpm_token():
    assert naming.has_bpm_token("Midnight_140BPM")
    assert naming.has_bpm_token("beat 92 bpm")
    assert not naming.has_bpm_token("Midnight")


def test_detects_existing_key_token():
    assert naming.has_key_token("Midnight_Fsharpmin")
    assert naming.has_key_token("track_F#min")
    assert naming.has_key_token("loop_Amin")
    assert not naming.has_key_token("Midnight")


# --- build_output_stem ------------------------------------------------------

def test_appends_bpm_key_and_suffix():
    assert (
        naming.build_output_stem("Midnight", bpm=140, key="F#min")
        == "Midnight_140BPM_Fsharpmin_tagged"
    )


def test_does_not_duplicate_existing_bpm_or_key():
    # Source already labelled — only the suffix is added.
    assert (
        naming.build_output_stem("Midnight_140BPM_Fsharpmin", bpm=140, key="F#min")
        == "Midnight_140BPM_Fsharpmin_tagged"
    )


def test_partial_existing_tokens_only_fills_gaps():
    # Has BPM already, missing key -> append only the key.
    assert (
        naming.build_output_stem("Beat_140BPM", bpm=140, key="Amin")
        == "Beat_140BPM_Amin_tagged"
    )


def test_missing_detection_skips_those_tokens():
    assert naming.build_output_stem("Beat", bpm=None, key=None) == "Beat_tagged"


def test_suffix_is_not_doubled():
    assert naming.build_output_stem("Beat_tagged", bpm=None, key=None) == "Beat_tagged"


def test_bpm_is_rounded_to_int():
    assert naming.build_output_stem("Beat", bpm=139.6, key=None) == "Beat_140BPM_tagged"
