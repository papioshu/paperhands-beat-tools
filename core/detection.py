"""Automatic BPM, musical-key, and best-effort "first drop" detection.

Heavy deps (numpy, librosa) are imported lazily inside the functions so that
importing this module never forces them on callers who only want type hints.

Honest caveats:
* BPM detection is solid for steady beats, shaky for rubato / half-time feels.
* Key detection (Krumhansl-Schmuckler profile correlation) is a best guess.
* First-drop detection is a crude energy heuristic — useful, not authoritative.
Always allow manual override.
"""

from __future__ import annotations

from typing import Optional

from .models import DetectionResult

# Krumhansl-Schmuckler key profiles (major / minor), indexed from the tonic.
_MAJOR_PROFILE = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
_MINOR_PROFILE = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
_NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def detect_bpm_key(samples, sr: int) -> DetectionResult:
    """Detect BPM and musical key from a mono float32 signal.

    Args:
        samples: 1-D numpy float array in roughly [-1, 1].
        sr: Sample rate in Hz.

    Returns:
        DetectionResult with bpm/key filled where possible; ``error`` set (and the
        other fields left ``None``) if analysis raised.
    """
    try:
        import numpy as np
        import librosa
    except ImportError as exc:  # pragma: no cover - environment guard
        return DetectionResult(error=f"missing dependency: {exc.name}")

    try:
        bpm = _detect_bpm(librosa, np, samples, sr)
        key = _detect_key(librosa, np, samples, sr)
        return DetectionResult(bpm=bpm, key=key)
    except Exception as exc:  # noqa: BLE001 - detection is best-effort, never fatal
        return DetectionResult(error=str(exc))


def _detect_bpm(librosa, np, samples, sr: int) -> Optional[float]:
    tempo, _ = librosa.beat.beat_track(y=samples, sr=sr)
    tempo = float(np.atleast_1d(tempo)[0])
    return round(tempo, 1) if tempo > 0 else None


def _detect_key(librosa, np, samples, sr: int) -> Optional[str]:
    chroma = librosa.feature.chroma_cqt(y=samples, sr=sr)
    profile = chroma.mean(axis=1)  # 12-vector, energy per pitch class
    if not np.any(profile):
        return None

    major = np.array(_MAJOR_PROFILE)
    minor = np.array(_MINOR_PROFILE)

    best_score = -1.0
    best_key = None
    for tonic in range(12):
        rotated = np.roll(profile, -tonic)
        maj_score = float(np.corrcoef(rotated, major)[0, 1])
        min_score = float(np.corrcoef(rotated, minor)[0, 1])
        if maj_score > best_score:
            best_score, best_key = maj_score, f"{_NOTE_NAMES[tonic]}maj"
        if min_score > best_score:
            best_score, best_key = min_score, f"{_NOTE_NAMES[tonic]}min"
    return best_key


def detect_first_drop(samples, sr: int) -> Optional[float]:
    """Best-effort guess at the first "drop" time, in seconds.

    Heuristic: track short-time RMS energy, then return the first moment energy
    climbs above the quiet-intro baseline by a clear margin. Returns ``None`` if
    nothing convincing is found (caller should fall back to 0:00).
    """
    try:
        import numpy as np
        import librosa
    except ImportError:  # pragma: no cover - environment guard
        return None

    try:
        hop = 512
        rms = librosa.feature.rms(y=samples, hop_length=hop)[0]
        if rms.size < 4:
            return None
        times = librosa.frames_to_time(np.arange(rms.size), sr=sr, hop_length=hop)

        # Baseline = median of the quietest 25% of frames; "loud" = well above it.
        baseline = float(np.percentile(rms, 25))
        peak = float(rms.max())
        if peak <= 0 or peak < baseline * 1.8:
            return None  # fairly flat dynamics -> no obvious drop
        threshold = baseline + 0.5 * (peak - baseline)

        loud = np.where(rms >= threshold)[0]
        if loud.size == 0:
            return None
        drop_time = float(times[loud[0]])
        # Ignore a "drop" detected in the first second (that's just the start).
        return drop_time if drop_time >= 1.0 else None
    except Exception:  # noqa: BLE001 - best-effort only
        return None
