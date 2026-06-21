"""Rename a cataloged file *in place* from a pattern, keeping the DB in sync.

Pattern tokens: ``{title}``, ``{bpm}``, ``{key}``, ``{name}`` (original stem).
Missing values collapse cleanly so you never get ``Beat [ ]`` or doubled spaces.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

from core.naming import format_key_for_filename

DEFAULT_PATTERN = "{title} [{bpm} {key}]"


def build_basename(
    pattern: str,
    *,
    title: str,
    original_stem: str,
    bpm: Optional[float] = None,
    key: Optional[str] = None,
) -> str:
    """Render a filename stem (no extension) from a pattern.

    Empty BPM/key are dropped and any leftover empty brackets / double spaces are
    tidied up, so ``"{title} [{bpm} {key}]"`` with no bpm/key -> just the title.
    """
    bpm_str = f"{int(round(bpm))}BPM" if bpm is not None else ""
    key_str = format_key_for_filename(key) if key else ""

    text = pattern.format(
        title=title or original_stem,
        name=original_stem,
        bpm=bpm_str,
        key=key_str,
    )

    # Tidy: empty brackets/parens, multiple spaces, stray separators.
    text = re.sub(r"[\[\(]\s*[\]\)]", "", text)   # "[]" or "( )"
    text = re.sub(r"\s{2,}", " ", text)            # collapse spaces
    text = re.sub(r"\s+([\]\)])", r"\1", text)     # " ]" -> "]"
    text = re.sub(r"([\[\(])\s+", r"\1", text)     # "[ " -> "["
    text = text.strip(" -_")
    # Strip characters illegal in Windows filenames.
    text = re.sub(r'[<>:"/\\|?*]', "", text)
    return text or original_stem


def plan_batch_rename(rows, pattern: str) -> list:
    """Compute new names for many beats from a pattern (no filesystem changes).

    Returns one dict per row: ``beat_id, current, new_name, new_stem, changed,
    conflict``. ``conflict`` flags when two beats in the batch would collapse to
    the same name (so the UI can warn and skip them).
    """
    plans = []
    for row in rows:
        stem = Path(row["filename"]).stem
        ext = Path(row["filename"]).suffix
        new_stem = build_basename(
            pattern,
            title=row["title"] or stem,
            original_stem=stem,
            bpm=row["bpm"],
            key=row["key"],
        )
        plans.append({
            "beat_id": row["id"],
            "current": row["filename"],
            "new_stem": new_stem,
            "new_name": new_stem + ext,
        })

    counts = {}
    for p in plans:
        counts[p["new_name"]] = counts.get(p["new_name"], 0) + 1
    for p in plans:
        p["changed"] = p["new_name"] != p["current"]
        p["conflict"] = counts[p["new_name"]] > 1
    return plans


def rename_in_place(db, beat_id: int, new_stem: str) -> str:
    """Rename the beat's file on disk to ``new_stem`` and update the DB.

    Returns the new absolute path. Raises:
        FileNotFoundError: source file is gone.
        FileExistsError: target name already exists (nothing is changed).
    """
    row = db.get_beat(beat_id)
    if row is None:
        raise KeyError(beat_id)

    old = Path(row["file_path"])
    if not old.exists():
        raise FileNotFoundError(str(old))

    new_path = old.with_name(new_stem + old.suffix)
    if new_path == old:
        return str(old)
    if new_path.exists():
        raise FileExistsError(str(new_path))

    old.rename(new_path)
    db.update_beat(beat_id, file_path=str(new_path), filename=new_path.name)
    return str(new_path)
