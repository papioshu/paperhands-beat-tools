# Paperhand Beat Manager

Catalog, tag, preview, split, and package your beats — built for producers.

Paperhand Beat Manager keeps your catalog organized, stamps your producer tags
on previews without touching your masters, splits beats into stems, and bundles
clean buyer packages — all from one app.

---

## Download & install

1. Download the latest **installer** from the
   [Releases page](https://github.com/papioshu/paperhands-beat-tools/releases).
2. Run it and choose where to install. Everything it needs is included.
3. Launch **Paperhand Beat Manager** from your Start menu or desktop.

On first launch Windows may show a "Windows protected your PC" notice for a new
app — choose **More info → Run anyway**.

The app checks for updates on launch and offers to install new versions for you.

---

## Quick start

1. **Import beats** — click **Import Beats** (pick files) or **Scan Folder**
   (pick a folder). Your files stay where they are; nothing is moved or changed.
   BPM and key are detected automatically in the background.
2. **Set your producer name** — open **Settings** and enter the name to stamp on
   exports.
3. **Add tags** — drop your tag files into your tag folder (set in **Settings**
   or the **Tag library** panel). Select a beat, pick a tag, toggle **Place on
   click**, and click the waveform to place it. Drag a marker to move it; click
   it to remove it.
4. **Auto-place** — click **Auto-place** to lay tags down by profile (Standard,
   Paperhand, BeatStars, Heavy Protection) or by mode (intro, fixed interval,
   structure, hook), with a minimum spacing so tags never stack.
5. **Export** — see below.

Press **Play** to preview; placed tags play at their spots over the full-volume
beat, exactly like the export.

---

## Exports

From the **Tag library** panel (or **Batch** for many beats at once):

- **Tagged Preview** — your beat with tags baked in, for sharing/previews.
  Cover art and your producer name are embedded.
- **Clean Master** — your untouched master, copied out for delivery.
- **Tag Stem** — a silent track with only your tags, aligned to the beat.
- **Buyer Package** — a ready-to-send zip with the clean master and a details
  file. (Never includes your originals' folders or anything private.)

Outputs are organized next to your library:

```
masters/  previews/  tag_stems/  stems/  buyer_packages/  sessions/
```

Files are named clearly, e.g. `Midnight Drive_140BPM_Fsharpmin_tagged.mp3`.

---

## Stem Splitter & DAW Mode

- **Split Stems** (Batch menu) separates a beat into **drums / bass / vocals /
  other**. The first split downloads a small separation model once (needs
  internet); after that it works offline. Stems are automatically separated and
  may contain artifacts; your original file is never modified.
- **DAW Mode** opens a lightweight multitrack workspace for a beat with stems:
  mute/solo/volume/pan each stem, play the live mix, place tags on the timeline,
  and export a tagged preview, the current mix, the clean master, individual
  stems, or a buyer package. Your mix and tags are saved and restored next time.

---

## Tips & troubleshooting

- **A beat shows "missing"** — the file moved or was renamed. Select it and use
  **Relocate** to point at its new location.
- **Duplicates** lights up when it finds matching beats; open it to clean them
  out of your library (your files on disk are kept).
- **Playback is silent** — check your output device in Windows sound settings.
- **Stem splitting unavailable** — accept the one-click setup prompt the first
  time you split (it downloads the stem engine).
- **Nothing imported** — only audio files are added (`.mp3 .wav .flac .aiff …`).

---

Paperhand Beat Manager only overlays your own tag audio onto previews. It never
generates vocals, and your masters are always left untouched.
