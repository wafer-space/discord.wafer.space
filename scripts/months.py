"""Month range computation and Discord snowflake conversion.

This module provides the primitives used by the export pipeline to do
correct month-based partitioning:

  - `month_bounds(month)` returns the (--after, --before) timestamps to pass
    to DiscordChatExporter such that the resulting export contains exactly
    the messages from that calendar month (UTC).
  - `month_range_iter(start, end)` iterates over the months in a closed
    range, used to backfill missing months.
  - `snowflake_to_datetime(snowflake)` decodes Discord's 64-bit snowflake ID
    to its creation timestamp; combined with `snowflake_to_month()` it gives
    us a cheap, no-API-call way to know the earliest possible month for a
    channel.
"""

import re
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Discord uses 2015-01-01T00:00:00.000 UTC as the epoch for its snowflake IDs.
# https://discord.com/developers/docs/reference#snowflakes
DISCORD_EPOCH_MS = 1420070400000

# Snowflakes are 64-bit integers; the top 42 bits encode milliseconds since
# the Discord epoch. The bottom 22 bits encode worker/process/sequence info.
SNOWFLAKE_TIMESTAMP_SHIFT = 22

# December wraps to January of the next year when stepping forward by one.
LAST_MONTH = 12

# YYYY-MM matches a 4-digit year, hyphen, 2-digit month (01-12).
_MONTH_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


def _parse_month(month: str) -> tuple[int, int]:
    """Parse a "YYYY-MM" string into (year, month) ints.

    Raises ValueError if the format or month value is invalid.
    """
    match = _MONTH_RE.match(month)
    if not match:
        raise ValueError(f"Invalid month {month!r}: must be 'YYYY-MM' with month 01-12")
    return int(match.group(1)), int(match.group(2))


def month_bounds(month: str) -> tuple[str, str]:
    """Return (--after, --before) ISO timestamps that bracket exactly `month`.

    DiscordChatExporter treats both --after and --before as exclusive bounds,
    so we use:
      - after  = one microsecond before the first instant of `month`
      - before = the first instant of the month after `month`

    This ensures messages at the exact boundary (midnight UTC of day 1) are
    included regardless of which side of the boundary DCE rounds to.
    """
    year, mon = _parse_month(month)
    start = datetime(year, mon, 1, tzinfo=timezone.utc)
    # First instant of the month after `month`.
    next_year, next_mon = (year + 1, 1) if mon == LAST_MONTH else (year, mon + 1)
    end = datetime(next_year, next_mon, 1, tzinfo=timezone.utc)
    # Subtract 1 microsecond so the after-bound is exclusive-just-before-start.
    after = (start - timedelta(microseconds=1)).isoformat()
    before = end.isoformat()
    return after, before


def month_range_iter(start_month: str, end_month: str) -> Iterator[str]:
    """Yield each month string from start to end inclusive, in order.

    If end is before start, yields nothing (rather than raising) — this lets
    callers safely use it as `for m in month_range_iter(first, current)`
    even on a fresh channel where the two are reversed.
    """
    start_year, start_mon = _parse_month(start_month)
    end_year, end_mon = _parse_month(end_month)
    year, mon = start_year, start_mon
    while (year, mon) <= (end_year, end_mon):
        yield f"{year:04d}-{mon:02d}"
        year, mon = (year + 1, 1) if mon == LAST_MONTH else (year, mon + 1)


def snowflake_to_datetime(snowflake: str) -> datetime:
    """Decode a Discord snowflake ID to its creation datetime (UTC).

    Raises ValueError if the snowflake is not a numeric string.
    """
    if not snowflake.isdigit():
        raise ValueError(f"Snowflake must be numeric, got {snowflake!r}")
    timestamp_ms = (int(snowflake) >> SNOWFLAKE_TIMESTAMP_SHIFT) + DISCORD_EPOCH_MS
    return datetime.fromtimestamp(timestamp_ms / 1000.0, tz=timezone.utc)


def snowflake_to_month(snowflake: str) -> str:
    """Return the YYYY-MM month string when the snowflake was created."""
    dt = snowflake_to_datetime(snowflake)
    return dt.strftime("%Y-%m")


def current_month_utc() -> str:
    """Return the current month in UTC as a YYYY-MM string."""
    return datetime.now(timezone.utc).strftime("%Y-%m")


def is_month_dir_name(name: str) -> bool:
    """Return True iff `name` is a YYYY-MM string with a valid month (01-12)."""
    return bool(_MONTH_RE.match(name))


def scan_completed_months(channel_dir: Path) -> set[str]:
    """Return the set of YYYY-MM months that already have a non-empty HTML export.

    The HTML file is the user-visible deliverable, so we treat its presence
    (with non-zero size) as the signal that a month has been successfully
    exported. Other formats (txt/json/csv) might be regenerable, but if the
    HTML is missing the month is not "done".
    """
    if not channel_dir.exists() or not channel_dir.is_dir():
        return set()
    completed: set[str] = set()
    for entry in channel_dir.iterdir():
        if not entry.is_dir() or not is_month_dir_name(entry.name):
            continue
        html_file = entry / f"{entry.name}.html"
        if html_file.exists() and html_file.stat().st_size > 0:
            completed.add(entry.name)
    return completed
