"""Tests for app.services importer + renamer (filesystem, headless, no Qt)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

from app.db.database import Database  # noqa: E402
from app.services import importer, renamer  # noqa: E402


@pytest.fixture
def db():
    d = Database(":memory:")
    yield d
    d.close()


def _make_audio(folder: Path, name: str) -> Path:
    p = folder / name
    p.write_bytes(b"\x00\x00")  # contents irrelevant for cataloging
    return p


# --- importer ---------------------------------------------------------------

def test_import_paths_adds_only_audio(db, tmp_path):
    _make_audio(tmp_path, "a.mp3")
    _make_audio(tmp_path, "b.wav")
    (tmp_path / "notes.txt").write_text("nope")
    added = importer.import_paths(db, [str(p) for p in tmp_path.iterdir()])
    assert added == 2
    assert len(db.list_beats()) == 2


def test_import_is_idempotent(db, tmp_path):
    f = _make_audio(tmp_path, "a.mp3")
    assert importer.import_paths(db, [str(f)]) == 1
    assert importer.import_paths(db, [str(f)]) == 0  # already present
    assert len(db.list_beats()) == 1


def test_scan_folder_recursive(db, tmp_path):
    _make_audio(tmp_path, "top.mp3")
    sub = tmp_path / "sub"
    sub.mkdir()
    _make_audio(sub, "deep.mp3")
    assert importer.scan_folder(db, str(tmp_path), recursive=True) == 2


def test_scan_folder_non_recursive(db, tmp_path):
    _make_audio(tmp_path, "top.mp3")
    sub = tmp_path / "sub"
    sub.mkdir()
    _make_audio(sub, "deep.mp3")
    assert importer.scan_folder(db, str(tmp_path), recursive=False) == 1


def test_scan_missing_folder_raises(db):
    with pytest.raises(NotADirectoryError):
        importer.scan_folder(db, "/no/such/folder")


def test_list_missing(db, tmp_path):
    present = _make_audio(tmp_path, "here.mp3")
    importer.import_paths(db, [str(present)])
    db.add_beat(str(tmp_path / "gone.mp3"), "gone.mp3")  # never existed on disk
    missing = importer.list_missing(db)
    assert len(missing) == 1


# --- renamer ----------------------------------------------------------------

def test_build_basename_full():
    out = renamer.build_basename(
        renamer.DEFAULT_PATTERN, title="Night", original_stem="raw", bpm=140, key="F#min"
    )
    assert out == "Night [140BPM Fsharpmin]"


def test_build_basename_drops_empty_metadata():
    out = renamer.build_basename(
        renamer.DEFAULT_PATTERN, title="Night", original_stem="raw", bpm=None, key=None
    )
    assert out == "Night"  # empty brackets removed


def test_build_basename_strips_illegal_chars():
    out = renamer.build_basename("{title}", title='a/b:c?', original_stem="x")
    assert "/" not in out and ":" not in out and "?" not in out


def test_rename_in_place_moves_file_and_updates_db(db, tmp_path):
    f = _make_audio(tmp_path, "raw.mp3")
    bid = db.add_beat(str(f), "raw.mp3", title="Night")
    db.update_beat(bid, bpm=140, key="F#min")

    new_stem = renamer.build_basename(
        renamer.DEFAULT_PATTERN, title="Night", original_stem="raw", bpm=140, key="F#min"
    )
    new_path = renamer.rename_in_place(db, bid, new_stem)

    assert Path(new_path).exists()
    assert not f.exists()
    assert db.get_beat(bid)["filename"] == "Night [140BPM Fsharpmin].mp3"


def test_rename_collision_raises_and_keeps_original(db, tmp_path):
    a = _make_audio(tmp_path, "a.mp3")
    _make_audio(tmp_path, "b.mp3")
    bid = db.add_beat(str(a), "a.mp3")
    with pytest.raises(FileExistsError):
        renamer.rename_in_place(db, bid, "b")
    assert a.exists()  # untouched
    assert db.get_beat(bid)["filename"] == "a.mp3"


def test_rename_missing_source_raises(db, tmp_path):
    bid = db.add_beat(str(tmp_path / "gone.mp3"), "gone.mp3")
    with pytest.raises(FileNotFoundError):
        renamer.rename_in_place(db, bid, "whatever")
