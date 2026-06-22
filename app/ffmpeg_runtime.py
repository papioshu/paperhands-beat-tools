"""Make ffmpeg available when the app is bundled (PyInstaller).

In a normal dev run pydub finds ffmpeg on PATH. In a frozen build we ship
``ffmpeg.exe`` / ``ffprobe.exe`` alongside the app and point pydub straight at
them (and prepend their folder to PATH), so the installed app needs no separate
ffmpeg install. A no-op when ffmpeg is already resolvable.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path
from typing import Optional


def _bundle_dir() -> Optional[Path]:
    """Where bundled binaries live, or None when not frozen."""
    if getattr(sys, "frozen", False):
        # onedir build: exe folder; onefile: sys._MEIPASS
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        return base
    return None


def _find(base: Path, name: str) -> Optional[Path]:
    for candidate in (base / name, base / "ffmpeg" / name, base / "bin" / name):
        if candidate.exists():
            return candidate
    return None


def configure_ffmpeg() -> None:
    """Resolve ffmpeg/ffprobe for pydub. Safe to call once at startup."""
    base = _bundle_dir()
    ffmpeg = ffprobe = None
    if base is not None:
        ffmpeg = _find(base, "ffmpeg.exe")
        ffprobe = _find(base, "ffprobe.exe")

    # Fall back to whatever is already on PATH (dev runs).
    ffmpeg = ffmpeg or (Path(p) if (p := shutil.which("ffmpeg")) else None)
    ffprobe = ffprobe or (Path(p) if (p := shutil.which("ffprobe")) else None)
    if ffmpeg is None:
        return  # nothing to configure; pydub will error clearly if it's used

    os.environ["PATH"] = str(ffmpeg.parent) + os.pathsep + os.environ.get("PATH", "")
    try:
        from pydub import AudioSegment

        AudioSegment.converter = str(ffmpeg)
        if ffprobe is not None:
            AudioSegment.ffprobe = str(ffprobe)
    except Exception:  # noqa: BLE001 - pydub not importable yet is fine
        pass
