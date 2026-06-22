"""Where the app keeps its data — a writable, per-user (or portable) location.

The installed app can't write next to its exe (Program Files is read-only), so
the library, exports, logs, backups, sessions, and recovery file all live under a
single data directory:

* **Portable build** (a ``portable.txt`` next to the exe): a ``Data`` folder
  beside the exe, so settings/sessions travel with it.
* **Installed / from source**: ``Documents/Paperhand Beat Manager``.

All paths are normalized; ``within(base, target)`` guards against writing outside
an approved directory (path-traversal safety).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

APP_DIRNAME = "Paperhand Beat Manager"


def exe_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def is_portable() -> bool:
    return (exe_dir() / "portable.txt").exists()


def data_dir() -> Path:
    if is_portable():
        d = exe_dir() / "Data"
    else:
        docs = Path(os.environ.get("USERPROFILE", Path.home())) / "Documents"
        d = (docs if docs.exists() else Path.home()) / APP_DIRNAME
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sub(name: str) -> Path:
    d = data_dir() / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def library_db() -> Path:
    return data_dir() / "library.db"


def logs_dir() -> Path:
    return _sub("logs")


def backups_dir() -> Path:
    return _sub("backups")


def recovery_path() -> Path:
    return data_dir() / "recovery.json"


def settings_ini() -> Path:
    """Local settings file (used in portable mode instead of the registry)."""
    return data_dir() / "settings.ini"


def within(base: Path, target: Path) -> bool:
    """True if ``target`` resolves to a path inside ``base`` (no traversal out)."""
    try:
        Path(target).resolve().relative_to(Path(base).resolve())
        return True
    except (ValueError, OSError):
        return False
