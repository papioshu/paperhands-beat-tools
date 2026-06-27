"""Plain data structures shared across the engine.

These are intentionally framework-free (no Qt, no audio libs) so they can be
used by the CLI, the unit tests, and the future PySide6 GUI alike.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Optional


@dataclass(frozen=True)
class Placement:
    """A single spot where a tag will be stamped onto a beat.

    Attributes:
        position_sec: When the tag starts, in seconds from the beat's start.
        tag_path: Absolute path to the tag audio file to overlay here.
        stretch_ratio: Time-stretch applied to the tag here (1.0 = none, >1 faster).
        preserve_pitch: Keep pitch when stretching (False = tape/pitch-shift).
    """

    position_sec: float
    tag_path: str
    stretch_ratio: float = 1.0
    preserve_pitch: bool = True


@dataclass(frozen=True)
class DetectionResult:
    """Outcome of automatic BPM / key analysis for one beat.

    Either field may be ``None`` when detection was skipped (already in the
    filename / manually overridden) or failed. ``error`` carries a short reason
    when analysis blew up, so the pipeline can keep going and still report it.

    The ``*_candidates`` lists offer alternates for a confirm/override UI (e.g.
    half/double tempo, relative major/minor); ``*_confidence`` is a rough 0..1
    score — honestly approximate, meant to flag "double-check this", not gospel.
    """

    bpm: Optional[float] = None
    key: Optional[str] = None
    error: Optional[str] = None
    bpm_candidates: tuple = ()
    key_candidates: tuple = ()
    bpm_confidence: Optional[float] = None
    key_confidence: Optional[float] = None


@dataclass
class TaggingConfig:
    """All the knobs the batch tagger and the GUI share.

    Defaults match the spec: tag at the start, again every 40s, 320k output,
    a gentle 6 dB duck under each tag, and a 1 dB safety headroom on normalize.
    """

    # Placement
    interval_sec: float = 40.0          # gap between repeated tags
    tag_at_start: bool = True           # also stamp a tag at the very beginning
    jitter_sec: float = 0.0             # +/- random wobble on each interval spot
    before_drop: bool = False           # anchor the first tag at the detected drop

    # Mixing
    duck_db: float = 0.0                # beat volume reduction under a tag (0 = off)
    headroom_db: float = 1.0            # peak target = -headroom_db dBFS

    # Detection / naming
    bpm_override: Optional[float] = None
    key_override: Optional[str] = None
    detect: bool = True                 # run BPM/key detection when missing
    suffix: str = "_tagged"

    # Export
    bitrate: str = "320k"
    producer: str = "paperhand"   # ID3 artist on exported MP3s

    # Reproducibility (seeded RNG for tag rotation + jitter); None = random
    seed: Optional[int] = None

    def with_overrides(self, **changes) -> "TaggingConfig":
        """Return a copy with the given fields replaced (non-mutating)."""
        return replace(self, **changes)


@dataclass
class TagResult:
    """One row of the CSV report — the outcome of processing a single file."""

    original_name: str
    output_name: str = ""
    bpm: Optional[float] = None
    key: Optional[str] = None
    placements_sec: list = field(default_factory=list)
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error
