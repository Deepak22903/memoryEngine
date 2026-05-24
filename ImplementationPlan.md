Perfect — I have everything I need. Let me put together the full plan.Here's the full plan for **memoryEngine**. Each phase box is clickable for a deep-dive. Here's what each phase means in practice:

**Phase 1 — Scan & discover** runs a Python script using `pathlib` or the shell's `find` command to walk every directory on your disk, collect all `.jpg`, `.jpeg`, `.png`, `.heic`, `.mp4`, `.mov`, `.avi` etc. files, and dump them into a master CSV. This is your ground truth — nothing gets touched yet.

**Phase 2 — Deduplicate** is critical before you copy 10–50k files. You compute MD5 hashes for exact duplicates, and perceptual hashes (via the `imagehash` library) to catch near-duplicates like the same photo saved at different resolutions. `dupeGuru` has a nice GUI if you prefer to review manually.

**Phase 3 — Extract metadata** uses `ExifTool` (the industry standard) to pull date taken, GPS coordinates, camera model, and video duration from every file, storing everything in a local SQLite database. Files without EXIF fall back to the filesystem's modified date.

**Phase 4 — Categorise** is where all four of your chosen dimensions kick in: date from EXIF, location from reverse-geocoding GPS coords (free via `geopy` + Nominatim/OpenStreetMap), faces via the `face_recognition` Python library (runs locally, no cloud), and events via clustering nearby dates + locations together.

**Phase 5 — Copy & organise** uses `shutil.copy2` to copy (never move) files into the structured folder tree on your external drive, preserving original timestamps. Naming conflicts get auto-renamed.

**Phase 6 — Maintain** sets up a recurring scan so new photos you take keep flowing in. `Immich` is worth looking at — it's a self-hosted Google Photos alternative that plugs into a library organised exactly this way.

---
