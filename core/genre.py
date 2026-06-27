"""Genre annotation: prefer the file's embedded genre tag, else a rough guess.

What the beatmaker wrote into the file's metadata is the best source, so we read
that first (via mutagen). When no tag is present we fall back to a cheap
BPM/key/feature heuristic, mirroring mood.py — honest about being approximate.

``_classify`` is pure (testable without audio); ``detect_genre`` reads the tag
then extracts features for the fallback.
"""

from __future__ import annotations

from typing import Optional, Tuple

VOCABULARY = ["lofi", "boom bap", "hip hop", "house", "trap", "drill",
              "drum & bass"]


def read_embedded_genre(path: str) -> Optional[str]:
    """Return the genre tag stored in the audio file, if any (via mutagen)."""
    try:
        from mutagen import File as MutagenFile
    except ImportError:  # mutagen optional — heuristic still works without it
        return None
    try:
        m = MutagenFile(path, easy=True)
        vals = (m.get("genre") if m else None) or []
        g = (vals[0] if vals else "").strip()
        return g or None
    except Exception:  # noqa: BLE001 - best-effort, never block analysis
        return None


def _classify(bpm, key, centroid_hz, rms) -> Tuple[str, float]:
    """Rough genre from tempo + key mode + brightness/energy. (genre, confidence).

    ponytail: BPM-bucket heuristic — won't reliably split trap from drill. The
    upgrade path is an embedded tag (preferred) or an ML classifier.
    """
    bpm = bpm or 0
    minor = (key or "").endswith("min")
    dark = centroid_hz < 1800
    energetic = rms >= 0.12

    if 0 < bpm <= 90:
        return ("boom bap", 0.4) if energetic else ("lofi", 0.4)
    if 90 < bpm <= 110:
        return "hip hop", 0.4
    if 110 < bpm <= 128:
        return "house", 0.4
    if 128 < bpm < 150:
        if bpm >= 138 and (dark or minor):
            return "drill", 0.4
        return "trap", 0.4
    if bpm >= 150:
        return "drum & bass", 0.4
    return "hip hop", 0.3


def detect_genre(path, samples, sr, key=None, bpm=None
                 ) -> Tuple[Optional[str], Optional[float]]:
    """Embedded genre tag if present (confidence 1.0), else heuristic guess."""
    embedded = read_embedded_genre(path)
    if embedded:
        return embedded, 1.0
    try:
        import librosa
        centroid = float(librosa.feature.spectral_centroid(y=samples, sr=sr).mean())
        rms = float(librosa.feature.rms(y=samples).mean())
        return _classify(bpm, key, centroid, rms)
    except Exception:  # noqa: BLE001 - best-effort
        return None, None
