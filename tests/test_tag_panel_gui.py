"""Tag panel tree: categories, enable toggle, favorite (offscreen)."""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from app import config  # noqa: E402
from app.db import Database  # noqa: E402
from app.ui.tag_panel import TagLibraryPanel  # noqa: E402


def _app():
    return QApplication.instance() or QApplication([])


def test_panel_lists_enables_and_favorites(tmp_path):
    tagdir = tmp_path / "tags"
    tagdir.mkdir()
    (tagdir / "PaperMadeIt.wav").write_bytes(b"\x00")
    (tagdir / "Oni.wav").write_bytes(b"\x00")

    old = config.tags_folder()
    config.set_tags_folder(str(tagdir))
    try:
        _app()
        db = Database(":memory:")
        panel = TagLibraryPanel(db)        # refresh_tags syncs the folder

        assert len(db.list_tag_files()) == 2
        assert panel.active_tag().endswith(".wav")
        assert len(panel.all_tag_paths()) == 2     # both enabled by default

        # Disable one -> all_tag_paths (enabled only) drops it.
        ids = [t["id"] for t in db.list_tag_files()]
        db.update_tag_file(ids[0], enabled=0)
        assert len(panel.all_tag_paths()) == 1

        # Favorite the currently-selected tag via the panel action.
        panel._toggle_favorite()
        assert any(t["favorite"] for t in db.list_tag_files())
        db.close()
    finally:
        config.set_tags_folder(old)
