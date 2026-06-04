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
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from scripts.months import is_month_dir_name

VALID_EXTENSIONS = {".html", ".txt", ".json", ".csv"}


def _json_message_count(json_file: Path) -> int:
    """Number of messages in a DCE JSON export (0 if missing/unreadable)."""
    try:
        with open(json_file, encoding="utf-8") as f:
            return len(json.load(f).get("messages", []))
    except (OSError, json.JSONDecodeError):
        return 0


def _accept_month_export(source_json: Path, dest_json: Path) -> tuple[bool, str | None]:
    """Decide whether a freshly-exported month may replace the published one.

    The latest *successful* export is authoritative: deletions propagate, so we
    do NOT preserve published messages absent from the new export. (The old
    by-ID union kept messages the latest HTML no longer rendered, which is what
    desynced the index count from the page — issue #1.)

    The single guard: a non-empty published month re-exporting to EMPTY is
    almost certainly a transient/partial fetch — a channel does not lose a whole
    month of messages to ordinary deletion in one run — so we keep the existing
    export and surface an error instead of blanking the page.
    """
    if not source_json.exists() or not dest_json.exists():
        return True, None
    new_count = _json_message_count(source_json)
    existing_count = _json_message_count(dest_json)
    if new_count == 0 and existing_count > 0:
        return (
            False,
            f"{source_json.name}: new export has 0 messages but the published month "
            f"has {existing_count} — treating as a transient/partial fetch and keeping "
            "the existing export (issue #1 transient guard)",
        )
    return True, None


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


_LATEST_REDIRECT_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="refresh" content="0; url={target}">
<link rel="canonical" href="{target}">
<title>Latest archive</title>
</head>
<body>
<p>Redirecting to the <a href="{target}">latest archive ({month})</a>&hellip;</p>
</body>
</html>
"""


def _update_latest_pointers(public_channel_dir: Path) -> None:
    """Make `latest.*` point at the newest month present.

    `latest.html` is written as a real HTML *redirect* (meta refresh) to
    `<newest>/<newest>.html`. It must NOT be a symlink: the deploy action
    (peaceiris/actions-gh-pages) dereferences symlinks into flat file
    copies, and a flat copy of the month's HTML at the channel root keeps
    its relative `<newest>_media/...` asset paths. Served at
    `/channel/latest.html` those resolve to `/channel/<newest>_media/...`
    (404) instead of `/channel/<newest>/<newest>_media/...`. A redirect
    sidesteps this — the browser navigates to the real per-month URL
    before resolving any relative asset paths.

    `latest.txt/json/csv` stay symlinks: plain data formats have no
    relative asset references, so the flat copy the deploy produces is
    correct for them.
    """
    months = sorted(
        (d.name for d in public_channel_dir.iterdir() if d.is_dir() and is_month_dir_name(d.name)),
        reverse=True,
    )
    if not months:
        return
    newest = months[0]

    # HTML: real redirect file (never a symlink).
    html_target_exists = (public_channel_dir / newest / f"{newest}.html").exists()
    latest_html = public_channel_dir / "latest.html"
    if latest_html.exists() or latest_html.is_symlink():
        latest_html.unlink()
    if html_target_exists:
        target = f"{newest}/{newest}.html"
        latest_html.write_text(
            _LATEST_REDIRECT_TEMPLATE.format(target=target, month=newest),
            encoding="utf-8",
        )

    # Data formats: symlink (deploy flattens to a correct standalone copy).
    for ext in ("txt", "json", "csv"):
        target_file = public_channel_dir / newest / f"{newest}.{ext}"
        if not target_file.exists():
            continue
        link = public_channel_dir / f"latest.{ext}"
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(f"{newest}/{newest}.{ext}")


def _iter_channel_dirs(exports_dir: Path) -> Iterator[Path]:
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


def _walk_paths(top: Path) -> Iterator[tuple[Path, list[str], list[str]]]:
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


def _organize_channel_directory(  # noqa: C901  # per-month atomic publish is branchy
    channel_export_dir: Path,
    exports_root: Path,
    public_root: Path,
) -> tuple[int, list[str]]:
    """Move all per-month files in a channel directory into `public_root`.

    Each month is published atomically: all of its formats come from the same
    (latest) export, or none do — see `_accept_month_export`.

    Returns (files_organized, errors).
    """
    relative = channel_export_dir.relative_to(exports_root)
    public_channel_dir = public_root / relative

    files_organized = 0
    errors: list[str] = []
    months_touched: set[str] = set()

    # Group this run's per-month files by month so each month publishes
    # ATOMICALLY: all of its formats come from the same (latest) export, or none
    # do. The old path merged JSON by ID while overwriting HTML wholesale, so a
    # month's JSON count could drift above what the HTML rendered (issue #1).
    by_month: dict[str, list[Path]] = {}
    for entry in sorted(channel_export_dir.iterdir()):
        if not entry.is_file():
            continue
        if entry.suffix not in VALID_EXTENSIONS or not is_month_dir_name(entry.stem):
            continue
        by_month.setdefault(entry.stem, []).append(entry)

    for month, files in sorted(by_month.items()):
        dest_month_dir = public_channel_dir / month
        accept, err = _accept_month_export(
            channel_export_dir / f"{month}.json", dest_month_dir / f"{month}.json"
        )
        if not accept:
            if err:
                errors.append(err)
                print(f"  ⚠ {relative}/{month}: {err}")
            continue
        dest_month_dir.mkdir(parents=True, exist_ok=True)
        for src in files:
            dest_file = dest_month_dir / src.name
            try:
                shutil.copy2(src, dest_file)
                files_organized += 1
                months_touched.add(month)
                print(f"  ✓ {relative}/{src.name} → {dest_file.relative_to(public_root)}")
            except OSError:
                errors.append(f"Failed to copy {src}")

    # Per-month media directories sit alongside the per-month files
    for month in months_touched:
        media_src = channel_export_dir / f"{month}_media"
        if media_src.exists():
            media_dst = public_channel_dir / month / f"{month}_media"
            if _copy_media_directory(media_src, media_dst):
                print(f"    ↳ media: {media_src.name} → {media_dst.relative_to(public_root)}")

    # Refresh the `latest.*` pointers at the channel root
    if public_channel_dir.exists():
        _update_latest_pointers(public_channel_dir)

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
    """Delete per-month files from `exports_dir`.

    Safe to run after a successful organize pass; preserves directory
    structure so the next export run lands in the same place.
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
