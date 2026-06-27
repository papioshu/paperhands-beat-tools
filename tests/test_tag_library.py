"""Tests for the producer-tag library (DB + sync, headless)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from app.db.database import Database  # noqa: E402
from app.services import tag_library  # noqa: E402


@pytest.fixture
def db():
    d = Database(":memory:")
    yield d
    d.close()


def _tag(folder: Path, name: str) -> Path:
    p = folder / name
    p.write_bytes(b"\x00")
    return p


def test_sync_adds_new_tag_files(db, tmp_path):
    _tag(tmp_path, "PaperMadeIt.wav")
    _tag(tmp_path, "Oni.mp3")
    (tmp_path / "notes.txt").write_text("x")
    assert tag_library.sync_folder(db, str(tmp_path)) == 2
    assert tag_library.sync_folder(db, str(tmp_path)) == 0   # idempotent
    names = {t["name"] for t in db.list_tag_files()}
    assert names == {"PaperMadeIt", "Oni"}


def test_enable_favorite_category(db, tmp_path):
    _tag(tmp_path, "Yoru.wav")
    tag_library.sync_folder(db, str(tmp_path))
    tid = db.list_tag_files()[0]["id"]

    db.update_tag_file(tid, enabled=0, favorite=1, category="Japanese")
    row = db.get_tag_file(tid)
    assert row["enabled"] == 0
    assert row["favorite"] == 1
    assert row["category"] == "Japanese"
    assert db.tag_categories() == ["Japanese"]


def test_list_filters(db, tmp_path):
    for n in ("a.wav", "b.wav", "c.wav"):
        _tag(tmp_path, n)
    tag_library.sync_folder(db, str(tmp_path))
    ids = [t["id"] for t in db.list_tag_files()]
    db.update_tag_file(ids[0], enabled=0)
    db.update_tag_file(ids[1], favorite=1)
    db.update_tag_file(ids[1], category="Hard")

    assert len(db.list_tag_files(enabled_only=True)) == 2
    assert len(db.list_tag_files(favorites_only=True)) == 1
    assert len(db.list_tag_files(category="Hard")) == 1


def test_no_duplicate_tags_case_insensitive(db):
    # Same file, different case path -> one row, same id.
    id1 = db.add_tag_file(r"C:/Tags/Drop.wav", "Drop")
    id2 = db.add_tag_file(r"c:/tags/drop.wav", "Drop")
    assert id1 == id2
    assert len(db.list_tag_files()) == 1


def test_migration_dedupes_legacy_rows(tmp_path):
    # Seed dupes directly (pre-index), then a re-open must collapse them.
    import sqlite3
    path = str(tmp_path / "legacy.db")
    d = Database(path)
    d.add_tag_file(r"C:/Tags/Oni.wav", "Oni")
    d.close()
    raw = sqlite3.connect(path)                       # sneak a dup past the index
    raw.execute("DROP INDEX IF EXISTS idx_producer_tags_path")
    raw.execute("INSERT INTO producer_tags (path, name, category, hidden) "
                "VALUES (?, ?, 'Uncategorized', 1)", (r"c:/tags/oni.wav", "Oni"))
    raw.commit()
    raw.close()
    d2 = Database(path)                               # _migrate dedupes on open
    rows = d2.list_tag_files(include_hidden=True)
    assert len(rows) == 1
    assert rows[0]["hidden"] == 1                     # removed state preserved
    d2.close()


def test_prune_missing(db, tmp_path):
    f = _tag(tmp_path, "Gone.wav")
    tag_library.sync_folder(db, str(tmp_path))
    f.unlink()
    assert tag_library.prune_missing(db) == 1
    assert db.list_tag_files() == []
