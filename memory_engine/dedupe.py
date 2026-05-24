from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator, Sequence

try:
    from PIL import Image
    import imagehash

    _IMAGEHASH_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    Image = None
    imagehash = None
    _IMAGEHASH_AVAILABLE = False


IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".heic",
    ".gif",
    ".bmp",
    ".tif",
    ".tiff",
}


@dataclass(frozen=True)
class HashRecord:
    path: str
    size_bytes: str
    mtime_utc: str
    extension: str
    md5: str | None
    phash: str | None
    error: str | None


def iter_csv_rows(input_csv: Path) -> Iterator[dict[str, str]]:
    with input_csv.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield row


def compute_md5(file_path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.md5()
    with file_path.open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def compute_phash(file_path: Path) -> str | None:
    if not _IMAGEHASH_AVAILABLE:
        return None
    if file_path.suffix.lower() not in IMAGE_EXTENSIONS:
        return None
    try:
        with Image.open(file_path) as img:
            return str(imagehash.phash(img))
    except Exception:
        return None


def hash_media_from_csv(
    input_csv: Path,
    output_csv: Path,
    include_phash: bool = True,
) -> list[HashRecord]:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    records: list[HashRecord] = []

    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = [
            "path",
            "size_bytes",
            "mtime_utc",
            "extension",
            "md5",
            "phash",
            "error",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()

        for row in iter_csv_rows(input_csv):
            path_value = row.get("path", "").strip()
            if not path_value:
                continue
            file_path = Path(path_value)
            error: str | None = None
            md5_value: str | None = None
            phash_value: str | None = None
            try:
                md5_value = compute_md5(file_path)
                if include_phash:
                    phash_value = compute_phash(file_path)
            except Exception as exc:
                error = f"hash_error: {exc}"

            record = HashRecord(
                path=path_value,
                size_bytes=row.get("size_bytes", ""),
                mtime_utc=row.get("mtime_utc", ""),
                extension=row.get("extension", ""),
                md5=md5_value,
                phash=phash_value,
                error=error,
            )
            writer.writerow(
                {
                    "path": record.path,
                    "size_bytes": record.size_bytes,
                    "mtime_utc": record.mtime_utc,
                    "extension": record.extension,
                    "md5": record.md5 or "",
                    "phash": record.phash or "",
                    "error": record.error or "",
                }
            )
            records.append(record)

    return records


def _phash_distance(hash_a: str, hash_b: str) -> int:
    if not _IMAGEHASH_AVAILABLE:
        return 9999
    return (imagehash.hex_to_hash(hash_a) - imagehash.hex_to_hash(hash_b))


def find_duplicate_groups(
    records: Sequence[HashRecord],
    phash_threshold: int = 0,
) -> list[dict[str, str]]:
    duplicates: list[dict[str, str]] = []
    md5_groups: dict[str, list[HashRecord]] = {}
    phash_groups: dict[str, list[HashRecord]] = {}

    for record in records:
        if record.md5:
            md5_groups.setdefault(record.md5, []).append(record)
        if record.phash:
            phash_groups.setdefault(record.phash, []).append(record)

    group_id = 1
    for md5_value, group in md5_groups.items():
        if len(group) < 2:
            continue
        for record in group:
            duplicates.append(
                {
                    "group_id": str(group_id),
                    "type": "md5",
                    "match": md5_value,
                    "path": record.path,
                }
            )
        group_id += 1

    if phash_threshold < 0:
        return duplicates

    if phash_threshold == 0:
        for phash_value, group in phash_groups.items():
            if len(group) < 2:
                continue
            for record in group:
                duplicates.append(
                    {
                        "group_id": str(group_id),
                        "type": "phash",
                        "match": phash_value,
                        "path": record.path,
                    }
                )
            group_id += 1
        return duplicates

    if not _IMAGEHASH_AVAILABLE:
        return duplicates

    phash_records = [record for record in records if record.phash]
    used = set()
    for idx, record in enumerate(phash_records):
        if record.path in used:
            continue
        group = [record]
        for other in phash_records[idx + 1 :]:
            if other.path in used:
                continue
            if _phash_distance(record.phash, other.phash) <= phash_threshold:
                group.append(other)
        if len(group) > 1:
            for member in group:
                used.add(member.path)
                duplicates.append(
                    {
                        "group_id": str(group_id),
                        "type": f"phash<= {phash_threshold}",
                        "match": record.phash or "",
                        "path": member.path,
                    }
                )
            group_id += 1

    return duplicates


def write_duplicates_csv(duplicates: Iterable[dict[str, str]], output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        fieldnames = ["group_id", "type", "match", "path"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in duplicates:
            writer.writerow(row)
