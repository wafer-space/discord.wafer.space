# scripts/export_channels.py
"""Export Discord channels using DiscordChatExporter CLI."""

import fnmatch
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.channel_classifier import ChannelType, classify_channel, sanitize_thread_name
from scripts.config import load_config
from scripts.months import (
    current_month_utc,
    month_bounds,
    month_range_iter,
    scan_completed_months,
    snowflake_to_month,
)
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
    """Determine the per-channel export directory and the safe name.

    Returns a tuple of (safe_name, channel_export_dir, forum_name):

      - `safe_name`: filesystem-safe identifier for this channel/thread
      - `channel_export_dir`: the directory inside `exports/` where this
        channel's per-month files (`{YYYY-MM}.html` etc.) will be written.
        For regular channels this is `exports/server/{channel}/`; for
        threads it is `exports/server/{forum_path}/{thread}/`.
      - `forum_name`: the parent forum's full path for threads, or ""
    """
    if channel_type == ChannelType.THREAD:
        forum_name_raw = channel.get("parent_id")
        forum_name_simple: str = forum_name_raw if forum_name_raw else "unknown-forum"

        # Look up the full hierarchical path for the forum
        # If forum is "cob" inside "🏗️ - Designing", path_map will have "cob" -> "🏗️ - Designing/cob"
        forum_full_path = channel_path_map.get(forum_name_simple, forum_name_simple)

        channel_name_raw = channel.get("name")
        safe_name = sanitize_thread_name(
            channel_name_raw if channel_name_raw else "unknown", channel_id
        )
        # Per-month files go into exports/server/forum/thread-name/
        thread_export_dir = server_dir / forum_full_path / safe_name
        thread_export_dir.mkdir(parents=True, exist_ok=True)
        return safe_name, thread_export_dir, forum_full_path
    else:
        # Regular channel
        channel_name_raw = channel.get("name")
        channel_name = channel_name_raw if channel_name_raw else "unknown"
        # Per-month files go into exports/server/channel-name/
        channel_export_dir = server_dir / channel_name
        channel_export_dir.mkdir(parents=True, exist_ok=True)
        return channel_name, channel_export_dir, ""


def _public_channel_dir(
    public_dir: Path,
    server_key: str,
    channel_type: ChannelType,
    safe_name: str,
    forum_name: str,
) -> Path:
    """Return the published location for a channel, where past months live.

    Used to scan for already-exported months so we don't re-export them.
    """
    if channel_type == ChannelType.THREAD:
        return public_dir / server_key / forum_name / safe_name
    return public_dir / server_key / safe_name


def _determine_months_to_export(
    channel_id: str,
    public_channel_dir: Path,
    current_month: str,
) -> list[str]:
    """Decide which months need to be exported for a channel.

    Returns months with the current month FIRST, then any missing past
    months oldest-to-newest. Current-first matters because the first run
    after a long outage has a lot of backfill work and may not finish in
    one workflow window — by exporting the current month first for every
    channel, we guarantee the user-visible state is fresh even if a
    backfill gets interrupted, and subsequent runs resume the backfill
    without losing currency.

    Strategy:

      - The earliest possible month for any messages is bounded by the
        channel's creation time, which we decode from its snowflake.
      - Past months that already have a non-empty HTML export in
        `public_channel_dir` AND whose JSON is month-pure are considered
        complete and skipped.
      - The current month is always included.
    """
    earliest = snowflake_to_month(channel_id)
    completed = scan_completed_months(public_channel_dir)
    past_months = [
        month
        for month in month_range_iter(earliest, current_month)
        if month != current_month and month not in completed
    ]
    # Current month first, then oldest past month -> newest past month.
    return [current_month, *past_months]


FORMAT_MAP = {"html": "HtmlDark", "txt": "PlainText", "json": "Json", "csv": "Csv"}


def _export_one_month(
    context: ChannelExportContext,
    channel_info: ChannelInfo,
    channel_export_dir: Path,
    month: str,
    is_current_month: bool,
) -> tuple[int, int, list[dict[str, str]]]:
    """Export a single month of a channel in all configured formats.

    The month is bracketed by --after / --before so DCE returns exactly
    the messages from this calendar month UTC. For the current month
    --before is omitted so newly-arrived messages are included.

    Output paths inside `channel_export_dir`:
      - `{month}.html`, `{month}.txt`, `{month}.json`, `{month}.csv`
      - `{month}_media/` for downloaded assets

    Returns (exports_completed, failures, errors).
    """
    after, before_bound = month_bounds(month)
    # For the current month we omit --before so newly-arrived messages are
    # included (DCE captures everything from `after` up to its API "now").
    before: str | None = None if is_current_month else before_bound

    media_dir_path = channel_export_dir / f"{month}_media"
    download_media = context.config["export"].get("download_media", False)

    exports_completed = 0
    failures = 0
    errors: list[dict[str, str]] = []

    print(f"    [{month}]")
    for fmt in context.config["export"]["formats"]:
        output_path = channel_export_dir / f"{month}.{fmt}"

        media_config = MediaConfig(
            download_media=download_media,
            media_dir=str(media_dir_path) if download_media else None,
            reuse_media=context.config["export"].get("reuse_media", False),
        )

        cmd = format_export_command(
            token=context.token,
            channel_id=channel_info.channel_id,
            output_path=str(output_path),
            format_type=FORMAT_MAP[fmt],
            after_timestamp=after,
            before_timestamp=before,
            media_config=media_config,
        )

        success, output = run_export(cmd)

        if success:
            exports_completed += 1
            print(f"      ✓ {fmt.upper()}")
        else:
            failures += 1
            errors.append(
                {
                    "channel": channel_info.channel_name,
                    "format": f"{month}/{fmt}",
                    "error": output,
                }
            )
            print(f"      ✗ {fmt.upper()} failed")

    # If no messages exist for this past month, DCE will have written empty
    # outputs that we don't want to keep — they'd just clutter public/. We
    # detect this via the JSON's messageCount and clean up the month.
    if exports_completed > 0 and not is_current_month:
        _discard_if_empty_month(channel_export_dir, month)

    return exports_completed, failures, errors


def _discard_if_empty_month(channel_export_dir: Path, month: str) -> None:
    """Delete a month's output files if the JSON shows zero messages.

    Past months with no messages are noise. The current month is always
    kept (the channel might be silent right now but get a message tomorrow).
    """
    import json as _json

    json_path = channel_export_dir / f"{month}.json"
    if not json_path.exists():
        return
    try:
        with open(json_path, encoding="utf-8") as f:
            data = _json.load(f)
    except (OSError, _json.JSONDecodeError):
        return
    messages = data.get("messages") or []
    if messages:
        return

    # Remove all formats and the media directory for this month
    for fmt in ("html", "txt", "json", "csv"):
        f_path = channel_export_dir / f"{month}.{fmt}"
        if f_path.exists():
            f_path.unlink()
    media_dir = channel_export_dir / f"{month}_media"
    if media_dir.exists() and media_dir.is_dir():
        import shutil as _shutil

        _shutil.rmtree(media_dir)
    print(f"      (empty — discarded {month})")


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


def _process_single_channel(  # noqa: PLR0913,PLR0911  # Orchestration needs all context
    context: ChannelExportContext,
    channel: dict[str, str | None],
    channel_type: ChannelType,
    server_dir: Path,
    filters: tuple[list[str], list[str]],  # (include_patterns, exclude_patterns)
    channel_path_map: dict[str, str],
    public_dir: Path,
) -> tuple[int, int, int, list[dict[str, str]]]:
    """Process and export a single channel, one calendar month at a time.

    The earliest possible month is derived from the channel snowflake. Past
    months that already have a non-empty HTML export in `public_dir` are
    skipped (Discord doesn't backdate messages, so a complete month stays
    complete). The current month is always re-exported.

    Returns (total_exports, channels_updated, channels_failed, errors).
    """
    include_patterns, exclude_patterns = filters
    channel_name_raw = channel.get("name")
    channel_id_raw = channel.get("id")

    # Skip malformed channels
    if not channel_name_raw or not channel_id_raw:
        return 0, 0, 0, []

    channel_name: str = channel_name_raw
    channel_id: str = channel_id_raw

    # Forum parent channels have no messages of their own — their threads
    # are exported separately.
    if channel_type == ChannelType.FORUM:
        forum_dir = server_dir / channel_name
        forum_dir.mkdir(exist_ok=True)
        print(f"  Created forum directory: {channel_name}/")
        return 0, 0, 0, []

    # Determine export location and the matching public/ path
    safe_name, channel_export_dir, forum_name = _determine_export_location(
        channel, channel_type, channel_id, server_dir, channel_path_map
    )

    # Apply include/exclude filters
    if not should_include_channel(channel_name, include_patterns, exclude_patterns):
        print(f"  Skipping {channel_name} (excluded by pattern)")
        return 0, 0, 0, []

    print(f"  Exporting #{channel_name}...")

    channel_info = ChannelInfo(
        channel_id=channel_id,
        channel_name=channel_name,
        safe_name=safe_name,
        forum_name=forum_name,
    )

    # Discover which months still need exporting
    public_channel_dir = _public_channel_dir(
        public_dir, context.server_key, channel_type, safe_name, forum_name
    )
    current_month = current_month_utc()
    try:
        months_to_export = _determine_months_to_export(
            channel_id, public_channel_dir, current_month
        )
    except ValueError as e:
        print(f"    ERROR computing months: {e}")
        return 0, 0, 1, [{"channel": channel_name, "format": "N/A", "error": str(e)}]

    if not months_to_export:
        print("    (no months need export)")
        return 0, 1, 0, []

    range_label = f"{months_to_export[0]}..{months_to_export[-1]}"
    print(f"    {len(months_to_export)} months to export: {range_label}")

    total_exports = 0
    total_failures = 0
    all_errors: list[dict[str, str]] = []

    for month in months_to_export:
        is_current = month == current_month
        m_exports, m_failures, m_errors = _export_one_month(
            context, channel_info, channel_export_dir, month, is_current
        )
        total_exports += m_exports
        total_failures += m_failures
        all_errors.extend(m_errors)

    # Update state with the last-export timestamp for observability
    _update_channel_state_after_export(context, channel_type, channel_info)

    if total_failures == 0:
        return total_exports, 1, 0, all_errors
    return total_exports, 0, total_failures, all_errors


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
    before_timestamp: str | None = None,
) -> list[str]:
    """Format DiscordChatExporter CLI command.

    Args:
        token: Discord bot token
        channel_id: Channel ID to export
        output_path: Output file path
        format_type: Export format (HtmlDark, HtmlLight, PlainText, Json, Csv)
        after_timestamp: Optional timestamp for incremental export
        media_config: Media download configuration
        before_timestamp: Optional upper-bound timestamp; paired with
            after_timestamp to bracket a single calendar month

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

    if before_timestamp:
        cmd.extend(["--before", before_timestamp])

    # Add media download flags if enabled
    if media_config and media_config.download_media:
        cmd.append("--media")

        if media_config.media_dir:
            cmd.extend(["--media-dir", media_config.media_dir])

        if media_config.reuse_media:
            cmd.append("--reuse-media")

    return cmd


def run_export(cmd: list[str], timeout: int = 900) -> tuple[bool, str]:
    """Run DiscordChatExporter command.

    Args:
        cmd: Command as list
        timeout: Timeout in seconds (default: 900 = 15 minutes for large channels)

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
                    name = channel["name"]
                    if name is not None:
                        if channel["parent_id"]:
                            parent = channel["parent_id"]
                            channel_path_map[name] = f"{parent}/{name}"
                        else:
                            channel_path_map[name] = name

        return channels, channel_path_map

    except subprocess.TimeoutExpired as e:
        raise RuntimeError("Channel fetching timed out after 30 seconds") from e
    except Exception as e:
        raise RuntimeError(f"Channel fetching failed: {str(e)}") from e


def export_all_channels(  # noqa: C901,PLR0915  # Orchestration top-level
    public_dir: Path | None = None,
    max_runtime_seconds: int | None = None,
) -> dict[str, Any]:
    """Main export orchestration function.

    Loads configuration, initializes state manager, and orchestrates
    per-month exports for all channels from all configured servers.

    `public_dir` is consulted to decide which past months are already
    complete; pass `Path("public")` in production (the GitHub Actions
    workflow checks out gh-pages into that directory before running this).

    `max_runtime_seconds` lets us stop gracefully before the workflow
    timeout — important on the first run after a long outage when there's
    a lot of backfill to do. When the budget is exhausted we still write a
    summary, save state, and exit 0 so the workflow can deploy what we have.
    The next workflow invocation will pick up the remaining months because
    `scan_completed_months` already knows which months are done.

    Returns a summary dict with `channels_updated`, `channels_failed`,
    `total_exports`, `errors`, and `time_budget_exhausted`.
    """
    if public_dir is None:
        public_dir = Path("public")

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
        "time_budget_exhausted": False,
    }

    # Create exports directory
    exports_dir = Path("exports")
    exports_dir.mkdir(exist_ok=True)

    # Media downloads enabled - assets stored per-channel/per-month
    if config["export"].get("download_media", False):
        print("Media downloads enabled - assets will be stored per-channel-per-month")

    start = time.monotonic()

    def out_of_time() -> bool:
        return max_runtime_seconds is not None and time.monotonic() - start > max_runtime_seconds

    print(f"\nStarting exports (current month: {current_month_utc()})...")
    if max_runtime_seconds:
        print(f"Time budget: {max_runtime_seconds} seconds")

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
            if out_of_time():
                summary["time_budget_exhausted"] = True
                print(
                    f"\n  TIME BUDGET EXHAUSTED after "
                    f"{int(time.monotonic() - start)}s — stopping gracefully. "
                    "Next workflow run will resume backfill."
                )
                break

            chan_id = channel.get("id")
            if not chan_id:
                continue

            channel_type = channel_classifications[chan_id]

            exports, updated, failed, errors = _process_single_channel(
                context,
                channel,
                channel_type,
                server_dir,
                filters,
                channel_path_map,
                public_dir,
            )

            summary["total_exports"] += exports
            summary["channels_updated"] += updated
            summary["channels_failed"] += failed
            summary["errors"].extend(errors)
        else:
            # No `break` happened, continue to next server
            continue
        # We broke out due to time budget — also break the server loop
        break

    # Save state
    state_manager.save()

    return summary


def main() -> None:
    """Entry point for export script."""
    print("Discord Channel Exporter")
    print("=" * 50)

    # The workflow caps the job at 240 minutes. We give the script a slightly
    # smaller budget so it can stop gracefully and let organize/navigate/deploy
    # publish whatever was completed.
    budget_str = os.environ.get("EXPORT_MAX_RUNTIME_SECONDS")
    max_runtime = int(budget_str) if budget_str else None

    try:
        summary = export_all_channels(max_runtime_seconds=max_runtime)

        print("\n" + "=" * 50)
        print("Export Summary:")
        print(f"  Channels updated: {summary['channels_updated']}")
        print(f"  Channels failed: {summary['channels_failed']}")
        print(f"  Total exports: {summary['total_exports']}")
        if summary.get("time_budget_exhausted"):
            print("  NOTE: stopped early due to time budget; backfill resumes next run")

        if summary["errors"]:
            print(f"\nErrors ({len(summary['errors'])}):")
            for error in summary["errors"]:  # Show all errors
                # Print full error message, with continuation lines indented
                error_lines = error["error"].splitlines()
                print(f"  - {error['channel']} ({error['format']}):")
                for line in error_lines:
                    print(f"    {line}")

        # Write a machine-readable summary so the workflow can decide what to do
        _write_summary_file(summary)

        # Exit code policy: exit 0 if we made any progress (including a clean
        # "nothing to do" run), so the workflow can proceed to organize/deploy
        # what we have. Exit 1 only on catastrophic failure where nothing
        # succeeded and we hit at least one error — that signals "drop tools
        # and investigate."
        catastrophic = summary["channels_updated"] == 0 and summary["channels_failed"] > 0
        sys.exit(1 if catastrophic else 0)

    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


def _write_summary_file(summary: dict[str, Any]) -> None:
    """Write a JSON summary of the run for downstream workflow steps to read."""
    import json as _json

    summary_path = Path("export-summary.json")
    try:
        with open(summary_path, "w", encoding="utf-8") as f:
            _json.dump(
                {
                    "channels_updated": summary["channels_updated"],
                    "channels_failed": summary["channels_failed"],
                    "total_exports": summary["total_exports"],
                    "error_count": len(summary["errors"]),
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                f,
                indent=2,
            )
    except OSError as e:
        print(f"WARNING: could not write export-summary.json: {e}")


if __name__ == "__main__":
    main()
