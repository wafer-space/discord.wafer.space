# tests/test_fetch_channels.py
"""Tests for dynamic channel fetching functionality."""
import pytest
from unittest.mock import Mock, patch
from scripts.export_channels import fetch_guild_channels


def test_fetch_guild_channels_success():
    """Test successful channel fetching."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Information / announcements [123456]\nGeneral / general [789012]\n",
            stderr=""
        )

        channels = fetch_guild_channels("test_token", "guild123")

        assert len(channels) == 2
        assert channels[0] == {'name': 'announcements', 'id': '123456'}
        assert channels[1] == {'name': 'general', 'id': '789012'}


def test_fetch_guild_channels_without_category():
    """Test channel fetching for channels without categories."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="general [123456]\nannouncements [789012]\n",
            stderr=""
        )

        channels = fetch_guild_channels("test_token", "guild123")

        assert len(channels) == 2
        assert channels[0] == {'name': 'general', 'id': '123456'}
        assert channels[1] == {'name': 'announcements', 'id': '789012'}


def test_fetch_guild_channels_empty_output():
    """Test handling of empty channel list."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="",
            stderr=""
        )

        channels = fetch_guild_channels("test_token", "guild123")

        assert channels == []


def test_fetch_guild_channels_command_failure():
    """Test handling of command failure."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="ERROR: Authentication failed"
        )

        with pytest.raises(RuntimeError, match="Failed to fetch channels"):
            fetch_guild_channels("test_token", "guild123")


def test_fetch_guild_channels_timeout():
    """Test handling of timeout."""
    with patch('subprocess.run') as mock_run:
        from subprocess import TimeoutExpired
        mock_run.side_effect = TimeoutExpired(cmd="test", timeout=30)

        with pytest.raises(RuntimeError, match="timed out"):
            fetch_guild_channels("test_token", "guild123")


def test_fetch_guild_channels_exception():
    """Test handling of unexpected exceptions."""
    with patch('subprocess.run') as mock_run:
        mock_run.side_effect = Exception("Unexpected error")

        with pytest.raises(RuntimeError, match="Channel fetching failed"):
            fetch_guild_channels("test_token", "guild123")
