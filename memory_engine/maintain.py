from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from .scan import scan_to_csv


def _timestamp() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def run_maintenance(
    roots: Sequence[Path],
    output_dir: Path,
    extensions: Iterable[str],
    exclude_dirs: Iterable[str],
    include_hidden: bool,
    follow_symlinks: bool,
    interval_minutes: float,
    max_files: int | None,
    max_runs: int | None,
    timestamped: bool,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    run_count = 0

    while True:
        run_count += 1
        if timestamped:
            output_csv = output_dir / f"media_master_{_timestamp()}.csv"
        else:
            output_csv = output_dir / "media_master.csv"

        scan_to_csv(
            roots=roots,
            output_csv=output_csv,
            extensions=extensions,
            exclude_dirs=exclude_dirs,
            include_hidden=include_hidden,
            follow_symlinks=follow_symlinks,
            max_files=max_files,
        )

        if max_runs is not None and run_count >= max_runs:
            break

        if interval_minutes <= 0:
            break

        time.sleep(interval_minutes * 60)
