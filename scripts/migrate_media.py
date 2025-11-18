#!/usr/bin/env python3
"""Migrate existing media files from channel level to month directories.

This script moves media directories from:
  public/server/channel/{channel}_media/
To:
  public/server/channel/YYYY-MM/{channel}_media/

For all existing YYYY-MM subdirectories.
"""

import shutil
import sys
from pathlib import Path


def migrate_media_for_channel(channel_dir: Path) -> tuple[int, int]:
    """Migrate media for a single channel directory.

    Args:
        channel_dir: Path to channel directory (e.g., public/server/channel/)

    Returns:
        Tuple of (migrations_count, errors_count)
    """
    channel_name = channel_dir.name
    media_dir_name = f"{channel_name}_media"
    source_media = channel_dir / media_dir_name

    # Skip if no source media directory
    if not source_media.exists() or not source_media.is_dir():
        return 0, 0

    migrations = 0
    errors = 0

    # Find all month subdirectories
    for month_dir in channel_dir.iterdir():
        if not month_dir.is_dir():
            continue

        # Check if directory name looks like YYYY-MM
        if not (len(month_dir.name) == 7 and month_dir.name[4] == "-"):
            continue

        # Destination: public/server/channel/YYYY-MM/{channel}_media/
        dest_media = month_dir / media_dir_name

        # Skip if already exists
        if dest_media.exists():
            print(f"  ⚠ Skipping {month_dir.name} (media already exists)")
            continue

        try:
            # Copy media directory to month directory
            shutil.copytree(source_media, dest_media)
            migrations += 1
            print(f"  ✓ Migrated media to {month_dir.name}/")
        except Exception as e:
            errors += 1
            print(f"  ✗ Error migrating to {month_dir.name}/: {e}")

    # Remove old media directory after successful migrations
    if migrations > 0 and errors == 0:
        try:
            shutil.rmtree(source_media)
            print(f"  ✓ Removed old media directory at channel level")
        except Exception as e:
            print(f"  ⚠ Could not remove old media directory: {e}")

    return migrations, errors


def migrate_media_for_thread(thread_dir: Path) -> tuple[int, int]:
    """Migrate media for a forum thread directory.

    Args:
        thread_dir: Path to thread directory (e.g., public/server/forum/thread/)

    Returns:
        Tuple of (migrations_count, errors_count)
    """
    thread_name = thread_dir.name
    media_dir_name = f"{thread_name}_media"
    source_media = thread_dir / media_dir_name

    # Skip if no source media directory
    if not source_media.exists() or not source_media.is_dir():
        return 0, 0

    migrations = 0
    errors = 0

    # Find all month subdirectories
    for month_dir in thread_dir.iterdir():
        if not month_dir.is_dir():
            continue

        # Check if directory name looks like YYYY-MM
        if not (len(month_dir.name) == 7 and month_dir.name[4] == "-"):
            continue

        # Destination: public/server/forum/thread/YYYY-MM/{thread}_media/
        dest_media = month_dir / media_dir_name

        # Skip if already exists
        if dest_media.exists():
            continue

        try:
            # Copy media directory to month directory
            shutil.copytree(source_media, dest_media)
            migrations += 1
            print(f"    ✓ Migrated media to {thread_name}/{month_dir.name}/")
        except Exception as e:
            errors += 1
            print(f"    ✗ Error migrating to {thread_name}/{month_dir.name}/: {e}")

    # Remove old media directory after successful migrations
    if migrations > 0 and errors == 0:
        try:
            shutil.rmtree(source_media)
            print(f"    ✓ Removed old media directory for thread {thread_name}")
        except Exception as e:
            print(f"    ⚠ Could not remove old media directory: {e}")

    return migrations, errors


def main() -> None:
    """Entry point for media migration."""
    print("Media Migration Script")
    print("=" * 50)

    public_dir = Path("public")

    if not public_dir.exists():
        print("ERROR: public/ directory not found")
        sys.exit(1)

    total_migrations = 0
    total_errors = 0

    # Process each server
    for server_dir in public_dir.iterdir():
        if not server_dir.is_dir():
            continue

        print(f"\nProcessing {server_dir.name}...")

        # Process each channel/forum
        for item_dir in server_dir.iterdir():
            if not item_dir.is_dir():
                continue

            # Check if this is a forum (has subdirectories that are threads)
            is_forum = any(
                d.is_dir() and not (len(d.name) == 7 and d.name[4] == "-") for d in item_dir.iterdir()
            )

            if is_forum:
                # This is a forum - process each thread
                print(f"  Forum: {item_dir.name}")
                for thread_dir in item_dir.iterdir():
                    if not thread_dir.is_dir():
                        continue
                    if len(thread_dir.name) == 7 and thread_dir.name[4] == "-":
                        continue  # Skip month directories at forum level

                    migrations, errors = migrate_media_for_thread(thread_dir)
                    total_migrations += migrations
                    total_errors += errors
            else:
                # Regular channel
                print(f"  Channel: {item_dir.name}")
                migrations, errors = migrate_media_for_channel(item_dir)
                total_migrations += migrations
                total_errors += errors

    print("\n" + "=" * 50)
    print(f"Migration Summary:")
    print(f"  Total migrations: {total_migrations}")
    print(f"  Total errors: {total_errors}")

    if total_errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
