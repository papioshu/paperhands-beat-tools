"""Mix stem tracks into a single rendered file (pure pydub).

DAW Mode previews/exports a "current mix" by summing the stems while honoring
each track's mute / solo / volume / pan. Stems are aligned at 0:00. This is for
*preview and export* — not a real-time multitrack engine.
"""

from __future__ import annotations

from typing import List, Optional


def audible_tracks(tracks: List[dict]) -> List[dict]:
    """Tracks that should sound, honoring enable + mute + solo (solo wins)."""
    soloed = any(t.get("solo") for t in tracks)
    out = []
    for t in tracks:
        if not t.get("enabled", True) or t.get("mute"):
            continue
        if soloed and not t.get("solo"):
            continue
        out.append(t)
    return out


def mix_stem_tracks(tracks: List[dict], out_path: str, fmt: str = "wav",
                    bitrate: Optional[str] = None) -> str:
    """Render the mix of ``tracks`` (each {path, volume_db, pan, mute, solo}).

    Returns the written path. If every track is silenced, writes silence the
    length of the longest track so the output is still valid.
    """
    from pydub import AudioSegment

    loaded = [(t, AudioSegment.from_file(t["path"])) for t in tracks]
    active = audible_tracks(tracks)

    mixed = None
    for t in active:
        seg = next(s for tt, s in loaded if tt is t)
        if t.get("volume_db"):
            seg = seg.apply_gain(float(t["volume_db"]))
        if t.get("pan"):
            seg = seg.pan(max(-1.0, min(1.0, float(t["pan"]))))
        mixed = seg if mixed is None else mixed.overlay(seg)

    if mixed is None:  # all muted -> silence matching the longest stem
        longest = max((s for _, s in loaded), key=len, default=AudioSegment.silent(1000))
        mixed = AudioSegment.silent(duration=len(longest), frame_rate=longest.frame_rate)

    params = {"format": fmt}
    if bitrate:
        params["bitrate"] = bitrate
    mixed.export(out_path, **params)
    return out_path
