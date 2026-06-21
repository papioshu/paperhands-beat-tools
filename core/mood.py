"""Heuristic mood suggestion (the roughest analyzer — treat as a hint).

Maps a few cheap features — spectral brightness, energy, key mode, tempo — onto a
small mood vocabulary with rule-of-thumb thresholds. It is intentionally honest
about being approximate: confidence stays low and the suggestion only pre-fills
an *empty* mood field, which the user freely overrides.

``_classify`` is pure (testable without audio); ``detect_mood`` extracts the
features then calls it.
"""

from __future__ import annotations

from typing import Optional, Tuple

VOCABULARY = ["aggressive", "dark", "uplifting", "chill", "bright", "melodic"]


def _classify(centroid_hz: float, rms: float,
              key: Optional[str], bpm: Optional[float]) -> Tuple[str, float]:
    """Rule-based mood from features. Returns (mood, confidence 0..1)."""
    key = (key or "").strip()
    minor = key.endswith("min")
    major = key.endswith("maj")
    fast = bool(bpm) and bpm >= 140
    slow = bool(bpm) and bpm <= 90
    bright = centroid_hz >= 2500
    dim = centroid_hz < 1500
    energetic = rms >= 0.12
    calm = rms < 0.06

    if energetic and fast:
        return "aggressive", 0.5
    if minor and (dim or calm):
        return "dark", 0.55
    if major and (bright or fast):
        return "uplifting", 0.5
    if calm or slow:
        return "chill", 0.5
    if bright:
        return "bright", 0.45
    return "melodic", 0.4


def detect_mood(samples, sr: int, key: Optional[str] = None,
                bpm: Optional[float] = None) -> Tuple[Optional[str], Optional[float]]:
    """Suggest a mood for the audio. Returns (mood, confidence) or (None, None)."""
    try:
        import numpy as np  # noqa: F401
        import librosa
    except ImportError:  # pragma: no cover
        return None, None
    try:
        centroid = float(librosa.feature.spectral_centroid(y=samples, sr=sr).mean())
        rms = float(librosa.feature.rms(y=samples).mean())
        return _classify(centroid, rms, key, bpm)
    except Exception:  # noqa: BLE001 - best-effort
        return None, None
