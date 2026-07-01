# Cache Invalidation + Queue Cancel — Design

**Sub-project #2 of the DAW Mode v1.5 roadmap** (sequence chosen by user:
#2 caching/queue → #1 zoomable timeline → #3 MIDI import).

## Context

The v1.5 spec asks for a "caching + queue" subsystem: analysis cache, waveform
cache, "don't re-analyze unless changed", background workers, and a queue with
progress/cancel/resume.

Most of this already exists in the shipping app:

| Spec ask | Already there |
|---|---|
| Store index in JSON/SQLite | SQLite `library.db` + JSON sessions + `.npy` peaks |
| Analysis cache (BPM/key/stems) | Results persist in `beats` columns — that *is* the cache |
| Don't re-analyze every launch | `analyze_pending()` skips `analysis_status='done'`; startup scan only *adds new* files |
| Waveform cache | `.peaks/<beat_id>.npy` written on analysis, reused after |
| Background workers | `app/workers/` on `QThreadPool` |
| Queue progress + ETA + log | `app/ui/progress_panel.py` |

So this sub-project is **not** a new caching subsystem. It fills the two real
gaps and nothing more.

## Goals

1. **Cache invalidation** — when a cataloged file changes on disk, notice it and
   re-analyze; otherwise never re-analyze. Makes "don't re-analyze *unless
   changed*" literally true.
2. **Cancel** — let the user stop an in-flight analysis batch.

## Non-goals (deferred / already done)

- Lazy / visible-only waveform rendering → belongs to sub-project #1 (timeline).
- Explicit in-session Pause/Resume → cross-launch DB persistence already covers
  resume; not building a pause toggle.
- Export asset reuse (skip re-rendering unchanged clean master) → optional
  micro-optimization, out of scope here.
- Any new cache store — the DB and `.peaks` already are the cache.

## Design

**Principle: the DB is the cache.** We add the missing staleness check plus a
Cancel button. No cache layer, no new storage.

### A. Change detection

- **Schema** (`app/db/database.py`): add one column via the existing
  `_MIGRATIONS` dict — `file_mtime REAL`. (`file_size` already exists.)
- **On add** (`app/services/importer.py`): `import_paths` already stores
  `file_size` — also store `file_mtime = p.stat().st_mtime`.
- **New** `importer.rescan_changed(db, folder) -> list[int]`:
  - Walk the folder (same walker as `scan_folder`).
  - For each file already cataloged (`db.get_by_path`), compare on-disk
    `(st_mtime, st_size)` against stored `(file_mtime, file_size)`.
  - If either differs: set `analysis_status='pending'`, update stored
    `file_mtime`/`file_size`, and collect the id.
  - Return the list of re-flagged ids. Pure logic, no Qt, unit-testable.
  - `ponytail:` mtime+size heuristic — cheap and catches real edits/replacements.
    Upgrade path (content hash) only if false-negatives ever bite.
- **Wiring** (`app/ui/main_window._startup_scan`): after the existing
  `scan_folder` (adds new), call `rescan_changed` for each watched folder, then
  `analyze_pending()`. Auto-flag, zero user clicks.

Staleness rule: a file is stale if `on_disk.st_mtime != stored.file_mtime` **or**
`on_disk.st_size != stored.file_size`. Stored stat is updated at flag time so the
next scan doesn't re-flag it.

### B. Cancel

- **`app/ui/progress_panel.py`**: add a Cancel button that emits a `cancelled`
  signal. Visible while a batch runs.
- **`app/ui/main_window.py`**: on `cancelled` →
  - `self.pool.clear()` — removes queued-but-not-yet-started runnables.
  - Reset `_analysis_total` / `_analysis_done` to 0, update/hide progress.
  - In-flight files (one un-chunkable librosa call each, ~thread-count of them)
    run to completion; their DB writes are real results, harmless to keep.
  - `ponytail:` cancel stops the queue, not the current file(s) — mid-file kill
    isn't worth the plumbing for a single opaque librosa call. Upgrade path:
    chunked analysis with a `threading.Event` check if users need instant stop.
- **Resume is free**: beats dropped from the queue stay `analysis_status='pending'`
  in the DB, so the next launch (or manual rescan) re-queues them automatically.

### C. Waveform cache

Nothing to build. `.peaks/<beat_id>.npy` is written during analysis and reused
thereafter; analysis now only runs when a file actually changed, so the peaks
cache is invalidated exactly when it should be.

## Data flow

```
launch
  └─ _startup_scan
       ├─ scan_folder(folder)        # add new files (existing behavior)
       ├─ rescan_changed(folder)     # stale files -> analysis_status='pending'
       └─ analyze_pending()          # queue workers for all pending
             └─ AnalysisRunnable ... -> WorkerSignals -> DB updated + .peaks written

Cancel button
  └─ pool.clear(); reset counters; hide progress
       (unfinished beats remain 'pending' -> re-queued next launch)
```

## Testing

- `tests/test_importer_changed.py` (pure, no Qt):
  1. Create a temp audio-named file, `scan_folder` → cataloged with stored
     mtime/size.
  2. Modify it (bump size + mtime), `rescan_changed` → returns that id, beat is
     `analysis_status='pending'`, stored stat updated.
  3. Rescan again with no change → returns empty, status unchanged.
- Cancel is thin Qt glue; the risky logic (change detection) carries the test.
  Existing GUI smoke tests continue to cover the progress panel constructing.

## Files touched

- `app/db/database.py` — add `file_mtime` migration; include in column list.
- `app/services/importer.py` — store mtime on add; add `rescan_changed`.
- `app/ui/main_window.py` — `_startup_scan` calls `rescan_changed` +
  `analyze_pending`; Cancel handler.
- `app/ui/progress_panel.py` — Cancel button + `cancelled` signal.
- `tests/test_importer_changed.py` — change-detection test.

No changes to tagging, export, update, or library semantics.
