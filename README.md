# memoryEngine

Phase 1 implementation: scan your disk for media files and build a master CSV.

## Usage

Run a scan from the project root:

- Scan current directory and subfolders:
  - `python -m memory_engine scan`
- Scan specific roots:
  - `python -m memory_engine scan --root /mnt/photos --root /home/deepak/Pictures`
- Custom output path and extensions:
  - `python -m memory_engine scan --output ./data/media_master.csv --extensions .jpg,.jpeg,.png,.heic,.mp4,.mov`
- Exclude folders (by name):
  - `python -m memory_engine scan --exclude-dir .git --exclude-dir node_modules`

The CSV includes: `path`, `size_bytes`, `mtime_utc`, `extension`.

## Next

Phase 2 hashing is available with the `dedupe` command.

## Phase 2 — Deduplicate

Generate hashes and a duplicate report from the Phase 1 CSV:

- Basic hashing (MD5 + pHash):
  - `python -m memory_engine dedupe --input media_master.csv`
- Skip perceptual hash:
  - `python -m memory_engine dedupe --no-phash`
- Near-duplicate matching with a threshold:
  - `python -m memory_engine dedupe --phash-threshold 6`

Outputs:

- media_hashes.csv: `path`, `md5`, `phash`, `error`
- media_duplicates.csv: duplicate groups across MD5 and pHash

Optional dependencies for pHash:

- `pip install pillow imagehash`

## Phase 3 — Extract metadata

Extract EXIF metadata into a local SQLite database:

- Basic extraction:
  - `python -m memory_engine metadata --input media_master.csv`
- Custom database path and exiftool binary:
  - `python -m memory_engine metadata --output ./data/media_metadata.db --exiftool /usr/bin/exiftool`

The database table is `media_metadata` with columns:
`path`, `size_bytes`, `mtime_utc`, `extension`, `date_taken`, `gps_lat`, `gps_lon`, `camera_model`, `video_duration`, `exif_json`, `error`.

Requires ExifTool:

- https://exiftool.org/

## Phase 4 — Categorise

Generate category labels (date bucket, optional reverse geocode, optional face count, event IDs):

- Basic categorisation:
  - `python -m memory_engine categorize --input-db media_metadata.db`
- Enable reverse-geocoding (Nominatim):
  - `python -m memory_engine categorize --enable-geocode --geocode-delay 1.0`
- Enable face detection:
  - `python -m memory_engine categorize --enable-faces`

Output CSV columns:
`path`, `date_taken`, `date_bucket`, `location_label`, `face_count`, `event_id`, `error`.

Optional dependencies:

- Reverse geocoding: `pip install geopy`
- Face detection: `pip install face_recognition`

## Phase 5 — Copy & organise

Copy files into a structured folder tree:

- Basic copy:
  - `python -m memory_engine organize --input media_categories.csv --output /mnt/drive/organized_media`
- Dry run (no copy):
  - `python -m memory_engine organize --dry-run`
- Overwrite existing files:
  - `python -m memory_engine organize --overwrite`

Folder structure used:
`<output>/<date_bucket>/<location_label>/<event_id>/<filename>`

Naming conflicts are auto-resolved with `__N` suffixes unless `--overwrite` is set.

## Phase 6 — Maintain

Run recurring scans to keep your master CSV up to date:

- Daily scan (default interval):
  - `python -m memory_engine maintain --root /mnt/photos --root /home/deepak/Pictures`
- Every 6 hours, keep timestamped outputs:
  - `python -m memory_engine maintain --interval-minutes 360 --timestamped --output-dir ./maintenance`
- Run a fixed number of scans (useful for testing):
  - `python -m memory_engine maintain --max-runs 3 --interval-minutes 1`

Outputs are written to the maintenance directory as `media_master.csv` (or timestamped variants).

## Master pipeline (all phases)

Run everything end-to-end with full control:

- Default run (scan → dedupe → metadata → categorize):
  - `python -m memory_engine run-all --root /mnt/photos --root /home/deepak/Pictures`
- Skip steps or enable optional features:
  - `python -m memory_engine run-all --skip-dedupe --skip-metadata`
  - `python -m memory_engine run-all --enable-geocode --enable-faces`
- Organize into a destination folder:
  - `python -m memory_engine run-all --organize --organize-root /mnt/drive/organized_media`

All outputs are written under `--output-dir` (default: `pipeline_output`).

## Move all media (flat destination)

Find all media files and move them into a single destination folder:

- Basic move:
  - `python -m memory_engine move-all --root /mnt/photos --output /mnt/drive/moved_media`
- Dry run (no move):
  - `python -m memory_engine move-all --dry-run`
- Overwrite existing files:
  - `python -m memory_engine move-all --overwrite`

Naming conflicts are auto-resolved with `__N` suffixes unless `--overwrite` is set.
