"""Audio fingerprinting for duplicate detection.

A perceptual hash (pHash) of the mel-spectrogram: reduce the spectrogram to a
fixed ``mel_bins x time_bins`` grid, threshold each cell against the grid median,
and pack the bits. Re-encodes / renames of the same beat produce nearly identical
hashes (small Hamming distance), while different beats are far apart.

``compute_fingerprint`` needs numpy + librosa; the comparison/grouping helpers
are pure and unit-tested without them.
"""

from __future__ import annotations

from typing import List, Sequence, Tuple

_MEL_BINS = 16
_TIME_BINS = 32          # 16 * 32 = 512-bit fingerprint
FINGERPRINT_BITS = _MEL_BINS * _TIME_BINS
# Default tolerance: two beats are "the same audio" within ~10% differing bits.
DEFAULT_MAX_DISTANCE = FINGERPRINT_BITS // 10


def compute_fingerprint(samples, sr: int) -> str:
    """Return a hex pHash of the audio (length-independent grid)."""
    import numpy as np
    import librosa

    spec = librosa.feature.melspectrogram(y=samples, sr=sr, n_mels=_MEL_BINS)
    spec = librosa.power_to_db(spec)
    if spec.shape[1] == 0:
        return ""
    # Aggregate the time axis to a fixed number of bins (length-independent).
    cols = np.array_split(spec, _TIME_BINS, axis=1)
    grid = np.stack([c.mean(axis=1) for c in cols], axis=1)   # mel x time
    bits = (grid > np.median(grid)).flatten()
    return np.packbits(bits).tobytes().hex()


def hamming_distance(a_hex: str, b_hex: str) -> int:
    """Number of differing bits between two hex fingerprints (large if mismatched)."""
    if not a_hex or not b_hex:
        return FINGERPRINT_BITS
    a = bytes.fromhex(a_hex)
    b = bytes.fromhex(b_hex)
    if len(a) != len(b):
        return FINGERPRINT_BITS
    return sum(bin(x ^ y).count("1") for x, y in zip(a, b))


def group_duplicates(
    items: Sequence[Tuple[int, str]],
    max_distance: int = DEFAULT_MAX_DISTANCE,
) -> List[List[int]]:
    """Cluster ids whose fingerprints are within ``max_distance`` of each other.

    Args:
        items: ``(beat_id, fingerprint_hex)`` pairs. Empty fingerprints are ignored.
    Returns:
        Groups (each a sorted list of ids) with two or more members. Single beats
        are omitted.
    """
    valid = [(bid, fp) for bid, fp in items if fp]
    parent = {bid: bid for bid, _ in valid}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        parent[find(x)] = find(y)

    for i in range(len(valid)):
        for j in range(i + 1, len(valid)):
            if hamming_distance(valid[i][1], valid[j][1]) <= max_distance:
                union(valid[i][0], valid[j][0])

    clusters = {}
    for bid, _ in valid:
        clusters.setdefault(find(bid), []).append(bid)
    return sorted(
        (sorted(group) for group in clusters.values() if len(group) > 1),
        key=lambda g: g[0],
    )
