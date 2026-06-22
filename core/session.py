"""DAW Mode session persistence: sessions/<BeatName>.session.json (pure).

A session captures everything needed to reopen a beat's DAW workspace: identity
(name/bpm/key/duration), the clean master + stem paths, tag placements, per-track
mix state (mute/solo/volume/pan), and an export history.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Dict, List, Optional


def session_path(base_dir: str, beat_name: str) -> str:
    return os.path.join(base_dir, "sessions", f"{beat_name}.session.json")


def build_session(
    beat_name: str,
    *,
    bpm=None,
    key=None,
    duration=None,
    source_master: str = "",
    stems: Optional[Dict[str, str]] = None,
    tag_placements: Optional[List[dict]] = None,
    tracks: Optional[Dict[str, dict]] = None,
    export_history: Optional[List[dict]] = None,
) -> dict:
    return {
        "beat_name": beat_name,
        "bpm": bpm,
        "key": key,
        "duration": duration,
        "source_master": source_master,
        "stems": stems or {},
        "tag_placements": tag_placements or [],
        "tracks": tracks or {},          # stem -> {mute, solo, volume_db, pan}
        "export_history": export_history or [],
    }


def save_session(path: str, data: dict) -> str:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    return path


def load_session(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


def record_export(data: dict, kind: str, out_path: str) -> dict:
    """Append an export to the session's history (in place) and return it."""
    data.setdefault("export_history", []).append({
        "type": kind,
        "path": out_path,
        "time": datetime.now().isoformat(timespec="seconds"),
    })
    return data
