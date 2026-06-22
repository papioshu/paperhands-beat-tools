"""Entry point for Paperhand Beat Manager."""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running as a script (so `core` and `app` import cleanly).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app import crashlog, paths  # noqa: E402
from app.branding import APP_NAME, icon_path  # noqa: E402
from app.ffmpeg_runtime import configure_ffmpeg  # noqa: E402
from app.theme import apply_theme  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402


def main() -> int:
    configure_ffmpeg()    # resolve bundled ffmpeg when frozen
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setWindowIcon(QIcon(icon_path()))
    apply_theme(app)
    crashlog.install()    # friendly errors + crash logs (no stack traces shown)

    # Library + all outputs live in a writable per-user (or portable) data dir.
    window = MainWindow(db_path=str(paths.library_db()))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
