# Paperhand Beat Manager — User Guide

Catalog, tag, preview, split, and package your beats. Tags only overlay your own
audio — no generated vocals, and your masters are never modified.

---

## Getting started
1. Install **Paperhand Beat Manager** (see the
   [Releases page](https://github.com/papioshu/paperhands-beat-tools/releases))
   and launch it.
2. Open **Settings** and set your **producer name** (stamped on exports), your
   **tag library folder**, and any **watched folders** to scan for new beats.

---

## Library
- **Import Beats** / **Scan Folder** add audio to your catalog in place — files
  are never moved or altered. Watched folders are picked up automatically on
  launch; only new files are added.
- BPM and key are detected in the background; the list fills in as it runs (watch
  the progress bar at the bottom).
- Use the **search box** to filter by title, genre, mood, key, or tag.
- Hold **Ctrl/Shift** to select several beats for batch actions.
- **Duplicates** lights up when matching beats are found; open it to remove the
  extras from your library (your files on disk are kept).

## Beat details
Edit title, **BPM/Key** (with detected suggestions), genre, sub-genre, mood,
tags, and notes — then **Save**. Attach your own cover art with **Set image…**
or **Generate** one; cover art is embedded into tagged previews. **Rename file…**
tidies a filename in place; **Relocate…** re-points a beat you've moved.

## Tagging
- The **Tag library** groups your tags by **category**; enable/disable each,
  mark **★ favorites**, and **▶ Preview** to hear one.
- Toggle **Place on click** and click the waveform to drop the active tag. Drag a
  marker to move it; click it to remove it. Scroll to **zoom** the waveform.
- **Tag @ Drop** / **Tag @ Hook** place at detected spots.
- **Auto-place** opens a dialog to lay tags by **profile** (Standard, Paperhand,
  BeatStars, Heavy Protection) or **mode** (intro, fixed/random interval,
  structure, hook), with a **minimum spacing** so tags never stack. Apply to one
  beat or to all selected beats at once.
- **Layers** lets each tag be its own layer with **mute / solo / volume / pan**,
  reflected in both the preview and the export.
- Press **Play** to preview — placed tags fire at their spots over the
  full-volume beat, just like the export. Toggle **Crop preview** and drag a
  region to preview/export just part of a beat.

## Exports
- **Tagged Preview** — beat + tags (cropped if you set a region), with your
  producer name and cover art embedded.
- **Clean Master** — your untouched master, copied out for delivery.
- **Tag Stem** — a beat-length track with only your tags.
- **Buyer Package** — a zip with the clean master and a details file.

Use the **Batch** menu to run these (plus Detect, Rename, Auto-Place, Split
Stems) across many selected beats with progress, time-remaining, and counts.

## Stem Splitter
**Batch → Split Stems** separates a beat into drums / bass / vocals / other. The
first split downloads the chosen model once (needs internet). Stems are
automatically separated and may contain artifacts; the source is never modified.
Pick the **stem model** in Settings (a faster default, a higher-quality
fine-tuned model, or a 6-stem model); switching downloads it in the background.

## DAW Mode
Opens a multitrack workspace for a beat with stems:
- Each stem row has **M** (mute), **S** (solo), a **volume** slider, a **pan**
  slider, and its **waveform** — **click a stem's waveform to scrub** the
  transport to that spot.
- Transport: **Play Mix** (renders + plays the current stem mix), **Stop**,
  **Loop**, and a seek bar.
- A non-destructive **tag timeline** (click to place, drag to move).
- **Export ▾** lets you choose what to export and where — nothing exports on its
  own. Your mix and tags are saved and restored next time.

Hover any control for a tooltip explaining what it does.

## Settings
Producer name, watched folders, tag library folder, **stem separation model**,
catalog backup (export/import), and update checks.

---

## Troubleshooting
- **"missing"** next to a beat — the file moved; select it and **Relocate**.
- **Silent playback** — check your Windows output device.
- **Stem splitting unavailable** — accept the one-click setup the first time.
- **Wrong BPM/key** — pick a suggested value in Beat details, or type your own.

Outputs are organized next to your library in `masters/`, `previews/`,
`tag_stems/`, `stems/`, `buyer_packages/`, and `sessions/`.
