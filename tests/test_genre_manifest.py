"""Genre heuristic + per-folder beats.json sidecar."""

import json
import os

from core import genre, manifest
from app.db import Database


def test_classify_buckets():
    # tempo drives the bucket; dark+fast leans drill, else trap
    assert genre._classify(80, "Amin", 1200, 0.03)[0] == "lofi"
    assert genre._classify(80, "Amin", 1200, 0.2)[0] == "boom bap"
    assert genre._classify(100, "Cmaj", 2000, 0.1)[0] == "hip hop"
    assert genre._classify(124, "Amin", 2500, 0.1)[0] == "house"
    assert genre._classify(140, "Cmaj", 3000, 0.1)[0] == "trap"
    assert genre._classify(142, "Amin", 1500, 0.1)[0] == "drill"
    assert genre._classify(170, "Amin", 2000, 0.1)[0] == "drum & bass"


def test_manifest_round_trip(tmp_path):
    folder = tmp_path / "MyBeats"
    folder.mkdir()
    f = folder / "trap1.wav"
    f.write_bytes(b"RIFF")  # content irrelevant; only the path is cataloged

    db = Database(":memory:")
    bid = db.add_beat(str(f), f.name, genre="trap", bpm=140)

    out = manifest.refresh_for_beat(db, str(f))
    assert out == str(folder / "beats.json")

    data = json.loads(open(out, encoding="utf-8").read())
    assert data["count"] == 1
    beat = data["beats"][0]
    assert beat["filename"] == "trap1.wav"
    assert beat["genre"] == "trap"
    assert beat["bpm"] == 140

    # an edit re-writes the sidecar with the new value
    db.update_beat(bid, genre="drill")
    manifest.refresh_for_beat(db, str(f))
    data = json.loads(open(out, encoding="utf-8").read())
    assert data["beats"][0]["genre"] == "drill"


def test_manifest_skips_empty_dir(tmp_path):
    db = Database(":memory:")
    assert manifest.write_dir_manifest(db, str(tmp_path)) is None
    assert not os.path.exists(tmp_path / "beats.json")
