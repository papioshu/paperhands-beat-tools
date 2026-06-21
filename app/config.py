"""Lightweight persistent app config via QSettings (watched scan folders)."""

from __future__ import annotations

from typing import List

ORG = "PaperhandBeatTools"
APP = "BeatTools"
_KEY = "watched_folders"


def _settings():
    from PySide6.QtCore import QSettings

    return QSettings(ORG, APP)


def watched_folders() -> List[str]:
    val = _settings().value(_KEY, [])
    if isinstance(val, str):  # QSettings may collapse a 1-item list to a string
        return [val] if val else []
    return list(val or [])


def set_watched_folders(folders: List[str]) -> None:
    # De-dup preserving order.
    seen, ordered = set(), []
    for f in folders:
        if f and f not in seen:
            seen.add(f)
            ordered.append(f)
    _settings().setValue(_KEY, ordered)


def add_watched_folder(folder: str) -> None:
    set_watched_folders(watched_folders() + [folder])


def remove_watched_folder(folder: str) -> None:
    set_watched_folders([f for f in watched_folders() if f != folder])
