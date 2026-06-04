# tests/test_export_channels.py
import os
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from scripts.export_channels import (
    ChannelExportContext,
    ChannelInfo,
    MediaConfig,
    _export_one_month,
    _is_permission_error,
    format_export_command,
    get_bot_token,
    should_include_channel,
)


def test_is_permission_error_detects_forbidden() -> None:
    """A DCE 'forbidden' response on a channel request is a permission boundary."""
    output = (
        "Resolving channel(s)...\nERROR\n"
        "DiscordChatExporter.Core.Exceptions.DiscordChatExporterException: "
        "Request to 'channels/1501103893571043379' failed: forbidden.\n"
        "  at DiscordChatExporter.Core.Discord.DiscordClient.GetJsonResponseAsync(...)"
    )
    assert _is_permission_error(output) is True


def test_is_permission_error_detects_unauthorized() -> None:
    """Unauthorized is also a permission boundary, not a pipeline failure."""
    output = "Request to 'channels/123' failed: unauthorized."
    assert _is_permission_error(output) is True


def test_is_permission_error_false_for_other_failures() -> None:
    """Genuine errors (timeouts, rate limits, parse errors) are NOT permission errors."""
    assert _is_permission_error("Export timed out after 900 seconds") is False
    assert _is_permission_error("Request failed: too many requests") is False
    assert _is_permission_error("Export completed successfully") is False
    assert _is_permission_error("") is False


def test_get_bot_token_from_env() -> None:
    """Test getting bot token from environment"""
    os.environ["DISCORD_BOT_TOKEN"] = "test_token_123"
    token = get_bot_token()
    assert token == "test_token_123"
    del os.environ["DISCORD_BOT_TOKEN"]


def test_get_bot_token_raises_if_not_set() -> None:
    """Test that missing token raises error"""
    if "DISCORD_BOT_TOKEN" in os.environ:
        del os.environ["DISCORD_BOT_TOKEN"]

    with pytest.raises(ValueError, match="DISCORD_BOT_TOKEN"):
        get_bot_token()


def test_should_include_channel_with_wildcard() -> None:
    """Test channel inclusion with wildcard pattern"""
    include = ["*"]
    exclude = ["admin", "private-*"]

    assert should_include_channel("general", include, exclude)
    assert should_include_channel("announcements", include, exclude)


def test_should_include_channel_excludes_patterns() -> None:
    """Test channel exclusion patterns"""
    include = ["*"]
    exclude = ["admin", "private-*"]

    assert not should_include_channel("admin", include, exclude)
    assert not should_include_channel("private-chat", include, exclude)
    assert not should_include_channel("private-logs", include, exclude)


def test_should_include_channel_specific_includes() -> None:
    """Test specific channel inclusion"""
    include: list[str] = ["general", "announcements"]
    exclude: list[str] = []

    assert should_include_channel("general", include, exclude)
    assert should_include_channel("announcements", include, exclude)
    assert not should_include_channel("random", include, exclude)


def test_format_export_command() -> None:
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
        "--locale",
        "en-CA",
    ]

    assert cmd == expected


def test_format_export_command_with_after() -> None:
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


def test_format_export_command_includes_iso_locale() -> None:
    """Every export must pass --locale so DCE formats dates ISO (en-CA →
    YYYY-MM-DD), not the US default MM/dd/yyyy (issue #3)."""
    cmd = format_export_command(
        token="test_token",
        channel_id="123456",
        output_path="exports/test.html",
        format_type="HtmlDark",
        after_timestamp=None,
    )
    assert "--locale" in cmd
    locale_value = cmd[cmd.index("--locale") + 1]
    assert locale_value == "en-CA"


def test_export_one_month_current_month_is_bounded(tmp_path: Path) -> None:
    """The current month must be bracketed with --before too, so DCE renders a
    bounded date range instead of an open-ended 'After ...' that reads as the
    prior day (issue #4). before-bound is the next month's first instant UTC."""
    captured: list[list[str]] = []

    def _capture(cmd: list[str], *args: object, **kwargs: object) -> tuple[bool, str]:
        captured.append(cmd)
        return True, "ok"

    context = ChannelExportContext(
        config={"export": {"formats": ["html"]}},
        token="test_token",
        server_key="wafer-space",
        state_manager=Mock(),
    )
    channel_info = ChannelInfo(
        channel_id="123456", channel_name="general", safe_name="general", forum_name=""
    )
    with patch("scripts.export_channels.run_export", side_effect=_capture):
        _export_one_month(context, channel_info, tmp_path, "2026-06", is_current_month=True)

    assert captured, "expected at least one export command"
    cmd = captured[0]
    assert "--before" in cmd, "current month must be bracketed with --before"
    assert "2026-07-01T00:00:00+00:00" in cmd


def test_write_channel_order_captures_guild_order_and_category(tmp_path: Path) -> None:
    """write_channel_order records non-thread channels in guild order with their
    category, so navigation can group + sort like the server (issue #5)."""
    import json

    from scripts.channel_classifier import ChannelType
    from scripts.export_channels import write_channel_order

    channels: list[dict[str, str | None]] = [
        {"name": "general", "id": "1", "parent_id": "Information"},
        {"name": "questions", "id": "2", "parent_id": "Information"},
        {"name": "How to?", "id": "3", "parent_id": "questions"},  # a thread
        {"name": "analog", "id": "4", "parent_id": "Designing"},
    ]
    classifications = {
        "1": ChannelType.REGULAR,
        "2": ChannelType.FORUM,
        "3": ChannelType.THREAD,
        "4": ChannelType.REGULAR,
    }
    path_map = {
        "general": "Information/general",
        "questions": "Information/questions",
        "analog": "Designing/analog",
    }
    write_channel_order(tmp_path, "wafer-space", channels, classifications, path_map)

    order = json.loads((tmp_path / "wafer-space" / "_order.json").read_text())
    # Threads excluded; guild order preserved; category derived from the path.
    assert order == [
        {"path": "Information/general", "category": "Information"},
        {"path": "Information/questions", "category": "Information"},
        {"path": "Designing/analog", "category": "Designing"},
    ]


def test_format_export_command_invalid_format() -> None:
    """Test that invalid format_type raises ValueError"""
    with pytest.raises(ValueError, match="Invalid format_type"):
        format_export_command(
            token="test_token",
            channel_id="123456",
            output_path="exports/test.html",
            format_type="InvalidFormat",
            after_timestamp=None,
        )


def test_format_export_command_invalid_channel_id() -> None:
    """Test that non-numeric channel_id raises ValueError"""
    with pytest.raises(ValueError, match="Invalid channel_id"):
        format_export_command(
            token="test_token",
            channel_id="abc123",
            output_path="exports/test.html",
            format_type="HtmlDark",
            after_timestamp=None,
        )


def test_format_export_command_with_media_download() -> None:
    """Test export command with media download enabled"""
    media_config = MediaConfig(
        download_media=True,
        media_dir="public/assets/media",
    )

    cmd = format_export_command(
        token="test_token",
        channel_id="123456",
        output_path="exports/test.html",
        format_type="HtmlDark",
        after_timestamp=None,
        media_config=media_config,
    )

    assert "--media" in cmd
    assert "--media-dir" in cmd
    assert "public/assets/media" in cmd


def test_format_export_command_with_media_reuse() -> None:
    """Test export command with media reuse enabled"""
    media_config = MediaConfig(
        download_media=True,
        media_dir="public/assets/media",
        reuse_media=True,
    )

    cmd = format_export_command(
        token="test_token",
        channel_id="123456",
        output_path="exports/test.html",
        format_type="HtmlDark",
        after_timestamp=None,
        media_config=media_config,
    )

    assert "--media" in cmd
    assert "--reuse-media" in cmd
    assert "--media-dir" in cmd


def test_format_export_command_without_media() -> None:
    """Test export command without media download"""
    media_config = MediaConfig(download_media=False)

    cmd = format_export_command(
        token="test_token",
        channel_id="123456",
        output_path="exports/test.html",
        format_type="HtmlDark",
        after_timestamp=None,
        media_config=media_config,
    )

    assert "--media" not in cmd
    assert "--media-dir" not in cmd


def test_format_export_command_with_before() -> None:
    """Bracketing a month requires --before so DCE stops at month end."""
    cmd = format_export_command(
        token="test_token",
        channel_id="123456",
        output_path="exports/test.html",
        format_type="HtmlDark",
        after_timestamp="2026-01-31T23:59:59.999999+00:00",
        before_timestamp="2026-03-01T00:00:00+00:00",
    )
    assert "--after" in cmd
    assert "2026-01-31T23:59:59.999999+00:00" in cmd
    assert "--before" in cmd
    assert "2026-03-01T00:00:00+00:00" in cmd


def test_format_export_command_before_only() -> None:
    """An export with only --before (no --after) is valid (e.g., 'find first message')."""
    cmd = format_export_command(
        token="test_token",
        channel_id="123456",
        output_path="exports/test.html",
        format_type="HtmlDark",
        after_timestamp=None,
        before_timestamp="2025-06-01T00:00:00+00:00",
    )
    assert "--after" not in cmd
    assert "--before" in cmd
    assert "2025-06-01T00:00:00+00:00" in cmd
