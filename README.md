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

Phase 2 will add hashing for exact and perceptual deduplication.
