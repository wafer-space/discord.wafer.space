# tests/test_generate_navigation_main.py
"""Tests for navigation generation main orchestration function."""

import tempfile
from pathlib import Path

import pytest

from scripts.generate_navigation import main, organize_data

# Test constants
EXPECTED_ARCHIVE_COUNT_TWO = 2
EXPECTED_ARCHIVE_COUNT_ONE = 1
EXPECTED_MESSAGE_COUNT_FIVE = 5


def test_organize_data_groups_by_server_and_channel() -> None:
    """Test that organize_data groups exports by server and channel"""
    exports = [
        {
            "server": "server1",
            "channel": "general",
            "date": "2025-01",
            "path": "server1/general/2025-01.html",
        },
        {
            "server": "server1",
            "channel": "general",
            "date": "2025-02",
            "path": "server1/general/2025-02.html",
        },
        {
            "server": "server1",
            "channel": "chat",
            "date": "2025-01",
            "path": "server1/chat/2025-01.html",
        },
        {
            "server": "server2",
            "channel": "announcements",
            "date": "2025-01",
            "path": "server2/announcements/2025-01.html",
        },
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        public_dir = Path(tmpdir) / "public"
        public_dir.mkdir()

        # Create dummy JSON files for message counting
        for export in exports:
            json_path = public_dir / export["server"] / export["channel"] / f"{export['date']}.json"
            json_path.parent.mkdir(parents=True, exist_ok=True)
            with open(json_path, "w") as f:
                for i in range(5):  # 5 messages per file
                    f.write(f'{{"id": "{i}", "content": "test"}}\n')

        servers_data = organize_data(exports, public_dir)

        # Verify structure
        assert "server1" in servers_data
        assert "server2" in servers_data
        assert "general" in servers_data["server1"]["channels"]
        assert "chat" in servers_data["server1"]["channels"]
        assert "announcements" in servers_data["server2"]["channels"]

        # Verify archives
        general_archives = servers_data["server1"]["channels"]["general"]["archives"]
        assert len(general_archives) == EXPECTED_ARCHIVE_COUNT_TWO
        assert len(servers_data["server1"]["channels"]["chat"]["archives"]) == 1

        # Verify message counts
        assert general_archives[0]["message_count"] == EXPECTED_MESSAGE_COUNT_FIVE


def test_organize_data_calculates_stats() -> None:
    """Test that organize_data calculates channel and server stats"""
    exports = [
        {
            "server": "server1",
            "channel": "general",
            "date": "2025-01",
            "path": "server1/general/2025-01.html",
        },
        {
            "server": "server1",
            "channel": "chat",
            "date": "2025-01",
            "path": "server1/chat/2025-01.html",
        },
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        public_dir = Path(tmpdir) / "public"
        public_dir.mkdir()

        # Create dummy JSON files
        for export in exports:
            json_path = public_dir / export["server"] / export["channel"] / f"{export['date']}.json"
            json_path.parent.mkdir(parents=True, exist_ok=True)
            with open(json_path, "w") as f:
                f.write('{"id": "1", "content": "test"}\n')

        servers_data = organize_data(exports, public_dir)

        # Verify stats
        assert servers_data["server1"]["channel_count"] == EXPECTED_ARCHIVE_COUNT_TWO
        assert "last_updated" in servers_data["server1"]
        assert servers_data["server1"]["channels"]["general"]["archive_count"] == 1
        assert servers_data["server1"]["channels"]["general"]["message_count"] == 1


def test_organize_data_sorts_archives() -> None:
    """Test that organize_data sorts archives reverse chronologically"""
    exports = [
        {
            "server": "server1",
            "channel": "general",
            "date": "2025-01",
            "path": "server1/general/2025-01.html",
        },
        {
            "server": "server1",
            "channel": "general",
            "date": "2025-03",
            "path": "server1/general/2025-03.html",
        },
        {
            "server": "server1",
            "channel": "general",
            "date": "2025-02",
            "path": "server1/general/2025-02.html",
        },
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        public_dir = Path(tmpdir) / "public"
        public_dir.mkdir()

        # Create dummy JSON files
        for export in exports:
            json_path = public_dir / export["server"] / export["channel"] / f"{export['date']}.json"
            json_path.parent.mkdir(parents=True, exist_ok=True)
            with open(json_path, "w") as f:
                f.write('{"id": "1", "content": "test"}\n')

        servers_data = organize_data(exports, public_dir)

        archives = servers_data["server1"]["channels"]["general"]["archives"]
        # Should be sorted newest first: 2025-03, 2025-02, 2025-01
        assert archives[0]["date"] == "2025-03"
        assert archives[1]["date"] == "2025-02"
        assert archives[2]["date"] == "2025-01"


def test_organize_data_handles_empty_exports() -> None:
    """Test that organize_data handles empty exports list"""
    with tempfile.TemporaryDirectory() as tmpdir:
        public_dir = Path(tmpdir) / "public"
        public_dir.mkdir()

        servers_data = organize_data([], public_dir)

        assert servers_data == {}


def test_organize_data_uses_display_names() -> None:
    """Test that organize_data creates display names from server names"""
    exports = [
        {
            "server": "wafer-space",
            "channel": "general",
            "date": "2025-01",
            "path": "wafer-space/general/2025-01.html",
        },
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        public_dir = Path(tmpdir) / "public"
        public_dir.mkdir()

        # Create dummy JSON file
        json_path = public_dir / "wafer-space" / "general" / "2025-01.json"
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text('{"id": "1", "content": "test"}\n')

        servers_data = organize_data(exports, public_dir)

        # Should convert wafer-space to Wafer Space
        assert servers_data["wafer-space"]["display_name"] == "Wafer Space"


def test_main_integration(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test main function integration (without actual file generation)"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Change to temp directory for testing
        monkeypatch.chdir(tmpdir)

        # Create directory structure
        public_dir = Path(tmpdir) / "public"
        templates_dir = Path(tmpdir) / "templates"
        public_dir.mkdir()
        templates_dir.mkdir()

        # Create config file
        config_path = Path(tmpdir) / "config.toml"
        config_path.write_text("""
[site]
title = "Test Discord Logs"
description = "Test description"
base_url = "https://test.example.com"
""")

        # Create test export files
        server_dir = public_dir / "test-server" / "general"
        server_dir.mkdir(parents=True)
        (server_dir / "2025-01.html").touch()
        json_path = server_dir / "2025-01.json"
        json_path.write_text('{"id": "1", "content": "test"}\n')

        # Create minimal templates
        site_template = templates_dir / "site_index.html.j2"
        site_template.write_text("<html><body>{{ site.title }}</body></html>")

        server_template = templates_dir / "server_index.html.j2"
        server_template.write_text("<html><body>{{ server.display_name }}</body></html>")

        channel_template = templates_dir / "channel_index.html.j2"
        channel_template.write_text("<html><body>#{{ channel.name }}</body></html>")

        # Run main function
        main()

        # Verify output
        captured = capsys.readouterr()
        assert "Generating navigation pages" in captured.out
        assert "Scanning exports" in captured.out
        assert "Generating site index" in captured.out


def test_main_exits_if_no_public_directory(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test that main exits gracefully if public/ doesn't exist"""
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.chdir(tmpdir)

        # Create config file
        config_path = Path(tmpdir) / "config.toml"
        config_path.write_text("""
[site]
title = "Test"
description = "Test"
base_url = "https://test.com"
""")

        # Don't create public directory

        with pytest.raises(SystemExit) as excinfo:
            main()

        assert excinfo.value.code == 1
        captured = capsys.readouterr()
        assert "ERROR: public/ directory not found" in captured.out


def test_main_handles_no_exports_gracefully(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test that main handles case with no exports gracefully"""
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.chdir(tmpdir)

        # Create empty public directory
        public_dir = Path(tmpdir) / "public"
        public_dir.mkdir()

        # Create config
        config_path = Path(tmpdir) / "config.toml"
        config_path.write_text("""
[site]
title = "Test"
description = "Test"
base_url = "https://test.com"
""")

        # Run main
        main()

        captured = capsys.readouterr()
        assert "WARNING: No exports found" in captured.out


def test_main_with_error_handling(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test that main handles errors with proper error messages"""
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.chdir(tmpdir)

        # Create public dir but no config
        public_dir = Path(tmpdir) / "public"
        public_dir.mkdir()

        # Run main - should fail with missing config
        with pytest.raises(SystemExit) as excinfo:
            main()

        assert excinfo.value.code == 1
        captured = capsys.readouterr()
        assert "FATAL ERROR" in captured.out
