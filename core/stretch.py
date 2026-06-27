"""Tempo-aware tag time-stretching.

Two pure-ish pieces:
  * ``compute`` — ratio math from beat/tag BPM, with safe limits and a
    half/double-time suggestion when a normal stretch would be too extreme.
  * ``stretch_segment`` — apply a stretch ratio to a pydub AudioSegment,
    pitch-preserving by default (librosa phase vocoder) or pitch-shifting
    "tape" style (resample) when ``preserve_pitch=False``.

The original tag file is never touched — callers stretch the in-memory segment.
``compute`` needs no audio libraries (unit-tested headless).
"""

from __future__ import annotations

from typing import Optional

LIMITS = (0.85, 1.25)               # safe normal-mode stretch range
_MODE_FACTOR = {"normal": 1.0, "half": 0.5, "double": 2.0}


def compute(beat_bpm: Optional[float], tag_bpm: Optional[float],
            mode: str = "normal", limits=LIMITS) -> dict:
    """Stretch ratio to lock a tag (``tag_bpm``) to a beat (``beat_bpm``).

    ``mode`` shifts the tag's effective tempo: normal=x1, half=x0.5, double=x2,
    so a 70-BPM tag can fit a 140-BPM beat in double-time at ratio ~1.0.

    Returns ``{ratio, in_limits, suggestion}``. ``suggestion`` is "half"/"double"
    when a normal stretch falls outside ``limits`` (else None).
    """
    if not beat_bpm or not tag_bpm or tag_bpm <= 0:
        return {"ratio": 1.0, "in_limits": True, "suggestion": None}
    effective = tag_bpm * _MODE_FACTOR.get(mode, 1.0)
    ratio = beat_bpm / effective
    lo, hi = limits
    in_limits = lo <= ratio <= hi
    suggestion = None
    if mode == "normal" and not in_limits:
        suggestion = "double" if ratio > hi else "half"
    return {"ratio": ratio, "in_limits": in_limits, "suggestion": suggestion}


def stretch_segment(seg, ratio: float, preserve_pitch: bool = True):
    """Return a copy of ``seg`` sped up/slowed by ``ratio`` (rate > 1 = faster).

    No-op for ratios within 0.001 of 1.0. Ratio is hard-clamped to [0.1, 10] as a
    final safety rail regardless of caller limits.
    """
    if not ratio or abs(ratio - 1.0) < 1e-3:
        return seg
    ratio = max(0.1, min(10.0, ratio))

    if not preserve_pitch:
        # Tape effect: reinterpret the samples at a new rate (pitch tracks speed).
        new_fr = int(seg.frame_rate * ratio)
        return seg._spawn(seg.raw_data, overrides={"frame_rate": new_fr}) \
            .set_frame_rate(seg.frame_rate)

    try:
        import numpy as np
        import librosa
    except ImportError:  # no librosa -> leave the tag unstretched
        return seg

    ch = seg.channels
    samples = np.array(seg.get_array_of_samples())
    max_int = float(1 << (8 * seg.sample_width - 1)) or 1.0
    y = samples.astype("float32") / max_int
    if ch > 1:
        y = y.reshape((-1, ch)).T          # (channels, n)
    stretched = librosa.effects.time_stretch(y, rate=ratio)
    if ch > 1:
        stretched = stretched.T.reshape(-1)
    out_int = np.clip(stretched, -1.0, 1.0)
    out_int = (out_int * max_int).astype(samples.dtype)
    return seg._spawn(out_int.tobytes())
