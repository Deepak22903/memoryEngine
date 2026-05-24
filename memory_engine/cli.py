from __future__ import annotations

import argparse
from pathlib import Path

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
        "--exclude-hidden",
        action="store_false",
        dest="include_hidden",
        default=True,
        help="Exclude hidden files and directories.",
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

    parser.error("Unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
