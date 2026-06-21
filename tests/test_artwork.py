"""Tests for core.artwork (needs Pillow)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

pytest.importorskip("PIL")

from core import artwork  # noqa: E402


def test_generate_artwork_creates_valid_square_png(tmp_path):
    from PIL import Image

    out = tmp_path / "art" / "cover.png"
    artwork.generate_artwork(
        str(out), title="Midnight Drive", bpm=140, key="F#min", mood="dark", size=512)
    assert out.exists()
    with Image.open(out) as im:
        assert im.size == (512, 512)


def test_generation_is_deterministic_per_metadata(tmp_path):
    a = tmp_path / "a.png"
    b = tmp_path / "b.png"
    kw = dict(title="X", bpm=120, key="Amin", mood="chill", size=256)
    artwork.generate_artwork(str(a), **kw)
    artwork.generate_artwork(str(b), **kw)
    assert a.read_bytes() == b.read_bytes()        # same metadata -> same art


def test_import_artwork_copies_verbatim(tmp_path):
    src = tmp_path / "mine.jpg"
    src.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg")
    dst = tmp_path / "art" / "beat.jpg"
    artwork.import_artwork(str(src), str(dst))
    assert dst.read_bytes() == src.read_bytes()
