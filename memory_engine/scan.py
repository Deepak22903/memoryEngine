from __future__ import annotations

import csv
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Sequence


DEFAULT_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".heic",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
    ".mp4",
    ".mov",
    ".avi",
    ".mkv",
    ".m4v",
}


@dataclass(frozen=True)
class MediaRecord:
    path: str
    size_bytes: int
    mtime_utc: str
    extension: str


def _normalize_extensions(extensions: Iterable[str]) -> set[str]:
    normalized = set()
    for ext in extensions:
        ext = ext.strip().lower()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = f".{ext}"
        normalized.add(ext)
    return normalized


def iter_media_files(
    roots: Sequence[Path],
    extensions: Iterable[str],
    exclude_dirs: Iterable[str],
    include_hidden: bool,
    follow_symlinks: bool,
) -> Iterator[Path]:
    ext_set = _normalize_extensions(extensions)
    exclude_set = {name.strip() for name in exclude_dirs if name.strip()}
    for root in roots:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root, followlinks=follow_symlinks):
            dirpath_path = Path(dirpath)
            if not include_hidden and dirpath_path.name.startswith("."):
                dirnames[:] = []
                continue

            dirnames[:] = [
                name
                for name in dirnames
                if name not in exclude_set
                and (include_hidden or not name.startswith("."))
            ]

            for filename in filenames:
                if not include_hidden and filename.startswith("."):
                    continue
                file_path = dirpath_path / filename
                if file_path.suffix.lower() not in ext_set:
                    continue
                yield file_path


def build_record(file_path: Path) -> MediaRecord | None:
    try:
        stat_result = file_path.stat()
    except (FileNotFoundError, PermissionError, OSError):
        return None

    mtime_utc = datetime.fromtimestamp(stat_result.st_mtime, tz=timezone.utc).isoformat()
    return MediaRecord(
        path=str(file_path.resolve()),
        size_bytes=stat_result.st_size,
        mtime_utc=mtime_utc,
        extension=file_path.suffix.lower(),
    )


def scan_to_csv(
    roots: Sequence[Path],
    output_csv: Path,
    extensions: Iterable[str] = DEFAULT_EXTENSIONS,
    exclude_dirs: Iterable[str] | None = None,
    include_hidden: bool = True,
    follow_symlinks: bool = False,
    max_files: int | None = None,
) -> tuple[int, int]:
    exclude_dirs = exclude_dirs or []
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    scanned = 0
    written = 0
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["path", "size_bytes", "mtime_utc", "extension"],
        )
        writer.writeheader()

        for file_path in iter_media_files(
            roots=roots,
            extensions=extensions,
            exclude_dirs=exclude_dirs,
            include_hidden=include_hidden,
            follow_symlinks=follow_symlinks,
        ):
            scanned += 1
            record = build_record(file_path)
            if record is None:
                continue
            writer.writerow(
                {
                    "path": record.path,
                    "size_bytes": record.size_bytes,
                    "mtime_utc": record.mtime_utc,
                    "extension": record.extension,
                }
            )
            written += 1
            if max_files is not None and written >= max_files:
                break

    return scanned, written
