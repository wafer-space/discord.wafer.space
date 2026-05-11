# tests/test_organize_exports.py
import tempfile
from pathlib import Path

import pytest

from scripts.organize_exports import cleanup_exports, organize_exports

# Test constants
EXPECTED_FILES_ORGANIZED = 4
EXPECTED_SERVERS_PROCESSED = 3
EXPECTED_MERGED_MESSAGES = 3


def test_organize_exports_creates_month_directory_from_filename() -> None:
    """Per-month input `2026-05.html` lands at `public/server/channel/2026-05/2026-05.html`.

    The month comes from the filename, NOT from datetime.now() — that's
    the entire point of the refactor. Otherwise a backfilled 2026-03
    export would be misfiled into the current calendar month.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        exports = tmpdir_path / "exports"
        public = tmpdir_path / "public"

        channel_dir = exports / "test-server" / "general"
        channel_dir.mkdir(parents=True)
        (channel_dir / "2026-05.html").write_text("<html>may</html>")
        (channel_dir / "2026-05.txt").write_text("may messages")
        (channel_dir / "2026-05.json").write_text('{"messages":[{"id":"1"}]}')
        (channel_dir / "2026-05.csv").write_text("id\n1\n")

        stats = organize_exports(exports, public)

        assert stats["files_organized"] == EXPECTED_FILES_ORGANIZED
        assert stats["channels_processed"] == 1
        assert len(stats["errors"]) == 0

        target = public / "test-server" / "general" / "2026-05"
        assert (target / "2026-05.html").exists()
        assert (target / "2026-05.txt").exists()
        assert (target / "2026-05.json").exists()
        assert (target / "2026-05.csv").exists()


def test_organize_exports_partitions_by_each_filename_month() -> None:
    """Multiple per-month files for one channel land in their own directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        exports = tmpdir_path / "exports"
        public = tmpdir_path / "public"

        channel_dir = exports / "test-server" / "general"
        channel_dir.mkdir(parents=True)
        (channel_dir / "2026-03.html").write_text("<html>march</html>")
        (channel_dir / "2026-04.html").write_text("<html>april</html>")
        (channel_dir / "2026-05.html").write_text("<html>may</html>")

        organize_exports(exports, public)

        assert (public / "test-server" / "general" / "2026-03" / "2026-03.html").exists()
        assert (public / "test-server" / "general" / "2026-04" / "2026-04.html").exists()
        assert (public / "test-server" / "general" / "2026-05" / "2026-05.html").exists()
        # And no cross-contamination
        march = (public / "test-server" / "general" / "2026-03" / "2026-03.html").read_text()
        assert "march" in march
        assert "april" not in march
        assert "may" not in march


def test_organize_exports_creates_latest_symlinks_to_most_recent_month() -> None:
    """`latest.html` points at the newest month for that channel."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        exports = tmpdir_path / "exports"
        public = tmpdir_path / "public"

        channel_dir = exports / "test-server" / "general"
        channel_dir.mkdir(parents=True)
        (channel_dir / "2026-03.html").write_text("<html>march</html>")
        (channel_dir / "2026-05.html").write_text("<html>may</html>")

        organize_exports(exports, public)

        latest_link = public / "test-server" / "general" / "latest.html"
        assert latest_link.is_symlink()
        # Should point at 2026-05 (the newest month present in the input)
        assert latest_link.readlink() == Path("2026-05/2026-05.html")


def test_organize_exports_multiple_servers() -> None:
    """Test organizing exports from multiple servers"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        exports = tmpdir_path / "exports"
        public = tmpdir_path / "public"

        # Server 1 with two channels
        (exports / "server-one" / "general").mkdir(parents=True)
        (exports / "server-one" / "general" / "2026-05.html").write_text("s1 general")
        (exports / "server-one" / "announcements").mkdir(parents=True)
        (exports / "server-one" / "announcements" / "2026-05.html").write_text("s1 ann")

        # Server 2 with one channel
        (exports / "server-two" / "general").mkdir(parents=True)
        (exports / "server-two" / "general" / "2026-05.html").write_text("s2 general")

        stats = organize_exports(exports, public)

        assert stats["files_organized"] == EXPECTED_SERVERS_PROCESSED
        assert stats["channels_processed"] == EXPECTED_SERVERS_PROCESSED

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

        channel_dir = exports / "test-server" / "general"
        channel_dir.mkdir(parents=True)
        (channel_dir / "2026-05.html").write_text("test")

        # Organize should create public directory
        organize_exports(exports, public)

        assert public.exists()
        assert public.is_dir()


def test_organize_exports_skips_invalid_extensions() -> None:
    """Test that organize_exports skips files with invalid extensions"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        exports = tmpdir_path / "exports"
        public = tmpdir_path / "public"

        channel_dir = exports / "test-server" / "general"
        channel_dir.mkdir(parents=True)
        (channel_dir / "2026-05.html").write_text("valid")
        (channel_dir / "2026-05.pdf").write_text("invalid")
        (channel_dir / "notes.md").write_text("invalid")

        stats = organize_exports(exports, public)

        # Only the html file should organize
        assert stats["files_organized"] == 1
        assert stats["channels_processed"] == 1


def test_organize_exports_skips_non_month_filenames() -> None:
    """Files that aren't named YYYY-MM.{ext} are ignored.

    This guards against accidentally treating an arbitrary filename as a
    month, which would create confusing directories like `latest/` if a
    leftover symlink or stray file landed in the channel directory.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        exports = tmpdir_path / "exports"
        public = tmpdir_path / "public"

        channel_dir = exports / "test-server" / "general"
        channel_dir.mkdir(parents=True)
        (channel_dir / "2026-05.html").write_text("ok")
        (channel_dir / "general.html").write_text("wrong format")
        (channel_dir / "latest.html").write_text("wrong format")

        stats = organize_exports(exports, public)

        assert stats["files_organized"] == 1
        # Only 2026-05 directory should exist
        assert (public / "test-server" / "general" / "2026-05").exists()
        assert not (public / "test-server" / "general" / "general").exists()
        assert not (public / "test-server" / "general" / "latest").exists()


def test_cleanup_exports_removes_organized_files() -> None:
    """Test that cleanup_exports removes per-month files from exports directory"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        exports = tmpdir_path / "exports"

        channel_dir = exports / "test-server" / "general"
        channel_dir.mkdir(parents=True)
        file1 = channel_dir / "2026-05.html"
        file2 = channel_dir / "2026-05.json"
        file1.write_text("test1")
        file2.write_text("test2")

        cleanup_exports(exports)

        assert not file1.exists()
        assert not file2.exists()


def test_cleanup_exports_handles_missing_dir() -> None:
    """Test that cleanup_exports handles missing directory gracefully"""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        exports = tmpdir_path / "exports"

        # Don't create directory
        # Should not raise error
        cleanup_exports(exports)


def test_organize_exports_handles_forum_threads() -> None:
    """Threads inside a forum directory get per-month organization."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        exports = tmpdir_path / "exports"
        public = tmpdir_path / "public"

        # exports/test-server/questions/how-to-start/2026-05.html
        thread_dir = exports / "test-server" / "questions" / "how-to-start"
        thread_dir.mkdir(parents=True)
        (thread_dir / "2026-05.html").write_text("<html>thread may</html>")
        (thread_dir / "2026-05.json").write_text('{"messages": []}')

        # Another thread in same forum
        thread2 = exports / "test-server" / "questions" / "help-needed"
        thread2.mkdir(parents=True)
        (thread2 / "2026-04.html").write_text("<html>thread april</html>")

        organize_exports(exports, public)

        assert (
            public / "test-server" / "questions" / "how-to-start" / "2026-05" / "2026-05.html"
        ).exists()
        assert (
            public / "test-server" / "questions" / "help-needed" / "2026-04" / "2026-04.html"
        ).exists()


def test_organize_exports_copies_per_month_media_directory() -> None:
    """Per-month media dir `2026-05_media/` lands inside `2026-05/`."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        exports = tmpdir_path / "exports"
        public = tmpdir_path / "public"

        channel_dir = exports / "test-server" / "general"
        channel_dir.mkdir(parents=True)
        (channel_dir / "2026-05.html").write_text("<html>content</html>")
        media_dir = channel_dir / "2026-05_media"
        media_dir.mkdir()
        (media_dir / "avatar.png").write_bytes(b"png-bytes")
        (media_dir / "doc.pdf").write_bytes(b"pdf-bytes")

        organize_exports(exports, public)

        public_media = public / "test-server" / "general" / "2026-05" / "2026-05_media"
        assert public_media.is_dir()
        assert (public_media / "avatar.png").read_bytes() == b"png-bytes"
        assert (public_media / "doc.pdf").read_bytes() == b"pdf-bytes"


def test_organize_exports_handles_missing_media_directory() -> None:
    """Channel without media still organizes cleanly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        exports = tmpdir_path / "exports"
        public = tmpdir_path / "public"

        channel_dir = exports / "test-server" / "general"
        channel_dir.mkdir(parents=True)
        (channel_dir / "2026-05.html").write_text("<html>no media</html>")

        stats = organize_exports(exports, public)
        assert stats["files_organized"] == 1
        assert len(stats["errors"]) == 0

        public_chan = public / "test-server" / "general" / "2026-05"
        assert public_chan.exists()
        assert not (public_chan / "2026-05_media").exists()


def test_organize_exports_merges_json_messages_same_month() -> None:
    """JSON merge deduplicates messages by ID for the same month."""
    import json

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        exports = tmpdir_path / "exports"
        public = tmpdir_path / "public"

        # Existing 2026-05 archive
        existing_dir = public / "test-server" / "general" / "2026-05"
        existing_dir.mkdir(parents=True)
        existing_json = {
            "guild": {"id": "123"},
            "channel": {"id": "456", "name": "general"},
            "dateRange": {"after": None, "before": None},
            "messages": [
                {"id": "1000", "content": "First", "timestamp": "2026-05-01T00:00:00"},
                {"id": "1001", "content": "Second", "timestamp": "2026-05-02T00:00:00"},
            ],
            "messageCount": 2,
        }
        (existing_dir / "2026-05.json").write_text(json.dumps(existing_json))

        # New per-month export for same month with overlap
        channel_dir = exports / "test-server" / "general"
        channel_dir.mkdir(parents=True)
        new_json = {
            "guild": {"id": "123"},
            "channel": {"id": "456", "name": "general"},
            "messages": [
                {"id": "1000", "content": "First (edited)", "timestamp": "2026-05-01T00:00:00"},
                {"id": "1002", "content": "Third", "timestamp": "2026-05-03T00:00:00"},
            ],
            "messageCount": 2,
        }
        (channel_dir / "2026-05.json").write_text(json.dumps(new_json))
        (channel_dir / "2026-05.html").write_text("<html>updated</html>")

        organize_exports(exports, public)

        merged = json.loads((existing_dir / "2026-05.json").read_text())
        assert merged["messageCount"] == EXPECTED_MERGED_MESSAGES
        ids = [m["id"] for m in merged["messages"]]
        assert ids == ["1000", "1001", "1002"]
        # New version of message 1000 wins
        msg_1000 = next(m for m in merged["messages"] if m["id"] == "1000")
        assert msg_1000["content"] == "First (edited)"
