from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from .categorize import categorize_from_db
from .dedupe import find_duplicate_groups, hash_media_from_csv, write_duplicates_csv
from .metadata import extract_metadata_from_csv
from .organize import copy_from_categories
from .scan import DEFAULT_EXTENSIONS, scan_to_csv


@dataclass(frozen=True)
class PipelineResult:
    scan_csv: Path
    hashes_csv: Path | None
    duplicates_csv: Path | None
    metadata_db: Path | None
    categories_csv: Path | None
    organized_root: Path | None


def run_pipeline(
    roots: Sequence[Path],
    output_dir: Path,
    extensions: Iterable[str] = DEFAULT_EXTENSIONS,
    exclude_dirs: Iterable[str] | None = None,
    include_hidden: bool = False,
    follow_symlinks: bool = False,
    max_files: int | None = None,
    enable_dedupe: bool = True,
    include_phash: bool = True,
    phash_threshold: int = 0,
    enable_metadata: bool = True,
    exiftool_path: str = "exiftool",
    enable_categorize: bool = True,
    enable_geocode: bool = False,
    geocode_delay: float = 1.0,
    geocode_user_agent: str = "memory_engine",
    enable_faces: bool = False,
    event_window_days: int = 1,
    enable_organize: bool = False,
    organize_root: Path | None = None,
    organize_dry_run: bool = False,
    organize_overwrite: bool = False,
) -> PipelineResult:
    exclude_dirs = exclude_dirs or []
    output_dir.mkdir(parents=True, exist_ok=True)

    scan_csv = output_dir / "media_master.csv"
    scan_to_csv(
        roots=roots,
        output_csv=scan_csv,
        extensions=extensions,
        exclude_dirs=exclude_dirs,
        include_hidden=include_hidden,
        follow_symlinks=follow_symlinks,
        max_files=max_files,
    )

    hashes_csv: Path | None = None
    duplicates_csv: Path | None = None
    if enable_dedupe:
        hashes_csv = output_dir / "media_hashes.csv"
        duplicates_csv = output_dir / "media_duplicates.csv"
        records = hash_media_from_csv(
            input_csv=scan_csv,
            output_csv=hashes_csv,
            include_phash=include_phash,
        )
        duplicates = find_duplicate_groups(records, phash_threshold=phash_threshold)
        write_duplicates_csv(duplicates, duplicates_csv)

    metadata_db: Path | None = None
    if enable_metadata:
        metadata_db = output_dir / "media_metadata.db"
        extract_metadata_from_csv(
            input_csv=scan_csv,
            output_db=metadata_db,
            exiftool_path=exiftool_path,
        )

    categories_csv: Path | None = None
    if enable_categorize:
        categories_csv = output_dir / "media_categories.csv"
        if metadata_db is None:
            metadata_db = output_dir / "media_metadata.db"
            extract_metadata_from_csv(
                input_csv=scan_csv,
                output_db=metadata_db,
                exiftool_path=exiftool_path,
            )
        categorize_from_db(
            input_db=metadata_db,
            output_csv=categories_csv,
            enable_geocode=enable_geocode,
            geocode_delay=geocode_delay,
            geocode_user_agent=geocode_user_agent,
            enable_faces=enable_faces,
            event_window_days=event_window_days,
        )

    organized_root: Path | None = None
    if enable_organize:
        organized_root = organize_root or (output_dir / "organized_media")
        if categories_csv is None:
            categories_csv = output_dir / "media_categories.csv"
            if metadata_db is None:
                metadata_db = output_dir / "media_metadata.db"
                extract_metadata_from_csv(
                    input_csv=scan_csv,
                    output_db=metadata_db,
                    exiftool_path=exiftool_path,
                )
            categorize_from_db(
                input_db=metadata_db,
                output_csv=categories_csv,
                enable_geocode=enable_geocode,
                geocode_delay=geocode_delay,
                geocode_user_agent=geocode_user_agent,
                enable_faces=enable_faces,
                event_window_days=event_window_days,
            )
        copy_from_categories(
            categories_csv=categories_csv,
            output_root=organized_root,
            dry_run=organize_dry_run,
            overwrite=organize_overwrite,
        )

    return PipelineResult(
        scan_csv=scan_csv,
        hashes_csv=hashes_csv,
        duplicates_csv=duplicates_csv,
        metadata_db=metadata_db,
        categories_csv=categories_csv,
        organized_root=organized_root,
    )
