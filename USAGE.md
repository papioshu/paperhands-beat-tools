# Paperhand's Beat Tools — Usage Guide

A producer beat toolkit: catalog, analyze, tag, preview, split stems, and export
beats. Tags only overlay your own audio — no generated vocals. Originals are
never modified.

---

## Install & launch

### Installed app (recommended)
1. Download `PaperhandsBeatTools-Setup-<version>.exe` from
   [Releases](https://github.com/papioshu/paperhands-beat-tools/releases).
2. Run it and choose an install folder. ffmpeg is bundled.
3. Launch from the Start menu / desktop shortcut. The app checks for updates on
   start and offers to download + install new releases.

### From source
```powershell
python -m pip install -r requirements.txt PySide6
python -m app.main          # desktop app
python tag_beats.py --help  # batch CLI
```
Requires Python 3.10+ and ffmpeg on PATH (`winget install Gyan.FFmpeg`).

---

## The desktop app

### Library (left)
- **Import Beats** / **Scan Folder** to catalog audio in place (files are never
  moved). Add persistent watched folders under **Settings**; they're auto-scanned
  on launch and only new files are added.
- BPM and key are detected in the background; the table fills in as analysis runs
  (watch the progress bar + log at the bottom).
- Search box filters by title / genre / mood / key / tag.
- Multi-select with Ctrl/Shift-click for batch actions.
- **Duplicates** lights up orange when fingerprint-matched copies exist; open it
  to remove extras from the library (files on disk are kept).

### Beat details (right, collapsible)
- Edit title, **BPM/Key** (with detected candidates + confidence), genre,
  sub-genre, mood (a low-confidence suggestion pre-fills an empty mood), tags,
  notes. **Save** to persist.
- **Set image…** to attach your own cover art, or **Generate** a procedural one.
  Cover art is embedded into exported MP3s.
- **Rename file…** renames in place from a pattern; **Relocate…** re-points a
  moved file.

### Tagging
- **Tag library** (collapsible): tags are grouped by **category**; enable/disable
  with the checkbox, **★ favorite**, **▶ Preview**, set category. Pick a tag to
  make it active.
- Toggle **Place on click** and click the waveform to drop the active tag; drag a
  marker to move it, click a marker to remove it.
- **Tag @ Drop** / **Tag @ Hook** place at detected positions.
- **Auto-place** opens a dialog: choose a **profile** (Standard / Paperhand /
  BeatStars / Heavy Protection) or **mode** (intro / fixed / random / structure /
  hook), set interval/jitter and **min spacing** (default 30s so tags never
  stack), and preview the count. Applies to the current beat — or to **all
  selected beats** at once.
- **Layers** (collapsible): each placed tag is a layer with **enable / M(ute) /
  S(olo) / volume / pan**, honored in the export and the live preview.
- **Live preview**: press Play and you'll hear tags fire at their positions
  (the beat stays at full volume — ducking is off by default).
- **Crop preview**: toggle Crop, drag a region on the waveform, then Export
  Tagged Preview to render just that region.
- Scroll the wheel over the waveform to **zoom**; Shift+wheel pans.

### Exports (Tag library panel)
- **Export Tagged Preview** — clean beat + tags (cropped if a region is set),
  320 kbps, with ID3 metadata (producer = your name from Settings) + cover art.
- **Export Clean Master** — your untouched master (verbatim, or WAV via Settings).
- **Export Tag Stem** — a beat-length WAV that is silence except the tags.
- **Export Buyer Package** — a zip with the clean master + manifest (+ license
  placeholder). Outputs land in `masters/ previews/ tag_stems/ packages/
  metadata/` next to your library.

### Batch (toolbar `Batch ▾`)
On the selected beats: Detect BPM/Key, Rename Files, Auto-Place Tags, Export
Tagged Previews, Generate Buyer Packages, Split Stems. Shows a progress bar with
ETA and ✓/✗ counts.

### Stem Splitter
**Batch ▾ → Split Stems** separates a beat into drums/bass/vocals/other (AI,
artifacts possible; source untouched). If the Demucs engine isn't installed, the
app offers a one-click install. Stems go to `stems/<BeatName>/`.

### DAW Mode (toolbar)
Opens a lightweight multitrack workspace for a beat with stems:
- One track per stem with **color / mute / solo / volume / pan / waveform**.
- Transport: **Play Mix** (renders the live stem mix), Stop, **Loop**, seek,
  timestamp.
- A **tag timeline** for non-destructive tags.
- Export menu: Tagged Preview MP3 / Current Mix WAV / Clean Master WAV /
  Individual Stems / Buyer Package ZIP.
- Your mix + tags are saved to `sessions/<BeatName>.session.json` and restored
  when you reopen.

### Settings
Producer name (ID3 artist), watched folders, tag library folder, catalog
export/import (CSV/JSON backup), convert-master-to-WAV toggle, and update repo /
"Check for updates".

---

## Batch CLI (`tag_beats.py`)
Stamp a tag across every MP3 in a folder:
```powershell
python tag_beats.py --input input --tags tags --output output
python tag_beats.py --interval 35 --jitter 4 --no-start --producer "yourname"
```
See `python tag_beats.py --help` for all options. Originals are never overwritten;
a CSV report is written to `reports/`.

---

## Notes
- Stem separation is AI-estimated and may contain artifacts.
- The installed app is unsigned, so Windows SmartScreen shows a "more info → run
  anyway" prompt on first launch (normal for indie apps).
