# Cache Invalidation + Queue Cancel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-analyze a cataloged beat only when its file actually changes on disk, and let the user cancel an in-flight analysis batch.

**Architecture:** The SQLite DB is already the analysis cache and `.peaks/*.npy` is the waveform cache; both are only written during analysis, which only runs for beats with `analysis_status` in (None,"","pending"). We add (A) a staleness check — store the file's mtime alongside the existing `file_size`, and on startup compare disk vs stored to re-flag changed files as `pending`; and (B) a Cancel button that clears the thread-pool queue. Resume is free: dropped beats stay `pending` and re-queue next launch.

**Tech Stack:** Python 3.10+, `sqlite3` (stdlib), PySide6 (Qt), pytest. No new dependencies.

## Global Constraints

- No new third-party dependencies — stdlib + existing PySide6 only.
- Non-destructive: never move, copy, or rewrite source audio.
- Do not change tagging, export, update, or library semantics.
- DB access layer (`app/db/database.py`) stays pure stdlib — no Qt, no audio imports.
- Schema changes are additive migrations in `_MIGRATIONS` so existing `library.db` upgrades in place.
- Pure-logic tests must run headless (no Qt import); the change-detection test is pure.

---

### Task 1: Add `file_mtime` column + store it on import

**Files:**
- Modify: `app/db/database.py` (`_EDITABLE` set ~line 20-27; `_MIGRATIONS` dict ~line 31-48)
- Modify: `app/services/importer.py` (`import_paths`, line 28)
- Test: `tests/test_importer_changed.py` (new)

**Interfaces:**
- Consumes: `Database.add_beat(file_path, filename, **fields)`, `Database.get_by_path(path)` (existing).
- Produces: `beats.file_mtime` (REAL) column, writable via `update_beat`/`add_beat`; `import_paths` stores `file_mtime` on new beats.

- [ ] **Step 1: Write the failing test**

Create `tests/test_importer_changed.py`:

```python
"""Change-detection for cache invalidation (headless, no Qt)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.database import Database          # noqa: E402
from app.services import importer             # noqa: E402


def _wav(folder: Path, name: str, size: int) -> Path:
    p = folder / name
    p.write_bytes(b"\0" * size)   # not real audio; scan only stats + checks suffix
    return p


def test_import_stores_mtime(tmp_path):
    db = Database(":memory:")
    _wav(tmp_path, "a.wav", 100)
    importer.scan_folder(db, str(tmp_path))
    row = db.get_by_path(str((tmp_path / "a.wav").resolve()))
    assert row["file_size"] == 100
    assert row["file_mtime"] is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_importer_changed.py::test_import_stores_mtime -v`
Expected: FAIL — `row["file_mtime"]` raises (no such column) or is `None`.

- [ ] **Step 3: Add the migration and make the column editable**

In `app/db/database.py`, add to the `_EDITABLE` set (alongside `"file_size"`):

```python
    "duration_sec", "file_size", "file_mtime", "waveform_path", "analysis_status",
```

In `_MIGRATIONS`, add an entry (after the `"auto_tag"` line):

```python
    "auto_tag": "ALTER TABLE beats ADD COLUMN auto_tag INTEGER DEFAULT 0",
    "file_mtime": "ALTER TABLE beats ADD COLUMN file_mtime REAL",
```

- [ ] **Step 4: Store mtime on import**

In `app/services/importer.py`, `import_paths`, change the `add_beat` call:

```python
        if db.get_by_path(abspath) is None:
            st = p.stat()
            db.add_beat(abspath, p.name, file_size=st.st_size, file_mtime=st.st_mtime)
            added += 1
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_importer_changed.py::test_import_stores_mtime -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/db/database.py app/services/importer.py tests/test_importer_changed.py
git commit -m "feat(cache): store file_mtime on import for change detection"
```

---

### Task 2: `importer.rescan_changed` — flag changed files as pending

**Files:**
- Modify: `app/services/importer.py`
- Test: `tests/test_importer_changed.py` (extend)

**Interfaces:**
- Consumes: `Database.list_beats()`, `Database.get_by_path(path)`, `Database.update_beat(id, **fields)`, `importer.is_audio`, `importer.is_missing`.
- Produces: `importer.rescan_changed(db, folder, recursive=True) -> list[int]` — returns ids re-flagged `pending`; updates their stored `file_size`/`file_mtime`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_importer_changed.py`:

```python
def test_rescan_flags_changed_file(tmp_path):
    db = Database(":memory:")
    p = _wav(tmp_path, "a.wav", 100)
    importer.scan_folder(db, str(tmp_path))
    bid = db.get_by_path(str(p.resolve()))["id"]
    db.update_beat(bid, analysis_status="done", bpm=140.0)

    # Change the file: bigger size + newer mtime.
    p.write_bytes(b"\0" * 250)
    import os, time
    os.utime(p, (time.time() + 10, time.time() + 10))

    changed = importer.rescan_changed(db, str(tmp_path))
    assert changed == [bid]
    row = db.get_beat(bid)
    assert row["analysis_status"] == "pending"
    assert row["file_size"] == 250          # stored stat refreshed


def test_rescan_ignores_unchanged_file(tmp_path):
    db = Database(":memory:")
    p = _wav(tmp_path, "a.wav", 100)
    importer.scan_folder(db, str(tmp_path))
    bid = db.get_by_path(str(p.resolve()))["id"]
    db.update_beat(bid, analysis_status="done")

    assert importer.rescan_changed(db, str(tmp_path)) == []
    assert db.get_beat(bid)["analysis_status"] == "done"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/test_importer_changed.py -v -k rescan`
Expected: FAIL — `AttributeError: module 'app.services.importer' has no attribute 'rescan_changed'`.

- [ ] **Step 3: Implement `rescan_changed`**

Add to `app/services/importer.py` (after `scan_folder`):

```python
def rescan_changed(db, folder: str, recursive: bool = True) -> List[int]:
    """Flag cataloged files under ``folder`` that changed on disk as pending.

    A file is stale when its on-disk (mtime, size) differs from what we stored.
    Stale beats are set analysis_status='pending' and their stored stat is
    refreshed so the next scan won't re-flag them. Returns the re-flagged ids.

    ponytail: mtime+size heuristic — cheap, catches real edits/replacements.
    Upgrade path (content hash) only if false-negatives ever bite.
    """
    root = Path(folder)
    if not root.is_dir():
        raise NotADirectoryError(folder)
    walker = root.rglob("*") if recursive else root.glob("*")
    flagged: List[int] = []
    for p in walker:
        if not (p.is_file() and is_audio(p)):
            continue
        row = db.get_by_path(str(p.resolve()))
        if row is None:
            continue
        st = p.stat()
        if row["file_mtime"] != st.st_mtime or row["file_size"] != st.st_size:
            db.update_beat(row["id"], analysis_status="pending",
                           file_size=st.st_size, file_mtime=st.st_mtime)
            flagged.append(row["id"])
    return flagged
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_importer_changed.py -v`
Expected: PASS (all four tests).

- [ ] **Step 5: Commit**

```bash
git add app/services/importer.py tests/test_importer_changed.py
git commit -m "feat(cache): rescan_changed flags edited files for re-analysis"
```

---

### Task 3: Wire change-rescan into startup

**Files:**
- Modify: `app/ui/main_window.py` (`_startup_scan`, ~line 500-516)

**Interfaces:**
- Consumes: `importer.scan_folder` (existing), `importer.rescan_changed` (Task 2), `self.analyze_pending()` (existing).
- Produces: no new public interface — on launch, changed files are re-queued.

- [ ] **Step 1: Add the rescan call to `_startup_scan`**

In `app/ui/main_window.py`, `_startup_scan`, add a changed-file pass after the existing add-new loop. Current body:

```python
        total = 0
        for folder in folders:
            try:
                total += importer.scan_folder(self.db, folder)
                core_manifest.refresh_under(self.db, folder)
            except NotADirectoryError:
                continue
        if total:
            self.refresh_library(self.search.text())
            self.statusBar().showMessage(
                f"Startup scan: {total} new beat(s) added (existing skipped)", 4000)
```

Change to:

```python
        total = 0
        changed = 0
        for folder in folders:
            try:
                total += importer.scan_folder(self.db, folder)
                changed += len(importer.rescan_changed(self.db, folder))
                core_manifest.refresh_under(self.db, folder)
            except NotADirectoryError:
                continue
        if total:
            self.refresh_library(self.search.text())
            self.statusBar().showMessage(
                f"Startup scan: {total} new beat(s) added (existing skipped)", 4000)
        if changed:
            self.statusBar().showMessage(
                f"{changed} changed file(s) queued for re-analysis", 4000)
        if total or changed:
            self.analyze_pending()
```

Note: `analyze_pending()` already skips beats that aren't `pending`, so calling it is safe even when nothing changed. It is also already called elsewhere on startup for first-time analysis; the guard `if total or changed` avoids a redundant no-op call otherwise.

- [ ] **Step 2: Verify the app still launches and existing GUI tests pass**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_gui_smoke.py -q`
Expected: PASS (no regressions).

- [ ] **Step 3: Commit**

```bash
git add app/ui/main_window.py
git commit -m "feat(cache): re-analyze changed files on startup scan"
```

---

### Task 4: Cancel button on the progress panel

**Files:**
- Modify: `app/ui/progress_panel.py`

**Interfaces:**
- Produces: `ProgressPanel.cancelled` (Qt `Signal()`), emitted when the user clicks Cancel; a `Cancel` button shown by `begin()` and hidden by `end()`.

- [ ] **Step 1: Add the Cancel button and signal**

In `app/ui/progress_panel.py`:

Change the class declaration and add the signal + button. Update the import line:

```python
from PySide6.QtCore import QUrl, Qt, Signal
```

Add the signal at class scope (right after `class ProgressPanel(QFrame):`):

```python
class ProgressPanel(QFrame):
    cancelled = Signal()   # user asked to stop the current batch
```

In `__init__`, after the `self.btn_log` block in the `top` row, add:

```python
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setFixedWidth(70)
        self.btn_cancel.setToolTip("Stop queuing the rest of this batch")
        self.btn_cancel.clicked.connect(self.cancelled)
        self.btn_cancel.hide()
        top.addWidget(self.btn_cancel)
```

In `begin()`, show it:

```python
        self.btn_cancel.show()
        self.show()
```

In `end()`, hide it (at the top of the method):

```python
        self.btn_cancel.hide()
        self.busy.setRange(0, 1)
```

- [ ] **Step 2: Write a construction/emit test**

Add to `tests/test_progress.py` (headless-offscreen; file already exists):

```python
def test_cancel_button_emits_signal(qapp):
    from app.ui.progress_panel import ProgressPanel
    panel = ProgressPanel()
    fired = []
    panel.cancelled.connect(lambda: fired.append(True))
    panel.begin("Analyzing", 3)
    assert panel.btn_cancel.isVisible()
    panel.btn_cancel.click()
    assert fired == [True]
```

If `tests/test_progress.py` has no `qapp` fixture, use the same QApplication setup the other tests in that file use (check the top of the file and mirror it).

- [ ] **Step 3: Run the test**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_progress.py::test_cancel_button_emits_signal -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app/ui/progress_panel.py tests/test_progress.py
git commit -m "feat(queue): add Cancel button + signal to progress panel"
```

---

### Task 5: Handle cancel in the main window

**Files:**
- Modify: `app/ui/main_window.py` (signal wiring near line 106-111; add `_cancel_analysis`; reset counters)

**Interfaces:**
- Consumes: `ProgressPanel.cancelled` (Task 4), `self.pool` (QThreadPool), `self._analysis_total`, `self._analysis_done`, `self.progress`.
- Produces: `MainWindow._cancel_analysis()` slot.

- [ ] **Step 1: Wire the signal**

In `app/ui/main_window.py`, after `self.progress = ProgressPanel()` (~line 356), connect:

```python
        self.progress = ProgressPanel()
        self.progress.cancelled.connect(self._cancel_analysis)
```

- [ ] **Step 2: Implement the slot**

Add near the other analysis handlers (after `_on_progress`):

```python
    def _cancel_analysis(self) -> None:
        """Stop queuing the rest of the analysis batch.

        pool.clear() drops runnables that haven't started; the few already
        running finish (their DB writes are real results, harmless to keep).
        Cancelled-but-unstarted beats stay analysis_status='pending', so they
        re-queue on the next launch/rescan — resume is free.

        ponytail: cancel stops the queue, not the current file — analysis is one
        opaque librosa call per file, not worth mid-call interruption plumbing.
        """
        self.pool.clear()
        self._analysis_total = self._analysis_done = 0
        self.progress.end("Analysis cancelled")
```

- [ ] **Step 3: Verify GUI smoke tests still pass**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/test_gui_smoke.py tests/test_progress.py -q`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app/ui/main_window.py
git commit -m "feat(queue): cancel clears the analysis queue (resume via pending state)"
```

---

### Task 6: Full-suite regression + manual smoke

**Files:** none (verification only)

- [ ] **Step 1: Run the whole suite**

Run: `QT_QPA_PLATFORM=offscreen python -m pytest tests/ -q`
Expected: all pass (previous 226 + new change-detection/cancel tests; the deleted stale `_playable_tag` test stays gone).

- [ ] **Step 2: Manual smoke (user)**

Launch `python -m app.main`. Confirm:
- App opens; startup scan runs without error.
- Edit/replace a cataloged file on disk, relaunch → status bar reports "N changed file(s) queued", and the beat re-analyzes.
- Start an analysis batch, click **Cancel** → progress shows "Analysis cancelled", queue stops; relaunch → remaining beats resume.

- [ ] **Step 3: Final commit (if any doc/notes updates)**

```bash
git add -A
git commit -m "chore: cache-invalidation + cancel verified"
```

---

## Self-Review

**Spec coverage:**
- Change detection (invalidate DB cache when file changes) → Tasks 1–3. ✅
- "Don't re-analyze unless changed" → Task 3 (rescan only flags changed; `analyze_pending` skips `done`). ✅
- Cancel → Tasks 4–5. ✅
- Resume (free via pending state) → Task 5 docstring + Task 6 manual check. ✅
- Waveform cache / analysis cache / SQLite storage / background workers → already exist, explicitly out of scope in spec. ✅
- Lazy/visible-only rendering + export asset reuse → deferred in spec (sub-project #1 / optional). ✅

**Placeholder scan:** No TBD/TODO; every code step shows real code and exact commands. One conditional instruction in Task 4 Step 2 (mirror existing `qapp` setup) — acceptable because it depends on the current contents of `test_progress.py`, which the implementer has open.

**Type consistency:** `rescan_changed(db, folder, recursive=True) -> list[int]` defined in Task 2, consumed identically in Task 3. `file_mtime` column name consistent across Tasks 1–2. `ProgressPanel.cancelled` signal defined in Task 4, consumed in Task 5. `_cancel_analysis` defined and wired in Task 5. Consistent.
