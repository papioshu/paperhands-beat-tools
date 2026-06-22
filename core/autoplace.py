"""Suggest tag placements by mode, with smart-spacing rules and presets (pure).

Modes: intro, fixed (interval), random (interval range), structure-aware,
hook-aware, fixed_times (explicit), custom (user markers — no auto placement).
Smart rule: enforce a minimum gap between tags (default 30s) so tags never stack.
All functions are pure (no audio/Qt) and unit-tested.
"""

from __future__ import annotations

import random
from typing import List, Optional, Sequence

from .models import Placement

MODES = ["intro", "fixed", "random", "structure", "hook", "fixed_times"]

# Reusable presets. Each maps to a mode (+ params). Built-ins; users can add more.
PROFILES = {
    "Standard": {"mode": "fixed_times", "times": [0.0, 45.0, 90.0]},
    "Paperhand": {"mode": "intro"},
    "BeatStars": {"mode": "structure"},          # intro + section boundaries ~ hooks
    "Heavy Protection": {"mode": "random", "interval": 37.0, "jitter": 8.0,
                          "include_outro": True},
}


def enforce_spacing(placements: List[Placement], min_spacing: float) -> List[Placement]:
    """Drop tags closer than ``min_spacing`` seconds (keeps the earliest)."""
    out: List[Placement] = []
    last: Optional[float] = None
    for p in sorted(placements, key=lambda x: x.position_sec):
        if last is None or p.position_sec - last >= min_spacing:
            out.append(p)
            last = p.position_sec
    return out


def _times_for_mode(mode, duration, *, interval, jitter, structure, drop, hook,
                    times, intro_sec, include_outro, outro_lead, rng) -> List[float]:
    out: List[float] = []
    if mode == "intro":
        out = [intro_sec]
    elif mode == "fixed_times":
        out = list(times or [])
    elif mode == "fixed":
        t = intro_sec
        while t < duration:
            out.append(t)
            t += interval
    elif mode == "random":
        t = intro_sec
        while t < duration:
            out.append(t)
            t += interval + rng.uniform(-jitter, jitter)
    elif mode == "structure":
        out = [intro_sec] + list(structure or [])
    elif mode == "hook":
        if drop is not None:
            out.append(drop)
        if hook is not None:
            out.append(hook[0] if isinstance(hook, (tuple, list)) else hook)
        if not out:
            out = [intro_sec]
    if include_outro and duration > outro_lead:
        out.append(duration - outro_lead)
    return out


def suggest_placements(
    mode: str,
    duration_sec: float,
    tag_paths: Sequence[str],
    *,
    interval: float = 40.0,
    jitter: float = 0.0,
    structure: Optional[Sequence[float]] = None,
    drop: Optional[float] = None,
    hook=None,
    times: Optional[Sequence[float]] = None,
    intro_sec: float = 0.0,
    include_outro: bool = False,
    outro_lead: float = 10.0,
    min_spacing: float = 30.0,
    rng: Optional[random.Random] = None,
) -> List[Placement]:
    """Compute suggested placements for ``mode``, rotating tags, spacing enforced."""
    if not tag_paths or duration_sec <= 0 or mode == "custom":
        return []
    rng = rng or random.Random()
    raw = _times_for_mode(
        mode, duration_sec, interval=interval, jitter=jitter, structure=structure,
        drop=drop, hook=hook, times=times, intro_sec=intro_sec,
        include_outro=include_outro, outro_lead=outro_lead, rng=rng)

    tags = list(tag_paths)
    valid = sorted({round(t, 3) for t in raw if 0.0 <= t < duration_sec})
    placements = [Placement(t, tags[i % len(tags)]) for i, t in enumerate(valid)]
    return enforce_spacing(placements, min_spacing)


def apply_profile(
    profile: dict,
    duration_sec: float,
    tag_paths: Sequence[str],
    *,
    structure=None,
    drop=None,
    hook=None,
    min_spacing: float = 30.0,
    rng: Optional[random.Random] = None,
) -> List[Placement]:
    """Run a profile dict (mode + params) through suggest_placements."""
    params = dict(profile)
    mode = params.pop("mode", "fixed")
    return suggest_placements(
        mode, duration_sec, tag_paths, structure=structure, drop=drop, hook=hook,
        min_spacing=min_spacing, rng=rng, **params)
