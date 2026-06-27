"""Per-folder ``beats.json`` sidecar: a readable mirror of each beat's library
metadata, written into the folder that holds the audio.

One file per folder (not per beat), refreshed after a scan and whenever a beat's
metadata changes — so it always reflects the library. It is a *derived* view of
the SQLite library: safe to delete, the next scan/edit rebuilds it.
"""

from __future__ import annotations

import json
import os
from typing import Optional

FILENAME = "beats.json"

# Library columns mirrored into the sidecar (skip cache/internal columns).
_FIELDS = ("filename", "title", "bpm", "key", "genre", "subgenre", "mood",
           "notes", "duration_sec", "analysis_status", "date_added",
           "date_modified")


def _beat_dict(row, tags) -> dict:
    d = {k: row[k] for k in _FIELDS}
    d["tags"] = tags
    return d


def write_dir_manifest(db, dir_path: str) -> Optional[str]:
    """(Re)write ``<dir_path>/beats.json`` for every library beat in that dir.

    Returns the manifest path, or None if the dir holds no cataloged beats or
    isn't writable.
    """
    target = os.path.normcase(os.path.abspath(dir_path))
    beats = [b for b in db.list_beats(order_by="filename COLLATE NOCASE")
             if os.path.normcase(os.path.dirname(b["file_path"])) == target]
    if not beats:
        return None
    data = {
        "folder": dir_path,
        "count": len(beats),
        "beats": [_beat_dict(b, db.get_tags(b["id"])) for b in beats],
    }
    out = os.path.join(dir_path, FILENAME)
    try:
        with open(out, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
    except OSError:  # ponytail: read-only folder (e.g. network share) — skip
        return None
    return out


def refresh_for_beat(db, file_path: str) -> Optional[str]:
    """Refresh the sidecar in the folder that contains ``file_path``."""
    return write_dir_manifest(db, os.path.dirname(file_path))


def refresh_under(db, folder: str) -> int:
    """Refresh the sidecar in every folder under ``folder`` that holds beats.

    ponytail: O(beats) scan per call — fine for a personal library; index by
    folder if catalogs ever get huge.
    """
    root = os.path.normcase(os.path.abspath(folder))
    dirs = set()
    for b in db.list_beats():
        d = os.path.dirname(b["file_path"])
        dn = os.path.normcase(os.path.abspath(d))
        if dn == root or dn.startswith(root + os.sep):
            dirs.add(d)
    return sum(1 for d in dirs if write_dir_manifest(db, d))
