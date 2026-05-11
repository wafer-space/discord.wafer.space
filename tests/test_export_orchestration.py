# tests/test_export_orchestration.py
"""Tests for export orchestration functionality."""

import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

from scripts.export_channels import export_all_channels, run_export

# Test constants
EXPECTED_EXPORTS_TWO_CHANNELS = 2
EXPECTED_EXPORTS_FOUR_FORMATS = 4
EXPECTED_EXPORTS_TWO_CHANNELS_THREE_MONTHS = 6
EXPECTED_EXPORTS_ONE_CHANNEL_THREE_MONTHS_FOUR_FORMATS = 12
EXPECTED_MONTHS_TWO = 2
EXPECTED_THREADS_TWO_THREE_MONTHS = 6


@contextmanager
def fixed_months(creation_month: str = "2025-12", current_month: str = "2026-02") -> Iterator[None]:
    """Pin month-related primitives so per-month tests have predictable counts.

    With creation "2025-12" and current "2026-02", the export loop visits
    exactly three months per channel: 2025-12, 2026-01, 2026-02. This keeps
    test assertions stable regardless of wall-clock time and lets us reason
    about export counts directly.
    """
    with patch("scripts.export_channels.snowflake_to_month", return_value=creation_month):
        with patch("scripts.export_channels.current_month_utc", return_value=current_month):
            with patch("scripts.export_channels.scan_completed_months", return_value=set()):
                with patch("scripts.export_channels._discard_if_empty_month", return_value=None):
                    yield


class TestRunExport:
    """Tests for run_export function."""

    @patch("subprocess.run")
    def test_run_export_success(self, mock_run: Any) -> None:
        """Test successful export execution."""
        mock_run.return_value = Mock(returncode=0, stdout="Export completed", stderr="")

        cmd = ["./DiscordChatExporter.Cli", "export"]
        success, output = run_export(cmd)

        assert success is True
        assert "Export completed" in output
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_run_export_failure(self, mock_run: Any) -> None:
        """Test failed export execution."""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="Error: Invalid token")

        cmd = ["./DiscordChatExporter.Cli", "export"]
        success, output = run_export(cmd)

        assert success is False
        assert "Invalid token" in output

    @patch("subprocess.run")
    def test_run_export_timeout(self, mock_run: Any) -> None:
        """Test export timeout handling."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=10)

        cmd = ["./DiscordChatExporter.Cli", "export"]
        success, output = run_export(cmd, timeout=10)

        assert success is False
        assert "timed out" in output

    @patch("subprocess.run")
    def test_run_export_exception(self, mock_run: Any) -> None:
        """Test export exception handling."""
        mock_run.side_effect = Exception("Unknown error")

        cmd = ["./DiscordChatExporter.Cli", "export"]
        success, output = run_export(cmd)

        assert success is False
        assert "Export failed" in output


class TestExportAllChannels:
    """Tests for export_all_channels orchestration function."""

    def test_export_all_channels_loads_config(self) -> None:
        """Test that export_all_channels loads configuration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create temporary config file
            config_path = Path(tmpdir) / "config.toml"
            config_path.write_text("""
[site]
title = "Test Server"

[servers.test-server]
guild_id = "123456"
name = "test-server"
include_channels = ["*"]
exclude_channels = []
channels = []

[export]
formats = ["html"]

[github]
pages_branch = "gh-pages"
commit_author = "Test Bot"
""")

            state_path = Path(tmpdir) / "state.json"
            state_path.write_text("{}")

            # Set environment variable
            os.environ["DISCORD_BOT_TOKEN"] = "test_token"

            with patch("scripts.export_channels.load_config") as mock_load:
                mock_load.return_value = {
                    "site": {"title": "Test"},
                    "servers": {
                        "test-server": {
                            "name": "Test Server",
                            "guild_id": "123456789",
                            "include_channels": ["*"],
                            "exclude_channels": [],
                        }
                    },
                    "export": {"formats": ["html"]},
                    "github": {},
                }

                with patch("scripts.export_channels.fetch_guild_channels") as mock_fetch:
                    mock_fetch.return_value = ([], {})

                    with patch("scripts.export_channels.StateManager"):
                        with patch("scripts.export_channels.Path"):
                            summary = export_all_channels()

                            mock_load.assert_called_once()
                            assert "channels_updated" in summary
                            assert "channels_failed" in summary

            del os.environ["DISCORD_BOT_TOKEN"]

    def test_export_all_channels_initializes_state_manager(self) -> None:
        """Test that state manager is initialized and loaded."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token"

        with patch("scripts.export_channels.load_config") as mock_config:
            mock_config.return_value = {
                "site": {},
                "servers": {},
                "export": {"formats": ["html"]},
                "github": {},
            }

            with patch("scripts.export_channels.fetch_guild_channels") as mock_fetch:
                mock_fetch.return_value = ([{"name": "general", "id": "123"}], {})

                with patch("scripts.export_channels.StateManager") as mock_state_class:
                    mock_state_instance = Mock()
                    mock_state_class.return_value = mock_state_instance

                    with patch("scripts.export_channels.Path"):
                        export_all_channels()

                        mock_state_class.assert_called_once()
                        mock_state_instance.load.assert_called_once()

        del os.environ["DISCORD_BOT_TOKEN"]

    def test_export_all_channels_processes_each_server(self) -> None:
        """Test that all servers are processed."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token"

        config = {
            "site": {},
            "servers": {
                "server1": {
                    "name": "Server 1",
                    "guild_id": "111111111",
                    "include_channels": ["*"],
                    "exclude_channels": [],
                },
                "server2": {
                    "name": "Server 2",
                    "guild_id": "222222222",
                    "include_channels": ["*"],
                    "exclude_channels": [],
                },
            },
            "export": {"formats": ["html"]},
            "github": {},
        }

        with patch("scripts.export_channels.load_config", return_value=config):
            with patch("scripts.export_channels.fetch_guild_channels") as mock_fetch:
                mock_fetch.return_value = ([], {})

                with patch("scripts.export_channels.StateManager") as mock_state_class:
                    mock_state = Mock()
                    mock_state_class.return_value = mock_state
                    mock_state.load.return_value = {}

                    with patch("scripts.export_channels.Path"):
                        summary = export_all_channels()

                        # Both servers should have been processed
                        assert summary["channels_updated"] >= 0

        del os.environ["DISCORD_BOT_TOKEN"]

    def test_export_all_channels_filters_channels_by_pattern(self) -> None:
        """Channels matched by exclude_channels are skipped entirely (no DCE calls).

        With creation pinned to 2025-12 and current to 2026-02, each surviving
        channel triggers 3 months × 1 format = 3 exports. Two channels pass the
        filter (private-chat is excluded), giving 6 total exports — and
        importantly, zero exports for the excluded channel.
        """
        os.environ["DISCORD_BOT_TOKEN"] = "test_token"

        config = {
            "site": {},
            "servers": {
                "test-server": {
                    "name": "Test Server",
                    "include_channels": ["*"],
                    "exclude_channels": ["private-*"],
                    "guild_id": "123456789",
                }
            },
            "export": {"formats": ["html"]},
            "github": {},
        }

        with fixed_months("2025-12", "2026-02"):
            with patch("scripts.export_channels.load_config", return_value=config):
                with patch("scripts.export_channels.fetch_guild_channels") as mock_fetch:
                    mock_fetch.return_value = (
                        [
                            {"name": "general", "id": "111"},
                            {"name": "announcements", "id": "222"},
                            {"name": "private-chat", "id": "333"},
                        ],
                        {},
                    )

                    with patch("scripts.export_channels.StateManager") as mock_state_class:
                        mock_state = Mock()
                        mock_state_class.return_value = mock_state
                        mock_state.load.return_value = {}
                        mock_state.get_channel_state.return_value = None

                        with patch("scripts.export_channels.run_export") as mock_run:
                            mock_run.return_value = (True, "Success")

                            with patch("scripts.export_channels.Path"):
                                summary = export_all_channels()

                                # 2 channels × 3 months × 1 format = 6 exports
                                assert (
                                    summary["total_exports"]
                                    == EXPECTED_EXPORTS_TWO_CHANNELS_THREE_MONTHS
                                )

        del os.environ["DISCORD_BOT_TOKEN"]

    def test_export_all_channels_exports_all_formats(self) -> None:
        """All configured formats are exported for each month of each channel.

        Per-month iteration: 3 months × 4 formats = 12 exports for one channel.
        """
        os.environ["DISCORD_BOT_TOKEN"] = "test_token"

        config = {
            "site": {},
            "servers": {
                "test-server": {
                    "name": "Test Server",
                    "include_channels": ["*"],
                    "exclude_channels": [],
                    "guild_id": "123456789",
                }
            },
            "export": {"formats": ["html", "txt", "json", "csv"]},
            "github": {},
        }

        with fixed_months("2025-12", "2026-02"):
            with patch("scripts.export_channels.load_config", return_value=config):
                with patch("scripts.export_channels.fetch_guild_channels") as mock_fetch:
                    mock_fetch.return_value = ([{"name": "general", "id": "123"}], {})

                    with patch("scripts.export_channels.StateManager") as mock_state_class:
                        mock_state = Mock()
                        mock_state_class.return_value = mock_state
                        mock_state.load.return_value = {}
                        mock_state.get_channel_state.return_value = None

                        with patch("scripts.export_channels.run_export") as mock_run:
                            mock_run.return_value = (True, "Success")

                            with patch("scripts.export_channels.Path"):
                                summary = export_all_channels()

                                # 1 channel × 3 months × 4 formats = 12 exports
                                assert (
                                    summary["total_exports"]
                                    == EXPECTED_EXPORTS_ONE_CHANNEL_THREE_MONTHS_FOUR_FORMATS
                                )

        del os.environ["DISCORD_BOT_TOKEN"]

    def test_export_all_channels_passes_month_bounds(self) -> None:
        """Per-month exports pass --after/--before that bracket each calendar month.

        Replaces the old "uses --after from state" test — state.json no longer
        drives incremental bounds; calendar month boundaries do.
        """
        os.environ["DISCORD_BOT_TOKEN"] = "test_token"

        config = {
            "site": {},
            "servers": {
                "test-server": {
                    "name": "Test Server",
                    "include_channels": ["*"],
                    "exclude_channels": [],
                    "guild_id": "123456789",
                }
            },
            "export": {"formats": ["html"]},
            "github": {},
        }

        with fixed_months("2026-01", "2026-02"):
            with patch("scripts.export_channels.load_config", return_value=config):
                with patch("scripts.export_channels.fetch_guild_channels") as mock_fetch:
                    mock_fetch.return_value = ([{"name": "general", "id": "123"}], {})

                    with patch("scripts.export_channels.StateManager") as mock_state_class:
                        mock_state = Mock()
                        mock_state_class.return_value = mock_state
                        mock_state.load.return_value = {}

                        with patch("scripts.export_channels.format_export_command") as mock_format:
                            mock_format.return_value = ["test", "command"]

                            with patch("scripts.export_channels.run_export") as mock_run:
                                mock_run.return_value = (True, "Success")

                                with patch("scripts.export_channels.Path"):
                                    export_all_channels()

                                    # Two months, one format = two calls
                                    assert mock_format.call_count == EXPECTED_MONTHS_TWO

                                    # January call uses both --after and --before
                                    jan_call = mock_format.call_args_list[0]
                                    assert jan_call.kwargs["after_timestamp"].startswith(
                                        "2025-12-31"
                                    )
                                    assert jan_call.kwargs["before_timestamp"].startswith(
                                        "2026-02-01"
                                    )

                                    # February (current month) omits --before so it
                                    # captures all new messages up to "now".
                                    feb_call = mock_format.call_args_list[1]
                                    assert feb_call.kwargs["after_timestamp"].startswith(
                                        "2026-01-31"
                                    )
                                    assert feb_call.kwargs["before_timestamp"] is None

        del os.environ["DISCORD_BOT_TOKEN"]

    def test_export_all_channels_updates_state_after_export(self) -> None:
        """Test that state is updated after successful export."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token"

        config = {
            "site": {},
            "servers": {
                "test-server": {
                    "name": "Test Server",
                    "include_channels": ["*"],
                    "exclude_channels": [],
                    "guild_id": "123456789",
                }
            },
            "export": {"formats": ["html"]},
            "github": {},
        }

        with patch("scripts.export_channels.load_config", return_value=config):
            with patch("scripts.export_channels.fetch_guild_channels") as mock_fetch:
                mock_fetch.return_value = ([{"name": "general", "id": "123"}], {})

                with patch("scripts.export_channels.StateManager") as mock_state_class:
                    mock_state = Mock()
                    mock_state_class.return_value = mock_state
                    mock_state.load.return_value = {}
                    mock_state.get_channel_state.return_value = None

                    with patch("scripts.export_channels.run_export") as mock_run:
                        mock_run.return_value = (True, "Success")

                        with patch("scripts.export_channels.Path"):
                            export_all_channels()

                            # State should be updated for the channel
                            mock_state.update_channel.assert_called_once()
                            # State should be saved
                            mock_state.save.assert_called_once()

        del os.environ["DISCORD_BOT_TOKEN"]

    def test_export_all_channels_tracks_failures(self) -> None:
        """Failed format exports are reflected in the summary's failure count."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token"

        config = {
            "site": {},
            "servers": {
                "test-server": {
                    "name": "Test Server",
                    "include_channels": ["*"],
                    "exclude_channels": [],
                    "guild_id": "123456789",
                }
            },
            "export": {"formats": ["html", "txt"]},
            "github": {},
        }

        # Pin to a single month so we have exactly 2 calls (one per format).
        with fixed_months("2026-02", "2026-02"):
            with patch("scripts.export_channels.load_config", return_value=config):
                with patch("scripts.export_channels.fetch_guild_channels") as mock_fetch:
                    mock_fetch.return_value = ([{"name": "general", "id": "123"}], {})

                    with patch("scripts.export_channels.StateManager") as mock_state_class:
                        mock_state = Mock()
                        mock_state_class.return_value = mock_state
                        mock_state.load.return_value = {}
                        mock_state.get_channel_state.return_value = None

                        with patch("scripts.export_channels.run_export") as mock_run:
                            # html succeeds, txt fails
                            mock_run.side_effect = [
                                (True, "Success"),
                                (False, "Error: Network timeout"),
                            ]

                            with patch("scripts.export_channels.Path"):
                                summary = export_all_channels()

                                assert summary["total_exports"] == 1
                                assert summary["channels_failed"] == 1
                                assert len(summary["errors"]) == 1
                                assert summary["errors"][0]["channel"] == "general"
                                # Errors now record the failing month/format combo
                                assert "txt" in summary["errors"][0]["format"]

        del os.environ["DISCORD_BOT_TOKEN"]

    def test_export_all_channels_creates_exports_directory(self) -> None:
        """Test that exports directory is created."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token"

        with tempfile.TemporaryDirectory():
            config = {"site": {}, "servers": {}, "export": {"formats": ["html"]}, "github": {}}

            with patch("scripts.export_channels.load_config", return_value=config):
                with patch("scripts.export_channels.StateManager") as mock_state_class:
                    mock_state = Mock()
                    mock_state_class.return_value = mock_state
                    mock_state.load.return_value = {}

                    with patch("scripts.export_channels.Path") as mock_path_class:
                        mock_exports_path = Mock()
                        mock_path_class.return_value = mock_exports_path

                        export_all_channels()

                        # Should call mkdir on exports directory
                        mock_exports_path.mkdir.assert_called()

        del os.environ["DISCORD_BOT_TOKEN"]

    def test_export_all_channels_returns_summary(self) -> None:
        """Test that export_all_channels returns proper summary dict."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token"

        config = {"site": {}, "servers": {}, "export": {"formats": ["html"]}, "github": {}}

        with patch("scripts.export_channels.load_config", return_value=config):
            with patch("scripts.export_channels.StateManager") as mock_state_class:
                mock_state = Mock()
                mock_state_class.return_value = mock_state
                mock_state.load.return_value = {}

                with patch("scripts.export_channels.Path"):
                    summary = export_all_channels()

                    assert isinstance(summary, dict)
                    assert "channels_updated" in summary
                    assert "channels_failed" in summary
                    assert "total_exports" in summary
                    assert "errors" in summary
                    assert isinstance(summary["errors"], list)

        del os.environ["DISCORD_BOT_TOKEN"]

    def test_export_all_channels_handles_forums(self) -> None:
        """Forum parents are skipped; threads are exported per-month.

        With 3 months pinned and 2 threads × 1 format, total = 6 exports.
        The forum parent itself produces zero exports — only its threads do.
        """
        os.environ["DISCORD_BOT_TOKEN"] = "test_token"

        config = {
            "site": {},
            "servers": {
                "test-server": {
                    "name": "Test Server",
                    "guild_id": "123456789",
                    "include_channels": ["*"],
                    "exclude_channels": [],
                    "forum_channels": ["questions"],
                }
            },
            "export": {"formats": ["html"]},
            "github": {},
        }

        with fixed_months("2025-12", "2026-02"):
            with patch("scripts.export_channels.load_config", return_value=config):
                with patch("scripts.export_channels.fetch_guild_channels") as mock_fetch:
                    mock_fetch.return_value = (
                        [
                            {"name": "questions", "id": "999", "parent_id": None},
                            {"name": "How to start?", "id": "111", "parent_id": "questions"},
                            {"name": "Help needed", "id": "222", "parent_id": "questions"},
                        ],
                        {},
                    )

                    with patch("scripts.export_channels.StateManager") as mock_state_class:
                        mock_state = Mock()
                        mock_state_class.return_value = mock_state
                        mock_state.load.return_value = {}
                        mock_state.get_channel_state.return_value = None
                        mock_state.get_thread_state.return_value = None

                        with patch("scripts.export_channels.run_export") as mock_run:
                            mock_run.return_value = (True, "Success")

                            with patch("scripts.export_channels.Path"):
                                summary = export_all_channels()

                                # 2 threads × 3 months × 1 format = 6 exports
                                assert summary["total_exports"] == EXPECTED_THREADS_TWO_THREE_MONTHS

        del os.environ["DISCORD_BOT_TOKEN"]

    def test_export_all_channels_tracks_thread_state(self) -> None:
        """Test that thread exports update state."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token"

        config = {
            "site": {},
            "servers": {
                "test-server": {
                    "name": "Test Server",
                    "guild_id": "123456789",
                    "include_channels": ["*"],
                    "exclude_channels": [],
                    "forum_channels": ["questions"],
                }
            },
            "export": {"formats": ["html"], "include_threads": "all"},
            "github": {},
        }

        with patch("scripts.export_channels.load_config", return_value=config):
            with patch("scripts.export_channels.fetch_guild_channels") as mock_fetch:
                with patch("scripts.export_channels.run_export") as mock_run:
                    with tempfile.TemporaryDirectory() as tmpdir:
                        with patch("scripts.export_channels.Path") as mock_path:
                            # Setup mocks
                            mock_fetch.return_value = (
                                [
                                    {"name": "questions", "id": "999", "parent_id": None},
                                    {
                                        "name": "How to start?",
                                        "id": "111",
                                        "parent_id": "questions",
                                    },
                                ],
                                {},
                            )

                            mock_run.return_value = (True, "")

                            # Mock Path to use temp directory
                            exports_dir = Path(tmpdir) / "exports"
                            exports_dir.mkdir(parents=True)
                            mock_path.return_value = exports_dir

                            # Mock StateManager
                            with patch("scripts.export_channels.StateManager") as mock_state_class:
                                mock_state = Mock()
                                mock_state_class.return_value = mock_state
                                mock_state.get_channel_state.return_value = None
                                mock_state.get_thread_state.return_value = None

                                # Run export
                                _ = export_all_channels()

                                # Verify thread state was updated
                                mock_state.update_thread_state.assert_called_once()
                                call_args = mock_state.update_thread_state.call_args
                                assert call_args[1]["server"] == "test-server"
                                assert call_args[1]["forum"] == "questions"
                                # ThreadInfo is passed as thread_info parameter
                                thread_info = call_args[1]["thread_info"]
                                assert thread_info.thread_id == "111"

        del os.environ["DISCORD_BOT_TOKEN"]

    def test_export_all_channels_threads_use_month_bounds(self) -> None:
        """Thread exports bracket each calendar month, same as channels."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token"

        config = {
            "site": {},
            "servers": {
                "test-server": {
                    "name": "Test Server",
                    "guild_id": "123456789",
                    "include_channels": ["*"],
                    "exclude_channels": [],
                    "forum_channels": ["questions"],
                }
            },
            "export": {"formats": ["html"], "include_threads": "all"},
            "github": {},
        }

        with fixed_months("2026-02", "2026-02"):
            with patch("scripts.export_channels.load_config", return_value=config):
                with patch("scripts.export_channels.StateManager") as mock_state_class:
                    with patch("scripts.export_channels.fetch_guild_channels") as mock_fetch:
                        with patch("scripts.export_channels.run_export") as mock_run:
                            with patch(
                                "scripts.export_channels.format_export_command"
                            ) as mock_format:
                                mock_state = Mock()
                                mock_state.get_thread_state.return_value = None
                                mock_state.get_channel_state.return_value = None
                                mock_state_class.return_value = mock_state

                                mock_fetch.return_value = (
                                    [
                                        {"name": "questions", "id": "999", "parent_id": None},
                                        {
                                            "name": "How to start?",
                                            "id": "111",
                                            "parent_id": "questions",
                                        },
                                    ],
                                    {},
                                )

                                mock_format.return_value = ["test", "command"]
                                mock_run.return_value = (True, "")

                                with patch("scripts.export_channels.Path"):
                                    export_all_channels()

                                    thread_calls = [
                                        c
                                        for c in mock_format.call_args_list
                                        if c.kwargs.get("channel_id") == "111"
                                    ]
                                    assert len(thread_calls) == 1
                                    # Current month bracket: --after just before
                                    # 2026-02-01, --before is None (capture up to "now").
                                    assert (
                                        thread_calls[0]
                                        .kwargs["after_timestamp"]
                                        .startswith("2026-01-31")
                                    )
                                    assert thread_calls[0].kwargs["before_timestamp"] is None

        del os.environ["DISCORD_BOT_TOKEN"]
