#!/usr/bin/env python3
"""Paperhand's Beat Tools — batch producer-tag stamper (CLI).

Stamps your producer tag across every MP3 in a folder and writes tagged copies
to an output folder, plus a CSV report. Originals are never touched.

This is a *beat preview* tool: it only overlays your existing tag audio onto
instrumentals. It never generates vocals or alters the musical content.

Quick start (Windows):
    1) Install ffmpeg:   winget install Gyan.FFmpeg   (restart terminal after)
    2) Install deps:     python -m pip install -r requirements.txt
    3) Put beats in .\\input  and tag files in .\\tags
    4) Run:              python tag_beats.py
    Tagged files land in .\\output ; a report lands in .\\reports

See README.md for the full guide. Run `python tag_beats.py --help` for all flags.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make `core` importable whether run from the repo root or elsewhere.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core import audio, report  # noqa: E402
from core.models import TaggingConfig, TagResult  # noqa: E402
from core.pipeline import process_file  # noqa: E402

AUDIO_TAG_EXTS = {".wav", ".mp3", ".aiff", ".aif", ".flac", ".ogg", ".m4a"}


def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="tag_beats",
        description="Batch-stamp a producer tag across every MP3 in a folder.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    # Folders
    p.add_argument("--input", default="input", help="Folder of untagged MP3 beats.")
    p.add_argument("--tags", default="tags", help="Folder of producer tag files.")
    p.add_argument("--output", default="output", help="Where tagged MP3s are written.")
    p.add_argument("--reports", default="reports", help="Where the CSV report is written.")

    # Placement
    p.add_argument("--interval", type=float, default=40.0,
                   help="Seconds between repeated tags.")
    p.add_argument("--jitter", type=float, default=0.0,
                   help="Random +/- wobble (seconds) on each interval spot.")
    start = p.add_mutually_exclusive_group()
    start.add_argument("--start", dest="tag_at_start", action="store_true", default=True,
                       help="Also place a tag at the very beginning (default).")
    start.add_argument("--no-start", dest="tag_at_start", action="store_false",
                       help="Do not place a tag at the beginning.")
    p.add_argument("--before-drop", action="store_true",
                   help="Best-effort: anchor the first tag at the detected drop "
                        "instead of 0:00 (experimental; falls back to 0:00).")

    # Mixing
    p.add_argument("--duck-db", type=float, default=6.0,
                   help="dB to lower the beat under each tag.")
    p.add_argument("--headroom-db", type=float, default=1.0,
                   help="Normalize peak target = -headroom dBFS (clip safety).")

    # Detection / naming
    p.add_argument("--bpm", type=float, default=None,
                   help="Manual BPM override (skips detection for BPM).")
    p.add_argument("--key", default=None,
                   help='Manual key override, e.g. "F#min" (skips key detection).')
    p.add_argument("--no-detect", dest="detect", action="store_false", default=True,
                   help="Disable automatic BPM/key detection entirely.")
    p.add_argument("--suffix", default="_tagged", help="Suffix added to output names.")

    # Export / reproducibility
    p.add_argument("--bitrate", default="320k", help="Output MP3 bitrate.")
    p.add_argument("--seed", type=int, default=None,
                   help="Seed RNG for reproducible tag rotation / jitter.")

    return p.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> TaggingConfig:
    return TaggingConfig(
        interval_sec=args.interval,
        tag_at_start=args.tag_at_start,
        jitter_sec=args.jitter,
        before_drop=args.before_drop,
        duck_db=args.duck_db,
        headroom_db=args.headroom_db,
        bpm_override=args.bpm,
        key_override=args.key,
        detect=args.detect,
        suffix=args.suffix,
        bitrate=args.bitrate,
        seed=args.seed,
    )


def _list_files(folder: Path, exts: set) -> list:
    return sorted(f for f in folder.iterdir() if f.is_file() and f.suffix.lower() in exts)


def main(argv=None) -> int:
    args = parse_args(argv)

    input_dir = Path(args.input)
    tags_dir = Path(args.tags)
    output_dir = Path(args.output)
    reports_dir = Path(args.reports)

    # --- validation / friendly errors -------------------------------------
    if not input_dir.is_dir():
        print(f"ERROR: input folder not found: {input_dir.resolve()}", file=sys.stderr)
        return 2
    if not tags_dir.is_dir():
        print(f"ERROR: tags folder not found: {tags_dir.resolve()}", file=sys.stderr)
        return 2

    try:
        audio.ensure_ffmpeg()
    except audio.FfmpegNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 3

    beats = _list_files(input_dir, {".mp3"})
    tag_paths = [str(t) for t in _list_files(tags_dir, AUDIO_TAG_EXTS)]
    if not beats:
        print(f"ERROR: no .mp3 files found in {input_dir.resolve()}", file=sys.stderr)
        return 4
    if not tag_paths:
        print(f"ERROR: no tag files found in {tags_dir.resolve()} "
              f"(supported: {', '.join(sorted(AUDIO_TAG_EXTS))})", file=sys.stderr)
        return 4

    output_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    config = config_from_args(args)

    print(f"Tagging {len(beats)} beat(s) with {len(tag_paths)} tag(s)...")
    print(f"  interval={config.interval_sec}s  start={config.tag_at_start}  "
          f"jitter={config.jitter_sec}s  before_drop={config.before_drop}  "
          f"duck={config.duck_db}dB  bitrate={config.bitrate}")

    # --- process each beat; one bad file never kills the batch ------------
    tag_cache: dict = {}
    results = []
    failures = 0
    for i, beat_path in enumerate(beats, start=1):
        print(f"  [{i}/{len(beats)}] {beat_path.name} ... ", end="", flush=True)
        try:
            res = process_file(str(beat_path), tag_paths, str(output_dir), config, tag_cache)
            results.append(res)
            extra = []
            if res.bpm is not None:
                extra.append(f"{res.bpm:g} BPM")
            if res.key:
                extra.append(res.key)
            tail = f" ({', '.join(extra)})" if extra else ""
            print(f"-> {res.output_name}{tail}  [{len(res.placements_sec)} tags]")
        except Exception as exc:  # noqa: BLE001 - record and continue
            failures += 1
            results.append(TagResult(original_name=beat_path.name, error=str(exc)))
            print(f"FAILED: {exc}")

    report_path = report.write_report(results, str(reports_dir))
    ok = len(results) - failures
    print(f"\nDone. {ok} tagged, {failures} failed.")
    print(f"Report: {report_path}")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
