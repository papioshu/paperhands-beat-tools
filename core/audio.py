"""Audio I/O and mixing built on pydub (ffmpeg backend).

pydub is imported lazily so the pure-logic modules and tests don't need it.
All gain math is in dB (pydub's native unit). Ducking lowers the beat *under*
each tag so the tag cuts through; normalize brings the final peak to a small
headroom below 0 dBFS so the export never clips.
"""

from __future__ import annotations

import shutil
from typing import Dict, List, Sequence

from .models import Placement


class FfmpegNotFoundError(RuntimeError):
    """Raised when the ffmpeg executable isn't on PATH."""


def ensure_ffmpeg() -> None:
    """Raise a helpful error if ffmpeg can't be found."""
    if shutil.which("ffmpeg") is None:
        raise FfmpegNotFoundError(
            "ffmpeg was not found on your PATH. Install it (see README), e.g.\n"
            "    winget install Gyan.FFmpeg\n"
            "then restart your terminal so PATH updates."
        )


def load_audio(path: str):
    """Load any audio file pydub/ffmpeg understands into an AudioSegment."""
    from pydub import AudioSegment

    return AudioSegment.from_file(path)


def duck_and_overlay(beat, tag, position_ms: int, duck_db: float):
    """Lower the beat under the tag's span, then overlay the tag.

    Args:
        beat: AudioSegment of the instrumental.
        tag: AudioSegment of the producer tag.
        position_ms: Where the tag starts, in milliseconds.
        duck_db: How many dB to drop the beat under the tag (positive number).

    Returns:
        A new AudioSegment with the tag mixed in. Out-of-range positions are
        skipped (returns the beat unchanged).
    """
    if position_ms < 0 or position_ms >= len(beat):
        return beat

    end_ms = min(position_ms + len(tag), len(beat))
    before = beat[:position_ms]
    under = beat[position_ms:end_ms] - duck_db  # attenuate just this region
    after = beat[end_ms:]
    ducked = before + under + after
    return ducked.overlay(tag, position=position_ms)


def apply_placements(
    beat,
    placements: Sequence[Placement],
    tag_cache: Dict[str, object],
    duck_db: float,
):
    """Apply every placement to the beat, in order, ducking under each tag."""
    result = beat
    for p in placements:
        tag = tag_cache[p.tag_path]
        result = duck_and_overlay(result, tag, int(round(p.position_sec * 1000)), duck_db)
    return result


def normalize_safe(seg, headroom_db: float = 1.0):
    """Peak-normalize so the loudest sample sits at ``-headroom_db`` dBFS.

    Brings quiet mixes up and hot mixes down to a consistent, clip-free peak.
    """
    if seg.max_dBFS == float("-inf"):  # pure silence
        return seg
    change = -abs(headroom_db) - seg.max_dBFS
    return seg.apply_gain(change)


def export_mp3(seg, path: str, bitrate: str = "320k", tags: dict = None,
               cover: str = None) -> None:
    """Export to MP3 with optional ID3 tags and embedded cover art (image path)."""
    kwargs = {"format": "mp3", "bitrate": bitrate, "tags": tags or None}
    if cover:
        kwargs["cover"] = cover
    seg.export(path, **kwargs)


def to_mono_float(seg):
    """Convert an AudioSegment to ``(numpy float32 mono, sample_rate)`` for librosa."""
    import numpy as np

    mono = seg.set_channels(1)
    samples = np.array(mono.get_array_of_samples()).astype("float32")
    # Scale integer PCM to [-1, 1] based on sample width.
    max_int = float(1 << (8 * mono.sample_width - 1))
    if max_int > 0:
        samples /= max_int
    return samples, mono.frame_rate
