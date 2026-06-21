"""Pure tests for core.exports manifest + buyer package (no audio needed)."""

import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import exports  # noqa: E402


def test_update_manifest_creates_and_merges(tmp_path):
    m = tmp_path / "beat.json"
    exports.update_manifest(str(m), {
        "beat_name": "Beat_140BPM_Fmin", "bpm": 140, "key": "Fmin",
        "tag_times": [3.0, 42.0],
    })
    exports.update_manifest(str(m), {"tagged_preview": "previews/Beat_TAGGED.mp3"})

    data = json.loads(m.read_text(encoding="utf-8"))
    assert data["beat_name"] == "Beat_140BPM_Fmin"
    assert data["bpm"] == 140
    assert data["tag_times"] == [3.0, 42.0]
    assert data["tagged_preview"] == "previews/Beat_TAGGED.mp3"   # merged, not lost


def test_update_manifest_skips_none_values(tmp_path):
    m = tmp_path / "b.json"
    exports.update_manifest(str(m), {"beat_name": "B", "tag_stem": None})
    data = json.loads(m.read_text(encoding="utf-8"))
    assert "tag_stem" not in data


def test_build_buyer_package_zips_master_and_manifest(tmp_path):
    master = tmp_path / "Beat.wav"
    master.write_bytes(b"RIFF....")
    manifest = tmp_path / "Beat.json"
    manifest.write_text('{"beat_name": "Beat"}', encoding="utf-8")
    out = tmp_path / "Beat.zip"

    exports.build_buyer_package(str(master), str(manifest), str(out))

    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
    assert names == {"Beat.wav", "Beat.json"}


def test_clean_master_is_verbatim_copy(tmp_path):
    src = tmp_path / "master.wav"
    src.write_bytes(b"\x01\x02\x03\x04")
    dst = tmp_path / "out" / "master.wav"
    exports.export_clean_master(str(src), str(dst))
    assert dst.read_bytes() == b"\x01\x02\x03\x04"   # untouched, byte-for-byte


def test_clean_master_to_wav_keeps_wav_source_verbatim(tmp_path):
    # to_wav=True but the source is already WAV -> still a verbatim copy (no decode)
    src = tmp_path / "master.wav"
    src.write_bytes(b"\x05\x06\x07\x08")
    dst = tmp_path / "out" / "master.wav"
    exports.export_clean_master(str(src), str(dst), to_wav=True)
    assert dst.read_bytes() == b"\x05\x06\x07\x08"
