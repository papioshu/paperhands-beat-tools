"""CSV report writer for a batch run.

Uses pandas (part of the project's stack) so the report is trivially re-openable
for later analytics. One row per processed file.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Sequence

from .models import TagResult

_COLUMNS = ["original_name", "output_name", "bpm", "key", "placements_sec", "error"]


def _row(r: TagResult) -> dict:
    return {
        "original_name": r.original_name,
        "output_name": r.output_name,
        "bpm": r.bpm,
        "key": r.key,
        # Seconds rounded for readability, semicolon-joined to stay one CSV cell.
        "placements_sec": ";".join(f"{s:.2f}" for s in r.placements_sec),
        "error": r.error,
    }


def write_report(results: Sequence[TagResult], reports_dir: str) -> str:
    """Write all results to ``reports_dir/tag_report_<timestamp>.csv``.

    Returns the path written. Falls back to stdlib ``csv`` if pandas is absent.
    """
    Path(reports_dir).mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = Path(reports_dir) / f"tag_report_{stamp}.csv"
    rows = [_row(r) for r in results]

    try:
        import pandas as pd

        pd.DataFrame(rows, columns=_COLUMNS).to_csv(out_path, index=False)
    except ImportError:  # pragma: no cover - graceful fallback
        import csv

        with open(out_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)

    return str(out_path)
