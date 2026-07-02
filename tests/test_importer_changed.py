"""Change-detection for cache invalidation (headless, no Qt)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import Database          # noqa: E402
from app.services import importer             # noqa: E402


def _wav(folder: Path, name: str, size: int) -> Path:
    p = folder / name
    p.write_bytes(b"\0" * size)   # not real audio; scan only stats + checks suffix
    return p


def test_import_stores_mtime(tmp_path):
    db = Database(":memory:")
    _wav(tmp_path, "a.wav", 100)
    importer.scan_folder(db, str(tmp_path))
    row = db.get_by_path(str((tmp_path / "a.wav").resolve()))
    assert row["file_size"] == 100
    assert row["file_mtime"] is not None


def test_rescan_flags_changed_file(tmp_path):
    db = Database(":memory:")
    p = _wav(tmp_path, "a.wav", 100)
    importer.scan_folder(db, str(tmp_path))
    bid = db.get_by_path(str(p.resolve()))["id"]
    db.update_beat(bid, analysis_status="done", bpm=140.0)

    # Change the file: bigger size + newer mtime.
    p.write_bytes(b"\0" * 250)
    import os
    import time
    os.utime(p, (time.time() + 10, time.time() + 10))

    changed = importer.rescan_changed(db, str(tmp_path))
    assert changed == [bid]
    row = db.get_beat(bid)
    assert row["analysis_status"] == "pending"
    assert row["file_size"] == 250          # stored stat refreshed


def test_rescan_ignores_unchanged_file(tmp_path):
    db = Database(":memory:")
    p = _wav(tmp_path, "a.wav", 100)
    importer.scan_folder(db, str(tmp_path))
    bid = db.get_by_path(str(p.resolve()))["id"]
    db.update_beat(bid, analysis_status="done")

    assert importer.rescan_changed(db, str(tmp_path)) == []
    assert db.get_beat(bid)["analysis_status"] == "done"
