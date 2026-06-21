"""Downsample audio to a compact peak array for drawing waveforms.

The expensive decode happens once (on analysis); we cache a small ``.npy`` peak
array to disk and the player just paints it. ``compute_peaks`` is pure numpy and
unit-tested; the file helpers wrap it with I/O.
"""

from __future__ import annotations

from typing import Optional


def compute_peaks(samples, buckets: int = 1000):
    """Reduce a 1-D signal to ``buckets`` peak magnitudes in [0, 1].

    Each bucket holds the maximum absolute amplitude of its slice, so the drawn
    waveform preserves transients. Returns a float32 array of length
    ``min(buckets, len(samples))`` (or empty for empty input).
    """
    import numpy as np

    samples = np.asarray(samples, dtype="float32")
    if samples.size == 0:
        return np.zeros(0, dtype="float32")

    buckets = max(1, min(buckets, samples.size))
    # Split into ~equal chunks; take max(abs) of each.
    chunks = np.array_split(np.abs(samples), buckets)
    peaks = np.array([float(c.max()) if c.size else 0.0 for c in chunks], dtype="float32")

    peak = float(peaks.max())
    if peak > 0:
        peaks /= peak  # normalize to 0..1 for consistent drawing
    return peaks


def save_peaks(path: str, peaks) -> None:
    import numpy as np

    np.save(path, np.asarray(peaks, dtype="float32"))


def load_peaks(path: str):
    import numpy as np

    return np.load(path)


def generate_peaks_file(samples, out_path: str, buckets: int = 1000) -> str:
    """Compute peaks from samples and save them. Returns the saved path.

    ``np.save`` appends ``.npy`` if missing; we normalize the return value so the
    caller stores the real path.
    """
    peaks = compute_peaks(samples, buckets)
    save_peaks(out_path, peaks)
    return out_path if out_path.endswith(".npy") else out_path + ".npy"
