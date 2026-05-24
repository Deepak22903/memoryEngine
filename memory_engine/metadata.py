from __future__ import annotations

import csv
import json
import sqlite3
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class MetadataRecord:
    path: str
    size_bytes: str
    mtime_utc: str
    extension: str
    date_taken: str
    gps_lat: float | None
    gps_lon: float | None
    camera_model: str | None
    video_duration: str | None
    exif_json: str | None
    error: str | None


def _parse_exif_datetime(value: str) -> str | None:
    if not value:
        return None
    for pattern in (
        "%Y:%m:%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ):
        try:
            return datetime.strptime(value, pattern).isoformat()
        except ValueError:
            continue
    return None


def _run_exiftool(file_path: Path, exiftool_path: str) -> tuple[dict[str, object] | None, str | None]:
    try:
        result = subprocess.run(
            [exiftool_path, "-json", "-n", str(file_path)],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None, "exiftool_not_found"
    except Exception as exc:  # pragma: no cover
        return None, f"exiftool_error: {exc}"

    if result.returncode != 0:
        error = result.stderr.strip() or "exiftool_failed"
        return None, error

    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None, "exiftool_invalid_json"

    if not payload:
        return None, "exiftool_empty"

    if isinstance(payload, list):
        return payload[0], None

    if isinstance(payload, dict):
        return payload, None

    return None, "exiftool_unexpected_format"


def _extract_fields(exif_data: dict[str, object] | None) -> dict[str, object | None]:
    if not exif_data:
        return {
            "date_taken": None,
            "gps_lat": None,
            "gps_lon": None,
            "camera_model": None,
            "video_duration": None,
        }

    date_taken = (
        exif_data.get("DateTimeOriginal")
        or exif_data.get("CreateDate")
        or exif_data.get("MediaCreateDate")
        or exif_data.get("TrackCreateDate")
    )
    date_taken = _parse_exif_datetime(str(date_taken)) if date_taken else None

    gps_lat = exif_data.get("GPSLatitude")
    gps_lon = exif_data.get("GPSLongitude")

    camera_model = exif_data.get("Model") or exif_data.get("CameraModelName")
    if camera_model is not None:
        camera_model = str(camera_model)

    video_duration = exif_data.get("Duration") or exif_data.get("MediaDuration")
    if video_duration is not None:
        video_duration = str(video_duration)

    return {
        "date_taken": date_taken,
        "gps_lat": float(gps_lat) if gps_lat is not None else None,
        "gps_lon": float(gps_lon) if gps_lon is not None else None,
        "camera_model": camera_model,
        "video_duration": video_duration,
    }


def _init_db(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS media_metadata (
            path TEXT PRIMARY KEY,
            size_bytes TEXT,
            mtime_utc TEXT,
            extension TEXT,
            date_taken TEXT,
            gps_lat REAL,
            gps_lon REAL,
            camera_model TEXT,
            video_duration TEXT,
            exif_json TEXT,
            error TEXT
        )
        """
    )
    connection.commit()


def extract_metadata_from_csv(
    input_csv: Path,
    output_db: Path,
    exiftool_path: str = "exiftool",
) -> list[MetadataRecord]:
    output_db.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(output_db)
    _init_db(connection)

    records: list[MetadataRecord] = []
    with input_csv.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            path_value = row.get("path", "").strip()
            if not path_value:
                continue
            file_path = Path(path_value)
            exif_data, error = _run_exiftool(file_path, exiftool_path)
            fields = _extract_fields(exif_data)
            date_taken = fields["date_taken"] or row.get("mtime_utc", "")

            record = MetadataRecord(
                path=path_value,
                size_bytes=row.get("size_bytes", ""),
                mtime_utc=row.get("mtime_utc", ""),
                extension=row.get("extension", ""),
                date_taken=date_taken or "",
                gps_lat=fields["gps_lat"],
                gps_lon=fields["gps_lon"],
                camera_model=fields["camera_model"],
                video_duration=fields["video_duration"],
                exif_json=json.dumps(exif_data) if exif_data else None,
                error=error,
            )

            connection.execute(
                """
                INSERT OR REPLACE INTO media_metadata (
                    path, size_bytes, mtime_utc, extension, date_taken,
                    gps_lat, gps_lon, camera_model, video_duration, exif_json, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.path,
                    record.size_bytes,
                    record.mtime_utc,
                    record.extension,
                    record.date_taken,
                    record.gps_lat,
                    record.gps_lon,
                    record.camera_model,
                    record.video_duration,
                    record.exif_json,
                    record.error,
                ),
            )
            records.append(record)

    connection.commit()
    connection.close()
    return records
