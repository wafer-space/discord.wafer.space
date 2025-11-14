# tests/test_organize_exports.py
import pytest
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from scripts.organize_exports import (
    get_current_month,
    organize_exports,
    cleanup_exports
)


def test_get_current_month():
    """Test that get_current_month returns YYYY-MM format"""
    result = get_current_month()
    # Should match YYYY-MM pattern
    assert len(result) == 7
    assert result[4] == '-'
    # Should be valid date
    year, month = result.split('-')
    assert year.isdigit() and len(year) == 4
    assert month.isdigit() and 1 <= int(month) <= 12


def test_organize_exports_creates_directory_structure():
    """Test that organize_exports creates proper directory structure"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        exports = tmpdir / "exports"
        public = tmpdir / "public"

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
        assert stats['files_organized'] == 4
        assert stats['channels_processed'] == 1
        assert len(stats['errors']) == 0

        # Check directory structure
        current_month = get_current_month()
        channel_dir = public / "test-server" / "general"
        assert channel_dir.exists()
        assert (channel_dir / f"{current_month}.html").exists()
        assert (channel_dir / f"{current_month}.txt").exists()
        assert (channel_dir / f"{current_month}.json").exists()
        assert (channel_dir / f"{current_month}.csv").exists()


def test_organize_exports_creates_latest_symlinks():
    """Test that organize_exports creates 'latest' symlinks"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        exports = tmpdir / "exports"
        public = tmpdir / "public"

        # Create fake export
        server_dir = exports / "test-server"
        server_dir.mkdir(parents=True)
        (server_dir / "general.html").write_text("<html>test</html>")

        # Organize exports
        organize_exports(exports, public)

        # Check symlink exists and points to correct file
        channel_dir = public / "test-server" / "general"
        latest_link = channel_dir / "latest.html"
        assert latest_link.exists()
        assert latest_link.is_symlink()

        current_month = get_current_month()
        expected_target = f"{current_month}.html"
        assert latest_link.readlink() == Path(expected_target)


def test_organize_exports_multiple_servers():
    """Test organizing exports from multiple servers"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        exports = tmpdir / "exports"
        public = tmpdir / "public"

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
        assert stats['files_organized'] == 3
        assert stats['channels_processed'] == 3  # 2 from server1, 1 from server2

        # Check both servers exist in public
        assert (public / "server-one").exists()
        assert (public / "server-two").exists()


def test_organize_exports_handles_missing_exports_dir():
    """Test that organize_exports raises error if exports dir missing"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        exports = tmpdir / "exports"
        public = tmpdir / "public"

        # Don't create exports directory
        with pytest.raises(FileNotFoundError, match="Exports directory not found"):
            organize_exports(exports, public)


def test_organize_exports_creates_public_dir_if_missing():
    """Test that organize_exports creates public dir if it doesn't exist"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        exports = tmpdir / "exports"
        public = tmpdir / "public"

        # Create exports but not public
        server_dir = exports / "test-server"
        server_dir.mkdir(parents=True)
        (server_dir / "general.html").write_text("test")

        # Organize should create public directory
        organize_exports(exports, public)

        assert public.exists()
        assert public.is_dir()


def test_organize_exports_preserves_file_metadata():
    """Test that organize_exports preserves file timestamps"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        exports = tmpdir / "exports"
        public = tmpdir / "public"

        # Create file with specific timestamp
        server_dir = exports / "test-server"
        server_dir.mkdir(parents=True)
        source_file = server_dir / "general.html"
        source_file.write_text("test")

        # Get original modification time
        original_mtime = source_file.stat().st_mtime

        # Organize exports
        organize_exports(exports, public)

        # Check that destination has same modification time
        current_month = get_current_month()
        dest_file = public / "test-server" / "general" / f"{current_month}.html"
        dest_mtime = dest_file.stat().st_mtime

        # Allow small difference due to filesystem precision
        assert abs(dest_mtime - original_mtime) < 1.0


def test_organize_exports_skips_invalid_extensions():
    """Test that organize_exports skips files with invalid extensions"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        exports = tmpdir / "exports"
        public = tmpdir / "public"

        # Create files with valid and invalid extensions
        server_dir = exports / "test-server"
        server_dir.mkdir(parents=True)
        (server_dir / "general.html").write_text("valid")
        (server_dir / "general.pdf").write_text("invalid")
        (server_dir / "notes.md").write_text("invalid")

        # Organize exports
        stats = organize_exports(exports, public)

        # Should only organize the html file
        assert stats['files_organized'] == 1
        assert stats['channels_processed'] == 1


def test_organize_exports_handles_errors_gracefully():
    """Test that organize_exports continues on individual file errors"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        exports = tmpdir / "exports"
        public = tmpdir / "public"

        # Create valid file
        server_dir = exports / "test-server"
        server_dir.mkdir(parents=True)
        (server_dir / "general.html").write_text("valid")

        # Note: It's difficult to create a reliable error condition that
        # would fail during copy but pass file creation checks.
        # This test verifies the error handling structure exists.

        stats = organize_exports(exports, public)
        assert 'errors' in stats
        assert isinstance(stats['errors'], list)


def test_cleanup_exports_removes_organized_files():
    """Test that cleanup_exports removes files from exports directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        exports = tmpdir / "exports"

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


def test_cleanup_exports_handles_missing_dir():
    """Test that cleanup_exports handles missing directory gracefully"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        exports = tmpdir / "exports"

        # Don't create directory
        # Should not raise error
        cleanup_exports(exports)


def test_organize_exports_replaces_existing_symlinks():
    """Test that organize_exports replaces existing 'latest' symlinks"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        exports = tmpdir / "exports"
        public = tmpdir / "public"

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

        # Organize should replace old symlink
        organize_exports(exports, public)

        current_month = get_current_month()
        expected_target = f"{current_month}.html"
        assert old_link.readlink() == Path(expected_target)
