#!/usr/bin/env python3
# scripts/organize_exports.py
"""Organize exported files into date-based directory structure.

This script moves exported files from the exports/ directory to the public/
directory, organizing them by server/channel structure with date-based naming.
"""

import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def get_current_month() -> str:
    """Get current month in YYYY-MM format.

    Returns:
        Current month string (e.g., "2025-11")
    """
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _update_latest_symlink(target_dir: Path, extension: str, current_month: str) -> None:
    """Create or update 'latest' symlink to current month's file.

    Args:
        target_dir: Directory containing the symlink
        extension: File extension (e.g., '.html')
        current_month: Current month string (YYYY-MM)
    """
    latest_link = target_dir / f"latest{extension}"
    if latest_link.exists() or latest_link.is_symlink():
        latest_link.unlink()
    latest_link.symlink_to(f"{current_month}/{current_month}{extension}")


def _copy_to_month_directory(
    source_file: Path, target_dir: Path, current_month: str
) -> tuple[Path, bool]:
    """Copy file to month-based directory structure.

    Args:
        source_file: Source file to copy
        target_dir: Target directory (channel or thread dir)
        current_month: Current month string (YYYY-MM)

    Returns:
        Tuple of (destination_path, success)
    """
    extension = source_file.suffix
    month_dir = target_dir / current_month
    month_dir.mkdir(parents=True, exist_ok=True)

    dest_file = month_dir / f"{current_month}{extension}"
    try:
        shutil.copy2(source_file, dest_file)
        _update_latest_symlink(target_dir, extension, current_month)
        return dest_file, True
    except Exception:
        return dest_file, False


def _organize_thread_file(
    thread_file: Path,
    forum_name: str,
    public_forum_dir: Path,
    server_context: tuple[str, str, Path],  # (server_name, current_month, public_dir)
) -> tuple[str | None, str | None]:
    """Organize a single thread file.

    Args:
        thread_file: Thread file to organize
        forum_name: Forum name
        public_forum_dir: Public directory for forum
        server_context: Tuple of (server_name, current_month, public_dir)

    Returns:
        Tuple of (channel_key, error_msg) - one will be None
    """
    server_name, current_month, public_dir = server_context
    thread_name = thread_file.stem
    extension = thread_file.suffix

    # Skip non-export files
    if extension not in [".html", ".txt", ".json", ".csv"]:
        return None, None

    public_thread_dir = public_forum_dir / thread_name
    dest_file, success = _copy_to_month_directory(thread_file, public_thread_dir, current_month)

    if success:
        channel_key = f"{server_name}/{forum_name}/{thread_name}"
        rel_path = dest_file.relative_to(public_dir)
        print(f"  ✓ {forum_name}/{thread_name}{extension} → {rel_path}")
        return channel_key, None
    else:
        return None, f"Failed to organize {thread_file.name}"


def _organize_channel_file(
    channel_file: Path,
    public_server: Path,
    current_month: str,
    server_name: str,
    public_dir: Path,
) -> tuple[str | None, str | None]:
    """Organize a single channel file.

    Args:
        channel_file: Channel file to organize
        public_server: Public directory for server
        current_month: Current month string
        server_name: Server name
        public_dir: Public root directory

    Returns:
        Tuple of (channel_key, error_msg) - one will be None
    """
    channel_name = channel_file.stem
    ext = channel_file.suffix

    # Skip non-export files
    if ext not in [".html", ".txt", ".json", ".csv"]:
        print(f"  ⚠ Skipping {channel_file.name} (unsupported format)")
        return None, None

    channel_dir = public_server / channel_name
    dest_file, success = _copy_to_month_directory(channel_file, channel_dir, current_month)

    if success:
        channel_key = f"{server_name}/{channel_name}"
        print(f"  ✓ {channel_name}{ext} → {dest_file.relative_to(public_dir)}")
        return channel_key, None
    else:
        return None, f"Failed to organize {channel_file.name}"


def _process_forum_directory(
    forum_dir: Path,
    server_context: tuple[str, Path, str, Path],
) -> tuple[list[str], list[str], int]:
    """Process all threads in a forum directory.

    Args:
        forum_dir: Forum directory path
        server_context: Tuple of (server_name, public_server, current_month, public_dir)

    Returns:
        Tuple of (channel_keys, errors, files_organized_count)
    """
    server_name, public_server, current_month, public_dir = server_context
    forum_name = forum_dir.name
    public_forum_dir = public_server / forum_name
    public_forum_dir.mkdir(parents=True, exist_ok=True)

    channel_keys: list[str] = []
    errors: list[str] = []
    files_count = 0

    thread_context = (server_name, current_month, public_dir)

    for thread_file in forum_dir.iterdir():
        if not thread_file.is_file():
            continue

        channel_key, error = _organize_thread_file(
            thread_file, forum_name, public_forum_dir, thread_context
        )

        if channel_key:
            channel_keys.append(channel_key)
            files_count += 1
        elif error:
            errors.append(error)

    return channel_keys, errors, files_count


def _process_server_directory(
    server_dir: Path,
    public_dir: Path,
    current_month: str,
) -> tuple[set[str], int, list[str]]:
    """Process all channels and forums in a server directory.

    Args:
        server_dir: Server export directory
        public_dir: Public root directory
        current_month: Current month string

    Returns:
        Tuple of (channels_seen, files_organized, errors)
    """
    server_name = server_dir.name
    public_server = public_dir / server_name
    channels_seen: set[str] = set()
    files_organized = 0
    errors: list[str] = []

    server_context = (server_name, public_server, current_month, public_dir)

    for item in server_dir.iterdir():
        if item.is_dir():
            # Forum directory - process threads
            keys, item_errors, files_count = _process_forum_directory(item, server_context)
            channels_seen.update(keys)
            files_organized += files_count
            errors.extend(item_errors)
        elif item.is_file():
            # Regular channel file
            channel_key, error = _organize_channel_file(
                item, public_server, current_month, server_name, public_dir
            )
            if channel_key:
                channels_seen.add(channel_key)
                files_organized += 1
            elif error:
                errors.append(error)

    return channels_seen, files_organized, errors


def organize_exports(
    exports_dir: Path | None = None, public_dir: Path | None = None
) -> dict[str, Any]:
    """Move exports from exports/ to public/ with date-based organization.

    Handles both regular channels and forum/thread structure:
    - Regular: exports/server/channel.html -> public/server/channel/YYYY-MM/YYYY-MM.html
    - Forums: exports/server/forum/thread.html -> public/server/forum/thread/YYYY-MM/YYYY-MM.html

    Args:
        exports_dir: Source directory (defaults to "exports")
        public_dir: Destination directory (defaults to "public")

    Returns:
        Dict with statistics:
            - files_organized: Number of files successfully organized
            - channels_processed: Number of unique channels processed
            - errors: List of error messages

    Raises:
        FileNotFoundError: If exports directory doesn't exist
    """
    # Use defaults if not provided
    if exports_dir is None:
        exports_dir = Path("exports")
    if public_dir is None:
        public_dir = Path("public")

    # Ensure exports directory exists
    if not exports_dir.exists():
        raise FileNotFoundError(
            f"Exports directory not found: {exports_dir}\n"
            "Run scripts/export_channels.py first to generate exports."
        )

    # Create public directory if it doesn't exist
    public_dir.mkdir(exist_ok=True)

    stats: dict[str, Any] = {"files_organized": 0, "channels_processed": 0, "errors": []}

    current_month = get_current_month()
    channels_seen = set()

    # Process each server directory
    for server_dir in exports_dir.iterdir():
        if not server_dir.is_dir():
            continue

        print(f"Organizing {server_dir.name}...")

        server_channels, server_files, server_errors = _process_server_directory(
            server_dir, public_dir, current_month
        )

        channels_seen.update(server_channels)
        stats["files_organized"] += server_files
        for error in server_errors:
            stats["errors"].append(error)
            print(f"  ✗ {error}")

    stats["channels_processed"] = len(channels_seen)
    return stats

def cleanup_exports(exports_dir: Path | None = None) -> None:
    """Remove organized files from exports directory.

    CAUTION: Only call this after successful organization!

    Args:
        exports_dir: Directory to clean (defaults to "exports")
    """
    if exports_dir is None:
        exports_dir = Path("exports")

    if not exports_dir.exists():
        return

    for server_dir in exports_dir.iterdir():
        if server_dir.is_dir():
            for export_file in server_dir.iterdir():
                if export_file.is_file():
                    export_file.unlink()

            # Remove empty server directory
            if not any(server_dir.iterdir()):
                server_dir.rmdir()


def main() -> None:
    """Entry point for organize script."""
    print("Discord Export Organizer")
    print("=" * 50)

    try:
        # Organize exports
        stats = organize_exports()

        # Print summary
        print("\n" + "=" * 50)
        print("Organization Summary:")
        print(f"  Files organized: {stats['files_organized']}")
        print(f"  Channels processed: {stats['channels_processed']}")

        if stats["errors"]:
            print(f"\nErrors ({len(stats['errors'])}):")
            for error in stats["errors"][:5]:  # Show first 5
                print(f"  - {error}")

        # Optional: Cleanup exports directory
        # Uncomment if you want to remove organized files from exports/
        # cleanup_exports()

        exit_code = 1 if stats["errors"] else 0
        sys.exit(exit_code)

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
