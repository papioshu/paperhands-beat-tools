"""Compute *where* tags land on a beat (pure logic, no audio libraries).

Given a beat's duration and the config, produce an ordered list of
:class:`~core.models.Placement` spots. Tag files are rotated randomly; pass a
seeded ``random.Random`` for deterministic output (used by the tests and the
``--seed`` flag).
"""

from __future__ import annotations

import random
from typing import List, Optional, Sequence

from .models import Placement


def compute_placements(
    duration_sec: float,
    tag_paths: Sequence[str],
    *,
    interval_sec: float = 40.0,
    tag_at_start: bool = True,
    jitter_sec: float = 0.0,
    start_offset_sec: float = 0.0,
    rng: Optional[random.Random] = None,
) -> List[Placement]:
    """Return the ordered list of tag placements for one beat.

    Args:
        duration_sec: Length of the beat. Placements must fall strictly inside it.
        tag_paths: One or more tag files to rotate through (randomly per spot).
        interval_sec: Gap between repeated tags. Must be > 0.
        tag_at_start: Include a placement at ``start_offset_sec`` (no jitter).
        jitter_sec: Each interval spot is wobbled by +/- this many seconds.
        start_offset_sec: Anchor for the first tag — 0.0 normally, or the detected
            drop time when ``--before-drop`` is used.
        rng: Seeded RNG for reproducibility; defaults to module ``random``.

    Returns:
        Placements sorted by time. Empty if there are no tags or no room.
    """
    if not tag_paths:
        return []
    if interval_sec <= 0:
        raise ValueError("interval_sec must be > 0")
    if duration_sec <= 0:
        return []

    rng = rng or random.Random()

    # Candidate times before jitter: the anchor, then every interval after it.
    times: List[float] = []
    if tag_at_start:
        times.append(start_offset_sec)

    t = start_offset_sec + interval_sec
    while t < duration_sec:
        if jitter_sec > 0:
            t_jittered = t + rng.uniform(-jitter_sec, jitter_sec)
        else:
            t_jittered = t
        # Clamp into the valid range; never before the anchor or past the beat.
        t_jittered = max(start_offset_sec, min(t_jittered, duration_sec - 0.001))
        times.append(t_jittered)
        t += interval_sec

    placements = [
        Placement(position_sec=round(max(0.0, pos), 3), tag_path=rng.choice(list(tag_paths)))
        for pos in times
        if 0.0 <= pos < duration_sec
    ]
    placements.sort(key=lambda p: p.position_sec)
    return placements
