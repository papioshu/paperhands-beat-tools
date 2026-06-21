"""Unit tests for core.placement — pure logic, no ffmpeg/librosa needed."""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.placement import compute_placements  # noqa: E402

TAGS = ["tagA.wav", "tagB.wav"]


def test_start_plus_intervals():
    p = compute_placements(100.0, ["t.wav"], interval_sec=40.0, tag_at_start=True)
    assert [round(x.position_sec) for x in p] == [0, 40, 80]


def test_no_start_tag_skips_zero():
    p = compute_placements(100.0, ["t.wav"], interval_sec=40.0, tag_at_start=False)
    assert [round(x.position_sec) for x in p] == [40, 80]


def test_placements_stay_inside_duration():
    p = compute_placements(45.0, ["t.wav"], interval_sec=40.0, tag_at_start=True)
    assert all(0.0 <= x.position_sec < 45.0 for x in p)
    assert [round(x.position_sec) for x in p] == [0, 40]


def test_before_drop_offsets_the_anchor():
    p = compute_placements(
        100.0, ["t.wav"], interval_sec=40.0, tag_at_start=True, start_offset_sec=8.0
    )
    assert [round(x.position_sec) for x in p] == [8, 48, 88]


def test_no_tags_means_no_placements():
    assert compute_placements(100.0, [], interval_sec=40.0) == []


def test_zero_duration_means_no_placements():
    assert compute_placements(0.0, ["t.wav"], interval_sec=40.0) == []


def test_interval_must_be_positive():
    import pytest

    with pytest.raises(ValueError):
        compute_placements(100.0, ["t.wav"], interval_sec=0)


def test_jitter_is_deterministic_with_seed():
    a = compute_placements(
        200.0, TAGS, interval_sec=40.0, jitter_sec=3.0, rng=random.Random(42)
    )
    b = compute_placements(
        200.0, TAGS, interval_sec=40.0, jitter_sec=3.0, rng=random.Random(42)
    )
    assert [(x.position_sec, x.tag_path) for x in a] == [
        (x.position_sec, x.tag_path) for x in b
    ]


def test_jitter_stays_within_bounds():
    p = compute_placements(
        200.0, ["t.wav"], interval_sec=40.0, jitter_sec=3.0, rng=random.Random(1)
    )
    # First spot is the un-jittered anchor at 0; the rest within +/-3 of multiples.
    for i, spot in enumerate(p[1:], start=1):
        expected = 40.0 * i
        assert abs(spot.position_sec - expected) <= 3.0 + 1e-6


def test_tag_rotation_uses_all_tags_over_many_spots():
    p = compute_placements(
        1000.0, TAGS, interval_sec=40.0, jitter_sec=0.0, rng=random.Random(7)
    )
    used = {x.tag_path for x in p}
    assert used == set(TAGS)
