# Paperhand's Beat Tools — Batch Producer-Tag Stamper

Stamp your producer tag across every MP3 in a folder, with one command (or one
double-click). Tagged copies go to a separate folder; **your originals are never
touched**. A CSV report records what happened to each file.

> This is a **beat-preview** tool. It only overlays *your existing tag audio*
> onto instrumentals — it never generates vocals or changes the music.

---

## What it does

For every `.mp3` in `input/`:

1. Optionally detects **BPM** and **key** (librosa) — only if they aren't already
   in the filename and you didn't override them.
2. Places your tag at the start (optional) and **again every ~40s** (configurable),
   with optional random **jitter** so placements aren't robotic.
3. **Rotates randomly** through every tag file in `tags/` (use one or many).
4. **Ducks** the beat a few dB under each tag so the tag is clearly audible.
5. **Normalizes** safely so the export never clips.
6. Exports a **320 kbps** MP3 named like `Beat_140BPM_Fsharpmin_tagged.mp3`
   (BPM/key appended only if missing — never duplicated).
7. Writes a CSV report to `reports/`.

---

## Folder structure

```
Paperhand'sBeatTools/
├── tag_beats.py          # the CLI
├── run_tagger.bat        # double-click launcher (Windows)
├── requirements.txt
├── core/                 # shared audio engine (reused by the future GUI)
├── tests/                # unit tests (no ffmpeg needed)
├── input/                # <- put untagged MP3 beats here
├── tags/                 # <- put your producer tag (WAV/MP3) here
├── output/               # -> tagged MP3s appear here
└── reports/              # -> CSV reports appear here
```

---

## Windows setup (one time)

**1. Python** — 3.10+ (3.13 recommended). Check:

```powershell
python --version
```

**2. ffmpeg** — required for reading/writing MP3. Easiest via winget:

```powershell
winget install Gyan.FFmpeg
```

Then **close and reopen** your terminal so `PATH` updates. Verify:

```powershell
ffmpeg -version
```

(Manual alternative: download from https://www.gyan.dev/ffmpeg/builds/, unzip,
and add the `bin` folder to your PATH.)

**3. Python packages:**

```powershell
python -m pip install -r requirements.txt
```

---

## Usage

Put beats in `input/`, your tag(s) in `tags/`, then:

```powershell
# Simplest — uses all defaults (start + every 40s, 320k):
python tag_beats.py

# Tag every 35s with +/-4s random wobble, no tag at the very start:
python tag_beats.py --interval 35 --jitter 4 --no-start

# Force a BPM/key (skips detection) and a lighter duck:
python tag_beats.py --bpm 140 --key F#min --duck-db 4

# Experimental: anchor the first tag at the detected drop:
python tag_beats.py --before-drop

# Reproducible rotation/jitter for a consistent run:
python tag_beats.py --seed 42
```

See every option:

```powershell
python tag_beats.py --help
```

### Double-click mode

Just run **`run_tagger.bat`**. To bake in options, edit its `set OPTIONS=` line,
e.g. `set OPTIONS=--interval 35 --jitter 4 --before-drop`.

---

## Options reference

| Flag | Default | Meaning |
|------|---------|---------|
| `--input / --tags / --output / --reports` | `input` / `tags` / `output` / `reports` | Folders |
| `--interval` | `40` | Seconds between repeated tags |
| `--jitter` | `0` | Random ± wobble (s) on each interval spot |
| `--start` / `--no-start` | `--start` | Place a tag at the very beginning |
| `--before-drop` | off | Anchor first tag at the detected drop (experimental) |
| `--duck-db` | `6` | dB the beat drops under each tag |
| `--headroom-db` | `1` | Normalize peak target = −headroom dBFS |
| `--bpm` | auto | Manual BPM (skips BPM detection) |
| `--key` | auto | Manual key e.g. `F#min` (skips key detection) |
| `--no-detect` | — | Disable BPM/key detection entirely |
| `--bitrate` | `320k` | Output MP3 bitrate |
| `--suffix` | `_tagged` | Suffix added to output filenames |
| `--seed` | random | Seed for reproducible rotation/jitter |

---

## Troubleshooting

- **`ffmpeg was not found`** — install it (step 2) and reopen your terminal.
- **`no .mp3 files found`** — put beats in `input/` (only `.mp3` is processed).
- **`no tag files found`** — put a `.wav`/`.mp3` tag in `tags/`.
- **Wrong BPM/key detected** — detection is a best guess; override with
  `--bpm` / `--key`, or disable it with `--no-detect`.
- **A single file failed** — the batch continues; the reason is logged in the
  `error` column of the CSV report.

---

## Quality note

MP3 is lossy, and tagging requires decode → mix → re-encode, so there's always
some re-encode loss. Exporting at **320 kbps** (the default) keeps it
near-transparent. For archival masters, tag from lossless sources instead.

---

## Running the tests

The pure-logic tests (naming + placement) need no ffmpeg or audio libraries:

```powershell
python -m pip install pytest
python -m pytest tests/ -q
```
