"""Crash recovery: remember the open beat, detect an unclean shutdown.

A tiny JSON marker beside the library. On a clean exit ``clean`` is set true; if
the app starts and finds it still false, the last beat is offered for restore.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


def _path(base) -> Path:
    return Path(base) / "recovery.json"


def note_open(base, beat_id: int) -> None:
    try:
        _path(base).write_text(json.dumps({"beat_id": beat_id, "clean": False}),
                               encoding="utf-8")
    except OSError:
        pass


def mark_clean(base) -> None:
    p = _path(base)
    try:
        if p.exists():
            p.unlink()
    except OSError:
        pass


def pending(base) -> Optional[int]:
    """Beat id from an unclean shutdown, or None."""
    p = _path(base)
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return None if data.get("clean") else data.get("beat_id")
    except (OSError, ValueError):
        return None
