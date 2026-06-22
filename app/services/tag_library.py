"""Keep the producer-tag library (DB) in sync with the tags folder.

Tag *files* live in the tags folder; their library metadata (category, enabled,
favorite, display name) lives in the ``producer_tags`` table. Syncing adds any
new audio files found in the folder; existing entries (and their metadata) are
preserved.
"""

from __future__ import annotations

from pathlib import Path

from app.services.importer import AUDIO_EXTS


def sync_folder(db, folder: str) -> int:
    """Add new tag files from ``folder`` to the library. Returns count added."""
    root = Path(folder)
    if not root.is_dir():
        return 0
    existing = {r["path"] for r in db.list_tag_files()}
    added = 0
    for f in sorted(root.iterdir()):
        if f.is_file() and f.suffix.lower() in AUDIO_EXTS:
            path = str(f.resolve())
            if path not in existing:
                db.add_tag_file(path, f.stem)
                added += 1
    return added


def prune_missing(db) -> int:
    """Drop library entries whose tag file no longer exists. Returns count removed."""
    removed = 0
    for row in db.list_tag_files():
        if not Path(row["path"]).exists():
            db.remove_tag_file(row["id"])
            removed += 1
    return removed
