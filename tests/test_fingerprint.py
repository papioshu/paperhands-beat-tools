"""Tests for core.fingerprint — pure grouping logic + a synthetic-audio check."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from core import fingerprint as fp  # noqa: E402


# --- pure: hamming + grouping ----------------------------------------------

def test_hamming_identical_is_zero():
    assert fp.hamming_distance("ff00", "ff00") == 0


def test_hamming_counts_differing_bits():
    assert fp.hamming_distance("00", "01") == 1
    assert fp.hamming_distance("00", "ff") == 8


def test_hamming_empty_or_mismatched_is_max():
    assert fp.hamming_distance("", "ff") == fp.FINGERPRINT_BITS
    assert fp.hamming_distance("ffff", "ff") == fp.FINGERPRINT_BITS


def test_group_duplicates_clusters_close_fingerprints():
    items = [
        (1, "ffff"), (2, "ffff"),     # identical -> group
        (3, "0000"),                  # alone
        (4, "fffe"),                  # 1 bit from group 1
    ]
    groups = fp.group_duplicates(items, max_distance=2)
    assert groups == [[1, 2, 4]]


def test_group_duplicates_respects_threshold():
    items = [(1, "ff"), (2, "0f")]    # 4 bits apart
    assert fp.group_duplicates(items, max_distance=2) == []
    assert fp.group_duplicates(items, max_distance=4) == [[1, 2]]


def test_group_ignores_empty_fingerprints():
    assert fp.group_duplicates([(1, ""), (2, "")], max_distance=10) == []


# --- synthetic audio: same beat re-encoded stays close ----------------------

def test_fingerprint_robust_to_small_changes():
    librosa = pytest.importorskip("librosa")  # noqa: F841
    import numpy as np

    sr = 22050
    rng = np.random.default_rng(0)
    base = rng.standard_normal(sr * 4).astype("float32") * 0.2
    # a "re-encode": add light noise + tiny gain change
    variant = (base + rng.standard_normal(base.size).astype("float32") * 0.005) * 0.98
    other = rng.standard_normal(sr * 4).astype("float32") * 0.2

    fa = fp.compute_fingerprint(base, sr)
    fb = fp.compute_fingerprint(variant, sr)
    fc = fp.compute_fingerprint(other, sr)

    assert fp.hamming_distance(fa, fb) < fp.hamming_distance(fa, fc)
    assert fp.hamming_distance(fa, fb) <= fp.DEFAULT_MAX_DISTANCE
