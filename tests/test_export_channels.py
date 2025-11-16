# tests/test_export_channels.py
import os

import pytest

from scripts.export_channels import format_export_command, get_bot_token, should_include_channel


def test_get_bot_token_from_env():
    """Test getting bot token from environment"""
    os.environ["DISCORD_BOT_TOKEN"] = "test_token_123"
    token = get_bot_token()
    assert token == "test_token_123"
    del os.environ["DISCORD_BOT_TOKEN"]


def test_get_bot_token_raises_if_not_set():
    """Test that missing token raises error"""
    if "DISCORD_BOT_TOKEN" in os.environ:
        del os.environ["DISCORD_BOT_TOKEN"]

    with pytest.raises(ValueError, match="DISCORD_BOT_TOKEN"):
        get_bot_token()


def test_should_include_channel_with_wildcard():
    """Test channel inclusion with wildcard pattern"""
    include = ["*"]
    exclude = ["admin", "private-*"]

    assert should_include_channel("general", include, exclude)
    assert should_include_channel("announcements", include, exclude)


def test_should_include_channel_excludes_patterns():
    """Test channel exclusion patterns"""
    include = ["*"]
    exclude = ["admin", "private-*"]

    assert not should_include_channel("admin", include, exclude)
    assert not should_include_channel("private-chat", include, exclude)
    assert not should_include_channel("private-logs", include, exclude)


def test_should_include_channel_specific_includes():
    """Test specific channel inclusion"""
    include = ["general", "announcements"]
    exclude = []

    assert should_include_channel("general", include, exclude)
    assert should_include_channel("announcements", include, exclude)
    assert not should_include_channel("random", include, exclude)


def test_format_export_command():
    """Test export command formatting"""
    cmd = format_export_command(
        token="test_token",
        channel_id="123456",
        output_path="exports/test.html",
        format_type="HtmlDark",
        after_timestamp=None,
    )

    expected = [
        "bin/discord-exporter/DiscordChatExporter.Cli",
        "export",
        "-t",
        "test_token",
        "-c",
        "123456",
        "-f",
        "HtmlDark",
        "-o",
        "exports/test.html",
    ]

    assert cmd == expected


def test_format_export_command_with_after():
    """Test export command with --after flag"""
    cmd = format_export_command(
        token="test_token",
        channel_id="123456",
        output_path="exports/test.html",
        format_type="HtmlDark",
        after_timestamp="2025-01-15T14:00:00Z",
    )

    assert "--after" in cmd
    assert "2025-01-15T14:00:00Z" in cmd


def test_format_export_command_invalid_format():
    """Test that invalid format_type raises ValueError"""
    with pytest.raises(ValueError, match="Invalid format_type"):
        format_export_command(
            token="test_token",
            channel_id="123456",
            output_path="exports/test.html",
            format_type="InvalidFormat",
            after_timestamp=None,
        )


def test_format_export_command_invalid_channel_id():
    """Test that non-numeric channel_id raises ValueError"""
    with pytest.raises(ValueError, match="Invalid channel_id"):
        format_export_command(
            token="test_token",
            channel_id="abc123",
            output_path="exports/test.html",
            format_type="HtmlDark",
            after_timestamp=None,
        )
