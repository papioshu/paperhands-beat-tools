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


def test_verify_sha256(tmp_path):
    import hashlib

    from app import updater
    f = tmp_path / "x.bin"
    f.write_bytes(b"hello")
    digest = hashlib.sha256(b"hello").hexdigest()
    assert updater.verify_sha256(str(f), digest)
    assert updater.verify_sha256(str(f), f"{digest}  x.bin")   # sha256sum format
    assert not updater.verify_sha256(str(f), "deadbeef")
