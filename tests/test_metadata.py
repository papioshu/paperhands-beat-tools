"""Unit tests for core.metadata.build_id3_tags (pure)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import metadata  # noqa: E402


def test_producer_maps_to_artist():
    tags = metadata.build_id3_tags("paperhand")
    assert tags["artist"] == "paperhand"
    assert tags["album_artist"] == "paperhand"


def test_full_set_builds_comment():
    tags = metadata.build_id3_tags(
        "paperhand", title="Night", genre="Trap", bpm=140.4, key="F#min",
        mood="Dark", tags=["dark", "808"],
    )
    assert tags["title"] == "Night"
    assert tags["genre"] == "Trap"
    assert tags["BPM"] == "140"                       # rounded
    assert tags["comment"] == "140 BPM | F#min | Dark | tags: dark, 808"


def test_empty_fields_are_omitted():
    tags = metadata.build_id3_tags("paperhand")
    assert "title" not in tags
    assert "genre" not in tags
    assert "comment" not in tags


def test_default_producer_constant():
    assert metadata.DEFAULT_PRODUCER == "paperhand"
