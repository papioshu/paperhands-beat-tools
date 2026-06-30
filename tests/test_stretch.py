"""Tempo-match ratio math + segment time-stretching."""

import pytest

from core import stretch


def test_compute_normal_in_limits():
    r = stretch.compute(140, 140, "normal")
    assert r["ratio"] == 1.0 and r["in_limits"] and r["suggestion"] is None


def test_compute_suggests_half_when_too_fast():
    # Normal match too fast -> slow it down with half-time.
    r = stretch.compute(140, 70, "normal")
    assert r["ratio"] == 2.0 and not r["in_limits"] and r["suggestion"] == "half"


def test_compute_suggests_double_when_too_slow():
    # Normal match too slow -> speed it up with double-time.
    r = stretch.compute(60, 120, "normal")
    assert r["ratio"] == 0.5 and r["suggestion"] == "double"


def test_compute_double_time_fits():
    # 120-BPM tag over a 60-BPM beat: normal=0.5 (too slow), double-time = 1.0.
    r = stretch.compute(60, 120, "double")
    assert r["ratio"] == 1.0 and r["in_limits"]


def test_mode_speed_is_literal():
    # Same tag+beat: double-time is faster than half-time (the user-facing fix).
    assert stretch.compute(140, 140, "double")["ratio"] == 2.0   # twice as fast
    assert stretch.compute(140, 140, "half")["ratio"] == 0.5     # half speed


def test_compute_missing_bpm_is_noop():
    assert stretch.compute(None, 140)["ratio"] == 1.0
    assert stretch.compute(140, 0)["ratio"] == 1.0


def test_stretch_segment_noop_at_one():
    seg = pytest.importorskip("pydub").AudioSegment.silent(duration=1000)
    assert stretch.stretch_segment(seg, 1.0) is seg


def test_stretch_segment_negligible_ratio_is_noop():
    # A ~1% ratio rounds to "1.00x" in the UI and is inaudible as tempo, so it
    # must NOT be phase-vocoded (that warble was the "all tags sound slowed" bug).
    seg = pytest.importorskip("pydub").AudioSegment.silent(duration=1000)
    assert stretch.stretch_segment(seg, 0.99) is seg
    assert stretch.stretch_segment(seg, 1.01) is seg


def test_stretch_segment_tape_halves_length():
    seg = pytest.importorskip("pydub").AudioSegment.silent(duration=1000)
    out = stretch.stretch_segment(seg, 2.0, preserve_pitch=False)
    assert 480 <= len(out) <= 520        # ~500ms at 2x speed


def test_stretch_segment_preserve_pitch_halves_length():
    pytest.importorskip("librosa")
    seg = pytest.importorskip("pydub").AudioSegment.silent(duration=1000)
    out = stretch.stretch_segment(seg, 2.0, preserve_pitch=True)
    assert len(out) < 700 and len(out) > 300   # phase-vocoder length is approximate
