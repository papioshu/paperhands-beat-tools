"""Tests for core.autoplace (pure placement modes + spacing + profiles)."""

import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import autoplace  # noqa: E402

TAGS = ["a.wav", "b.wav"]


def _pos(placements):
    return [round(p.position_sec) for p in placements]


def test_intro_mode_one_tag_at_start():
    p = autoplace.suggest_placements("intro", 120, TAGS)
    assert _pos(p) == [0]


def test_fixed_mode_interval():
    p = autoplace.suggest_placements("fixed", 130, TAGS, interval=40, min_spacing=10)
    assert _pos(p) == [0, 40, 80, 120]


def test_fixed_times_mode():
    p = autoplace.suggest_placements("fixed_times", 200, TAGS, times=[0, 45, 90])
    assert _pos(p) == [0, 45, 90]


def test_structure_mode_uses_boundaries():
    p = autoplace.suggest_placements(
        "structure", 200, TAGS, structure=[60, 120], min_spacing=10)
    assert _pos(p) == [0, 60, 120]


def test_hook_mode_uses_drop_and_hook():
    p = autoplace.suggest_placements(
        "hook", 200, TAGS, drop=30, hook=(90, 110), min_spacing=10)
    assert _pos(p) == [30, 90]


def test_min_spacing_drops_close_tags():
    # times 0,10,20 with 30s spacing -> only 0 survives
    p = autoplace.suggest_placements("fixed_times", 200, TAGS, times=[0, 10, 20],
                                     min_spacing=30)
    assert _pos(p) == [0]


def test_random_mode_respects_spacing_and_is_seeded():
    a = autoplace.suggest_placements("random", 300, TAGS, interval=40, jitter=8,
                                     min_spacing=30, rng=random.Random(1))
    b = autoplace.suggest_placements("random", 300, TAGS, interval=40, jitter=8,
                                     min_spacing=30, rng=random.Random(1))
    assert _pos(a) == _pos(b)                       # deterministic with seed
    times = [p.position_sec for p in a]
    assert all(times[i + 1] - times[i] >= 30 for i in range(len(times) - 1))


def test_tags_rotate_across_placements():
    p = autoplace.suggest_placements("fixed_times", 200, TAGS, times=[0, 45, 90],
                                     min_spacing=10)
    assert [x.tag_path for x in p] == ["a.wav", "b.wav", "a.wav"]


def test_profiles_apply():
    paperhand = autoplace.apply_profile(autoplace.PROFILES["Paperhand"], 180, TAGS)
    assert _pos(paperhand) == [0]

    standard = autoplace.apply_profile(autoplace.PROFILES["Standard"], 180, TAGS)
    assert _pos(standard) == [0, 45, 90]

    heavy = autoplace.apply_profile(
        autoplace.PROFILES["Heavy Protection"], 200, TAGS, rng=random.Random(3))
    assert len(heavy) >= 3                          # intro-ish + intervals + outro
    assert heavy[-1].position_sec > 150             # outro near the end


def test_custom_mode_returns_nothing():
    assert autoplace.suggest_placements("custom", 200, TAGS) == []
