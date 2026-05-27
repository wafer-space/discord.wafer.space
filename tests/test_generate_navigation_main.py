# tests/test_generate_navigation_main.py
"""Tests for navigation generation main orchestration function."""

import json
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

        # Create dummy JSON files for message counting — files live inside
        # the YYYY-MM directory under the channel, matching the per-month layout.
        for export in exports:
            json_path = (
                public_dir
                / export["server"]
                / export["channel"]
                / export["date"]
                / f"{export['date']}.json"
            )
            json_path.parent.mkdir(parents=True, exist_ok=True)
            with open(json_path, "w") as f:
                sample_data = {
                    "guild": {"id": "123", "name": "Test"},
                    "channel": {"id": "456", "name": export["channel"]},
                    "messages": [{"id": str(i), "content": "test"} for i in range(5)],
                }
                json.dump(sample_data, f)

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

        # Create dummy JSON files inside per-month directories
        for export in exports:
            json_path = (
                public_dir
                / export["server"]
                / export["channel"]
                / export["date"]
                / f"{export['date']}.json"
            )
            json_path.parent.mkdir(parents=True, exist_ok=True)
            with open(json_path, "w") as f:
                sample_data = {
                    "guild": {"id": "123", "name": "Test"},
                    "channel": {"id": "456", "name": export["channel"]},
                    "messages": [{"id": "1", "content": "test"}],
                }
                json.dump(sample_data, f)

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

        # Create dummy JSON files inside per-month directories
        for export in exports:
            json_path = (
                public_dir
                / export["server"]
                / export["channel"]
                / export["date"]
                / f"{export['date']}.json"
            )
            json_path.parent.mkdir(parents=True, exist_ok=True)
            with open(json_path, "w") as f:
                f.write('{"id": "1", "content": "test"}\n')

        servers_data = organize_data(exports, public_dir)

        archives = servers_data["server1"]["channels"]["general"]["archives"]
        # Should be sorted newest first: 2025-03, 2025-02, 2025-01
        assert archives[0]["date"] == "2025-03"
        assert archives[1]["date"] == "2025-02"
        assert archives[2]["date"] == "2025-01"


def _write_json(public_dir: Path, rel: str, channel_name: str, n_msgs: int) -> None:
    """Write a DCE-style month JSON at public_dir/<rel>/<rel last seg date>.json."""
    p = public_dir / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(
            {
                "guild": {"id": "1", "name": "T"},
                "channel": {"id": "2", "name": channel_name},
                "messages": [
                    {"id": str(i), "timestamp": "2026-04-02T00:00:00+00:00"} for i in range(n_msgs)
                ],
            }
        )
    )


def test_organize_data_nests_threads_under_parent_channel() -> None:
    """A 3-segment path whose parent is itself an exported channel is a THREAD.

    It must be nested under its parent channel — NOT listed as its own
    top-level channel. This is the core fix: threads appearing as channels.
    """
    exports = [
        {
            "server": "wafer-space",
            "channel": "Information/announcements",
            "date": "2026-04",
            "path": "wafer-space/Information/announcements/2026-04/2026-04.html",
        },
        {
            "server": "wafer-space",
            "channel": "Information/announcements/can-one-join",
            "date": "2026-04",
            "path": ("wafer-space/Information/announcements/can-one-join/2026-04/2026-04.html"),
        },
    ]

    with tempfile.TemporaryDirectory() as tmpdir:
        public_dir = Path(tmpdir) / "public"
        public_dir.mkdir()
        _write_json(
            public_dir,
            "wafer-space/Information/announcements/2026-04/2026-04.json",
            "announcements",
            4,
        )
        _write_json(
            public_dir,
            "wafer-space/Information/announcements/can-one-join/2026-04/2026-04.json",
            "Can one join even if I wasn't part of?",
            7,
        )

        servers_data = organize_data(exports, public_dir)
        channels = servers_data["wafer-space"]["channels"]

        # The channel is present; the thread path is NOT a top-level channel.
        assert "Information/announcements" in channels
        assert "Information/announcements/can-one-join" not in channels
        # channel_count counts real channels only (the thread doesn't count).
        assert servers_data["wafer-space"]["channel_count"] == EXPECTED_ARCHIVE_COUNT_ONE

        chan = channels["Information/announcements"]
        assert len(chan["threads"]) == EXPECTED_ARCHIVE_COUNT_ONE
        thread = chan["threads"][0]
        # Thread carries a human title (from JSON channel.name), a URL-safe
        # slug, its full path, and its own archives.
        assert thread["title"] == "Can one join even if I wasn't part of?"
        assert thread["name"] == "can-one-join"
        assert thread["path"] == "Information/announcements/can-one-join"
        assert thread["total_messages"] == 7  # noqa: PLR2004
        assert thread["archives"][0]["date"] == "2026-04"


def test_organize_data_nests_threads_under_forum_with_no_own_export() -> None:
    """A FORUM channel has no month export of its own — only its threads do.

    This is the real-data case that the parent-must-be-an-exported-path rule
    missed: `Information/questions` (a forum) has zero direct exports, so its
    68 threads were wrongly rendered as top-level channels. The forum entry
    must be SYNTHESIZED so threads nest under it, and the forum itself must
    never appear nested as a thread, nor the category as a channel.
    """
    exports = [
        {
            "server": "wafer-space",
            "channel": "Information/general",
            "date": "2026-04",
            "path": "wafer-space/Information/general/2026-04/2026-04.html",
        },
        {
            "server": "wafer-space",
            "channel": "Information/questions/antenna-error",
            "date": "2026-04",
            "path": "wafer-space/Information/questions/antenna-error/2026-04/2026-04.html",
        },
        {
            "server": "wafer-space",
            "channel": "Information/questions/cadence-pdk",
            "date": "2026-03",
            "path": "wafer-space/Information/questions/cadence-pdk/2026-03/2026-03.html",
        },
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        public_dir = Path(tmpdir) / "public"
        public_dir.mkdir()
        _write_json(
            public_dir, "wafer-space/Information/general/2026-04/2026-04.json", "general", 5
        )
        _write_json(
            public_dir,
            "wafer-space/Information/questions/antenna-error/2026-04/2026-04.json",
            "Antenna error on M3",
            9,
        )
        _write_json(
            public_dir,
            "wafer-space/Information/questions/cadence-pdk/2026-03/2026-03.json",
            "Cadence PDK access",
            4,
        )

        servers_data = organize_data(exports, public_dir)
        channels = servers_data["wafer-space"]["channels"]

        # The forum is a synthesized top-level entry; its threads are NOT.
        assert "Information/questions" in channels
        assert "Information/questions/antenna-error" not in channels
        assert "Information/questions/cadence-pdk" not in channels
        # The category itself is never a channel.
        assert "Information" not in channels
        # Real top-level entries: the regular channel + the forum (threads excluded).
        assert servers_data["wafer-space"]["channel_count"] == EXPECTED_ARCHIVE_COUNT_TWO

        forum = channels["Information/questions"]
        assert forum["total_messages"] == 0  # forum has no messages of its own
        assert forum["display_name"] == "questions"
        assert forum["category"] == "Information"
        assert {t["name"] for t in forum["threads"]} == {"antenna-error", "cadence-pdk"}
        # Threads keep their human titles and nest with their own message counts.
        titles = {t["title"] for t in forum["threads"]}
        assert titles == {"Antenna error on M3", "Cadence PDK access"}


def test_organize_data_channel_without_threads_has_empty_thread_list() -> None:
    """A plain channel (no nested threads) still exposes an empty threads list."""
    exports = [
        {
            "server": "s",
            "channel": "general",
            "date": "2026-04",
            "path": "s/general/2026-04/2026-04.html",
        },
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        public_dir = Path(tmpdir) / "public"
        public_dir.mkdir()
        _write_json(public_dir, "s/general/2026-04/2026-04.json", "general", 3)

        servers_data = organize_data(exports, public_dir)
        chan = servers_data["s"]["channels"]["general"]
        assert chan["threads"] == []
        assert chan["total_messages"] == 3  # noqa: PLR2004


def test_organize_data_channel_display_name_is_leaf_not_full_path() -> None:
    """A channel nested under a category keeps the full path as its URL key
    (`name`) but exposes a `display_name` of just the leaf segment and a
    `category` of the parent. Without this the UI renders "#Information/general"
    instead of "#general"."""
    exports = [
        {
            "server": "wafer-space",
            "channel": "Information/general",
            "date": "2026-04",
            "path": "wafer-space/Information/general/2026-04/2026-04.html",
        },
        {
            "server": "wafer-space",
            "channel": "welcome",
            "date": "2026-04",
            "path": "wafer-space/welcome/2026-04/2026-04.html",
        },
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        public_dir = Path(tmpdir) / "public"
        public_dir.mkdir()
        _write_json(
            public_dir, "wafer-space/Information/general/2026-04/2026-04.json", "general", 2
        )
        _write_json(public_dir, "wafer-space/welcome/2026-04/2026-04.json", "welcome", 1)

        channels = organize_data(exports, public_dir)["wafer-space"]["channels"]

        nested = channels["Information/general"]
        assert nested["name"] == "Information/general"  # URL key keeps full path
        assert nested["display_name"] == "general"  # what the UI shows
        assert nested["category"] == "Information"

        top = channels["welcome"]
        assert top["display_name"] == "welcome"
        assert top["category"] == ""


def test_copy_static_assets_emits_versioned_stylesheet() -> None:
    """copy_static_assets writes the version-controlled stylesheet into
    public/assets/. The deploy does `rm -rf public` then checks out gh-pages,
    so a stylesheet committed under public/ never ships; emitting it from a
    source outside public/ during the build is what gets it deployed. The
    emitted CSS must include the rules for the navigation's own classes."""
    from scripts.generate_navigation import copy_static_assets

    with tempfile.TemporaryDirectory() as tmpdir:
        public_dir = Path(tmpdir) / "public"
        public_dir.mkdir()

        copy_static_assets(public_dir)

        css = public_dir / "assets" / "style.css"
        assert css.exists()
        text = css.read_text()
        assert ".category" in text
        assert ".thread-list" in text


def test_copy_static_assets_never_raises_when_dest_unwritable(tmp_path: Path) -> None:
    """A copy failure must NOT abort navigation/deploy — it is swallowed.

    We point public_dir at a path whose `assets` is a regular file, so mkdir
    fails; the function must warn and return rather than raise."""
    from scripts.generate_navigation import copy_static_assets

    public_dir = tmp_path / "public"
    public_dir.mkdir()
    (public_dir / "assets").write_text("not a directory")  # blocks mkdir

    copy_static_assets(public_dir)  # must not raise


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

        # Create test export files with month directory structure
        month_dir = public_dir / "test-server" / "general" / "2025-01"
        month_dir.mkdir(parents=True)
        (month_dir / "2025-01.html").touch()
        json_path = month_dir / "2025-01.json"
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
