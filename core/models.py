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
    """

    position_sec: float
    tag_path: str


@dataclass(frozen=True)
class DetectionResult:
    """Outcome of automatic BPM / key analysis for one beat.

    Either field may be ``None`` when detection was skipped (already in the
    filename / manually overridden) or failed. ``error`` carries a short reason
    when analysis blew up, so the pipeline can keep going and still report it.
    """

    bpm: Optional[float] = None
    key: Optional[str] = None
    error: Optional[str] = None


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
    duck_db: float = 6.0                # how much to lower the beat under a tag
    headroom_db: float = 1.0            # peak target = -headroom_db dBFS

    # Detection / naming
    bpm_override: Optional[float] = None
    key_override: Optional[str] = None
    detect: bool = True                 # run BPM/key detection when missing
    suffix: str = "_tagged"

    # Export
    bitrate: str = "320k"

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
