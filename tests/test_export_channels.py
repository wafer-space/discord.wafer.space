# tests/test_export_channels.py
import pytest
import os
from scripts.export_channels import (
    get_bot_token,
    should_include_channel,
    format_export_command
)

def test_get_bot_token_from_env():
    """Test getting bot token from environment"""
    os.environ['DISCORD_BOT_TOKEN'] = 'test_token_123'
    token = get_bot_token()
    assert token == 'test_token_123'
    del os.environ['DISCORD_BOT_TOKEN']

def test_get_bot_token_raises_if_not_set():
    """Test that missing token raises error"""
    if 'DISCORD_BOT_TOKEN' in os.environ:
        del os.environ['DISCORD_BOT_TOKEN']

    with pytest.raises(ValueError, match="DISCORD_BOT_TOKEN"):
        get_bot_token()

def test_should_include_channel_with_wildcard():
    """Test channel inclusion with wildcard pattern"""
    include = ["*"]
    exclude = ["admin", "private-*"]

    assert should_include_channel("general", include, exclude) == True
    assert should_include_channel("announcements", include, exclude) == True

def test_should_include_channel_excludes_patterns():
    """Test channel exclusion patterns"""
    include = ["*"]
    exclude = ["admin", "private-*"]

    assert should_include_channel("admin", include, exclude) == False
    assert should_include_channel("private-chat", include, exclude) == False
    assert should_include_channel("private-logs", include, exclude) == False

def test_should_include_channel_specific_includes():
    """Test specific channel inclusion"""
    include = ["general", "announcements"]
    exclude = []

    assert should_include_channel("general", include, exclude) == True
    assert should_include_channel("announcements", include, exclude) == True
    assert should_include_channel("random", include, exclude) == False

def test_format_export_command():
    """Test export command formatting"""
    cmd = format_export_command(
        token="test_token",
        channel_id="123456",
        output_path="exports/test.html",
        format_type="HtmlDark",
        after_timestamp=None
    )

    expected = [
        "./DiscordChatExporter.Cli", "export",
        "-t", "test_token",
        "-c", "123456",
        "-f", "HtmlDark",
        "-o", "exports/test.html"
    ]

    assert cmd == expected

def test_format_export_command_with_after():
    """Test export command with --after flag"""
    cmd = format_export_command(
        token="test_token",
        channel_id="123456",
        output_path="exports/test.html",
        format_type="HtmlDark",
        after_timestamp="2025-01-15T14:00:00Z"
    )

    assert "--after" in cmd
    assert "2025-01-15T14:00:00Z" in cmd
