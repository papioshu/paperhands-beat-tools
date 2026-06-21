"""Structure / drop / hook detection on synthetic audio (needs librosa)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

pytest.importorskip("librosa")

from core import structure  # noqa: E402


def _tone(freq, sr, seconds, amp=0.3):
    t = np.linspace(0, seconds, int(sr * seconds), endpoint=False)
    return (amp * np.sin(2 * np.pi * freq * t)).astype("float32")


def test_structure_finds_a_boundary_at_the_change():
    sr = 22050
    sig = np.concatenate([_tone(110, sr, 10), _tone(440, sr, 10)])  # change at 10s
    bounds = structure.detect_structure(sig, sr)
    assert bounds, "expected at least one boundary"
    assert any(abs(b - 10.0) < 3.0 for b in bounds)


def test_short_clip_returns_no_structure():
    sr = 22050
    assert structure.detect_structure(_tone(220, sr, 4), sr) == []


def test_drop_detects_energy_lift():
    sr = 22050
    # quiet intro then loud section at 10s
    sig = np.concatenate([_tone(220, sr, 10, amp=0.05), _tone(220, sr, 10, amp=0.6)])
    drop = structure.detect_drop(sig, sr)
    assert drop is not None
    assert abs(drop - 10.0) < 3.0


def test_hook_returns_a_span():
    sr = 22050
    sig = np.concatenate([_tone(220, sr, 10, amp=0.1), _tone(220, sr, 10, amp=0.6)])
    hook = structure.detect_hook(sig, sr)
    assert hook is not None
    start, end = hook
    assert end > start
