"""Unit tests for app.db.database — headless, in-memory SQLite, no Qt."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from app.db.database import Database  # noqa: E402


@pytest.fixture
def db():
    d = Database(":memory:")
    yield d
    d.close()


def test_add_and_get_beat(db):
    bid = db.add_beat("/music/Night.mp3", "Night.mp3")
    row = db.get_beat(bid)
    assert row["filename"] == "Night.mp3"
    assert row["title"] == "Night.mp3"
    assert row["analysis_status"] == "pending"


def test_add_is_idempotent_by_path(db):
    a = db.add_beat("/music/Night.mp3", "Night.mp3")
    b = db.add_beat("/music/Night.mp3", "Night.mp3")
    assert a == b
    assert len(db.list_beats()) == 1


def test_update_beat_fields(db):
    bid = db.add_beat("/music/Night.mp3", "Night.mp3")
    db.update_beat(bid, bpm=140.0, key="F#min", genre="Trap", analysis_status="done")
    row = db.get_beat(bid)
    assert row["bpm"] == 140.0
    assert row["key"] == "F#min"
    assert row["genre"] == "Trap"
    assert row["analysis_status"] == "done"


def test_update_ignores_unknown_columns(db):
    bid = db.add_beat("/music/Night.mp3", "Night.mp3")
    db.update_beat(bid, not_a_column="x", bpm=90)  # unknown silently dropped
    assert db.get_beat(bid)["bpm"] == 90


def test_relocate_updates_path(db):
    bid = db.add_beat("/old/Night.mp3", "Night.mp3")
    db.update_beat(bid, file_path="/new/Night.mp3")
    assert db.get_by_path("/new/Night.mp3")["id"] == bid
    assert db.get_by_path("/old/Night.mp3") is None


def test_tags_set_get_and_dedup(db):
    bid = db.add_beat("/music/Night.mp3", "Night.mp3")
    db.set_tags(bid, ["dark", "Dark", " melodic ", "sample-free"])
    tags = db.get_tags(bid)
    # case-insensitive dedup, trimmed
    assert "melodic" in tags
    assert "sample-free" in tags
    assert sum(1 for t in tags if t.lower() == "dark") == 1


def test_set_tags_replaces(db):
    bid = db.add_beat("/music/Night.mp3", "Night.mp3")
    db.set_tags(bid, ["a", "b"])
    db.set_tags(bid, ["c"])
    assert db.get_tags(bid) == ["c"]


def test_search_matches_title_genre_and_tags(db):
    b1 = db.add_beat("/m/Night.mp3", "Night.mp3")
    db.update_beat(b1, genre="Trap")
    b2 = db.add_beat("/m/Sunrise.mp3", "Sunrise.mp3")
    db.set_tags(b2, ["melodic"])

    assert {r["id"] for r in db.list_beats(search="trap")} == {b1}
    assert {r["id"] for r in db.list_beats(search="melodic")} == {b2}
    assert {r["id"] for r in db.list_beats(search="night")} == {b1}


def test_filter_by_genre_and_mood(db):
    b1 = db.add_beat("/m/a.mp3", "a.mp3")
    db.update_beat(b1, genre="Trap", mood="Dark")
    b2 = db.add_beat("/m/b.mp3", "b.mp3")
    db.update_beat(b2, genre="Drill", mood="Dark")

    assert {r["id"] for r in db.list_beats(genre="Trap")} == {b1}
    assert {r["id"] for r in db.list_beats(mood="Dark")} == {b1, b2}


def test_distinct_values_and_tag_names(db):
    b1 = db.add_beat("/m/a.mp3", "a.mp3")
    db.update_beat(b1, genre="Trap")
    db.set_tags(b1, ["dark", "melodic"])
    b2 = db.add_beat("/m/b.mp3", "b.mp3")
    db.update_beat(b2, genre="Drill")

    assert db.distinct_values("genre") == ["Drill", "Trap"]
    assert db.all_tag_names() == ["dark", "melodic"]


def test_placements_column_roundtrip(db):
    bid = db.add_beat("/m/Night.mp3", "Night.mp3")
    db.update_beat(bid, placements='[{"pos": 3.0, "tag": "/t/a.wav"}]')
    assert db.get_beat(bid)["placements"] == '[{"pos": 3.0, "tag": "/t/a.wav"}]'


def test_delete_cascades_tags(db):
    bid = db.add_beat("/m/a.mp3", "a.mp3")
    db.set_tags(bid, ["dark"])
    db.delete_beat(bid)
    assert db.get_beat(bid) is None
    # tag vocabulary remains, but the link is gone
    assert db.conn.execute("SELECT COUNT(*) FROM beat_tags").fetchone()[0] == 0
