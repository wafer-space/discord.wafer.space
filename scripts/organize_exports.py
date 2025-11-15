#!/usr/bin/env python3
# scripts/organize_exports.py
"""Organize exported files into date-based directory structure.

This script moves exported files from the exports/ directory to the public/
directory, organizing them by server/channel structure with date-based naming.
"""
import shutil
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict


def get_current_month() -> str:
    """
    Get current month in YYYY-MM format.

    Returns:
        Current month string (e.g., "2025-11")
    """
    return datetime.now(timezone.utc).strftime('%Y-%m')


def organize_exports(exports_dir: Path = None, public_dir: Path = None) -> Dict[str, int]:
    """
    Move exports from exports/ to public/ with date-based organization.

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

    stats = {
        'files_organized': 0,
        'channels_processed': 0,
        'errors': []
    }

    current_month = get_current_month()
    channels_seen = set()

    # Process each server directory
    for server_dir in exports_dir.iterdir():
        if not server_dir.is_dir():
            continue

        server_name = server_dir.name
        public_server = public_dir / server_name

        print(f"Organizing {server_name}...")

        # Process all items in server directory
        for item in server_dir.iterdir():
            # Check if it's a forum directory (contains multiple files, no parent channel)
            if item.is_dir():
                # Forum directory - process threads
                forum_name = item.name
                public_forum_dir = public_server / forum_name
                public_forum_dir.mkdir(parents=True, exist_ok=True)

                # Process each thread in forum
                for thread_file in item.iterdir():
                    if thread_file.is_file():
                        thread_name = thread_file.stem  # filename without extension
                        extension = thread_file.suffix

                        # Skip non-export files
                        if extension not in ['.html', '.txt', '.json', '.csv']:
                            continue

                        try:
                            # Create thread directory
                            public_thread_dir = public_forum_dir / thread_name
                            month_dir = public_thread_dir / current_month
                            month_dir.mkdir(parents=True, exist_ok=True)

                            # Copy file to month directory
                            dest_file = month_dir / f"{current_month}{extension}"
                            shutil.copy2(thread_file, dest_file)
                            stats['files_organized'] += 1

                            # Create/update latest symlink
                            latest_link = public_thread_dir / f"latest{extension}"
                            if latest_link.exists() or latest_link.is_symlink():
                                latest_link.unlink()
                            latest_link.symlink_to(f"{current_month}/{current_month}{extension}")

                            # Track unique channels
                            channel_key = f"{server_name}/{forum_name}/{thread_name}"
                            channels_seen.add(channel_key)

                            print(f"  ✓ {forum_name}/{thread_name}{extension} → {dest_file.relative_to(public_dir)}")

                        except Exception as e:
                            error_msg = f"Failed to organize {thread_file.name}: {str(e)}"
                            stats['errors'].append(error_msg)
                            print(f"  ✗ {error_msg}")

            elif item.is_file():
                # Regular channel file
                try:
                    channel_name = item.stem
                    ext = item.suffix

                    # Skip non-export files
                    if ext not in ['.html', '.txt', '.json', '.csv']:
                        print(f"  ⚠ Skipping {item.name} (unsupported format)")
                        continue

                    # Create channel directory structure
                    channel_dir = public_server / channel_name
                    month_dir = channel_dir / current_month
                    month_dir.mkdir(parents=True, exist_ok=True)

                    # Copy file to month directory
                    dest_file = month_dir / f"{current_month}{ext}"
                    shutil.copy2(item, dest_file)
                    stats['files_organized'] += 1

                    # Create/update latest symlink
                    latest_link = channel_dir / f"latest{ext}"
                    if latest_link.exists() or latest_link.is_symlink():
                        latest_link.unlink()
                    latest_link.symlink_to(f"{current_month}/{current_month}{ext}")

                    # Track unique channels
                    channel_key = f"{server_name}/{channel_name}"
                    channels_seen.add(channel_key)

                    print(f"  ✓ {channel_name}{ext} → {dest_file.relative_to(public_dir)}")

                except Exception as e:
                    error_msg = f"Failed to organize {item.name}: {str(e)}"
                    stats['errors'].append(error_msg)
                    print(f"  ✗ {error_msg}")

    stats['channels_processed'] = len(channels_seen)
    return stats


def cleanup_exports(exports_dir: Path = None) -> None:
    """
    Remove organized files from exports directory.

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


def main():
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

        if stats['errors']:
            print(f"\nErrors ({len(stats['errors'])}):")
            for error in stats['errors'][:5]:  # Show first 5
                print(f"  - {error}")

        # Optional: Cleanup exports directory
        # Uncomment if you want to remove organized files from exports/
        # cleanup_exports()

        exit_code = 1 if stats['errors'] else 0
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
