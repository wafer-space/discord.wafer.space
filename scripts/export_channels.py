# scripts/export_channels.py
"""Export Discord channels using DiscordChatExporter CLI."""
import os
import re
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
        regex_pattern = pattern.replace('*', '.*')
        if re.match(f'^{regex_pattern}$', channel_name):
            return False

    # Check inclusions
    if '*' in include_patterns:
        return True

    for pattern in include_patterns:
        regex_pattern = pattern.replace('*', '.*')
        if re.match(f'^{regex_pattern}$', channel_name):
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
        format_type: Export format (HtmlDark, PlainText, Json, Csv)
        after_timestamp: Optional timestamp for incremental export

    Returns:
        Command as list of arguments
    """
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
