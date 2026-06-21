"""Export / import the beat catalog as CSV or JSON (metadata backup).

A portable snapshot of everything the library knows about each beat, so the
catalog survives a lost ``library.db`` or moves between machines. The audio
files themselves are referenced by path, not copied. Re-import upserts by
``file_path`` and restores the editable metadata + tags (it does not restore the
machine-specific waveform cache — those re-generate on analysis).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Optional, Tuple

# Fields written/read per beat (plus a joined "tags" column/array).
FIELDS = [
    "file_path", "filename", "title", "bpm", "key", "genre", "subgenre",
    "mood", "notes", "duration_sec", "analysis_status", "date_added",
]
# Subset that import_catalog is allowed to write back onto a beat row.
_RESTORE = [
    "title", "bpm", "key", "genre", "subgenre", "mood", "notes",
    "duration_sec", "analysis_status",
]
_TAG_SEP = ";"


def _fmt_for(path: str, fmt: Optional[str]) -> str:
    if fmt:
        return fmt.lower()
    return "json" if Path(path).suffix.lower() == ".json" else "csv"


def _as_float(value):
    if value in (None, "", "None"):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def export_catalog(db, path: str, fmt: Optional[str] = None) -> int:
    """Write the whole catalog to ``path``. Returns the number of beats written."""
    fmt = _fmt_for(path, fmt)
    beats = db.list_beats(order_by="date_added ASC")

    records = []
    for b in beats:
        rec = {k: b[k] for k in FIELDS}
        rec["tags"] = db.get_tags(b["id"])
        records.append(rec)

    if fmt == "json":
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(records, fh, indent=2, ensure_ascii=False)
    else:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDS + ["tags"])
            writer.writeheader()
            for rec in records:
                row = dict(rec)
                row["tags"] = _TAG_SEP.join(rec["tags"])
                writer.writerow(row)

    return len(records)


def _read_records(path: str, fmt: str):
    if fmt == "json":
        with open(path, encoding="utf-8") as fh:
            for rec in json.load(fh):
                tags = rec.get("tags") or []
                if isinstance(tags, str):
                    tags = [t for t in tags.split(_TAG_SEP) if t]
                yield rec, tags
    else:
        with open(path, newline="", encoding="utf-8") as fh:
            for rec in csv.DictReader(fh):
                tags = [t for t in (rec.get("tags") or "").split(_TAG_SEP) if t]
                yield rec, tags


def import_catalog(db, path: str, fmt: Optional[str] = None) -> Tuple[int, int]:
    """Restore a catalog file into the DB. Returns ``(added, updated)``.

    Beats are matched by ``file_path``; new ones are added, existing ones updated.
    Metadata and tags are restored; waveform cache is intentionally left alone.
    """
    fmt = _fmt_for(path, fmt)
    added = updated = 0

    for rec, tags in _read_records(path, fmt):
        file_path = rec.get("file_path")
        if not file_path:
            continue
        filename = rec.get("filename") or Path(file_path).name

        existed = db.get_by_path(file_path) is not None
        bid = db.add_beat(file_path, filename)

        fields = {}
        for k in _RESTORE:
            val = rec.get(k)
            if k in ("bpm", "duration_sec"):
                val = _as_float(val)
            elif val == "":
                val = None
            if val is not None:
                fields[k] = val
        if fields:
            db.update_beat(bid, **fields)
        if tags:
            db.set_tags(bid, tags)

        updated += int(existed)
        added += int(not existed)

    return added, updated
