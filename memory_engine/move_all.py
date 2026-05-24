from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from .scan import DEFAULT_EXTENSIONS, iter_media_files


@dataclass(frozen=True)
class MoveResult:
    source: str
    destination: str
    status: str
    error: str | None


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


def move_media(
    roots: Sequence[Path],
    output_root: Path,
    extensions: Iterable[str] = DEFAULT_EXTENSIONS,
    exclude_dirs: Iterable[str] | None = None,
    include_hidden: bool = False,
    follow_symlinks: bool = False,
    max_files: int | None = None,
    dry_run: bool = False,
    overwrite: bool = False,
) -> list[MoveResult]:
    exclude_dirs = exclude_dirs or []
    output_root.mkdir(parents=True, exist_ok=True)
    results: list[MoveResult] = []
    moved = 0

    for file_path in iter_media_files(
        roots=roots,
        extensions=extensions,
        exclude_dirs=exclude_dirs,
        include_hidden=include_hidden,
        follow_symlinks=follow_symlinks,
    ):
        destination = output_root / file_path.name
        final_destination = destination
        if destination.exists() and not overwrite:
            final_destination = _resolve_conflict(destination)

        if dry_run:
            results.append(
                MoveResult(
                    source=str(file_path),
                    destination=str(final_destination),
                    status="dry_run",
                    error=None,
                )
            )
        else:
            try:
                shutil.move(str(file_path), str(final_destination))
                results.append(
                    MoveResult(
                        source=str(file_path),
                        destination=str(final_destination),
                        status="moved",
                        error=None,
                    )
                )
                moved += 1
            except Exception as exc:
                results.append(
                    MoveResult(
                        source=str(file_path),
                        destination=str(final_destination),
                        status="error",
                        error=str(exc),
                    )
                )

        if max_files is not None and moved >= max_files:
            break

    return results
