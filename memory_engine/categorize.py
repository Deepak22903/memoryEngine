from __future__ import annotations

import csv
import math
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

try:
    from geopy.geocoders import Nominatim

    _GEOPY_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency
    Nominatim = None
    _GEOPY_AVAILABLE = False

_FACE_MODULE = None
_FACE_IMPORT_ERROR: str | None = None


@dataclass(frozen=True)
class CategoryRecord:
    path: str
    date_taken: str
    date_bucket: str
    location_label: str | None
    face_count: int | None
    event_id: str
    error: str | None


def _parse_date(date_value: str) -> datetime | None:
    if not date_value:
        return None
    try:
        return datetime.fromisoformat(date_value)
    except ValueError:
        return None


def _date_bucket(date_value: str) -> str:
    parsed = _parse_date(date_value)
    if not parsed:
        return "unknown"
    return parsed.strftime("%Y/%m")


def _round_coord(value: float | None, digits: int = 4) -> float | None:
    if value is None:
        return None
    return round(float(value), digits)


def _format_location_label(location: dict[str, str]) -> str:
    parts = [
        location.get("city")
        or location.get("town")
        or location.get("village")
        or location.get("hamlet"),
        location.get("state"),
        location.get("country"),
    ]
    return ", ".join([part for part in parts if part])


def _reverse_geocode(
    geocoder: Nominatim,
    lat: float,
    lon: float,
) -> str | None:
    try:
        location = geocoder.reverse((lat, lon), exactly_one=True)
    except Exception:
        return None
    if not location or not hasattr(location, "raw"):
        return None
    address = location.raw.get("address") or {}
    return _format_location_label(address)


def _get_face_recognition():
    global _FACE_MODULE, _FACE_IMPORT_ERROR
    if _FACE_IMPORT_ERROR:
        return None, _FACE_IMPORT_ERROR
    if _FACE_MODULE is not None:
        return _FACE_MODULE, None
    try:
        import face_recognition  # type: ignore

        _FACE_MODULE = face_recognition
        return _FACE_MODULE, None
    except Exception as exc:  # pragma: no cover - optional dependency
        _FACE_IMPORT_ERROR = str(exc)
        return None, _FACE_IMPORT_ERROR


def _count_faces(image_path: Path) -> tuple[int | None, str | None]:
    module, error = _get_face_recognition()
    if module is None:
        return None, error or "face_recognition_unavailable"
    try:
        image = module.load_image_file(str(image_path))
        locations = module.face_locations(image)
        return len(locations), None
    except Exception as exc:
        return None, str(exc)


def _event_key(date_value: str, location_label: str | None, window_days: int) -> str:
    parsed = _parse_date(date_value)
    if not parsed:
        return f"unknown::{location_label or 'unknown'}"
    window_start = parsed - timedelta(days=window_days)
    bucket = window_start.strftime("%Y-%m-%d")
    return f"{bucket}::{location_label or 'unknown'}"


def categorize_from_db(
    input_db: Path,
    output_csv: Path,
    enable_geocode: bool = False,
    geocode_delay: float = 1.0,
    geocode_user_agent: str = "memory_engine",
    enable_faces: bool = False,
    event_window_days: int = 1,
) -> list[CategoryRecord]:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(input_db)
    connection.row_factory = sqlite3.Row

    geocoder = None
    if enable_geocode and _GEOPY_AVAILABLE:
        geocoder = Nominatim(user_agent=geocode_user_agent)

    location_cache: dict[tuple[float, float], str | None] = {}
    event_ids: dict[str, str] = {}
    next_event = 1
    records: list[CategoryRecord] = []

    rows = connection.execute(
        """
        SELECT path, date_taken, gps_lat, gps_lon
        FROM media_metadata
        ORDER BY date_taken
        """
    )

    with output_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "path",
                "date_taken",
                "date_bucket",
                "location_label",
                "face_count",
                "event_id",
                "error",
            ],
        )
        writer.writeheader()

        for row in rows:
            path_value = row["path"]
            date_taken = row["date_taken"] or ""
            date_bucket = _date_bucket(date_taken)
            lat = _round_coord(row["gps_lat"])
            lon = _round_coord(row["gps_lon"])
            location_label = None
            error: str | None = None

            if enable_geocode and geocoder and lat is not None and lon is not None:
                cache_key = (lat, lon)
                if cache_key not in location_cache:
                    location_cache[cache_key] = _reverse_geocode(geocoder, lat, lon)
                    if geocode_delay > 0:
                        time.sleep(geocode_delay)
                location_label = location_cache[cache_key]

            face_count = None
            if enable_faces:
                face_count, face_error = _count_faces(Path(path_value))
                if face_error and error is None:
                    error = f"face_error: {face_error}"

            event_key = _event_key(date_taken, location_label, event_window_days)
            if event_key not in event_ids:
                event_ids[event_key] = f"event_{next_event}"
                next_event += 1

            record = CategoryRecord(
                path=path_value,
                date_taken=date_taken,
                date_bucket=date_bucket,
                location_label=location_label,
                face_count=face_count,
                event_id=event_ids[event_key],
                error=error,
            )
            writer.writerow(
                {
                    "path": record.path,
                    "date_taken": record.date_taken,
                    "date_bucket": record.date_bucket,
                    "location_label": record.location_label or "",
                    "face_count": "" if record.face_count is None else record.face_count,
                    "event_id": record.event_id,
                    "error": record.error or "",
                }
            )
            records.append(record)

    connection.close()
    return records
