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

    def __init__(self, model_name: str = "htdemucs"):
        self.model_name = model_name
        self._model = None   # cached across splits in a session

    def available(self) -> bool:
        return importlib.util.find_spec("demucs") is not None

    def install_command(self) -> List[str]:
        # demucs + a NumPy-2-safe torch; torchcodec is avoided (we save via soundfile)
        return [sys.executable, "-m", "pip", "install", "demucs"]

    def _load_model(self):
        if self._model is None:
            from demucs.pretrained import get_model
            self._model = get_model(self.model_name)
            self._model.eval()
        return self._model

    def split(self, input_path: str, out_dir: str) -> Dict[str, str]:
        """Separate via the Demucs model and write each stem with soundfile.

        Uses the low-level model API (not the CLI) and saves with soundfile to
        avoid torchaudio's torchcodec dependency. Runs on GPU if available.
        """
        import numpy as np
        import soundfile as sf
        import torch
        from demucs.apply import apply_model
        from demucs.audio import AudioFile

        model = self._load_model()
        wav = AudioFile(input_path).read(
            samplerate=model.samplerate, channels=model.audio_channels)
        if wav.dim() == 3:           # drop the stream dim -> (channels, samples)
            wav = wav[0]
        ref = wav.mean(0)
        wav_n = (wav - ref.mean()) / (ref.std() + 1e-8)

        device = "cuda" if torch.cuda.is_available() else "cpu"
        with torch.no_grad():
            sources = apply_model(model, wav_n[None], device=device, progress=False)[0]
        sources = sources * (ref.std() + 1e-8) + ref.mean()

        os.makedirs(out_dir, exist_ok=True)
        found: Dict[str, str] = {}
        for name, src in zip(model.sources, sources):
            path = os.path.join(out_dir, f"{name}.wav")
            sf.write(path, np.ascontiguousarray(src.cpu().numpy().T), model.samplerate)
            found[name] = path
        if not found:
            raise RuntimeError("Demucs produced no stems.")
        return found


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
