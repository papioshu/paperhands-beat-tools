import os

from app import paths, recovery
from app.db import Database


def test_recovery_roundtrip(tmp_path):
    base = str(tmp_path)
    assert recovery.pending(base) is None
    recovery.note_open(base, 7)
    assert recovery.pending(base) == 7      # unclean -> offered
    recovery.mark_clean(base)
    assert recovery.pending(base) is None    # clean -> nothing to restore


def test_db_backup_creates_copy(tmp_path):
    db = Database(str(tmp_path / "library.db"))
    db.add_beat("a.mp3", "a.mp3")
    dest = db.backup(str(tmp_path / "backups"))
    assert dest and os.path.exists(dest)
    db.close()


def test_within_blocks_traversal(tmp_path):
    assert paths.within(tmp_path, tmp_path / "previews" / "x.mp3")
    assert not paths.within(tmp_path, tmp_path / ".." / ".." / "etc" / "x")
