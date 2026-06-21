"""End-to-end processing of a single beat: detect -> place -> mix -> export.

This is the seam the GUI will reuse: give it a beat, some tags, an output dir,
and a TaggingConfig, and it returns a TagResult (one CSV row). Detection
failures are swallowed (the beat is still tagged); load/export failures raise so
the caller can record them per-file and keep the batch going.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Dict, Optional, Sequence

from . import audio, detection, naming
from .models import TaggingConfig, TagResult
from .placement import compute_placements


def _resolve_bpm_key(beat, stem: str, config: TaggingConfig):
    """Decide the BPM/key to use, detecting only what's missing and wanted."""
    bpm: Optional[float] = config.bpm_override
    key: Optional[str] = config.key_override

    want_bpm = bpm is None and not naming.has_bpm_token(stem)
    want_key = key is None and not naming.has_key_token(stem)

    if config.detect and (want_bpm or want_key):
        samples, sr = audio.to_mono_float(beat)
        result = detection.detect_bpm_key(samples, sr)
        if want_bpm:
            bpm = result.bpm
        if want_key:
            key = result.key
    return bpm, key


def _start_offset(beat, config: TaggingConfig) -> float:
    """Where the first tag anchors: detected drop (if enabled) else 0.0."""
    if not config.before_drop:
        return 0.0
    samples, sr = audio.to_mono_float(beat)
    drop = detection.detect_first_drop(samples, sr)
    return drop if drop is not None else 0.0


def process_file(
    input_path: str,
    tag_paths: Sequence[str],
    output_dir: str,
    config: TaggingConfig,
    tag_cache: Optional[Dict[str, object]] = None,
) -> TagResult:
    """Tag one beat and write the result. Returns a TagResult for the report.

    Args:
        input_path: Source MP3.
        tag_paths: Producer tag files to rotate through.
        output_dir: Where the tagged MP3 is written (created by the caller).
        config: All placement/mixing/naming/export settings.
        tag_cache: Optional shared cache of loaded tag AudioSegments (avoids
            re-decoding the same tag for every beat in a batch).

    Raises:
        Exceptions from loading/exporting audio (caller records them per-file).
    """
    src = Path(input_path)
    result = TagResult(original_name=src.name)

    beat = audio.load_audio(input_path)

    # --- detection (best-effort, never fatal) ---
    bpm, key = _resolve_bpm_key(beat, src.stem, config)
    result.bpm, result.key = bpm, key

    # --- where do tags go? ---
    rng = random.Random(config.seed) if config.seed is not None else random.Random()
    offset = _start_offset(beat, config)
    placements = compute_placements(
        duration_sec=len(beat) / 1000.0,
        tag_paths=list(tag_paths),
        interval_sec=config.interval_sec,
        tag_at_start=config.tag_at_start,
        jitter_sec=config.jitter_sec,
        start_offset_sec=offset,
        rng=rng,
    )
    result.placements_sec = [p.position_sec for p in placements]

    # --- mix tags in, ducking under each ---
    if tag_cache is None:
        tag_cache = {}
    for path in {p.tag_path for p in placements}:
        if path not in tag_cache:
            tag_cache[path] = audio.load_audio(path)

    mixed = audio.apply_placements(beat, placements, tag_cache, config.duck_db)
    mixed = audio.normalize_safe(mixed, config.headroom_db)

    # --- name + export ---
    out_stem = naming.build_output_stem(src.stem, bpm, key, config.suffix)
    out_path = Path(output_dir) / f"{out_stem}.mp3"
    audio.export_mp3(mixed, str(out_path), config.bitrate)

    result.output_name = out_path.name
    return result


def export_with_placements(
    input_path: str,
    placements: Sequence,
    out_path: str,
    config: TaggingConfig,
    tag_cache: Optional[Dict[str, object]] = None,
) -> str:
    """Mix an explicit list of placements onto a beat and export it.

    This is the GUI's export path: the user has placed tags by hand on the
    waveform, so we skip auto-placement/detection and just duck+overlay+normalize
    the given :class:`~core.models.Placement` list, then write ``out_path``.

    Returns the path written.
    """
    beat = audio.load_audio(input_path)

    tag_cache = tag_cache if tag_cache is not None else {}
    for p in placements:
        if p.tag_path not in tag_cache:
            tag_cache[p.tag_path] = audio.load_audio(p.tag_path)

    mixed = audio.apply_placements(beat, placements, tag_cache, config.duck_db)
    mixed = audio.normalize_safe(mixed, config.headroom_db)
    audio.export_mp3(mixed, out_path, config.bitrate)
    return out_path
