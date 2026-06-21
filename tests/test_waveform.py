"""Unit tests for core.waveform.compute_peaks (pure numpy, no ffmpeg)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from core import waveform  # noqa: E402


def test_peaks_length_matches_buckets():
    sig = np.sin(np.linspace(0, 100, 50_000)).astype("float32")
    peaks = waveform.compute_peaks(sig, buckets=200)
    assert len(peaks) == 200


def test_peaks_are_normalized_0_to_1():
    sig = (np.random.rand(10_000) * 2 - 1).astype("float32") * 0.3
    peaks = waveform.compute_peaks(sig, buckets=100)
    assert peaks.min() >= 0.0
    assert peaks.max() == pytest.approx(1.0)  # normalized so loudest bucket = 1


def test_peaks_capture_a_transient():
    sig = np.zeros(10_000, dtype="float32")
    sig[5000] = 1.0  # single spike in the middle
    peaks = waveform.compute_peaks(sig, buckets=100)
    assert peaks.argmax() == 50  # spike lands in the middle bucket


def test_empty_input_returns_empty():
    assert waveform.compute_peaks(np.zeros(0)).size == 0


def test_fewer_samples_than_buckets():
    peaks = waveform.compute_peaks(np.array([0.1, -0.9, 0.2]), buckets=1000)
    assert len(peaks) == 3
    assert peaks.max() == pytest.approx(1.0)


def test_save_and_load_roundtrip(tmp_path):
    sig = np.sin(np.linspace(0, 50, 20_000)).astype("float32")
    peaks = waveform.compute_peaks(sig, buckets=300)
    out = waveform.generate_peaks_file(sig, str(tmp_path / "p"), buckets=300)
    assert Path(out).exists()
    loaded = waveform.load_peaks(out)
    assert np.allclose(loaded, peaks)
