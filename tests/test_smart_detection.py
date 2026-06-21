"""Smart detection: candidates + confidence on a synthetic beat.

Needs numpy + librosa (no ffmpeg — we synthesize samples directly).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

pytest.importorskip("librosa")

from core import detection  # noqa: E402


def _click_train(bpm: float, sr: int = 22050, seconds: int = 12):
    """A regular click train at the given BPM (perfectly steady -> high conf)."""
    sig = np.zeros(sr * seconds, dtype="float32")
    period = int(round(60.0 / bpm * sr))
    # short decaying blips so onsets are crisp
    blip = np.hanning(64).astype("float32")
    for start in range(0, sig.size - blip.size, period):
        sig[start:start + blip.size] += blip
    return sig, sr


def test_detects_tempo_with_candidates_and_confidence():
    sig, sr = _click_train(120.0)
    det = detection.detect_bpm_key(sig, sr)

    assert det.error is None
    # primary or an octave candidate lands on ~120
    all_bpm = [det.bpm, *det.bpm_candidates]
    assert any(abs(c - 120.0) < 4 for c in all_bpm if c is not None)
    # candidates include a half/double alternate
    assert len(det.bpm_candidates) >= 2
    # steady clicks -> high confidence
    assert det.bpm_confidence is not None and det.bpm_confidence > 0.7


def test_key_detection_returns_three_candidates():
    sig, sr = _click_train(100.0)
    det = detection.detect_bpm_key(sig, sr)
    assert det.key is not None
    assert len(det.key_candidates) == 3
    assert det.key in det.key_candidates
    assert det.key_confidence is not None
