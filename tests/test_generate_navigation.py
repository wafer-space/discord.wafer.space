# tests/test_generate_navigation.py
import json
import tempfile
from pathlib import Path

from scripts.generate_navigation import (
    count_messages_from_json,
    generate_channel_index,
    generate_server_index,
    generate_site_index,
    group_by_year,
    scan_exports,
)

# Test constants
EXPECTED_ARCHIVES_IN_2025 = 2
EXPECTED_ARCHIVES_IN_2024 = 2
EXPECTED_REPLY_COUNT = 2
EXPECTED_THREAD_COUNT = 2
EXPECTED_THREE_EXPORTS = 3
EXPECTED_THREE_MESSAGES = 3


def test_scan_exports_finds_files() -> None:
    """Test that scan_exports finds exported files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create fake export structure
        public = Path(tmpdir) / "public"
        server_dir = public / "test-server" / "general"
        server_dir.mkdir(parents=True)

        (server_dir / "2025-01.html").touch()
        (server_dir / "2025-01.json").touch()
        (server_dir / "2025-01.txt").touch()

        exports = scan_exports(public)

        assert len(exports) > 0
        assert any(e["channel"] == "general" for e in exports)


def test_scan_exports_skips_index_files() -> None:
    """Test that scan_exports skips index.html files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        public = Path(tmpdir) / "public"
        server_dir = public / "test-server" / "general"
        server_dir.mkdir(parents=True)

        (server_dir / "2025-01.html").touch()
        (server_dir / "index.html").touch()
        (public / "index.html").touch()

        exports = scan_exports(public)

        # Should only find 2025-01.html, not the index files
        assert len(exports) == 1
        assert exports[0]["date"] == "2025-01"


def test_scan_exports_multiple_channels() -> None:
    """Test scanning multiple channels and servers"""
    with tempfile.TemporaryDirectory() as tmpdir:
        public = Path(tmpdir) / "public"

        # Create multiple servers and channels
        (public / "server1" / "general" / "2025-01.html").parent.mkdir(parents=True)
        (public / "server1" / "general" / "2025-01.html").touch()
        (public / "server1" / "announcements" / "2025-01.html").parent.mkdir(parents=True)
        (public / "server1" / "announcements" / "2025-01.html").touch()
        (public / "server2" / "chat" / "2025-02.html").parent.mkdir(parents=True)
        (public / "server2" / "chat" / "2025-02.html").touch()

        exports = scan_exports(public)

        assert len(exports) == EXPECTED_THREE_EXPORTS
        servers = {e["server"] for e in exports}
        channels = {e["channel"] for e in exports}
        assert "server1" in servers
        assert "server2" in servers
        assert "general" in channels
        assert "announcements" in channels
        assert "chat" in channels


def test_count_messages_from_json() -> None:
    """Test counting messages from JSON file in DiscordChatExporter format"""
    sample_export = {
        "guild": {"id": "123", "name": "Test"},
        "channel": {"id": "456", "name": "test-channel"},
        "messages": [
            {"id": "1", "content": "Hello"},
            {"id": "2", "content": "World"},
            {"id": "3", "content": "Test"},
        ]
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(sample_export, f)
        json_path = f.name

    count = count_messages_from_json(json_path)
    assert count == EXPECTED_THREE_MESSAGES

    Path(json_path).unlink()


def test_count_messages_from_json_empty_messages_array() -> None:
    """Test counting messages with empty messages array"""
    sample_export = {
        "guild": {"id": "123", "name": "Test"},
        "channel": {"id": "456", "name": "test-channel"},
        "messages": []
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(sample_export, f)
        json_path = f.name

    count = count_messages_from_json(json_path)
    assert count == 0

    Path(json_path).unlink()


def test_count_messages_from_json_nonexistent() -> None:
    """Test counting messages from nonexistent file returns 0"""
    count = count_messages_from_json("/nonexistent/path/file.json")
    assert count == 0


def test_group_by_year() -> None:
    """Test grouping archives by year"""
    archives = [
        {"date": "2025-01", "message_count": 100},
        {"date": "2025-02", "message_count": 150},
        {"date": "2024-12", "message_count": 200},
        {"date": "2024-11", "message_count": 250},
    ]

    grouped = group_by_year(archives)

    assert "2025" in grouped
    assert "2024" in grouped
    assert len(grouped["2025"]) == EXPECTED_ARCHIVES_IN_2025
    assert len(grouped["2024"]) == EXPECTED_ARCHIVES_IN_2024


def test_group_by_year_sorted() -> None:
    """Test that archives within each year are sorted reverse chronologically"""
    archives = [
        {"date": "2025-01", "message_count": 100},
        {"date": "2025-03", "message_count": 150},
        {"date": "2025-02", "message_count": 200},
    ]

    grouped = group_by_year(archives)

    # Should be sorted newest first: 2025-03, 2025-02, 2025-01
    assert grouped["2025"][0]["date"] == "2025-03"
    assert grouped["2025"][1]["date"] == "2025-02"
    assert grouped["2025"][2]["date"] == "2025-01"


def test_generate_site_index() -> None:
    """Test generating site index page"""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "public" / "index.html"

        config = {"site": {"title": "Test Discord Logs", "description": "Test description"}}

        servers = [
            {
                "name": "test-server",
                "display_name": "Test Server",
                "channel_count": 5,
                "last_updated": "2025-01-15 14:00 UTC",
            }
        ]

        generate_site_index(config, servers, output_path)

        assert output_path.exists()
        html = output_path.read_text()
        assert "Test Discord Logs" in html
        assert "Test Server" in html
        assert "5 channels" in html


def test_generate_server_index() -> None:
    """Test generating server index page"""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "public" / "test-server" / "index.html"

        config = {"site": {"title": "Test Discord Logs"}}

        server = {"name": "test-server", "display_name": "Test Server"}

        channels = [{"name": "general", "message_count": 100, "archive_count": 3, "archives": []}]

        generate_server_index(config, server, channels, output_path)

        assert output_path.exists()
        html = output_path.read_text()
        assert "Test Server" in html
        assert "#general" in html


def test_generate_channel_index() -> None:
    """Test generating channel index page"""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "public" / "test-server" / "general" / "index.html"

        config = {"site": {"title": "Test Discord Logs"}}

        server = {"name": "test-server", "display_name": "Test Server"}

        channel = {"name": "general"}

        archives = [
            {"date": "2025-01", "message_count": 100},
            {"date": "2025-02", "message_count": 150},
        ]

        generate_channel_index(config, server, channel, archives, output_path)

        assert output_path.exists()
        html = output_path.read_text()
        assert "#general" in html
        assert "2025-01" in html
        assert "2025-02" in html


def test_generate_forum_index() -> None:
    """Test forum index generation."""
    from scripts.generate_navigation import ForumInfo, generate_forum_index

    # Setup
    config = {"site": {"title": "Test Site"}}
    server_info = {"name": "test-server", "display_name": "Test Server"}

    threads_data = [
        {
            "name": "how-to-start",
            "title": "How to start?",
            "url": "how-to-start/",
            "reply_count": 5,
            "last_activity": "2025-11-10",
            "archived": False,
        },
        {
            "name": "old-thread",
            "title": "Old Thread",
            "url": "old-thread/",
            "reply_count": 10,
            "last_activity": "2025-01-15",
            "archived": True,
        },
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "index.html"

        forum_info = ForumInfo(name="questions", description="Ask questions")
        generate_forum_index(
            config,
            server_info,
            forum_info,
            threads_data,
            output_path,
        )

        html = output_path.read_text()

        assert "<!DOCTYPE html>" in html
        assert "Questions" in html or "questions" in html
        assert "Ask questions" in html
        assert "How to start?" in html
        assert "5 replies" in html
        assert "Old Thread" in html
        assert "10 replies" in html


def test_collect_forum_threads() -> None:
    """Test collecting thread metadata from forum directory."""
    import json
    import tempfile
    from pathlib import Path

    from scripts.generate_navigation import collect_forum_threads

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create forum directory structure
        forum_dir = Path(tmpdir) / "questions"
        forum_dir.mkdir()

        # Create thread directories with JSON files
        thread1_dir = forum_dir / "how-to-start"
        thread1_dir.mkdir()

        thread1_json = {
            "channel": {"name": "How to start?"},
            "messages": [
                {"id": "1", "timestamp": "2025-11-01T10:00:00Z", "content": "msg1"},
                {"id": "2", "timestamp": "2025-11-10T15:00:00Z", "content": "msg2"},
            ],
        }
        (thread1_dir / "2025-11" / "2025-11.json").parent.mkdir(parents=True, exist_ok=True)
        with open(thread1_dir / "2025-11" / "2025-11.json", "w") as f:
            json.dump(thread1_json, f)

        # Collect threads
        threads = collect_forum_threads(forum_dir)

        assert len(threads) == 1
        assert threads[0]["name"] == "how-to-start"
        assert threads[0]["title"] == "How to start?"
        assert threads[0]["reply_count"] == EXPECTED_REPLY_COUNT
        assert threads[0]["last_activity"] == "2025-11-10"


def test_collect_forum_threads_multiple() -> None:
    """Test collecting metadata from multiple threads, sorted by activity."""
    import json
    import tempfile
    from pathlib import Path

    from scripts.generate_navigation import collect_forum_threads

    with tempfile.TemporaryDirectory() as tmpdir:
        forum_dir = Path(tmpdir) / "questions"
        forum_dir.mkdir()

        # Create thread 1 (older)
        thread1_dir = forum_dir / "old-thread"
        thread1_dir.mkdir()
        thread1_json = {
            "channel": {"name": "Old Thread"},
            "messages": [
                {"id": "1", "timestamp": "2025-01-15T10:00:00Z", "content": "msg1"},
            ],
        }
        (thread1_dir / "2025-01" / "2025-01.json").parent.mkdir(parents=True)
        with open(thread1_dir / "2025-01" / "2025-01.json", "w") as f:
            json.dump(thread1_json, f)

        # Create thread 2 (newer)
        thread2_dir = forum_dir / "new-thread"
        thread2_dir.mkdir()
        thread2_json = {
            "channel": {"name": "New Thread"},
            "messages": [
                {"id": "1", "timestamp": "2025-11-10T10:00:00Z", "content": "msg1"},
            ],
        }
        (thread2_dir / "2025-11" / "2025-11.json").parent.mkdir(parents=True)
        with open(thread2_dir / "2025-11" / "2025-11.json", "w") as f:
            json.dump(thread2_json, f)

        # Collect threads
        threads = collect_forum_threads(forum_dir)

        assert len(threads) == EXPECTED_THREAD_COUNT
        # Should be sorted by last_activity, newest first
        assert threads[0]["name"] == "new-thread"
        assert threads[0]["last_activity"] == "2025-11-10"
        assert threads[1]["name"] == "old-thread"
        assert threads[1]["last_activity"] == "2025-01-15"


def test_collect_forum_threads_empty_directory() -> None:
    """Test collecting threads from empty forum directory."""
    import tempfile
    from pathlib import Path

    from scripts.generate_navigation import collect_forum_threads

    with tempfile.TemporaryDirectory() as tmpdir:
        forum_dir = Path(tmpdir) / "questions"
        forum_dir.mkdir()

        threads = collect_forum_threads(forum_dir)

        assert threads == []
