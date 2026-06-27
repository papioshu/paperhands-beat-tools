# Changelog

## 1.2.1
- Keep all AI assistant tooling/config/output out of the repo: ignore `.claude/`,
  `brag-output/`, and common assistant files; untrack the previously committed
  `.claude/settings.json` (stays local).

## 1.2.0

### Tempo-aware tag placement & stretching
- Producer tags can store a **native BPM**; tags are time-stretched to lock to
  the selected beat's BPM.
- **Tempo match** controls in the Tag library: Tag BPM, Match-beat toggle, Mode
  (Normal / Half-Time / Double-Time / Manual), Preserve-pitch toggle, a live
  stretch readout (with a half/double-time suggestion when out of range), and
  Preview.
- Safe stretch limits (0.85×–1.25×); pitch-preserving by default, with an
  optional tape mode where pitch tracks speed.
- Stretch is stored **per placement** and applied by click-placement, Auto-Place,
  and Batch Tag. New **Stretch editor** button fine-tunes each placed tag, with
  in-window help.
- Rendered into tagged previews and tag stems on export. Original tag files and
  the clean master are never modified.

### Library & metadata
- **Auto-detect genre**: reads the file's embedded genre tag, falling back to a
  BPM/key/feature heuristic.
- **Rescan Library (fill missing)** re-analyzes beats missing BPM/key/genre.
- Scans now pick up **embedded cover art** (never overwrites art you set).
- Per-folder **`beats.json`** sidecar written/updated after every scan and on any
  metadata change.
- Scan Folder gains an **Include subfolders** checkbox.

### Selection & duplicates
- **Checkboxes + Select all** in the library; batch actions act on checked beats.
- Duplicates window: **Select all** and a **Mark ignore** option (ignored beats
  stop being flagged as duplicates).

### Batch & exports
- **Batch Tag (manual times)**: place tags at up to 4 manual times (1 required)
  across many beats.
- A **`previews.json`** is written after a batch of tagged previews is generated.

### Fixes
- Auto-Place now defaults to placing a tag **every 30s** (was a single intro tag).
