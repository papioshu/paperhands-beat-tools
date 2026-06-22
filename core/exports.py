"""Non-destructive export pieces: clean master, tag-only stem, manifest, package.

Design rule: the cataloged file IS the clean master and is never modified. Tags
are an overlay layer. Previews are rendered from *clean source + tag layer*; we
never strip tags from a baked MP3. The tag stem lets a buyer/engineer reproduce
or remove tagging cleanly because it's a separate silent-plus-tags track.

This module is additive — it does not change the existing engine in
``core.audio`` / ``core.pipeline``; it builds on it.
"""

from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path
from typing import Dict, Optional, Sequence

from . import audio


def export_clean_master(src_path: str, dst_path: str, to_wav: bool = False) -> str:
    """Place the untouched master into the export tree.

    By default this is a verbatim byte-for-byte copy (never re-encoded — the most
    non-destructive choice). With ``to_wav=True`` a non-WAV source is decoded once
    to PCM WAV (e.g. for buyers who require WAV); a WAV source is still copied
    verbatim.
    """
    Path(dst_path).parent.mkdir(parents=True, exist_ok=True)
    if to_wav and Path(src_path).suffix.lower() != ".wav":
        audio.load_audio(src_path).export(dst_path, format="wav")
    else:
        shutil.copy2(src_path, dst_path)
    return dst_path


def export_tag_stem(
    beat_path: str,
    placements: Sequence,
    dst_path: str,
    tag_cache: Optional[Dict[str, object]] = None,
) -> str:
    """Render a tag-only WAV: silence the exact length of the beat, tags overlaid.

    Same duration / sample-rate / channels as the master, so the stem lines up
    sample-for-sample. No beat audio is present — only the producer tags at their
    placement times.
    """
    from pydub import AudioSegment

    beat = audio.load_audio(beat_path)
    stem = AudioSegment.silent(duration=len(beat), frame_rate=beat.frame_rate)
    stem = stem.set_channels(beat.channels)

    tag_cache = tag_cache if tag_cache is not None else {}
    for p in placements:
        if not Path(p.tag_path).exists():
            continue                                  # skip missing tag files
        if p.tag_path not in tag_cache:
            try:
                tag_cache[p.tag_path] = audio.load_audio(p.tag_path)
            except Exception:  # noqa: BLE001 - skip a bad tag, keep going
                tag_cache[p.tag_path] = None
        tag = tag_cache[p.tag_path]
        if tag is None:
            continue
        if tag.channels != stem.channels:
            tag = tag.set_channels(stem.channels)
        stem = stem.overlay(tag, position=int(round(p.position_sec * 1000)))

    Path(dst_path).parent.mkdir(parents=True, exist_ok=True)
    stem.export(dst_path, format="wav")
    return dst_path


def update_manifest(manifest_path: str, updates: Dict) -> Dict:
    """Merge ``updates`` into the per-beat manifest JSON (created if absent)."""
    path = Path(manifest_path)
    data: Dict = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
    data.update({k: v for k, v in updates.items() if v is not None})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return data


def build_buyer_package(clean_master_path: str, manifest_path: str, dst_zip: str) -> str:
    """Zip the clean master + manifest for delivery. Never includes a tagged file."""
    Path(dst_zip).parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dst_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        if Path(clean_master_path).exists():
            zf.write(clean_master_path, Path(clean_master_path).name)
        if Path(manifest_path).exists():
            zf.write(manifest_path, Path(manifest_path).name)
    return dst_zip
