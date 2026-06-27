"""Extract a cover image embedded in an audio file's tags (best-effort, mutagen).

Covers the common containers: ID3/APIC (mp3), FLAC/OGG ``.pictures``, and MP4
``covr`` atoms. Writes the picture next to the library's other artwork and returns
its path, or None when there's no embedded image (or mutagen isn't installed).
The original audio file is never modified.
"""

from __future__ import annotations

import os
from typing import Optional, Tuple


def _ext(mime: str) -> str:
    return ".png" if "png" in (mime or "").lower() else ".jpg"


def _find_picture(m) -> Tuple[Optional[bytes], str]:
    pics = getattr(m, "pictures", None)        # FLAC / OGG
    if pics:
        return pics[0].data, _ext(pics[0].mime)
    tags = getattr(m, "tags", None)
    if tags:
        for key in list(tags.keys()):          # ID3 APIC:* frames
            if str(key).startswith("APIC"):
                p = tags[key]
                return p.data, _ext(getattr(p, "mime", ""))
        covr = tags.get("covr") if hasattr(tags, "get") else None
        if covr:                                # MP4 / M4A
            c = covr[0]
            ext = ".png" if getattr(c, "imageformat", None) == 13 else ".jpg"
            return bytes(c), ext
    return None, ""


def extract_cover(audio_path: str, out_dir: str, stem: str) -> Optional[str]:
    """Save the embedded cover (if any) to ``<out_dir>/<stem><ext>``; return path."""
    try:
        from mutagen import File as MutagenFile
    except ImportError:
        return None
    try:
        m = MutagenFile(audio_path)
        if m is None:
            return None
        data, ext = _find_picture(m)
        if not data:
            return None
        os.makedirs(out_dir, exist_ok=True)
        out = os.path.join(out_dir, f"{stem}{ext}")
        with open(out, "wb") as fh:
            fh.write(data)
        return out
    except Exception:  # noqa: BLE001 - best-effort, never block analysis
        return None
