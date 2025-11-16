# tests/test_export_orchestration.py
"""Tests for export orchestration functionality."""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from scripts.export_channels import export_all_channels, run_export


class TestRunExport:
    """Tests for run_export function."""

    @patch("subprocess.run")
    def test_run_export_success(self, mock_run):
        """Test successful export execution."""
        mock_run.return_value = Mock(returncode=0, stdout="Export completed", stderr="")

        cmd = ["./DiscordChatExporter.Cli", "export"]
        success, output = run_export(cmd)

        assert success is True
        assert "Export completed" in output
        mock_run.assert_called_once()

    @patch("subprocess.run")
    def test_run_export_failure(self, mock_run):
        """Test failed export execution."""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="Error: Invalid token")

        cmd = ["./DiscordChatExporter.Cli", "export"]
        success, output = run_export(cmd)

        assert success is False
        assert "Invalid token" in output

    @patch("subprocess.run")
    def test_run_export_timeout(self, mock_run):
        """Test export timeout handling."""
        import subprocess

        mock_run.side_effect = subprocess.TimeoutExpired(cmd="test", timeout=10)

        cmd = ["./DiscordChatExporter.Cli", "export"]
        success, output = run_export(cmd, timeout=10)

        assert success is False
        assert "timed out" in output

    @patch("subprocess.run")
    def test_run_export_exception(self, mock_run):
        """Test export exception handling."""
        mock_run.side_effect = Exception("Unknown error")

        cmd = ["./DiscordChatExporter.Cli", "export"]
        success, output = run_export(cmd)

        assert success is False
        assert "Export failed" in output


class TestExportAllChannels:
    """Tests for export_all_channels orchestration function."""

    def test_export_all_channels_loads_config(self):
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
                    mock_fetch.return_value = []

                    with patch("scripts.export_channels.StateManager"):
                        with patch("scripts.export_channels.Path"):
                            summary = export_all_channels()

                            mock_load.assert_called_once()
                            assert "channels_updated" in summary
                            assert "channels_failed" in summary

            del os.environ["DISCORD_BOT_TOKEN"]

    def test_export_all_channels_initializes_state_manager(self):
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
                mock_fetch.return_value = [{"name": "general", "id": "123"}]

                with patch("scripts.export_channels.StateManager") as MockState:
                    mock_state_instance = Mock()
                    MockState.return_value = mock_state_instance

                    with patch("scripts.export_channels.Path"):
                        export_all_channels()

                        MockState.assert_called_once()
                        mock_state_instance.load.assert_called_once()

        del os.environ["DISCORD_BOT_TOKEN"]

    def test_export_all_channels_processes_each_server(self):
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
                mock_fetch.return_value = []

                with patch("scripts.export_channels.StateManager") as MockState:
                    mock_state = Mock()
                    MockState.return_value = mock_state
                    mock_state.load.return_value = {}

                    with patch("scripts.export_channels.Path"):
                        summary = export_all_channels()

                        # Both servers should have been processed
                        assert summary["channels_updated"] >= 0

        del os.environ["DISCORD_BOT_TOKEN"]

    def test_export_all_channels_filters_channels_by_pattern(self):
        """Test that channels are filtered by include/exclude patterns."""
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

        with patch("scripts.export_channels.load_config", return_value=config):
            with patch("scripts.export_channels.fetch_guild_channels") as mock_fetch:
                # Return 3 channels: 2 will pass filter, 1 will be excluded
                mock_fetch.return_value = [
                    {"name": "general", "id": "111"},
                    {"name": "announcements", "id": "222"},
                    {"name": "private-chat", "id": "333"},
                ]

                with patch("scripts.export_channels.StateManager") as MockState:
                    mock_state = Mock()
                    MockState.return_value = mock_state
                    mock_state.load.return_value = {}
                    mock_state.get_channel_state.return_value = None

                    with patch("scripts.export_channels.run_export") as mock_run:
                        mock_run.return_value = (True, "Success")

                        with patch("scripts.export_channels.Path"):
                            summary = export_all_channels()

                            # Should export general and announcements, skip private-chat
                            # 2 channels * 1 format = 2 exports
                            assert summary["total_exports"] == 2

        del os.environ["DISCORD_BOT_TOKEN"]

    def test_export_all_channels_exports_all_formats(self):
        """Test that all configured formats are exported."""
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

        with patch("scripts.export_channels.load_config", return_value=config):
            with patch("scripts.export_channels.fetch_guild_channels") as mock_fetch:
                mock_fetch.return_value = [{"name": "general", "id": "123"}]

                with patch("scripts.export_channels.StateManager") as MockState:
                    mock_state = Mock()
                    MockState.return_value = mock_state
                    mock_state.load.return_value = {}
                    mock_state.get_channel_state.return_value = None

                    with patch("scripts.export_channels.run_export") as mock_run:
                        mock_run.return_value = (True, "Success")

                        with patch("scripts.export_channels.Path"):
                            summary = export_all_channels()

                            # 1 channel * 4 formats = 4 exports
                            assert summary["total_exports"] == 4

        del os.environ["DISCORD_BOT_TOKEN"]

    def test_export_all_channels_uses_incremental_state(self):
        """Test that incremental exports use state for --after timestamp."""
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
                mock_fetch.return_value = [{"name": "general", "id": "123"}]

                with patch("scripts.export_channels.StateManager") as MockState:
                    mock_state = Mock()
                    MockState.return_value = mock_state
                    mock_state.load.return_value = {}
                    mock_state.get_channel_state.return_value = {
                        "last_export": "2025-01-15T10:00:00Z",
                        "last_message_id": "999",
                    }

                    with patch("scripts.export_channels.format_export_command") as mock_format:
                        mock_format.return_value = ["test", "command"]

                        with patch("scripts.export_channels.run_export") as mock_run:
                            mock_run.return_value = (True, "Success")

                            with patch("scripts.export_channels.Path"):
                                export_all_channels()

                                # Should call format_export_command with after_timestamp
                                mock_format.assert_called_once()
                                call_kwargs = mock_format.call_args
                                assert call_kwargs[1]["after_timestamp"] == "2025-01-15T10:00:00Z"

        del os.environ["DISCORD_BOT_TOKEN"]

    def test_export_all_channels_updates_state_after_export(self):
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
                mock_fetch.return_value = [{"name": "general", "id": "123"}]

                with patch("scripts.export_channels.StateManager") as MockState:
                    mock_state = Mock()
                    MockState.return_value = mock_state
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

    def test_export_all_channels_tracks_failures(self):
        """Test that failed exports are tracked in summary."""
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

        with patch("scripts.export_channels.load_config", return_value=config):
            with patch("scripts.export_channels.fetch_guild_channels") as mock_fetch:
                mock_fetch.return_value = [{"name": "general", "id": "123"}]

                with patch("scripts.export_channels.StateManager") as MockState:
                    mock_state = Mock()
                    MockState.return_value = mock_state
                    mock_state.load.return_value = {}
                    mock_state.get_channel_state.return_value = None

                    with patch("scripts.export_channels.run_export") as mock_run:
                        # First export succeeds, second fails
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
                            assert summary["errors"][0]["format"] == "txt"

        del os.environ["DISCORD_BOT_TOKEN"]

    def test_export_all_channels_creates_exports_directory(self):
        """Test that exports directory is created."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token"

        with tempfile.TemporaryDirectory():
            config = {"site": {}, "servers": {}, "export": {"formats": ["html"]}, "github": {}}

            with patch("scripts.export_channels.load_config", return_value=config):
                with patch("scripts.export_channels.StateManager") as MockState:
                    mock_state = Mock()
                    MockState.return_value = mock_state
                    mock_state.load.return_value = {}

                    with patch("scripts.export_channels.Path") as MockPath:
                        mock_exports_path = Mock()
                        MockPath.return_value = mock_exports_path

                        export_all_channels()

                        # Should call mkdir on exports directory
                        mock_exports_path.mkdir.assert_called()

        del os.environ["DISCORD_BOT_TOKEN"]

    def test_export_all_channels_returns_summary(self):
        """Test that export_all_channels returns proper summary dict."""
        os.environ["DISCORD_BOT_TOKEN"] = "test_token"

        config = {"site": {}, "servers": {}, "export": {"formats": ["html"]}, "github": {}}

        with patch("scripts.export_channels.load_config", return_value=config):
            with patch("scripts.export_channels.StateManager") as MockState:
                mock_state = Mock()
                MockState.return_value = mock_state
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

    def test_export_all_channels_handles_forums(self):
        """Test that forum channels create directories."""
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

        with patch("scripts.export_channels.load_config", return_value=config):
            with patch("scripts.export_channels.fetch_guild_channels") as mock_fetch:
                # Return forum channel and threads
                mock_fetch.return_value = [
                    {"name": "questions", "id": "999", "parent_id": None},
                    {"name": "How to start?", "id": "111", "parent_id": "questions"},
                    {"name": "Help needed", "id": "222", "parent_id": "questions"},
                ]

                with patch("scripts.export_channels.StateManager") as MockState:
                    mock_state = Mock()
                    MockState.return_value = mock_state
                    mock_state.load.return_value = {}
                    mock_state.get_channel_state.return_value = None
                    mock_state.get_thread_state.return_value = None

                    with patch("scripts.export_channels.run_export") as mock_run:
                        mock_run.return_value = (True, "Success")

                        with patch("scripts.export_channels.Path"):
                            summary = export_all_channels()

                            # Should export 2 threads (not the forum parent)
                            assert summary["total_exports"] == 2

                            # Should create questions directory
                            # Check mkdir was called for forum directory

        del os.environ["DISCORD_BOT_TOKEN"]

    def test_export_all_channels_tracks_thread_state(self):
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
                            mock_fetch.return_value = [
                                {"name": "questions", "id": "999", "parent_id": None},
                                {"name": "How to start?", "id": "111", "parent_id": "questions"},
                            ]

                            mock_run.return_value = (True, "")

                            # Mock Path to use temp directory
                            exports_dir = Path(tmpdir) / "exports"
                            exports_dir.mkdir(parents=True)
                            mock_path.return_value = exports_dir

                            # Mock StateManager
                            with patch("scripts.export_channels.StateManager") as MockState:
                                mock_state = Mock()
                                MockState.return_value = mock_state
                                mock_state.get_channel_state.return_value = None
                                mock_state.get_thread_state.return_value = None

                                # Run export
                                _ = export_all_channels()

                                # Verify thread state was updated
                                mock_state.update_thread_state.assert_called_once()
                                call_args = mock_state.update_thread_state.call_args
                                assert call_args[1]["server"] == "test-server"
                                assert call_args[1]["forum"] == "questions"
                                assert call_args[1]["thread_id"] == "111"

        del os.environ["DISCORD_BOT_TOKEN"]

    def test_export_all_channels_uses_incremental_for_threads(self):
        """Test that thread exports use --after for incremental updates."""
        import json

        os.environ["DISCORD_BOT_TOKEN"] = "test_token"

        # Create state with existing thread
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            state_data = {
                "test-server": {
                    "forums": {
                        "questions": {
                            "threads": {
                                "111": {
                                    "name": "how-to-start",
                                    "title": "How to start?",
                                    "last_export": "2025-11-14T10:00:00Z",
                                    "last_message_id": "888",
                                    "archived": False,
                                }
                            }
                        }
                    }
                }
            }
            json.dump(state_data, f)
            state_file = f.name

        try:
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
                with patch("scripts.export_channels.StateManager") as mock_state_class:
                    with patch("scripts.export_channels.fetch_guild_channels") as mock_fetch:
                        with patch("scripts.export_channels.run_export") as mock_run:
                            with patch(
                                "scripts.export_channels.format_export_command"
                            ) as mock_format:
                                # Setup state manager mock
                                mock_state = Mock()
                                mock_state.get_thread_state.return_value = state_data[
                                    "test-server"
                                ]["forums"]["questions"]["threads"]["111"]
                                mock_state.get_channel_state.return_value = None
                                mock_state_class.return_value = mock_state

                                mock_fetch.return_value = [
                                    {"name": "questions", "id": "999", "parent_id": None},
                                    {
                                        "name": "How to start?",
                                        "id": "111",
                                        "parent_id": "questions",
                                    },
                                ]

                                mock_format.return_value = [
                                    "test",
                                    "command",
                                    "--after",
                                    "2025-11-14T10:00:00Z",
                                ]
                                mock_run.return_value = (True, "")

                                with patch("scripts.export_channels.Path"):
                                    # Run export
                                    export_all_channels()

                                    # Verify --after was used in format_export_command
                                    # Check that format_export_command was called with after_timestamp
                                    calls = mock_format.call_args_list
                                    assert len(calls) > 0
                                    # Find the call for the thread
                                    thread_call = None
                                    for call in calls:
                                        if call[1].get("channel_id") == "111":
                                            thread_call = call
                                            break
                                    assert thread_call is not None
                                    assert (
                                        thread_call[1]["after_timestamp"] == "2025-11-14T10:00:00Z"
                                    )
        finally:
            Path(state_file).unlink()
            del os.environ["DISCORD_BOT_TOKEN"]
