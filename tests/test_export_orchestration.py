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
TIME_BUDGET_TOTAL_CHANNELS = 3


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

                                    # Current month (February) is processed FIRST,
                                    # with --after at the January boundary and no
                                    # --before so it captures messages up to "now".
                                    feb_call = mock_format.call_args_list[0]
                                    assert feb_call.kwargs["after_timestamp"].startswith(
                                        "2026-01-31"
                                    )
                                    assert feb_call.kwargs["before_timestamp"] is None

                                    # January backfill comes after, fully bracketed.
                                    jan_call = mock_format.call_args_list[1]
                                    assert jan_call.kwargs["after_timestamp"].startswith(
                                        "2025-12-31"
                                    )
                                    assert jan_call.kwargs["before_timestamp"].startswith(
                                        "2026-02-01"
                                    )

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

    def test_current_month_done_for_all_channels_before_any_backfill(self) -> None:
        """Phase 1 exports the current month for EVERY channel before Phase 2
        backfills ANY history.

        This is the anti-starvation guarantee: a channel late in the listing
        must still get its latest messages even if earlier channels have huge
        backfills. We assert the global ordering of DCE invocations: every
        channel's current-month export precedes every backfill export.
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

        # creation 2025-12, current 2026-02 → per channel: current=2026-02,
        # backfill=[2025-12, 2026-01]. Three channels.
        observed_months: list[str] = []

        def fake_format(**kwargs: object) -> list[str]:
            before = kwargs.get("before_timestamp")
            # Current month = the call with no --before (open-ended).
            observed_months.append("current" if before is None else "backfill")
            return ["dce", "stub"]

        with fixed_months("2025-12", "2026-02"):
            with patch("scripts.export_channels.load_config", return_value=config):
                with patch("scripts.export_channels.fetch_guild_channels") as mock_fetch:
                    mock_fetch.return_value = (
                        [
                            {"name": "alpha", "id": "111"},
                            {"name": "beta", "id": "222"},
                            {"name": "gamma", "id": "333"},
                        ],
                        {},
                    )
                    with patch("scripts.export_channels.StateManager") as mock_state_class:
                        mock_state = Mock()
                        mock_state_class.return_value = mock_state
                        mock_state.load.return_value = {}
                        mock_state.get_channel_state.return_value = None

                        with patch(
                            "scripts.export_channels.format_export_command",
                            side_effect=fake_format,
                        ):
                            with patch(
                                "scripts.export_channels.run_export",
                                return_value=(True, "ok"),
                            ):
                                with patch("scripts.export_channels.Path"):
                                    export_all_channels()

        # 3 channels: 3 current + 3 channels × 2 backfill months = 9 total
        expected_current = 3
        expected_backfill = 6
        assert observed_months.count("current") == expected_current
        assert observed_months.count("backfill") == expected_backfill
        # The decisive assertion: NO backfill export occurs before ALL three
        # current-month exports are done.
        first_backfill = observed_months.index("backfill")
        assert observed_months[:first_backfill] == ["current"] * expected_current

        del os.environ["DISCORD_BOT_TOKEN"]

    def test_export_all_channels_skips_forbidden_channel_without_failing(self) -> None:
        """A forbidden channel is skipped (not failed) and keeps the run green.

        The bot can list the channel but Discord denies read access. This
        is an expected boundary — it must NOT increment channels_failed or
        add to the error list (which would turn every workflow run red),
        but it MUST be visibly counted as skipped.
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
            "export": {"formats": ["html", "txt"]},
            "github": {},
        }

        forbidden_output = (
            "Resolving channel(s)...\nERROR\n"
            "DiscordChatExporter.Core.Exceptions.DiscordChatExporterException: "
            "Request to 'channels/1501103893571043379' failed: forbidden."
        )

        with fixed_months("2026-02", "2026-02"):
            with patch("scripts.export_channels.load_config", return_value=config):
                with patch("scripts.export_channels.fetch_guild_channels") as mock_fetch:
                    mock_fetch.return_value = (
                        [{"name": "updates-prep", "id": "1501103893571043379"}],
                        {},
                    )

                    with patch("scripts.export_channels.StateManager") as mock_state_class:
                        mock_state = Mock()
                        mock_state_class.return_value = mock_state
                        mock_state.load.return_value = {}
                        mock_state.get_channel_state.return_value = None

                        with patch("scripts.export_channels.run_export") as mock_run:
                            # First format attempt hits forbidden → whole
                            # channel short-circuits (no further calls).
                            mock_run.return_value = (False, forbidden_output)

                            with patch("scripts.export_channels.Path"):
                                summary = export_all_channels()

                                assert summary["channels_failed"] == 0
                                assert summary["channels_skipped_forbidden"] == 1
                                assert summary["errors"] == []
                                assert summary["total_exports"] == 0
                                # Short-circuited after the first format probe
                                assert mock_run.call_count == 1

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

    def test_export_all_channels_stops_on_time_budget(self) -> None:
        """When max_runtime is exceeded, stop gracefully and flag the summary.

        We force out_of_time via a mocked time.monotonic that increments by
        100 seconds on every call, so by the third channel we've blown past
        a 60-second budget. The third channel must be skipped, summary must
        flag time_budget_exhausted, and earlier channels' work is preserved.
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
                }
            },
            "export": {"formats": ["html"]},
            "github": {},
        }

        with fixed_months("2026-02", "2026-02"):
            with patch("scripts.export_channels.load_config", return_value=config):
                with patch("scripts.export_channels.fetch_guild_channels") as mock_fetch:
                    mock_fetch.return_value = (
                        [
                            {"name": "a", "id": "1"},
                            {"name": "b", "id": "2"},
                            {"name": "c", "id": "3"},
                        ],
                        {},
                    )
                    with patch("scripts.export_channels.StateManager") as mock_state_class:
                        mock_state = Mock()
                        mock_state_class.return_value = mock_state
                        mock_state.load.return_value = {}

                        with patch("scripts.export_channels.run_export") as mock_run:
                            mock_run.return_value = (True, "")

                            # Each call to time.monotonic() advances 40s.
                            # Budget of 60s: iter1 check at 40s (allowed),
                            # iter2 check at 80s (exhausted).
                            counter = {"v": 0.0}

                            def fake_monotonic() -> float:
                                v = counter["v"]
                                counter["v"] += 40.0
                                return v

                            with patch(
                                "scripts.export_channels.time.monotonic",
                                side_effect=fake_monotonic,
                            ):
                                with patch("scripts.export_channels.Path"):
                                    summary = export_all_channels(max_runtime_seconds=60)

                            assert summary["time_budget_exhausted"] is True
                            # At least one channel processed before stopping
                            assert summary["channels_updated"] >= 1
                            # Not all three
                            assert summary["channels_updated"] < TIME_BUDGET_TOTAL_CHANNELS

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
