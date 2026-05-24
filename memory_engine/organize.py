from __future__ import annotations

import csv
import shutil
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CopyResult:
    source: str
    destination: str
    status: str
    error: str | None


def _safe_part(value: str | None, fallback: str) -> str:
    if not value:
        return fallback
    sanitized = "".join(ch for ch in value if ch not in "\0/\\")
    sanitized = sanitized.strip() or fallback
    return sanitized


def _build_destination(root: Path, row: dict[str, str]) -> Path:
    date_bucket = _safe_part(row.get("date_bucket"), "unknown_date")
    location_label = _safe_part(row.get("location_label"), "unknown_location")
    event_id = _safe_part(row.get("event_id"), "event_unknown")
    source_path = Path(row.get("path", ""))
    filename = source_path.name or "unknown_file"
    return root / date_bucket / location_label / event_id / filename


def _resolve_conflict(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}__{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def copy_from_categories(
    categories_csv: Path,
    output_root: Path,
    dry_run: bool = False,
    overwrite: bool = False,
) -> list[CopyResult]:
    output_root.mkdir(parents=True, exist_ok=True)
    results: list[CopyResult] = []

    with categories_csv.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            source_value = row.get("path", "").strip()
            if not source_value:
                continue
            source_path = Path(source_value)
            destination = _build_destination(output_root, row)
            destination.parent.mkdir(parents=True, exist_ok=True)

            final_destination = destination
            if destination.exists() and not overwrite:
                final_destination = _resolve_conflict(destination)

            if dry_run:
                results.append(
                    CopyResult(
                        source=source_value,
                        destination=str(final_destination),
                        status="dry_run",
                        error=None,
                    )
                )
                continue

            try:
                shutil.copy2(source_path, final_destination)
                results.append(
                    CopyResult(
                        source=source_value,
                        destination=str(final_destination),
                        status="copied",
                        error=None,
                    )
                )
            except Exception as exc:
                results.append(
                    CopyResult(
                        source=source_value,
                        destination=str(final_destination),
                        status="error",
                        error=str(exc),
                    )
                )

    return results
