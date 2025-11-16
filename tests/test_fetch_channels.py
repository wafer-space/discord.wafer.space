# tests/test_fetch_channels.py
"""Tests for dynamic channel fetching functionality."""

from unittest.mock import Mock, patch

import pytest

from scripts.export_channels import fetch_guild_channels

# Test constants
EXPECTED_TWO_CHANNELS = 2
EXPECTED_THREE_CHANNELS = 3


def test_fetch_guild_channels_success() -> None:
    """Test successful channel fetching."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="123456 | Information / announcements\n789012 | General / general\n",
            stderr="",
        )

        channels = fetch_guild_channels("test_token", "guild123")

        assert len(channels) == EXPECTED_TWO_CHANNELS
        assert channels[0] == {"name": "announcements", "id": "123456", "parent_id": "Information"}
        assert channels[1] == {"name": "general", "id": "789012", "parent_id": "General"}


def test_fetch_guild_channels_without_category() -> None:
    """Test channel fetching for channels without categories."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            returncode=0, stdout="123456 | general\n789012 | announcements\n", stderr=""
        )

        channels = fetch_guild_channels("test_token", "guild123")

        assert len(channels) == EXPECTED_TWO_CHANNELS
        assert channels[0] == {"name": "general", "id": "123456", "parent_id": None}
        assert channels[1] == {"name": "announcements", "id": "789012", "parent_id": None}


def test_fetch_guild_channels_empty_output() -> None:
    """Test handling of empty channel list."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")

        channels = fetch_guild_channels("test_token", "guild123")

        assert channels == []


def test_fetch_guild_channels_command_failure() -> None:
    """Test handling of command failure."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="ERROR: Authentication failed")

        with pytest.raises(RuntimeError, match="Failed to fetch channels"):
            fetch_guild_channels("test_token", "guild123")


def test_fetch_guild_channels_timeout() -> None:
    """Test handling of timeout."""
    with patch("subprocess.run") as mock_run:
        from subprocess import TimeoutExpired

        mock_run.side_effect = TimeoutExpired(cmd="test", timeout=30)

        with pytest.raises(RuntimeError, match="timed out"):
            fetch_guild_channels("test_token", "guild123")


def test_fetch_guild_channels_exception() -> None:
    """Test handling of unexpected exceptions."""
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = Exception("Unexpected error")

        with pytest.raises(RuntimeError, match="Channel fetching failed"):
            fetch_guild_channels("test_token", "guild123")


def test_fetch_guild_channels_includes_threads() -> None:
    """Test that threads are included when fetching channels."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="""123456 | General / general
 * 789012 | Thread / How do I start? | Active
 * 789013 | Thread / Troubleshooting help | Archived
""",
            stderr="",
        )

        channels = fetch_guild_channels("test_token", "guild123", include_threads=True)

        # Should include both regular channel and threads
        assert len(channels) == EXPECTED_THREE_CHANNELS
        assert channels[0] == {"name": "general", "id": "123456", "parent_id": "General"}
        assert channels[1] == {"name": "How do I start?", "id": "789012", "parent_id": "Thread"}
        assert channels[2] == {
            "name": "Troubleshooting help",
            "id": "789013",
            "parent_id": "Thread",
        }


def test_fetch_guild_channels_without_threads() -> None:
    """Test that threads are excluded when include_threads=False."""
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = Mock(returncode=0, stdout="123456 | General / general\n", stderr="")

        channels = fetch_guild_channels("test_token", "guild123", include_threads=False)

        assert len(channels) == 1
        assert channels[0] == {"name": "general", "id": "123456", "parent_id": "General"}
