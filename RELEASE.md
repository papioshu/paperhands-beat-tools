# Paperhand Beat Manager — Release Notes

## v1.0.0

### Install
Pick one from the [Releases page](https://github.com/papioshu/paperhands-beat-tools/releases):

- **Installer** — `PaperhandsBeatTools-Setup-1.0.1.exe`. Run it, choose where to
  install, then open **Paperhand Beat Manager** from your Start menu/desktop.
- **Portable** — `PaperhandBeatManager-Portable-1.0.1.zip`. Unzip anywhere and
  run `PaperhandsBeatTools.exe`; it keeps its settings and sessions in a `Data`
  folder next to the app, so it runs from a USB drive with no install.

(If Windows shows a "protected your PC" notice for a new app, choose
**More info → Run anyway**.)

**Verify your download (optional, advanced):** each file has a matching
`.sha256`. In PowerShell: `Get-FileHash .\<file> -Algorithm SHA256` and compare.

### First run
1. Open **Settings** and set your **producer name**, your **tag library folder**,
   and any **watched folders** to scan for beats.
2. **Import Beats** or **Scan Folder** to build your catalog (files stay in
   place; BPM and key are detected for you).
3. Place tags on the waveform — or use **Auto-place** — then **Export Tagged
   Preview**. Use **Batch** to tag and export many beats at once.

### What's in this release
- Beat catalog with automatic BPM/key detection, search, duplicate cleanup, and
  cover art.
- Non-destructive tagging: place tags by hand or by profile, with layers
  (mute/solo/volume/pan) and live preview.
- Exports: tagged previews, clean masters, tag stems, and buyer packages.
- Batch operations across many beats with progress and time-remaining.
- Stem splitting (drums/bass/vocals/other), included and ready to use.
- DAW Mode: a lightweight multitrack stem workspace with saved sessions.
- Automatic update checking.

### Known issues
- Because it's a new, unsigned app, Windows SmartScreen may warn on first launch
  (choose **Run anyway**).
- Stem separation downloads a small model the first time you use it (needs
  internet once), and is automatically estimated — results may contain artifacts. Your originals are
  never changed.
- Stem splitting is CPU-intensive; large libraries take time to process.
