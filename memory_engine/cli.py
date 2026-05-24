from __future__ import annotations

import argparse
from pathlib import Path

from .dedupe import find_duplicate_groups, hash_media_from_csv, write_duplicates_csv
from .metadata import extract_metadata_from_csv
from .categorize import categorize_from_db
from .organize import copy_from_categories
from .maintain import run_maintenance
from .pipeline import run_pipeline
from .scan import DEFAULT_EXTENSIONS, scan_to_csv


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="memory_engine")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="Scan for media files and write a CSV")
    scan_parser.add_argument(
        "--root",
        action="append",
        default=[],
        help="Root directory to scan (repeatable). Defaults to current directory.",
    )
    scan_parser.add_argument(
        "--output",
        default="media_master.csv",
        help="Output CSV path (default: media_master.csv).",
    )
    scan_parser.add_argument(
        "--extensions",
        default=",".join(sorted(DEFAULT_EXTENSIONS)),
        help="Comma-separated list of extensions to include.",
    )
    scan_parser.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        help="Directory name to exclude (repeatable).",
    )
    scan_parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="Include hidden files and directories.",
    )
    scan_parser.add_argument(
        "--follow-symlinks",
        action="store_true",
        help="Follow symlinked directories.",
    )
    scan_parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Stop after writing N rows (for quick tests).",
    )

    dedupe_parser = subparsers.add_parser(
        "dedupe", help="Hash files from a scan CSV and report duplicates"
    )
    dedupe_parser.add_argument(
        "--input",
        default="media_master.csv",
        help="Input CSV from scan (default: media_master.csv).",
    )
    dedupe_parser.add_argument(
        "--hashes",
        default="media_hashes.csv",
        help="Output CSV with MD5 and pHash (default: media_hashes.csv).",
    )
    dedupe_parser.add_argument(
        "--duplicates",
        default="media_duplicates.csv",
        help="Output CSV listing duplicate groups (default: media_duplicates.csv).",
    )
    dedupe_parser.add_argument(
        "--no-phash",
        action="store_true",
        help="Skip perceptual hashing for images.",
    )
    dedupe_parser.add_argument(
        "--phash-threshold",
        type=int,
        default=0,
        help="Hamming distance threshold for near-duplicate pHash matching (default: 0).",
    )

    metadata_parser = subparsers.add_parser(
        "metadata", help="Extract EXIF metadata and store in SQLite"
    )
    metadata_parser.add_argument(
        "--input",
        default="media_master.csv",
        help="Input CSV from scan (default: media_master.csv).",
    )
    metadata_parser.add_argument(
        "--output",
        default="media_metadata.db",
        help="Output SQLite DB (default: media_metadata.db).",
    )
    metadata_parser.add_argument(
        "--exiftool",
        default="exiftool",
        help="Path to exiftool binary (default: exiftool).",
    )

    categorize_parser = subparsers.add_parser(
        "categorize", help="Categorize media using metadata"
    )
    categorize_parser.add_argument(
        "--input-db",
        default="media_metadata.db",
        help="Input SQLite DB from metadata (default: media_metadata.db).",
    )
    categorize_parser.add_argument(
        "--output",
        default="media_categories.csv",
        help="Output CSV for categories (default: media_categories.csv).",
    )
    categorize_parser.add_argument(
        "--enable-geocode",
        action="store_true",
        help="Reverse-geocode GPS coordinates via Nominatim (requires geopy).",
    )
    categorize_parser.add_argument(
        "--geocode-delay",
        type=float,
        default=1.0,
        help="Delay between geocode requests in seconds (default: 1.0).",
    )
    categorize_parser.add_argument(
        "--geocode-user-agent",
        default="memory_engine",
        help="User agent string for Nominatim (default: memory_engine).",
    )
    categorize_parser.add_argument(
        "--enable-faces",
        action="store_true",
        help="Detect faces in images (requires face_recognition).",
    )
    categorize_parser.add_argument(
        "--event-window-days",
        type=int,
        default=1,
        help="Days window used for simple event grouping (default: 1).",
    )

    organize_parser = subparsers.add_parser(
        "organize", help="Copy files into a structured folder tree"
    )
    organize_parser.add_argument(
        "--input",
        default="media_categories.csv",
        help="Input categories CSV (default: media_categories.csv).",
    )
    organize_parser.add_argument(
        "--output",
        default="organized_media",
        help="Output root directory for copied files.",
    )
    organize_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview copy operations without copying.",
    )
    organize_parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files instead of renaming.",
    )

    maintain_parser = subparsers.add_parser(
        "maintain", help="Run recurring scans to keep the master CSV updated"
    )
    maintain_parser.add_argument(
        "--root",
        action="append",
        default=[],
        help="Root directory to scan (repeatable). Defaults to current directory.",
    )
    maintain_parser.add_argument(
        "--output-dir",
        default="maintenance",
        help="Directory for scan outputs (default: maintenance).",
    )
    maintain_parser.add_argument(
        "--extensions",
        default=",".join(sorted(DEFAULT_EXTENSIONS)),
        help="Comma-separated list of extensions to include.",
    )
    maintain_parser.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        help="Directory name to exclude (repeatable).",
    )
    maintain_parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="Include hidden files and directories.",
    )
    maintain_parser.add_argument(
        "--follow-symlinks",
        action="store_true",
        help="Follow symlinked directories.",
    )
    maintain_parser.add_argument(
        "--interval-minutes",
        type=float,
        default=1440.0,
        help="Minutes between scans (default: 1440 = daily).",
    )
    maintain_parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Stop after writing N rows (for quick tests).",
    )
    maintain_parser.add_argument(
        "--max-runs",
        type=int,
        default=None,
        help="Stop after N scans (default: run forever).",
    )
    maintain_parser.add_argument(
        "--timestamped",
        action="store_true",
        help="Write timestamped CSVs instead of overwriting media_master.csv.",
    )

    pipeline_parser = subparsers.add_parser(
        "run-all", help="Run scan -> dedupe -> metadata -> categorize -> organize"
    )
    pipeline_parser.add_argument(
        "--root",
        action="append",
        default=[],
        help="Root directory to scan (repeatable). Defaults to current directory.",
    )
    pipeline_parser.add_argument(
        "--output-dir",
        default="pipeline_output",
        help="Directory for pipeline outputs (default: pipeline_output).",
    )
    pipeline_parser.add_argument(
        "--extensions",
        default=",".join(sorted(DEFAULT_EXTENSIONS)),
        help="Comma-separated list of extensions to include.",
    )
    pipeline_parser.add_argument(
        "--exclude-dir",
        action="append",
        default=[],
        help="Directory name to exclude (repeatable).",
    )
    pipeline_parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="Include hidden files and directories.",
    )
    pipeline_parser.add_argument(
        "--follow-symlinks",
        action="store_true",
        help="Follow symlinked directories.",
    )
    pipeline_parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Stop after writing N rows (for quick tests).",
    )
    pipeline_parser.add_argument(
        "--skip-dedupe",
        action="store_true",
        help="Skip hashing and duplicate detection.",
    )
    pipeline_parser.add_argument(
        "--no-phash",
        action="store_true",
        help="Skip perceptual hashing for images.",
    )
    pipeline_parser.add_argument(
        "--phash-threshold",
        type=int,
        default=0,
        help="Hamming distance threshold for near-duplicate pHash matching (default: 0).",
    )
    pipeline_parser.add_argument(
        "--skip-metadata",
        action="store_true",
        help="Skip EXIF metadata extraction.",
    )
    pipeline_parser.add_argument(
        "--exiftool",
        default="exiftool",
        help="Path to exiftool binary (default: exiftool).",
    )
    pipeline_parser.add_argument(
        "--skip-categorize",
        action="store_true",
        help="Skip categorization step.",
    )
    pipeline_parser.add_argument(
        "--enable-geocode",
        action="store_true",
        help="Reverse-geocode GPS coordinates via Nominatim (requires geopy).",
    )
    pipeline_parser.add_argument(
        "--geocode-delay",
        type=float,
        default=1.0,
        help="Delay between geocode requests in seconds (default: 1.0).",
    )
    pipeline_parser.add_argument(
        "--geocode-user-agent",
        default="memory_engine",
        help="User agent string for Nominatim (default: memory_engine).",
    )
    pipeline_parser.add_argument(
        "--enable-faces",
        action="store_true",
        help="Detect faces in images (requires face_recognition).",
    )
    pipeline_parser.add_argument(
        "--event-window-days",
        type=int,
        default=1,
        help="Days window used for simple event grouping (default: 1).",
    )
    pipeline_parser.add_argument(
        "--organize",
        action="store_true",
        help="Copy files into a structured folder tree.",
    )
    pipeline_parser.add_argument(
        "--organize-root",
        default=None,
        help="Output root for organized files (default: <output-dir>/organized_media).",
    )
    pipeline_parser.add_argument(
        "--organize-dry-run",
        action="store_true",
        help="Preview organize step without copying.",
    )
    pipeline_parser.add_argument(
        "--organize-overwrite",
        action="store_true",
        help="Overwrite existing files instead of renaming.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command == "scan":
        roots = [Path(p) for p in args.root] if args.root else [Path.cwd()]
        extensions = [ext.strip() for ext in args.extensions.split(",") if ext.strip()]
        output_csv = Path(args.output)
        scanned, written = scan_to_csv(
            roots=roots,
            output_csv=output_csv,
            extensions=extensions,
            exclude_dirs=args.exclude_dir,
            include_hidden=args.include_hidden,
            follow_symlinks=args.follow_symlinks,
            max_files=args.max_files,
        )
        print(f"Scanned {scanned} files, wrote {written} rows to {output_csv}")
        return 0

    if args.command == "dedupe":
        input_csv = Path(args.input)
        hashes_csv = Path(args.hashes)
        duplicates_csv = Path(args.duplicates)
        records = hash_media_from_csv(
            input_csv=input_csv,
            output_csv=hashes_csv,
            include_phash=not args.no_phash,
        )
        duplicates = find_duplicate_groups(
            records,
            phash_threshold=args.phash_threshold,
        )
        write_duplicates_csv(duplicates, duplicates_csv)
        print(
            "Hashed "
            f"{len(records)} files, found {len(duplicates)} duplicate rows. "
            f"Hashes: {hashes_csv} Duplicates: {duplicates_csv}"
        )
        return 0

    if args.command == "metadata":
        input_csv = Path(args.input)
        output_db = Path(args.output)
        records = extract_metadata_from_csv(
            input_csv=input_csv,
            output_db=output_db,
            exiftool_path=args.exiftool,
        )
        print(f"Extracted metadata for {len(records)} files into {output_db}")
        return 0

    if args.command == "categorize":
        input_db = Path(args.input_db)
        output_csv = Path(args.output)
        records = categorize_from_db(
            input_db=input_db,
            output_csv=output_csv,
            enable_geocode=args.enable_geocode,
            geocode_delay=args.geocode_delay,
            geocode_user_agent=args.geocode_user_agent,
            enable_faces=args.enable_faces,
            event_window_days=args.event_window_days,
        )
        print(f"Categorized {len(records)} files into {output_csv}")
        return 0

    if args.command == "organize":
        input_csv = Path(args.input)
        output_root = Path(args.output)
        results = copy_from_categories(
            categories_csv=input_csv,
            output_root=output_root,
            dry_run=args.dry_run,
            overwrite=args.overwrite,
        )
        copied = sum(1 for result in results if result.status == "copied")
        errors = [result for result in results if result.status == "error"]
        print(
            f"Organized {copied} files into {output_root} "
            f"({len(errors)} errors, {len(results) - copied - len(errors)} skipped)."
        )
        return 0

    if args.command == "maintain":
        roots = [Path(p) for p in args.root] if args.root else [Path.cwd()]
        extensions = [ext.strip() for ext in args.extensions.split(",") if ext.strip()]
        output_dir = Path(args.output_dir)
        run_maintenance(
            roots=roots,
            output_dir=output_dir,
            extensions=extensions,
            exclude_dirs=args.exclude_dir,
            include_hidden=args.include_hidden,
            follow_symlinks=args.follow_symlinks,
            interval_minutes=args.interval_minutes,
            max_files=args.max_files,
            max_runs=args.max_runs,
            timestamped=args.timestamped,
        )
        print("Maintenance scans complete.")
        return 0

    if args.command == "run-all":
        roots = [Path(p) for p in args.root] if args.root else [Path.cwd()]
        extensions = [ext.strip() for ext in args.extensions.split(",") if ext.strip()]
        output_dir = Path(args.output_dir)
        result = run_pipeline(
            roots=roots,
            output_dir=output_dir,
            extensions=extensions,
            exclude_dirs=args.exclude_dir,
            include_hidden=args.include_hidden,
            follow_symlinks=args.follow_symlinks,
            max_files=args.max_files,
            enable_dedupe=not args.skip_dedupe,
            include_phash=not args.no_phash,
            phash_threshold=args.phash_threshold,
            enable_metadata=not args.skip_metadata,
            exiftool_path=args.exiftool,
            enable_categorize=not args.skip_categorize,
            enable_geocode=args.enable_geocode,
            geocode_delay=args.geocode_delay,
            geocode_user_agent=args.geocode_user_agent,
            enable_faces=args.enable_faces,
            event_window_days=args.event_window_days,
            enable_organize=args.organize,
            organize_root=Path(args.organize_root) if args.organize_root else None,
            organize_dry_run=args.organize_dry_run,
            organize_overwrite=args.organize_overwrite,
        )
        print(
            "Pipeline complete. "
            f"Scan: {result.scan_csv} "
            f"Hashes: {result.hashes_csv or 'skipped'} "
            f"Duplicates: {result.duplicates_csv or 'skipped'} "
            f"Metadata: {result.metadata_db or 'skipped'} "
            f"Categories: {result.categories_csv or 'skipped'} "
            f"Organized: {result.organized_root or 'skipped'}"
        )
        return 0

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
