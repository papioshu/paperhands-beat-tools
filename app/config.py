"""Lightweight persistent app config via QSettings (watched scan folders)."""

from __future__ import annotations

from typing import List

ORG = "PaperhandBeatTools"
APP = "BeatTools"
_KEY = "watched_folders"
_TAGS_KEY = "tags_folder"
_PRODUCER_KEY = "producer"
_MASTER_WAV_KEY = "convert_master_to_wav"
_UPDATE_REPO_KEY = "update_repo"


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


def tags_folder(default: str = "tags") -> str:
    """Folder the tag library reads producer tags from (defaults to ./tags)."""
    return str(_settings().value(_TAGS_KEY, default) or default)


def set_tags_folder(folder: str) -> None:
    _settings().setValue(_TAGS_KEY, folder)


def producer(default: str = "paperhand") -> str:
    """Producer name embedded as the ID3 artist on exports."""
    return str(_settings().value(_PRODUCER_KEY, default) or default)


def set_producer(name: str) -> None:
    _settings().setValue(_PRODUCER_KEY, name.strip() or "paperhand")


def convert_master_to_wav(default: bool = False) -> bool:
    """Whether 'Export Clean Master' converts to WAV (vs verbatim copy)."""
    val = _settings().value(_MASTER_WAV_KEY, default)
    return str(val).lower() in ("1", "true", "yes")


def set_convert_master_to_wav(on: bool) -> None:
    _settings().setValue(_MASTER_WAV_KEY, "1" if on else "0")


def update_repo(default: str = None) -> str:
    """GitHub 'owner/name' the app checks for updates (empty = disabled)."""
    if default is None:
        from app.version import UPDATE_REPO
        default = UPDATE_REPO
    return str(_settings().value(_UPDATE_REPO_KEY, default) or default)


def set_update_repo(repo: str) -> None:
    _settings().setValue(_UPDATE_REPO_KEY, repo.strip())
