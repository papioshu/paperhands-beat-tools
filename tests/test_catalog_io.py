"""Tests for catalog export/import round-trips (headless, no Qt)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from app.db.database import Database  # noqa: E402
from app.services import catalog_io  # noqa: E402


def _seed(db):
    b1 = db.add_beat("/m/Night.mp3", "Night.mp3", title="Night Drive")
    db.update_beat(b1, bpm=140, key="F#min", genre="Trap", mood="Dark",
                   notes="leased", duration_sec=180.0, analysis_status="done")
    db.set_tags(b1, ["dark", "808"])
    b2 = db.add_beat("/m/Sun.mp3", "Sun.mp3", title="Sunrise")
    db.update_beat(b2, bpm=92, key="Cmaj", genre="R&B")
    db.set_tags(b2, ["melodic"])
    return b1, b2


@pytest.mark.parametrize("ext", [".csv", ".json"])
def test_export_then_import_into_fresh_db(tmp_path, ext):
    src = Database(":memory:")
    _seed(src)
    out = tmp_path / f"catalog{ext}"
    assert catalog_io.export_catalog(src, str(out)) == 2
    src.close()

    fresh = Database(":memory:")
    added, updated = catalog_io.import_catalog(fresh, str(out))
    assert (added, updated) == (2, 0)

    night = fresh.get_by_path("/m/Night.mp3")
    assert night["title"] == "Night Drive"
    assert night["bpm"] == 140.0
    assert night["key"] == "F#min"
    assert night["genre"] == "Trap"
    assert night["analysis_status"] == "done"
    assert set(fresh.get_tags(night["id"])) == {"dark", "808"}
    fresh.close()


def test_reimport_updates_existing(tmp_path):
    db = Database(":memory:")
    _seed(db)
    out = tmp_path / "catalog.json"
    catalog_io.export_catalog(db, str(out))

    # Same DB already has both beats -> all updates, no adds.
    added, updated = catalog_io.import_catalog(db, str(out))
    assert added == 0
    assert updated == 2
    db.close()


def test_csv_preserves_tags_roundtrip(tmp_path):
    db = Database(":memory:")
    bid = db.add_beat("/m/A.mp3", "A.mp3")
    db.set_tags(bid, ["one", "two", "three"])
    out = tmp_path / "c.csv"
    catalog_io.export_catalog(db, str(out))
    db.close()

    fresh = Database(":memory:")
    catalog_io.import_catalog(fresh, str(out))
    assert set(fresh.get_tags(fresh.get_by_path("/m/A.mp3")["id"])) == {"one", "two", "three"}
    fresh.close()


def test_format_inferred_from_extension(tmp_path):
    db = Database(":memory:")
    _seed(db)
    csv_path = tmp_path / "c.csv"
    json_path = tmp_path / "c.json"
    catalog_io.export_catalog(db, str(csv_path))
    catalog_io.export_catalog(db, str(json_path))
    assert csv_path.read_text(encoding="utf-8").startswith("file_path,")
    assert json_path.read_text(encoding="utf-8").lstrip().startswith("[")
    db.close()
