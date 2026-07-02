"""Importing/scanning beats into the library, and finding missing files.

Catalog-in-place: we record absolute paths; we never move or copy the audio.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List

AUDIO_EXTS = {".mp3", ".wav", ".aiff", ".aif", ".flac", ".ogg", ".m4a"}


def is_audio(path: str | os.PathLike) -> bool:
    return Path(path).suffix.lower() in AUDIO_EXTS


def import_paths(db, paths: Iterable[str]) -> int:
    """Add the given audio files to the library. Returns how many were new."""
    added = 0
    for raw in paths:
        p = Path(raw)
        if not is_audio(p) or not p.is_file():
            continue
        abspath = str(p.resolve())
        if db.get_by_path(abspath) is None:
            st = p.stat()
            db.add_beat(abspath, p.name, file_size=st.st_size, file_mtime=st.st_mtime)
            added += 1
    return added


def scan_folder(db, folder: str, recursive: bool = True) -> int:
    """Scan a folder for audio files and add new ones. Returns count added."""
    root = Path(folder)
    if not root.is_dir():
        raise NotADirectoryError(folder)
    walker = root.rglob("*") if recursive else root.glob("*")
    return import_paths(db, (str(p) for p in walker if p.is_file()))


def rescan_changed(db, folder: str, recursive: bool = True) -> List[int]:
    """Flag cataloged files under ``folder`` that changed on disk as pending.

    A file is stale when its on-disk (mtime, size) differs from what we stored.
    Stale beats are set analysis_status='pending' and their stored stat is
    refreshed so the next scan won't re-flag them. Returns the re-flagged ids.

    ponytail: mtime+size heuristic — cheap, catches real edits/replacements.
    Upgrade path (content hash) only if false-negatives ever bite.
    """
    root = Path(folder)
    if not root.is_dir():
        raise NotADirectoryError(folder)
    walker = root.rglob("*") if recursive else root.glob("*")
    flagged: List[int] = []
    for p in walker:
        if not (p.is_file() and is_audio(p)):
            continue
        row = db.get_by_path(str(p.resolve()))
        if row is None:
            continue
        st = p.stat()
        if row["file_mtime"] != st.st_mtime or row["file_size"] != st.st_size:
            db.update_beat(row["id"], analysis_status="pending",
                           file_size=st.st_size, file_mtime=st.st_mtime)
            flagged.append(row["id"])
    return flagged


def list_missing(db) -> List[int]:
    """Return ids of cataloged beats whose file no longer exists on disk."""
    return [row["id"] for row in db.list_beats() if not os.path.exists(row["file_path"])]


def is_missing(row) -> bool:
    return not os.path.exists(row["file_path"])
