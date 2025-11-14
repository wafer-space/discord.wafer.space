# scripts/export_channels.py
"""Export Discord channels using DiscordChatExporter CLI."""
import fnmatch
import os
from typing import List, Optional

def get_bot_token() -> str:
    """
    Get Discord bot token from environment.

    Returns:
        Bot token string

    Raises:
        ValueError: If DISCORD_BOT_TOKEN not set
    """
    token = os.environ.get('DISCORD_BOT_TOKEN')
    if not token:
        raise ValueError(
            "DISCORD_BOT_TOKEN environment variable not set. "
            "Add bot token to GitHub Secrets or export locally."
        )
    return token

def should_include_channel(
    channel_name: str,
    include_patterns: List[str],
    exclude_patterns: List[str]
) -> bool:
    """
    Check if channel should be included based on patterns.

    Args:
        channel_name: Name of the channel
        include_patterns: List of patterns to include (supports * wildcard)
        exclude_patterns: List of patterns to exclude (supports * wildcard)

    Returns:
        True if channel should be included
    """
    # Check exclusions first
    for pattern in exclude_patterns:
        if fnmatch.fnmatch(channel_name, pattern):
            return False

    # Check inclusions
    if '*' in include_patterns:
        return True

    for pattern in include_patterns:
        if fnmatch.fnmatch(channel_name, pattern):
            return True

    return False

def format_export_command(
    token: str,
    channel_id: str,
    output_path: str,
    format_type: str,
    after_timestamp: Optional[str] = None
) -> List[str]:
    """
    Format DiscordChatExporter CLI command.

    Args:
        token: Discord bot token
        channel_id: Channel ID to export
        output_path: Output file path
        format_type: Export format (HtmlDark, HtmlLight, PlainText, Json, Csv)
        after_timestamp: Optional timestamp for incremental export

    Returns:
        Command as list of arguments

    Raises:
        ValueError: If format_type is invalid or channel_id is not numeric
    """
    # Validate format_type
    valid_formats = {'HtmlDark', 'HtmlLight', 'PlainText', 'Json', 'Csv'}
    if format_type not in valid_formats:
        raise ValueError(
            f"Invalid format_type '{format_type}'. "
            f"Must be one of: {', '.join(sorted(valid_formats))}"
        )

    # Validate channel_id is numeric
    if not channel_id.isdigit():
        raise ValueError(
            f"Invalid channel_id '{channel_id}'. Must be numeric (digits only)."
        )

    cmd = [
        "./DiscordChatExporter.Cli", "export",
        "-t", token,
        "-c", channel_id,
        "-f", format_type,
        "-o", output_path
    ]

    if after_timestamp:
        cmd.extend(["--after", after_timestamp])

    return cmd
