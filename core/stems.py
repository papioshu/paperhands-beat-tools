"""Pluggable stem separation. Default engine: Demucs.

Stem separation is AI-estimated and may contain artifacts; it never touches the
original file. The engine is pluggable so MDX-Net / audio-separator / Spleeter /
external APIs can be added later behind the same interface.

Demucs (and its PyTorch dependency, multi-GB) is intentionally NOT bundled. The
GUI offers a one-click install via ``install_command()`` when it's missing.
"""

from __future__ import annotations

import glob
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional

DEFAULT_STEMS = ["vocals", "drums", "bass", "other"]


class StemEngine:
    name = "base"

    def available(self) -> bool:
        raise NotImplementedError

    def split(self, input_path: str, out_dir: str) -> Dict[str, str]:
        raise NotImplementedError

    def install_command(self) -> Optional[List[str]]:
        """pip command to install this engine, or None if not installable."""
        return None


def _collect_stems(search_dir: str, out_dir: str) -> Dict[str, str]:
    """Find the standard stems anywhere under ``search_dir`` and copy to out_dir."""
    os.makedirs(out_dir, exist_ok=True)
    found: Dict[str, str] = {}
    for stem in DEFAULT_STEMS:
        hits = glob.glob(os.path.join(search_dir, "**", f"{stem}.*"), recursive=True)
        if hits:
            dst = os.path.join(out_dir, f"{stem}.wav")
            shutil.copy(hits[0], dst)
            found[stem] = dst
    return found


class DemucsEngine(StemEngine):
    name = "Demucs"

    def available(self) -> bool:
        return (importlib.util.find_spec("demucs") is not None
                or shutil.which("demucs") is not None)

    def install_command(self) -> List[str]:
        return [sys.executable, "-m", "pip", "install", "demucs"]

    def split(self, input_path: str, out_dir: str) -> Dict[str, str]:
        tmp = tempfile.mkdtemp(prefix="demucs_")
        proc = subprocess.run(
            [sys.executable, "-m", "demucs", "-o", tmp, input_path],
            capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError((proc.stderr or proc.stdout or "demucs failed")[-600:])
        stems = _collect_stems(tmp, out_dir)
        if not stems:
            raise RuntimeError("Demucs produced no stems.")
        return stems


ENGINES = {"Demucs": DemucsEngine}
# Future: "MDX-Net", "audio-separator", "Spleeter", external APIs.


def get_engine(name: str = "Demucs") -> StemEngine:
    return ENGINES.get(name, DemucsEngine)()


def build_instrumental(stems: Dict[str, str], out_path: str) -> Optional[str]:
    """Sum the non-vocal stems into an instrumental WAV. Returns path or None."""
    from pydub import AudioSegment

    parts = [stems[s] for s in ("drums", "bass", "other") if s in stems]
    if not parts:
        return None
    mix = AudioSegment.from_file(parts[0])
    for p in parts[1:]:
        mix = mix.overlay(AudioSegment.from_file(p))
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    mix.export(out_path, format="wav")
    return out_path
