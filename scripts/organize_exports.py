#!/usr/bin/env python3
# scripts/organize_exports.py
"""Move per-month exports from `exports/` to `public/`.

The exporter writes one file per (channel, month, format):

    exports/<server>/<channel>/<YYYY-MM>.<ext>
    exports/<server>/<forum>/<thread>/<YYYY-MM>.<ext>

This script copies each `<YYYY-MM>.<ext>` (and its sibling `<YYYY-MM>_media/`)
into the published layout:

    public/<server>/<channel>/<YYYY-MM>/<YYYY-MM>.<ext>
    public/<server>/<forum>/<thread>/<YYYY-MM>/<YYYY-MM>.<ext>

The month is taken from the filename — never from `datetime.now()`. That's
the whole point of the refactor: a backfilled 2026-03 export must land in
the `2026-03/` directory, not the current month's directory.

JSON files are merged with any existing archive in the destination so we
keep historical messages even if a future re-export trims a range.
"""

import json
import shutil
import sys
from pathlib import Path
from typing import Any

from scripts.months import is_month_dir_name

VALID_EXTENSIONS = {".html", ".txt", ".json", ".csv"}


def _merge_json_exports(source_file: Path, dest_file: Path) -> bool:
    """Merge new JSON export into the existing archive, deduplicating by ID.

    DCE message IDs are snowflakes, which sort chronologically, so we use
    them as the natural key and sort by integer value at the end.
    """
    try:
        with open(source_file, encoding="utf-8") as f:
            new_data = json.load(f)

        if not dest_file.exists():
            with open(dest_file, "w", encoding="utf-8") as f:
                json.dump(new_data, f, indent=2)
            return True

        with open(dest_file, encoding="utf-8") as f:
            existing_data = json.load(f)

        existing_messages = existing_data.get("messages", [])
        new_messages = new_data.get("messages", [])

        messages_by_id: dict[str, Any] = {}
        for msg in existing_messages:
            msg_id = msg.get("id")
            if msg_id:
                messages_by_id[msg_id] = msg
        # New messages override existing entries with the same ID (edits).
        for msg in new_messages:
            msg_id = msg.get("id")
            if msg_id:
                messages_by_id[msg_id] = msg

        sorted_messages = sorted(messages_by_id.values(), key=lambda m: int(m.get("id", 0)))

        merged_data = new_data.copy()
        merged_data["messages"] = sorted_messages
        merged_data["messageCount"] = len(sorted_messages)

        # Since we keep history across runs, the merged file represents the
        # full month range, not the bracket of any single export.
        merged_data["dateRange"] = {"after": None, "before": None}

        with open(dest_file, "w", encoding="utf-8") as f:
            json.dump(merged_data, f, indent=2)

        return True

    except Exception as e:
        print(f"    ⚠ JSON merge failed for {source_file}: {e}")
        return False


def _copy_media_directory(source_media_dir: Path, dest_media_dir: Path) -> bool:
    """Copy `source_media_dir` to `dest_media_dir`, replacing any existing copy."""
    if not source_media_dir.exists() or not source_media_dir.is_dir():
        return False
    try:
        if dest_media_dir.exists():
            shutil.rmtree(dest_media_dir)
        shutil.copytree(source_media_dir, dest_media_dir)
        return True
    except Exception:
        return False


def _copy_month_file(source_file: Path, dest_file: Path) -> bool:
    """Copy a single per-month file, merging if JSON."""
    extension = source_file.suffix
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        if extension == ".json":
            return _merge_json_exports(source_file, dest_file)
        shutil.copy2(source_file, dest_file)
        return True
    except Exception:
        return False


def _update_latest_symlink(public_channel_dir: Path) -> None:
    """Point `latest.html` (and friends) at the newest month present.

    Scans the channel directory for `YYYY-MM/` subdirectories and creates
    a symlink for each extension that exists in the most recent month.
    """
    months = sorted(
        (
            d.name
            for d in public_channel_dir.iterdir()
            if d.is_dir() and is_month_dir_name(d.name)
        ),
        reverse=True,
    )
    if not months:
        return
    newest = months[0]
    for ext in ("html", "txt", "json", "csv"):
        target_file = public_channel_dir / newest / f"{newest}.{ext}"
        if not target_file.exists():
            continue
        link = public_channel_dir / f"latest.{ext}"
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(f"{newest}/{newest}.{ext}")


def _iter_channel_dirs(exports_dir: Path):
    """Yield each directory that directly contains `YYYY-MM.<ext>` files.

    A channel directory is the leaf level of the export tree: it may be
    `exports/server/channel/` for a regular channel or
    `exports/server/forum/thread/` for a thread. We walk the tree and yield
    any directory whose direct children include a month-named file.
    """
    if not exports_dir.exists():
        return
    for root, _dirs, files in _walk_paths(exports_dir):
        for name in files:
            stem, _, ext = name.rpartition(".")
            if ext and f".{ext}" in VALID_EXTENSIONS and is_month_dir_name(stem):
                yield root
                break  # one match is enough to mark this directory


def _walk_paths(top: Path):
    """Yield (root_path, [dir_names], [file_names]) like os.walk but with Paths."""
    stack = [top]
    while stack:
        current = stack.pop()
        try:
            entries = list(current.iterdir())
        except OSError:
            continue
        dirs = [e for e in entries if e.is_dir()]
        files = [e.name for e in entries if e.is_file()]
        yield current, [d.name for d in dirs], files
        stack.extend(dirs)


def _organize_channel_directory(
    channel_export_dir: Path,
    exports_root: Path,
    public_root: Path,
) -> tuple[int, list[str]]:
    """Move all per-month files in a channel directory into `public_root`.

    Returns (files_organized, errors).
    """
    relative = channel_export_dir.relative_to(exports_root)
    public_channel_dir = public_root / relative

    files_organized = 0
    errors: list[str] = []
    months_touched: set[str] = set()

    for entry in sorted(channel_export_dir.iterdir()):
        if not entry.is_file():
            continue
        stem = entry.stem
        ext = entry.suffix
        if ext not in VALID_EXTENSIONS or not is_month_dir_name(stem):
            continue
        dest_file = public_channel_dir / stem / f"{stem}{ext}"
        if _copy_month_file(entry, dest_file):
            files_organized += 1
            months_touched.add(stem)
            print(f"  ✓ {relative}/{entry.name} → {dest_file.relative_to(public_root)}")
        else:
            errors.append(f"Failed to copy {entry}")

    # Per-month media directories sit alongside the per-month files
    for month in months_touched:
        media_src = channel_export_dir / f"{month}_media"
        if media_src.exists():
            media_dst = public_channel_dir / month / f"{month}_media"
            if _copy_media_directory(media_src, media_dst):
                print(f"    ↳ media: {media_src.name} → {media_dst.relative_to(public_root)}")

    # Refresh the `latest.*` symlinks at the channel root
    if public_channel_dir.exists():
        _update_latest_symlink(public_channel_dir)

    return files_organized, errors


def organize_exports(
    exports_dir: Path | None = None, public_dir: Path | None = None
) -> dict[str, Any]:
    """Move per-month exports from `exports/` into `public/` with date-based layout.

    Returns a stats dict with `files_organized`, `channels_processed`, and `errors`.
    """
    if exports_dir is None:
        exports_dir = Path("exports")
    if public_dir is None:
        public_dir = Path("public")

    if not exports_dir.exists():
        raise FileNotFoundError(
            f"Exports directory not found: {exports_dir}\n"
            "Run scripts/export_channels.py first to generate exports."
        )

    public_dir.mkdir(exist_ok=True)

    stats: dict[str, Any] = {"files_organized": 0, "channels_processed": 0, "errors": []}
    channel_dirs_seen: set[Path] = set()

    for channel_dir in _iter_channel_dirs(exports_dir):
        if channel_dir in channel_dirs_seen:
            continue
        channel_dirs_seen.add(channel_dir)
        print(f"Organizing {channel_dir.relative_to(exports_dir)}...")
        files, errors = _organize_channel_directory(channel_dir, exports_dir, public_dir)
        stats["files_organized"] += files
        stats["errors"].extend(errors)

    stats["channels_processed"] = len(channel_dirs_seen)
    return stats


def cleanup_exports(exports_dir: Path | None = None) -> None:
    """Delete per-month files from `exports_dir`. Safe to run after a successful
    organize pass; preserves directory structure so the next export run lands
    in the same place.
    """
    if exports_dir is None:
        exports_dir = Path("exports")
    if not exports_dir.exists():
        return
    for path in exports_dir.rglob("*"):
        if path.is_file():
            stem = path.stem
            ext = path.suffix
            if ext in VALID_EXTENSIONS and is_month_dir_name(stem):
                path.unlink()


def main() -> None:
    """Entry point for organize script."""
    print("Discord Export Organizer")
    print("=" * 50)

    try:
        stats = organize_exports()
        print("\n" + "=" * 50)
        print("Organization Summary:")
        print(f"  Files organized: {stats['files_organized']}")
        print(f"  Channels processed: {stats['channels_processed']}")

        if stats["errors"]:
            print(f"\nErrors ({len(stats['errors'])}):")
            for error in stats["errors"][:10]:
                print(f"  - {error}")

        sys.exit(1 if stats["errors"] else 0)

    except FileNotFoundError as e:
        print(f"\nERROR: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
