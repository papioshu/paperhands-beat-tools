"""Entry point for the Paperhand's Beat Tools desktop app.

Run from the repo root with:
    python -m app.main
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running as a script (so `core` and `app` import cleanly).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PySide6.QtWidgets import QApplication  # noqa: E402

from app.ffmpeg_runtime import configure_ffmpeg  # noqa: E402
from app.theme import apply_theme  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402


def main() -> int:
    configure_ffmpeg()    # resolve bundled ffmpeg when frozen
    app = QApplication(sys.argv)
    app.setApplicationName("Paperhand's Beat Tools")
    apply_theme(app)

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
