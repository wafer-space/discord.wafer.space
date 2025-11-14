# scripts/export_channels.py
"""Export Discord channels using DiscordChatExporter CLI."""
import fnmatch
import os
import subprocess
import sys
from pathlib import Path
from datetime import datetime, UTC
from typing import List, Optional, Dict, Tuple
from scripts.config import load_config
from scripts.state import StateManager

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
        "bin/discord-exporter/DiscordChatExporter.Cli", "export",
        "-t", token,
        "-c", channel_id,
        "-f", format_type,
        "-o", output_path
    ]

    if after_timestamp:
        cmd.extend(["--after", after_timestamp])

    return cmd


def run_export(
    cmd: List[str],
    timeout: int = 300
) -> Tuple[bool, str]:
    """
    Run DiscordChatExporter command.

    Args:
        cmd: Command as list
        timeout: Timeout in seconds

    Returns:
        Tuple of (success, output)
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        success = result.returncode == 0
        output = result.stdout + result.stderr

        return success, output

    except subprocess.TimeoutExpired:
        return False, f"Export timed out after {timeout} seconds"
    except Exception as e:
        return False, f"Export failed: {str(e)}"


def fetch_guild_channels(token: str, guild_id: str, include_threads: bool = True) -> List[Dict[str, str]]:
    """
    Fetch all channels from a Discord guild using DiscordChatExporter.

    Args:
        token: Discord bot token
        guild_id: Guild (server) ID
        include_threads: Whether to include threads (default: True)

    Returns:
        List of channel dicts with 'name', 'id', and 'parent_id' keys

    Raises:
        RuntimeError: If channel fetching fails
    """
    cmd = [
        "bin/discord-exporter/DiscordChatExporter.Cli", "channels",
        "-t", token,
        "-g", guild_id
    ]

    if include_threads:
        cmd.extend(["--include-threads", "All"])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to fetch channels: {result.stderr or result.stdout}"
            )

        # Parse output - DiscordChatExporter outputs one channel per line
        # Format: "Category / ChannelName [ChannelID]" or "ChannelName [ChannelID]"
        channels = []
        for line in result.stdout.strip().split('\n'):
            if not line or not line.strip():
                continue

            # Extract channel ID from brackets
            if '[' in line and ']' in line:
                channel_id = line.split('[')[-1].split(']')[0].strip()

                # Extract channel name (after last / or whole line before [)
                name_part = line.split('[')[0].strip()
                parent_id = None

                if '/' in name_part:
                    parts = name_part.split('/')
                    if len(parts) == 2:
                        parent_id = parts[0].strip()
                        channel_name = parts[1].strip()
                    else:
                        channel_name = parts[-1].strip()
                else:
                    channel_name = name_part

                channels.append({
                    'name': channel_name,
                    'id': channel_id,
                    'parent_id': parent_id
                })

        return channels

    except subprocess.TimeoutExpired:
        raise RuntimeError("Channel fetching timed out after 30 seconds")
    except Exception as e:
        raise RuntimeError(f"Channel fetching failed: {str(e)}")


def export_all_channels() -> Dict:
    """
    Main export orchestration function.

    Loads configuration, initializes state manager, and orchestrates
    export of all channels from all configured servers.

    Returns:
        Summary dict with stats:
            - channels_updated: Number of channels successfully exported
            - channels_failed: Number of channels that failed export
            - total_exports: Total number of format exports completed
            - errors: List of error dicts with channel, format, and error details
    """
    from scripts.channel_classifier import classify_channel, ChannelType, sanitize_thread_name

    print("Loading configuration...")
    config = load_config()

    token = get_bot_token()
    state_manager = StateManager()
    state_manager.load()

    summary = {
        'channels_updated': 0,
        'channels_failed': 0,
        'total_exports': 0,
        'errors': []
    }

    # Create exports directory
    exports_dir = Path("exports")
    exports_dir.mkdir(exist_ok=True)

    print(f"\nStarting exports...")

    for server_key, server_config in config['servers'].items():
        print(f"\nProcessing server: {server_config['name']}")

        server_dir = exports_dir / server_key
        server_dir.mkdir(exist_ok=True)

        # Fetch channels dynamically from Discord
        try:
            print(f"  Fetching channels from Discord...")
            include_threads = config['export'].get('include_threads', 'all').lower() == 'all'
            channels = fetch_guild_channels(token, server_config['guild_id'], include_threads)
            print(f"  Found {len(channels)} channels")
        except RuntimeError as e:
            print(f"  ERROR: {e}")
            summary['errors'].append({
                'channel': 'N/A',
                'format': 'N/A',
                'error': f"Failed to fetch channels: {e}"
            })
            continue

        include_patterns = server_config['include_channels']
        exclude_patterns = server_config['exclude_channels']
        forum_list = server_config.get('forum_channels', [])

        # Classify all channels
        channel_classifications = {}
        for channel in channels:
            channel_type = classify_channel(channel, forum_list, channels)
            channel_classifications[channel['id']] = channel_type

        channel_export_attempted = False

        for channel in channels:
            channel_name = channel['name']
            channel_id = channel['id']
            channel_type = channel_classifications[channel_id]

            # Skip forum parent channels (only export their threads)
            if channel_type == ChannelType.FORUM:
                # Create directory for forum
                forum_dir = server_dir / channel_name
                forum_dir.mkdir(exist_ok=True)
                print(f"  Created forum directory: {channel_name}/")
                continue

            # For threads, use sanitized name and forum directory
            if channel_type == ChannelType.THREAD:
                forum_name = channel.get('parent_id', 'unknown-forum')
                thread_dir = server_dir / forum_name
                thread_dir.mkdir(exist_ok=True)

                # Sanitize thread name for filename
                safe_name = sanitize_thread_name(channel_name, channel_id)
                export_name = safe_name
                export_dir = thread_dir
            else:
                # Regular channel
                export_name = channel_name
                export_dir = server_dir

            # Apply include/exclude filters to channel names
            if not should_include_channel(channel_name, include_patterns, exclude_patterns):
                print(f"  Skipping {channel_name} (excluded by pattern)")
                continue

            print(f"  Exporting #{channel_name}...")

            # Get last export time for incremental updates
            if channel_type == ChannelType.THREAD:
                # TODO: Thread state tracking (will implement in state management task)
                channel_state = None
            else:
                channel_state = state_manager.get_channel_state(server_key, channel_name)

            after_timestamp = channel_state['last_export'] if channel_state else None

            # Export all configured formats
            format_map = {
                'html': 'HtmlDark',
                'txt': 'PlainText',
                'json': 'Json',
                'csv': 'Csv'
            }

            channel_export_attempted = True
            channel_failed = False

            for fmt in config['export']['formats']:
                output_path = export_dir / f"{export_name}.{fmt}"

                cmd = format_export_command(
                    token=token,
                    channel_id=channel_id,
                    output_path=str(output_path),
                    format_type=format_map[fmt],
                    after_timestamp=after_timestamp
                )

                success, output = run_export(cmd)

                if success:
                    summary['total_exports'] += 1
                    print(f"    ✓ {fmt.upper()}")
                else:
                    channel_failed = True
                    summary['channels_failed'] += 1
                    summary['errors'].append({
                        'channel': channel_name,
                        'format': fmt,
                        'error': output
                    })
                    print(f"    ✗ {fmt.upper()} failed")

            # Update state with current timestamp
            # In real implementation, we'd parse the actual last message timestamp from export
            if not channel_failed and channel_type != ChannelType.THREAD:
                state_manager.update_channel(
                    server_key,
                    channel_name,
                    datetime.now(UTC).isoformat(),
                    "placeholder_message_id"
                )
                summary['channels_updated'] += 1

    # Save state
    state_manager.save()

    return summary


def main():
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

        if summary['errors']:
            print(f"\nErrors ({len(summary['errors'])}):")
            for error in summary['errors'][:5]:  # Show first 5
                print(f"  - {error['channel']} ({error['format']}): {error['error'][:100]}")

        sys.exit(0 if summary['channels_failed'] == 0 else 1)

    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
