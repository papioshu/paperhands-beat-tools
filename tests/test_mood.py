"""Tests for core.mood._classify (pure rule logic, no audio)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import mood  # noqa: E402


def test_loud_and_fast_is_aggressive():
    m, conf = mood._classify(centroid_hz=3000, rms=0.2, key="Fmin", bpm=150)
    assert m == "aggressive"
    assert 0 < conf <= 1


def test_minor_and_dim_is_dark():
    m, _ = mood._classify(centroid_hz=1000, rms=0.08, key="Amin", bpm=120)
    assert m == "dark"


def test_major_and_bright_is_uplifting():
    m, _ = mood._classify(centroid_hz=3000, rms=0.08, key="Cmaj", bpm=120)
    assert m == "uplifting"


def test_calm_is_chill():
    m, _ = mood._classify(centroid_hz=1800, rms=0.03, key="", bpm=None)
    assert m == "chill"


def test_default_is_melodic():
    m, _ = mood._classify(centroid_hz=2000, rms=0.09, key="", bpm=110)
    assert m == "melodic"


def test_all_outputs_are_in_vocabulary():
    for cent in (800, 2000, 3200):
        for rms in (0.03, 0.1, 0.2):
            for key in ("", "Amin", "Cmaj"):
                for bpm in (None, 80, 150):
                    m, _ = mood._classify(cent, rms, key, bpm)
                    assert m in mood.VOCABULARY
