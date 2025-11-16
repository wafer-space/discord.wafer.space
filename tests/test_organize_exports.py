# tests/test_organize_exports.py
import tempfile
from pathlib import Path

import pytest

from scripts.organize_exports import cleanup_exports, get_current_month, organize_exports

# Test constants
EXPECTED_MONTH_LENGTH = 7
EXPECTED_YEAR_LENGTH = 4
MAX_MONTH_VALUE = 12
EXPECTED_FILES_ORGANIZED = 4
EXPECTED_SERVERS_PROCESSED = 3


def test_get_current_month() -> None:
    """Test that get_current_month returns YYYY-MM format"""
    result = get_current_month()
    # Should match YYYY-MM pattern
    assert len(result) == EXPECTED_MONTH_LENGTH
    assert result[4] == "-"
    # Should be valid date
    year, month = result.split("-")
    assert year.isdigit() and len(year) == EXPECTED_YEAR_LENGTH
    assert month.isdigit() and 1 <= int(month) <= MAX_MONTH_VALUE


def test_organize_exports_creates_directory_structure() -> None:
    """Test that organize_exports creates proper directory structure"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        exports = tmpdir_path / "exports"
        public = tmpdir_path / "public"

        # Create fake export structure
        server_dir = exports / "test-server"
        server_dir.mkdir(parents=True)
        (server_dir / "general.html").write_text("<html>test</html>")
        (server_dir / "general.txt").write_text("test messages")
        (server_dir / "general.json").write_text('{"id": "1"}')
        (server_dir / "general.csv").write_text("id,content\n1,test")

        # Organize exports
        stats = organize_exports(exports, public)

        # Check statistics
        assert stats["files_organized"] == EXPECTED_FILES_ORGANIZED
        assert stats["channels_processed"] == 1
        assert len(stats["errors"]) == 0

        # Check directory structure (now with month subdirectories)
        current_month = get_current_month()
        channel_dir = public / "test-server" / "general"
        assert channel_dir.exists()
        month_dir = channel_dir / current_month
        assert month_dir.exists()
        assert (month_dir / f"{current_month}.html").exists()
        assert (month_dir / f"{current_month}.txt").exists()
        assert (month_dir / f"{current_month}.json").exists()
        assert (month_dir / f"{current_month}.csv").exists()


def test_organize_exports_creates_latest_symlinks() -> None:
    """Test that organize_exports creates 'latest' symlinks"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        exports = tmpdir_path / "exports"
        public = tmpdir_path / "public"

        # Create fake export
        server_dir = exports / "test-server"
        server_dir.mkdir(parents=True)
        (server_dir / "general.html").write_text("<html>test</html>")

        # Organize exports
        organize_exports(exports, public)

        # Check symlink exists and points to correct file (now in month subdirectory)
        channel_dir = public / "test-server" / "general"
        latest_link = channel_dir / "latest.html"
        assert latest_link.exists()
        assert latest_link.is_symlink()

        current_month = get_current_month()
        expected_target = f"{current_month}/{current_month}.html"
        assert latest_link.readlink() == Path(expected_target)


def test_organize_exports_multiple_servers() -> None:
    """Test organizing exports from multiple servers"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        exports = tmpdir_path / "exports"
        public = tmpdir_path / "public"

        # Create multiple servers
        server1 = exports / "server-one"
        server1.mkdir(parents=True)
        (server1 / "general.html").write_text("server1 general")
        (server1 / "announcements.html").write_text("server1 announcements")

        server2 = exports / "server-two"
        server2.mkdir(parents=True)
        (server2 / "general.html").write_text("server2 general")

        # Organize exports
        stats = organize_exports(exports, public)

        # Check statistics
        assert stats["files_organized"] == EXPECTED_SERVERS_PROCESSED
        # 2 from server1, 1 from server2
        assert stats["channels_processed"] == EXPECTED_SERVERS_PROCESSED

        # Check both servers exist in public
        assert (public / "server-one").exists()
        assert (public / "server-two").exists()


def test_organize_exports_handles_missing_exports_dir() -> None:
    """Test that organize_exports raises error if exports dir missing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        exports = tmpdir_path / "exports"
        public = tmpdir_path / "public"

        # Don't create exports directory
        with pytest.raises(FileNotFoundError, match="Exports directory not found"):
            organize_exports(exports, public)


def test_organize_exports_creates_public_dir_if_missing() -> None:
    """Test that organize_exports creates public dir if it doesn't exist"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        exports = tmpdir_path / "exports"
        public = tmpdir_path / "public"

        # Create exports but not public
        server_dir = exports / "test-server"
        server_dir.mkdir(parents=True)
        (server_dir / "general.html").write_text("test")

        # Organize should create public directory
        organize_exports(exports, public)

        assert public.exists()
        assert public.is_dir()


def test_organize_exports_preserves_file_metadata() -> None:
    """Test that organize_exports preserves file timestamps"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        exports = tmpdir_path / "exports"
        public = tmpdir_path / "public"

        # Create file with specific timestamp
        server_dir = exports / "test-server"
        server_dir.mkdir(parents=True)
        source_file = server_dir / "general.html"
        source_file.write_text("test")

        # Get original modification time
        original_mtime = source_file.stat().st_mtime

        # Organize exports
        organize_exports(exports, public)

        # Check that destination has same modification time (now in month subdirectory)
        current_month = get_current_month()
        dest_file = public / "test-server" / "general" / current_month / f"{current_month}.html"
        dest_mtime = dest_file.stat().st_mtime

        # Allow small difference due to filesystem precision
        assert abs(dest_mtime - original_mtime) < 1.0


def test_organize_exports_skips_invalid_extensions() -> None:
    """Test that organize_exports skips files with invalid extensions"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        exports = tmpdir_path / "exports"
        public = tmpdir_path / "public"

        # Create files with valid and invalid extensions
        server_dir = exports / "test-server"
        server_dir.mkdir(parents=True)
        (server_dir / "general.html").write_text("valid")
        (server_dir / "general.pdf").write_text("invalid")
        (server_dir / "notes.md").write_text("invalid")

        # Organize exports
        stats = organize_exports(exports, public)

        # Should only organize the html file
        assert stats["files_organized"] == 1
        assert stats["channels_processed"] == 1


def test_organize_exports_handles_errors_gracefully() -> None:
    """Test that organize_exports continues on individual file errors"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        exports = tmpdir_path / "exports"
        public = tmpdir_path / "public"

        # Create valid file
        server_dir = exports / "test-server"
        server_dir.mkdir(parents=True)
        (server_dir / "general.html").write_text("valid")

        # Note: It's difficult to create a reliable error condition that
        # would fail during copy but pass file creation checks.
        # This test verifies the error handling structure exists.

        stats = organize_exports(exports, public)
        assert "errors" in stats
        assert isinstance(stats["errors"], list)


def test_cleanup_exports_removes_organized_files() -> None:
    """Test that cleanup_exports removes files from exports directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        exports = tmpdir_path / "exports"

        # Create export files
        server_dir = exports / "test-server"
        server_dir.mkdir(parents=True)
        file1 = server_dir / "general.html"
        file2 = server_dir / "general.json"
        file1.write_text("test1")
        file2.write_text("test2")

        # Cleanup
        cleanup_exports(exports)

        # Files should be deleted
        assert not file1.exists()
        assert not file2.exists()
        # Empty server directory should also be removed
        assert not server_dir.exists()


def test_cleanup_exports_handles_missing_dir() -> None:
    """Test that cleanup_exports handles missing directory gracefully"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        exports = tmpdir_path / "exports"

        # Don't create directory
        # Should not raise error
        cleanup_exports(exports)


def test_organize_exports_replaces_existing_symlinks() -> None:
    """Test that organize_exports replaces existing 'latest' symlinks"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        exports = tmpdir_path / "exports"
        public = tmpdir_path / "public"

        # Create channel directory with existing symlink
        channel_dir = public / "test-server" / "general"
        channel_dir.mkdir(parents=True)
        old_link = channel_dir / "latest.html"
        old_target = channel_dir / "old-file.html"
        old_target.write_text("old")
        old_link.symlink_to(old_target.name)

        # Create new export
        server_dir = exports / "test-server"
        server_dir.mkdir(parents=True)
        (server_dir / "general.html").write_text("new")

        # Organize should replace old symlink (now pointing to month subdirectory)
        organize_exports(exports, public)

        current_month = get_current_month()
        expected_target = f"{current_month}/{current_month}.html"
        assert old_link.readlink() == Path(expected_target)


def test_organize_exports_handles_forum_structure() -> None:
    """Test that forum directories are organized correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        exports = tmpdir_path / "exports"
        public = tmpdir_path / "public"

        # Create forum structure
        forum_dir = exports / "test-server" / "questions"
        forum_dir.mkdir(parents=True)
        (forum_dir / "how-to-start.html").write_text("<html>Thread 1</html>")
        (forum_dir / "how-to-start.json").write_text('{"messages": []}')
        (forum_dir / "help-needed.html").write_text("<html>Thread 2</html>")

        # Organize exports
        organize_exports(exports, public)

        # Should create forum directory in public
        assert (public / "test-server" / "questions").exists()

        # Should create thread directories
        assert (public / "test-server" / "questions" / "how-to-start").exists()
        assert (public / "test-server" / "questions" / "help-needed").exists()

        # Should organize files by month
        current_month = get_current_month()
        assert (public / "test-server" / "questions" / "how-to-start" / current_month).exists()
        assert (
            public
            / "test-server"
            / "questions"
            / "how-to-start"
            / current_month
            / f"{current_month}.html"
        ).exists()
        assert (
            public
            / "test-server"
            / "questions"
            / "how-to-start"
            / current_month
            / f"{current_month}.json"
        ).exists()


def test_organize_exports_mixed_regular_and_forum() -> None:
    """Test organizing mix of regular channels and forums."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        exports = tmpdir_path / "exports"
        public = tmpdir_path / "public"

        # Create regular channel
        server_dir = exports / "test-server"
        server_dir.mkdir(parents=True)
        (server_dir / "general.html").write_text("<html>General</html>")

        # Create forum structure
        forum_dir = server_dir / "questions"
        forum_dir.mkdir(parents=True)
        (forum_dir / "thread-1.html").write_text("<html>Thread</html>")

        # Organize exports
        organize_exports(exports, public)

        # Should have both regular and forum (both in month subdirectories)
        current_month = get_current_month()
        assert (
            public / "test-server" / "general" / current_month / f"{current_month}.html"
        ).exists()
        assert (
            public
            / "test-server"
            / "questions"
            / "thread-1"
            / current_month
            / f"{current_month}.html"
        ).exists()


def test_organize_exports_copies_channel_media_directory() -> None:
    """Test that media directories are copied alongside channel files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        exports = tmpdir_path / "exports"
        public = tmpdir_path / "public"

        # Create channel with media directory
        server_dir = exports / "test-server"
        server_dir.mkdir(parents=True)
        (server_dir / "general.html").write_text("<html>Channel content</html>")

        # Create media directory with sample media files
        media_dir = server_dir / "general_media"
        media_dir.mkdir()
        (media_dir / "avatar.png").write_bytes(b"fake png data")
        (media_dir / "attachment.jpg").write_bytes(b"fake jpg data")

        # Organize exports
        organize_exports(exports, public)

        # Check that media directory was copied
        channel_dir = public / "test-server" / "general"
        assert channel_dir.exists()

        public_media_dir = channel_dir / "general_media"
        assert public_media_dir.exists()
        assert public_media_dir.is_dir()

        # Check that media files were copied
        assert (public_media_dir / "avatar.png").exists()
        assert (public_media_dir / "attachment.jpg").exists()
        assert (public_media_dir / "avatar.png").read_bytes() == b"fake png data"
        assert (public_media_dir / "attachment.jpg").read_bytes() == b"fake jpg data"


def test_organize_exports_copies_thread_media_directory() -> None:
    """Test that media directories are copied for forum threads."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        exports = tmpdir_path / "exports"
        public = tmpdir_path / "public"

        # Create forum thread with media directory
        forum_dir = exports / "test-server" / "questions"
        forum_dir.mkdir(parents=True)
        (forum_dir / "help-needed.html").write_text("<html>Thread content</html>")

        # Create media directory for thread
        media_dir = forum_dir / "help-needed_media"
        media_dir.mkdir()
        (media_dir / "screenshot.png").write_bytes(b"fake screenshot")

        # Organize exports
        organize_exports(exports, public)

        # Check that media directory was copied
        thread_dir = public / "test-server" / "questions" / "help-needed"
        assert thread_dir.exists()

        public_media_dir = thread_dir / "help-needed_media"
        assert public_media_dir.exists()
        assert public_media_dir.is_dir()
        assert (public_media_dir / "screenshot.png").exists()
        assert (public_media_dir / "screenshot.png").read_bytes() == b"fake screenshot"


def test_organize_exports_handles_missing_media_directory() -> None:
    """Test that organizing works when no media directory exists."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        exports = tmpdir_path / "exports"
        public = tmpdir_path / "public"

        # Create channel WITHOUT media directory
        server_dir = exports / "test-server"
        server_dir.mkdir(parents=True)
        (server_dir / "general.html").write_text("<html>No media</html>")

        # Organize should work without errors
        stats = organize_exports(exports, public)
        assert stats["files_organized"] == 1
        assert len(stats["errors"]) == 0

        # Channel should exist but no media directory
        channel_dir = public / "test-server" / "general"
        assert channel_dir.exists()
        assert not (channel_dir / "general_media").exists()


def test_organize_exports_replaces_existing_media_directory() -> None:
    """Test that existing media directory is replaced with new one."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        exports = tmpdir_path / "exports"
        public = tmpdir_path / "public"

        # Create channel directory with old media
        channel_dir = public / "test-server" / "general"
        old_media_dir = channel_dir / "general_media"
        old_media_dir.mkdir(parents=True)
        (old_media_dir / "old-file.png").write_bytes(b"old data")

        # Create new export with new media
        server_dir = exports / "test-server"
        server_dir.mkdir(parents=True)
        (server_dir / "general.html").write_text("<html>Updated</html>")

        media_dir = server_dir / "general_media"
        media_dir.mkdir()
        (media_dir / "new-file.png").write_bytes(b"new data")

        # Organize exports
        organize_exports(exports, public)

        # Old file should be gone, new file should exist
        public_media_dir = channel_dir / "general_media"
        assert not (public_media_dir / "old-file.png").exists()
        assert (public_media_dir / "new-file.png").exists()
        assert (public_media_dir / "new-file.png").read_bytes() == b"new data"
