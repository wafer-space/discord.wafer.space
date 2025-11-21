# scripts/export_channels.py
"""Export Discord channels using DiscordChatExporter CLI."""

import fnmatch
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.channel_classifier import ChannelType, classify_channel, sanitize_thread_name
from scripts.config import load_config
from scripts.state import StateManager, ThreadInfo

# Constants
CHANNEL_PATH_PARTS = 2
MIN_PIPE_PARTS = 2


@dataclass
class ChannelExportContext:
    """Context for channel export operations."""

    config: dict[str, Any]
    token: str
    server_key: str
    state_manager: StateManager


@dataclass
class ChannelInfo:
    """Information about a channel being exported."""

    channel_id: str
    channel_name: str
    safe_name: str
    forum_name: str


@dataclass
class MediaConfig:
    """Configuration for media download."""

    download_media: bool = False
    media_dir: str | None = None
    reuse_media: bool = False


def _determine_export_location(
    channel: dict[str, str | None],
    channel_type: ChannelType,
    channel_id: str,
    server_dir: Path,
    channel_path_map: dict[str, str],
) -> tuple[str, Path, str]:
    """Determine export location and name based on channel type.

    Args:
        channel: Channel data dict
        channel_type: Type of channel
        channel_id: Channel ID
        server_dir: Server export directory
        channel_path_map: Dict mapping channel names to their full hierarchical paths

    Returns:
        Tuple of (safe_name, export_dir, forum_name)
    """
    if channel_type == ChannelType.THREAD:
        forum_name_raw = channel.get("parent_id")
        forum_name_simple: str = forum_name_raw if forum_name_raw else "unknown-forum"

        # Look up the full hierarchical path for the forum
        # If forum is "cob" inside "🏗️ - Designing", path_map will have "cob" -> "🏗️ - Designing/cob"
        forum_full_path = channel_path_map.get(forum_name_simple, forum_name_simple)

        thread_dir = server_dir / forum_full_path
        thread_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize thread name for filename
        channel_name_raw = channel.get("name")
        safe_name = sanitize_thread_name(
            channel_name_raw if channel_name_raw else "unknown", channel_id
        )
        # Return forum_full_path as the forum_name for proper state tracking
        return safe_name, thread_dir, forum_full_path
    else:
        # Regular channel
        channel_name_raw = channel.get("name")
        channel_name = channel_name_raw if channel_name_raw else "unknown"
        return channel_name, server_dir, ""


def _get_last_export_timestamp(
    context: ChannelExportContext,
    channel_type: ChannelType,
    channel_name: str,
    channel_id: str,
    forum_name: str,
) -> str | None:
    """Get last export timestamp for incremental updates.

    Args:
        context: Export context with state manager
        channel_type: Type of channel
        channel_name: Channel name
        channel_id: Channel ID
        forum_name: Forum name (for threads)

    Returns:
        Last export timestamp or None
    """
    if channel_type == ChannelType.THREAD:
        thread_state = context.state_manager.get_thread_state(
            context.server_key, forum_name, channel_id
        )
        return thread_state["last_export"] if thread_state else None
    else:
        channel_state = context.state_manager.get_channel_state(context.server_key, channel_name)
        return channel_state["last_export"] if channel_state else None


def _export_channel_formats(
    context: ChannelExportContext,
    channel_info: ChannelInfo,
    export_dir: Path,
    export_name: str,
    after_timestamp: str | None,
) -> tuple[int, int, list[dict[str, str]]]:
    """Export channel in all configured formats.

    Args:
        context: Export context with config and token
        channel_info: Channel information
        export_dir: Directory for exports
        export_name: Base name for export files
        after_timestamp: Timestamp for incremental export

    Returns:
        Tuple of (exports_completed, failures, errors)
    """
    format_map = {"html": "HtmlDark", "txt": "PlainText", "json": "Json", "csv": "Csv"}

    exports_completed = 0
    failures = 0
    errors: list[dict[str, str]] = []

    for fmt in context.config["export"]["formats"]:
        output_path = export_dir / f"{export_name}.{fmt}"

        # Create media config from export settings
        # Store media alongside each channel: export_dir/channel_name_media/
        media_dir = None
        if context.config["export"].get("download_media", False):
            media_dir = str(export_dir / f"{export_name}_media")

        media_config = MediaConfig(
            download_media=context.config["export"].get("download_media", False),
            media_dir=media_dir,
            reuse_media=context.config["export"].get("reuse_media", False),
        )

        cmd = format_export_command(
            token=context.token,
            channel_id=channel_info.channel_id,
            output_path=str(output_path),
            format_type=format_map[fmt],
            after_timestamp=after_timestamp,
            media_config=media_config,
        )

        success, output = run_export(cmd)

        if success:
            exports_completed += 1
            print(f"    ✓ {fmt.upper()}")
        else:
            failures += 1
            errors.append({"channel": channel_info.channel_name, "format": fmt, "error": output})
            print(f"    ✗ {fmt.upper()} failed")

    return exports_completed, failures, errors


def _update_channel_state_after_export(
    context: ChannelExportContext,
    channel_type: ChannelType,
    channel_info: ChannelInfo,
) -> None:
    """Update state after successful channel export.

    Args:
        context: Export context with state manager
        channel_type: Type of channel
        channel_info: Channel information
    """
    if channel_type == ChannelType.THREAD:
        thread_info = ThreadInfo(
            thread_id=channel_info.channel_id,
            thread_name=channel_info.safe_name,
            thread_title=channel_info.channel_name,
            last_message_id=None,  # Could extract from export
            archived=False,  # Could detect from channel data
        )
        context.state_manager.update_thread_state(
            server=context.server_key,
            forum=channel_info.forum_name,
            thread_info=thread_info,
        )
    else:
        context.state_manager.update_channel(
            context.server_key,
            channel_info.channel_name,
            datetime.now(UTC).isoformat(),
            "placeholder_message_id",
        )


def _process_single_channel(  # noqa: PLR0913  # Orchestration function needs all context
    context: ChannelExportContext,
    channel: dict[str, str | None],
    channel_type: ChannelType,
    server_dir: Path,
    filters: tuple[list[str], list[str]],  # (include_patterns, exclude_patterns)
    channel_path_map: dict[str, str],
) -> tuple[int, int, int, list[dict[str, str]]]:
    """Process and export a single channel.

    Args:
        context: Export context
        channel: Channel data
        channel_type: Type of channel
        server_dir: Server export directory
        filters: Tuple of (include_patterns, exclude_patterns) for filtering
        channel_path_map: Dict mapping channel names to their full hierarchical paths

    Returns:
        Tuple of (total_exports, channels_updated, channels_failed, errors)
    """
    include_patterns, exclude_patterns = filters
    channel_name_raw = channel.get("name")
    channel_id_raw = channel.get("id")

    # Skip malformed channels
    if not channel_name_raw or not channel_id_raw:
        return 0, 0, 0, []

    channel_name: str = channel_name_raw
    channel_id: str = channel_id_raw

    # Skip forum parent channels (only export their threads)
    if channel_type == ChannelType.FORUM:
        forum_dir = server_dir / channel_name
        forum_dir.mkdir(exist_ok=True)
        print(f"  Created forum directory: {channel_name}/")
        return 0, 0, 0, []

    # Determine export location based on channel type
    safe_name, export_dir, forum_name = _determine_export_location(
        channel, channel_type, channel_id, server_dir, channel_path_map
    )
    export_name = safe_name

    # Apply include/exclude filters to channel names
    if not should_include_channel(channel_name, include_patterns, exclude_patterns):
        print(f"  Skipping {channel_name} (excluded by pattern)")
        return 0, 0, 0, []

    print(f"  Exporting #{channel_name}...")

    # Create channel info object
    channel_info = ChannelInfo(
        channel_id=channel_id,
        channel_name=channel_name,
        safe_name=safe_name,
        forum_name=forum_name,
    )

    # Get last export time for incremental updates
    after_timestamp = _get_last_export_timestamp(
        context, channel_type, channel_name, channel_id, forum_name
    )

    # Export all configured formats
    exports_completed, failures, errors = _export_channel_formats(
        context, channel_info, export_dir, export_name, after_timestamp
    )

    # Update state if no failures occurred
    if failures == 0:
        _update_channel_state_after_export(context, channel_type, channel_info)
        return exports_completed, 1, 0, errors
    else:
        return exports_completed, 0, failures, errors


def get_bot_token() -> str:
    """Get Discord bot token from environment.

    Returns:
        Bot token string

    Raises:
        ValueError: If DISCORD_BOT_TOKEN not set
    """
    token = os.environ.get("DISCORD_BOT_TOKEN")
    if not token:
        raise ValueError(
            "DISCORD_BOT_TOKEN environment variable not set. "
            "Add bot token to GitHub Secrets or export locally."
        )
    return token


def should_include_channel(
    channel_name: str, include_patterns: list[str], exclude_patterns: list[str]
) -> bool:
    """Check if channel should be included based on patterns.

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
    if "*" in include_patterns:
        return True

    for pattern in include_patterns:
        if fnmatch.fnmatch(channel_name, pattern):
            return True

    return False


def format_export_command(  # noqa: PLR0913
    token: str,
    channel_id: str,
    output_path: str,
    format_type: str,
    after_timestamp: str | None = None,
    media_config: MediaConfig | None = None,
) -> list[str]:
    """Format DiscordChatExporter CLI command.

    Args:
        token: Discord bot token
        channel_id: Channel ID to export
        output_path: Output file path
        format_type: Export format (HtmlDark, HtmlLight, PlainText, Json, Csv)
        after_timestamp: Optional timestamp for incremental export
        media_config: Media download configuration

    Returns:
        Command as list of arguments

    Raises:
        ValueError: If format_type is invalid or channel_id is not numeric
    """
    # Validate format_type
    valid_formats = {"HtmlDark", "HtmlLight", "PlainText", "Json", "Csv"}
    if format_type not in valid_formats:
        raise ValueError(
            f"Invalid format_type '{format_type}'. "
            f"Must be one of: {', '.join(sorted(valid_formats))}"
        )

    # Validate channel_id is numeric
    if not channel_id.isdigit():
        raise ValueError(f"Invalid channel_id '{channel_id}'. Must be numeric (digits only).")

    cmd = [
        "bin/discord-exporter/DiscordChatExporter.Cli",
        "export",
        "-t",
        token,
        "-c",
        channel_id,
        "-f",
        format_type,
        "-o",
        output_path,
    ]

    if after_timestamp:
        cmd.extend(["--after", after_timestamp])

    # Add media download flags if enabled
    if media_config and media_config.download_media:
        cmd.append("--media")

        if media_config.media_dir:
            cmd.extend(["--media-dir", media_config.media_dir])

        if media_config.reuse_media:
            cmd.append("--reuse-media")

    return cmd


def run_export(cmd: list[str], timeout: int = 300) -> tuple[bool, str]:
    """Run DiscordChatExporter command.

    Args:
        cmd: Command as list
        timeout: Timeout in seconds

    Returns:
        Tuple of (success, output)
    """
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

        success = result.returncode == 0
        output = result.stdout + result.stderr

        return success, output

    except subprocess.TimeoutExpired:
        return False, f"Export timed out after {timeout} seconds"
    except Exception as e:
        return False, f"Export failed: {str(e)}"


def _parse_channel_line(line: str) -> dict[str, str | None] | None:
    """Parse a single channel line from DiscordChatExporter output.

    Args:
        line: Output line from DiscordChatExporter

    Returns:
        Channel dict with 'name', 'id', and 'parent_id' keys, or None if invalid
    """
    # Remove thread indicator if present
    line = line.lstrip(" *").strip()

    # Split by pipe to get channel ID and name
    if "|" not in line:
        return None

    parts = line.split("|")
    if len(parts) < MIN_PIPE_PARTS:
        return None

    channel_id = parts[0].strip()
    name_part = parts[1].strip()

    # For threads, there may be a third part (status), ignore it
    # Extract category and channel name from the name part
    parent_id = None
    if "/" in name_part:
        name_parts = name_part.split("/")
        if len(name_parts) >= CHANNEL_PATH_PARTS:
            parent_id = name_parts[0].strip()
            channel_name = name_parts[1].strip()
        else:
            channel_name = name_parts[-1].strip()
    else:
        channel_name = name_part

    return {"name": channel_name, "id": channel_id, "parent_id": parent_id}


def fetch_guild_channels(  # noqa: C901  # Complex parsing of DiscordChatExporter output
    token: str, guild_id: str, include_threads: bool = True
) -> tuple[list[dict[str, str | None]], dict[str, str]]:
    """Fetch all channels from a Discord guild using DiscordChatExporter.

    Args:
        token: Discord bot token
        guild_id: Guild (server) ID
        include_threads: Whether to include threads (default: True)

    Returns:
        Tuple of:
            - List of channel dicts with 'name', 'id', and 'parent_id' keys
            - Dict mapping channel names to their full hierarchical paths

    Raises:
        RuntimeError: If channel fetching fails
    """
    cmd = ["bin/discord-exporter/DiscordChatExporter.Cli", "channels", "-t", token, "-g", guild_id]

    if include_threads:
        cmd.extend(["--include-threads", "All"])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            raise RuntimeError(f"Failed to fetch channels: {result.stderr or result.stdout}")

        # Parse output - DiscordChatExporter outputs one channel per line
        # Format: "ChannelID | Category / ChannelName" or "ChannelID | ChannelName"
        # Threads: " * ChannelID | Thread / ThreadName | Status"
        channels = []
        channel_path_map: dict[str, str] = {}  # Maps channel name to full path
        current_parent_channel = None

        for line in result.stdout.strip().split("\n"):
            if not line or not line.strip():
                continue

            # Check if this is a thread (starts with " * ")
            is_thread = line.lstrip().startswith("* ")

            channel = _parse_channel_line(line)
            if channel:
                # If this is a thread and parent_id is "Thread", replace with actual parent
                if is_thread and channel["parent_id"] == "Thread" and current_parent_channel:
                    channel["parent_id"] = current_parent_channel

                channels.append(channel)

                # Update current parent for next threads (only for non-thread channels)
                if not is_thread:
                    current_parent_channel = channel["name"]

                    # Build channel path map for hierarchical channels
                    # If channel has a parent_id (category/forum structure), store full path
                    if channel["parent_id"]:
                        parent = channel["parent_id"]
                        name = channel["name"]
                        channel_path_map[name] = f"{parent}/{name}"
                    else:
                        channel_path_map[channel["name"]] = channel["name"]

        return channels, channel_path_map

    except subprocess.TimeoutExpired as e:
        raise RuntimeError("Channel fetching timed out after 30 seconds") from e
    except Exception as e:
        raise RuntimeError(f"Channel fetching failed: {str(e)}") from e


def export_all_channels() -> dict[str, Any]:
    """Main export orchestration function.

    Loads configuration, initializes state manager, and orchestrates
    export of all channels from all configured servers.

    Returns:
        Summary dict with stats:
            - channels_updated: Number of channels successfully exported
            - channels_failed: Number of channels that failed export
            - total_exports: Total number of format exports completed
            - errors: List of error dicts with channel, format, and error details
    """
    print("Loading configuration...")
    config = load_config()

    token = get_bot_token()
    state_manager = StateManager()
    state_manager.load()

    summary: dict[str, Any] = {
        "channels_updated": 0,
        "channels_failed": 0,
        "total_exports": 0,
        "errors": [],
    }

    # Create exports directory
    exports_dir = Path("exports")
    exports_dir.mkdir(exist_ok=True)

    # Media downloads enabled - assets stored per-channel in {channel_name}_media/
    if config["export"].get("download_media", False):
        print("Media downloads enabled - assets will be stored per-channel")

    print("\nStarting exports...")

    for server_key, server_config in config["servers"].items():
        print(f"\nProcessing server: {server_config['name']}")

        # Create export context for this server
        context = ChannelExportContext(
            config=config,
            token=token,
            server_key=server_key,
            state_manager=state_manager,
        )

        server_dir = exports_dir / server_key
        server_dir.mkdir(exist_ok=True)

        # Fetch channels dynamically from Discord
        try:
            print("  Fetching channels from Discord...")
            include_threads = config["export"].get("include_threads", "all").lower() == "all"
            channels, channel_path_map = fetch_guild_channels(
                token, server_config["guild_id"], include_threads
            )
            print(f"  Found {len(channels)} channels")
        except RuntimeError as e:
            print(f"  ERROR: {e}")
            summary["errors"].append(
                {"channel": "N/A", "format": "N/A", "error": f"Failed to fetch channels: {e}"}
            )
            continue

        include_patterns = server_config["include_channels"]
        exclude_patterns = server_config["exclude_channels"]
        forum_list = server_config.get("forum_channels", [])

        # Classify all channels
        channel_classifications: dict[str, ChannelType] = {}
        for channel in channels:
            chan_id = channel.get("id")
            if not chan_id:
                continue
            channel_type = classify_channel(channel, forum_list, channels)
            channel_classifications[chan_id] = channel_type

        # Process each channel
        filters = (include_patterns, exclude_patterns)
        for channel in channels:
            chan_id = channel.get("id")
            if not chan_id:
                continue

            channel_type = channel_classifications[chan_id]

            exports, updated, failed, errors = _process_single_channel(
                context, channel, channel_type, server_dir, filters, channel_path_map
            )

            summary["total_exports"] += exports
            summary["channels_updated"] += updated
            summary["channels_failed"] += failed
            summary["errors"].extend(errors)

    # Save state
    state_manager.save()

    return summary


def main() -> None:
    """Entry point for export script."""
    print("Discord Channel Exporter")
    print("=" * 50)

    try:
        summary = export_all_channels()

        print("\n" + "=" * 50)
        print("Export Summary:")
        print(f"  Channels updated: {summary['channels_updated']}")
        print(f"  Channels failed: {summary['channels_failed']}")
        print(f"  Total exports: {summary['total_exports']}")

        if summary["errors"]:
            print(f"\nErrors ({len(summary['errors'])}):")
            for error in summary["errors"]:  # Show all errors
                # Print full error message, with continuation lines indented
                error_lines = error['error'].splitlines()
                print(f"  - {error['channel']} ({error['format']}):")
                for line in error_lines:
                    print(f"    {line}")

        sys.exit(0 if summary["channels_failed"] == 0 else 1)

    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
