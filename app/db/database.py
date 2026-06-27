"""SQLite access layer for the beat library.

Pure stdlib (``sqlite3``) — no Qt, no audio libs — so it can be unit-tested
headless and reused anywhere. One ``Database`` instance owns one connection;
create a separate instance per thread (the analysis worker gets its own).

Schema (see the design spec):
    beats      one row per cataloged beat (path is the dedupe key)
    tags       free-form tag vocabulary
    beat_tags  many-to-many between beats and tags
"""

from __future__ import annotations

import sqlite3
import time
from typing import Iterable, List, Optional

# Columns a caller may freely update via update_beat().
_EDITABLE = {
    "title", "bpm", "key", "genre", "subgenre", "mood", "notes",
    "duration_sec", "file_size", "waveform_path", "analysis_status",
    "file_path", "filename", "placements",
    "bpm_confidence", "key_confidence", "bpm_candidates", "key_candidates",
    "fingerprint", "structure", "drop_sec", "hook_start", "hook_end",
    "mood_suggested", "artwork_path", "layers", "stems", "ignored", "auto_tag",
}

# Columns added after the original schema shipped; applied as additive migrations
# so existing library.db files upgrade in place without losing data.
_MIGRATIONS = {
    "placements": "ALTER TABLE beats ADD COLUMN placements TEXT",
    "bpm_confidence": "ALTER TABLE beats ADD COLUMN bpm_confidence REAL",
    "key_confidence": "ALTER TABLE beats ADD COLUMN key_confidence REAL",
    "bpm_candidates": "ALTER TABLE beats ADD COLUMN bpm_candidates TEXT",
    "key_candidates": "ALTER TABLE beats ADD COLUMN key_candidates TEXT",
    "fingerprint": "ALTER TABLE beats ADD COLUMN fingerprint TEXT",
    "structure": "ALTER TABLE beats ADD COLUMN structure TEXT",
    "drop_sec": "ALTER TABLE beats ADD COLUMN drop_sec REAL",
    "hook_start": "ALTER TABLE beats ADD COLUMN hook_start REAL",
    "hook_end": "ALTER TABLE beats ADD COLUMN hook_end REAL",
    "mood_suggested": "ALTER TABLE beats ADD COLUMN mood_suggested TEXT",
    "artwork_path": "ALTER TABLE beats ADD COLUMN artwork_path TEXT",
    "layers": "ALTER TABLE beats ADD COLUMN layers TEXT",
    "stems": "ALTER TABLE beats ADD COLUMN stems TEXT",
    "ignored": "ALTER TABLE beats ADD COLUMN ignored INTEGER DEFAULT 0",
    "auto_tag": "ALTER TABLE beats ADD COLUMN auto_tag INTEGER DEFAULT 0",
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS beats (
    id              INTEGER PRIMARY KEY,
    file_path       TEXT UNIQUE NOT NULL,
    filename        TEXT NOT NULL,
    title           TEXT,
    bpm             REAL,
    key             TEXT,
    genre           TEXT,
    subgenre        TEXT,
    mood            TEXT,
    notes           TEXT,
    duration_sec    REAL,
    file_size       INTEGER,
    waveform_path   TEXT,
    analysis_status TEXT DEFAULT 'pending',
    date_added      TEXT,
    date_modified   TEXT
);
CREATE TABLE IF NOT EXISTS tags (
    id   INTEGER PRIMARY KEY,
    name TEXT UNIQUE NOT NULL COLLATE NOCASE
);
CREATE TABLE IF NOT EXISTS beat_tags (
    beat_id INTEGER NOT NULL REFERENCES beats(id) ON DELETE CASCADE,
    tag_id  INTEGER NOT NULL REFERENCES tags(id)  ON DELETE CASCADE,
    PRIMARY KEY (beat_id, tag_id)
);
CREATE INDEX IF NOT EXISTS idx_beats_bpm   ON beats(bpm);
CREATE INDEX IF NOT EXISTS idx_beats_key   ON beats(key);
CREATE INDEX IF NOT EXISTS idx_beats_genre ON beats(genre);
CREATE INDEX IF NOT EXISTS idx_beats_mood  ON beats(mood);

-- Producer tag files (the audio overlays), with library metadata.
CREATE TABLE IF NOT EXISTS producer_tags (
    id        INTEGER PRIMARY KEY,
    path      TEXT UNIQUE NOT NULL,
    name      TEXT NOT NULL,
    category  TEXT DEFAULT 'Uncategorized',
    enabled   INTEGER DEFAULT 1,
    favorite  INTEGER DEFAULT 0
);
"""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


class Database:
    """Thin, well-bounded wrapper over the library's SQLite file."""

    def __init__(self, path: str = "library.db"):
        self.path = path
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.executescript(_SCHEMA)
        self._migrate()
        self.conn.commit()

    def _migrate(self) -> None:
        """Apply additive column migrations to existing tables."""
        existing = {row["name"] for row in self.conn.execute("PRAGMA table_info(beats)")}
        for column, ddl in _MIGRATIONS.items():
            if column not in existing:
                self.conn.execute(ddl)
        pt = {row["name"] for row in self.conn.execute("PRAGMA table_info(producer_tags)")}
        if "native_bpm" not in pt:
            self.conn.execute("ALTER TABLE producer_tags ADD COLUMN native_bpm REAL")
        if "hidden" not in pt:
            self.conn.execute(
                "ALTER TABLE producer_tags ADD COLUMN hidden INTEGER DEFAULT 0")

    def close(self) -> None:
        self.conn.close()

    def backup(self, dest_dir: str, keep: int = 5) -> Optional[str]:
        """Write a rolling, timestamped copy of the DB; keep the newest ``keep``."""
        import datetime
        import glob
        import os
        import shutil

        if self.path == ":memory:" or not os.path.exists(self.path):
            return None
        os.makedirs(dest_dir, exist_ok=True)
        self.conn.commit()
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        dest = os.path.join(dest_dir, f"library_{ts}.db")
        shutil.copy2(self.path, dest)
        old = sorted(glob.glob(os.path.join(dest_dir, "library_*.db")))[:-keep]
        for f in old:
            try:
                os.remove(f)
            except OSError:
                pass
        return dest

    # -- beats -------------------------------------------------------------

    def add_beat(self, file_path: str, filename: str, **fields) -> int:
        """Insert a beat (idempotent by path). Returns the beat id either way."""
        existing = self.get_by_path(file_path)
        if existing is not None:
            return existing["id"]
        now = _now()
        cur = self.conn.execute(
            "INSERT INTO beats (file_path, filename, title, date_added, date_modified) "
            "VALUES (?, ?, ?, ?, ?)",
            (file_path, filename, fields.get("title", filename), now, now),
        )
        beat_id = cur.lastrowid
        extra = {k: v for k, v in fields.items() if k in _EDITABLE and k != "title"}
        if extra:
            self.update_beat(beat_id, **extra)
        self.conn.commit()
        return beat_id

    def get_beat(self, beat_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute("SELECT * FROM beats WHERE id = ?", (beat_id,)).fetchone()

    def get_by_path(self, file_path: str) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM beats WHERE file_path = ?", (file_path,)
        ).fetchone()

    def update_beat(self, beat_id: int, **fields) -> None:
        """Update whitelisted columns on a beat; bumps date_modified."""
        cols = {k: v for k, v in fields.items() if k in _EDITABLE}
        if not cols:
            return
        cols["date_modified"] = _now()
        assignments = ", ".join(f"{k} = ?" for k in cols)
        self.conn.execute(
            f"UPDATE beats SET {assignments} WHERE id = ?",
            (*cols.values(), beat_id),
        )
        self.conn.commit()

    def delete_beat(self, beat_id: int) -> None:
        self.conn.execute("DELETE FROM beats WHERE id = ?", (beat_id,))
        self.conn.commit()

    def list_beats(
        self,
        search: Optional[str] = None,
        genre: Optional[str] = None,
        mood: Optional[str] = None,
        order_by: str = "date_added DESC",
    ) -> List[sqlite3.Row]:
        """Return beats, optionally filtered by free-text/genre/mood.

        ``search`` matches title, filename, genre, mood, key, or any tag.
        """
        sql = "SELECT DISTINCT b.* FROM beats b"
        params: list = []
        where: list = []

        if search:
            sql += (
                " LEFT JOIN beat_tags bt ON bt.beat_id = b.id"
                " LEFT JOIN tags t ON t.id = bt.tag_id"
            )
            like = f"%{search}%"
            where.append(
                "(b.title LIKE ? OR b.filename LIKE ? OR b.genre LIKE ?"
                " OR b.mood LIKE ? OR b.key LIKE ? OR t.name LIKE ?)"
            )
            params += [like, like, like, like, like, like]
        if genre:
            where.append("b.genre = ?")
            params.append(genre)
        if mood:
            where.append("b.mood = ?")
            params.append(mood)

        if where:
            sql += " WHERE " + " AND ".join(where)
        # order_by is caller-controlled, not user input — safe to inline.
        sql += f" ORDER BY {order_by}"
        return self.conn.execute(sql, params).fetchall()

    # -- tags --------------------------------------------------------------

    def _tag_id(self, name: str) -> int:
        name = name.strip()
        self.conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (name,))
        row = self.conn.execute("SELECT id FROM tags WHERE name = ?", (name,)).fetchone()
        return row["id"]

    def set_tags(self, beat_id: int, names: Iterable[str]) -> None:
        """Replace a beat's free-form tags with ``names`` (dedup, case-insensitive)."""
        self.conn.execute("DELETE FROM beat_tags WHERE beat_id = ?", (beat_id,))
        seen = set()
        for name in names:
            name = name.strip()
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            tag_id = self._tag_id(name)
            self.conn.execute(
                "INSERT OR IGNORE INTO beat_tags (beat_id, tag_id) VALUES (?, ?)",
                (beat_id, tag_id),
            )
        self.conn.commit()

    def get_tags(self, beat_id: int) -> List[str]:
        rows = self.conn.execute(
            "SELECT t.name FROM tags t JOIN beat_tags bt ON bt.tag_id = t.id "
            "WHERE bt.beat_id = ? ORDER BY t.name",
            (beat_id,),
        ).fetchall()
        return [r["name"] for r in rows]

    # -- autocomplete helpers ---------------------------------------------

    def distinct_values(self, column: str) -> List[str]:
        """Distinct non-empty values for an autocomplete field (genre/mood/...)."""
        if column not in {"genre", "subgenre", "mood", "key"}:
            raise ValueError(f"not an autocomplete column: {column}")
        rows = self.conn.execute(
            f"SELECT DISTINCT {column} AS v FROM beats "
            f"WHERE {column} IS NOT NULL AND {column} != '' ORDER BY {column}"
        ).fetchall()
        return [r["v"] for r in rows]

    def all_tag_names(self) -> List[str]:
        rows = self.conn.execute("SELECT name FROM tags ORDER BY name").fetchall()
        return [r["name"] for r in rows]

    # -- producer tag files (the audio overlays) ---------------------------

    def add_tag_file(self, path: str, name: str, category: str = "Uncategorized") -> int:
        existing = self.conn.execute(
            "SELECT id FROM producer_tags WHERE path = ?", (path,)).fetchone()
        if existing:
            return existing["id"]
        cur = self.conn.execute(
            "INSERT INTO producer_tags (path, name, category) VALUES (?, ?, ?)",
            (path, name, category))
        self.conn.commit()
        return cur.lastrowid

    def list_tag_files(self, enabled_only: bool = False, category: str = None,
                       favorites_only: bool = False,
                       include_hidden: bool = False) -> List[sqlite3.Row]:
        sql = "SELECT * FROM producer_tags"
        where, params = [], []
        if not include_hidden:
            where.append("hidden = 0")
        if enabled_only:
            where.append("enabled = 1")
        if favorites_only:
            where.append("favorite = 1")
        if category:
            where.append("category = ?")
            params.append(category)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY category, favorite DESC, name COLLATE NOCASE"
        return self.conn.execute(sql, params).fetchall()

    def get_tag_file(self, tag_id: int) -> Optional[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM producer_tags WHERE id = ?", (tag_id,)).fetchone()

    def update_tag_file(self, tag_id: int, **fields) -> None:
        allowed = {"name", "category", "enabled", "favorite", "native_bpm", "hidden"}
        cols = {k: v for k, v in fields.items() if k in allowed}
        if not cols:
            return
        assignments = ", ".join(f"{k} = ?" for k in cols)
        self.conn.execute(
            f"UPDATE producer_tags SET {assignments} WHERE id = ?",
            (*cols.values(), tag_id))
        self.conn.commit()

    def remove_tag_file(self, tag_id: int) -> None:
        self.conn.execute("DELETE FROM producer_tags WHERE id = ?", (tag_id,))
        self.conn.commit()

    def tag_categories(self) -> List[str]:
        rows = self.conn.execute(
            "SELECT DISTINCT category FROM producer_tags "
            "WHERE category IS NOT NULL AND category != '' ORDER BY category").fetchall()
        return [r["category"] for r in rows]
