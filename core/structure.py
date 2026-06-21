"""Song-structure analysis: section boundaries, drop, and hook (best-effort).

These are *approximate* — they read musical change from spectral self-similarity
and energy, not from a score. Treat the results as helpful guides, not ground
truth, and always allow manual override. ``numpy``/``librosa`` are imported
lazily so importing this module stays cheap.
"""

from __future__ import annotations

from typing import List, Optional


def detect_structure(samples, sr: int, max_sections: int = 8) -> List[float]:
    """Return interior section-boundary times (seconds), sorted.

    Segments the track by clustering chroma + MFCC frames; the number of sections
    scales with duration (≈ one every 20s), clamped to ``[2, max_sections]``.
    Returns an empty list if the track is too short or analysis fails.
    """
    try:
        import numpy as np
        import librosa
    except ImportError:  # pragma: no cover
        return []

    try:
        dur = len(samples) / sr
        if dur < 8:
            return []
        chroma = librosa.feature.chroma_cqt(y=samples, sr=sr)
        mfcc = librosa.feature.mfcc(y=samples, sr=sr, n_mfcc=13)
        feats = np.vstack([
            librosa.util.normalize(chroma, axis=1),
            librosa.util.normalize(mfcc, axis=1),
        ])
        k = int(max(2, min(max_sections, round(dur / 20))))
        bound_frames = librosa.segment.agglomerative(feats, k)
        times = librosa.frames_to_time(bound_frames, sr=sr)
        return sorted({round(float(t), 2) for t in times if 1.0 < t < dur - 1.0})
    except Exception:  # noqa: BLE001 - best-effort
        return []


def _section_energy(samples, sr, boundaries):
    """Mean RMS energy of each section delimited by ``boundaries`` (+ start/end)."""
    import numpy as np
    import librosa

    dur = len(samples) / sr
    edges = [0.0, *boundaries, dur]
    rms = librosa.feature.rms(y=samples)[0]
    times = librosa.times_like(rms, sr=sr)
    energies = []
    for a, b in zip(edges[:-1], edges[1:]):
        mask = (times >= a) & (times < b)
        energies.append((a, b, float(rms[mask].mean()) if mask.any() else 0.0))
    return energies


def detect_drop(samples, sr: int, boundaries: Optional[List[float]] = None) -> Optional[float]:
    """Best-effort first 'drop' time: the boundary with the biggest energy jump.

    Falls back to ``None`` when there's no clear lift in energy across a boundary.
    """
    try:
        import numpy as np  # noqa: F401
        import librosa  # noqa: F401
    except ImportError:  # pragma: no cover
        return None
    try:
        if boundaries is None:
            boundaries = detect_structure(samples, sr)
        if not boundaries:
            return None
        energies = _section_energy(samples, sr, boundaries)
        best_time, best_jump = None, 0.0
        for (prev, cur) in zip(energies[:-1], energies[1:]):
            jump = cur[2] - prev[2]            # energy rise entering this section
            if jump > best_jump:
                best_jump, best_time = jump, cur[0]
        # Require a meaningful lift over the quietest section.
        floor = min(e[2] for e in energies) or 1e-9
        if best_time is not None and best_jump > floor * 0.5:
            return round(best_time, 2)
        return None
    except Exception:  # noqa: BLE001
        return None


def detect_hook(samples, sr: int, boundaries: Optional[List[float]] = None):
    """Best-effort hook: the highest-energy section, as ``(start, end)`` seconds."""
    try:
        import numpy as np  # noqa: F401
        import librosa  # noqa: F401
    except ImportError:  # pragma: no cover
        return None
    try:
        if boundaries is None:
            boundaries = detect_structure(samples, sr)
        energies = _section_energy(samples, sr, boundaries)
        if not energies:
            return None
        a, b, _ = max(energies, key=lambda e: e[2])
        return (round(a, 2), round(b, 2))
    except Exception:  # noqa: BLE001
        return None
