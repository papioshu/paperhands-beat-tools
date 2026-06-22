"""Product branding: name + asset resolution (works in dev and frozen builds)."""

from __future__ import annotations

import sys
from pathlib import Path

APP_NAME = "Paperhand Beat Manager"
PUBLISHER = "Paperhand"


def asset_path(name: str) -> str:
    """Locate a bundled asset (icon, logo) in dev or a packaged build."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    else:
        base = Path(__file__).resolve().parents[1]
    for candidate in (base / "assets" / name, base / name):
        if candidate.exists():
            return str(candidate)
    return str(base / "assets" / name)


def icon_path() -> str:
    return asset_path("icon.ico")


def logo_path() -> str:
    return asset_path("icon.png")
