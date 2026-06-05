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

# DCE HtmlDark minifies attributes (no quotes), so each rendered message is
# marked by `data-message-id=<snowflake>`. Counting these gives the number of
# messages actually shown on the page, which we compare against the JSON's
# message count to detect the issue-#1 JSON/HTML divergence.
_HTML_MESSAGE_RE = re.compile(rb"data-message-id=(\d+)")

# DCE renders dates per --locale: the en-CA fix produces ISO yyyy-MM-dd, while
# pre-fix exports produced US MM/dd/yyyy. We compare counts (not mere presence)
# so a stray date typed into a message never misclassifies an otherwise-ISO page.
_ISO_DATE_RE = re.compile(rb"\d{4}-\d{2}-\d{2}")
_US_DATE_RE = re.compile(rb"\d{1,2}/\d{1,2}/\d{4}")


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
    """Return the set of YYYY-MM months that are correctly partitioned.

    A month is "completed" only if:

      - the HTML file exists and is non-empty (user-visible deliverable), AND
      - the JSON's messages all belong to that month (no cross-contamination).

    The second check is essential for fixing legacy data: the previous
    implementation dumped messages from many months into a single
    current-month JSON, so `2025-11/2025-11.json` on the live site contains
    messages going back to 2025-04. We treat those as incomplete so they
    get re-exported properly partitioned. Once an honestly-partitioned
    export replaces them, this function returns "completed" for that month
    again on subsequent runs.
    """
    if not channel_dir.exists() or not channel_dir.is_dir():
        return set()
    completed: set[str] = set()
    for entry in channel_dir.iterdir():
        if not entry.is_dir() or not is_month_dir_name(entry.name):
            continue
        html_file = entry / f"{entry.name}.html"
        if not html_file.exists() or html_file.stat().st_size == 0:
            continue
        json_file = entry / f"{entry.name}.json"
        if json_file.exists():
            if not _json_is_month_pure(json_file, entry.name):
                continue
            # Complete only if the rendered HTML matches the JSON message count.
            # When they disagree (issue #1: the JSON drifted above what the HTML
            # renders), treat the month as incomplete so it re-exports and heals.
            if not _month_is_consistent(json_file, html_file):
                continue
        # Re-export months still rendered with American dates so they convert to
        # ISO (issue #3) — the --locale fix only reaches a month on re-export.
        if _html_uses_american_dates(html_file):
            continue
        completed.add(entry.name)
    return completed


# An empty DCE per-month JSON (0 messages) is the guild/channel/dateRange
# scaffold only — measured at ~487-522 bytes on the live archive. A month
# with even one message is multiple KB. 1500 bytes cleanly separates the
# two without parsing the file (a cheap os.stat), which matters when
# ranking hundreds of channels/threads by neediness every run.
EMPTY_MONTH_JSON_MAX_BYTES = 1500


def count_nonempty_months(channel_dir: Path) -> int:
    """Count months in `channel_dir` whose JSON is larger than an empty export.

    Used to rank backfill priority: an entry with 0 non-empty months is a
    "starved" channel/thread (only an empty current-month export exists)
    and must be backfilled before entries that already have real data.
    Uses file size (os.stat) rather than parsing — fast at scale.
    """
    if not channel_dir.exists() or not channel_dir.is_dir():
        return 0
    count = 0
    for entry in channel_dir.iterdir():
        if not entry.is_dir() or not is_month_dir_name(entry.name):
            continue
        json_file = entry / f"{entry.name}.json"
        try:
            if json_file.stat().st_size > EMPTY_MONTH_JSON_MAX_BYTES:
                count += 1
        except OSError:
            continue
    return count


def _json_is_month_pure(json_file: Path, month: str) -> bool:
    """Return True iff every message in the JSON is timestamped within `month`.

    Used to detect legacy mixed-month JSONs from the pre-refactor era. Edge
    cases (file missing/unreadable/malformed) return True so we don't flag
    files we can't introspect — the worst case is leaving a month alone when
    we could have re-exported it, which the user can resolve by deleting
    the directory if needed.
    """
    import json as _json

    try:
        with open(json_file, encoding="utf-8") as f:
            data = _json.load(f)
    except (OSError, _json.JSONDecodeError):
        return True

    messages = data.get("messages") or []
    if not messages:
        # Empty month is consistent with any month tag.
        return True

    for msg in messages:
        ts = msg.get("timestamp", "")
        # Timestamps look like "2026-02-23T05:01:27.918510+00:00" — the
        # first 7 chars are the YYYY-MM we compare against.
        if not isinstance(ts, str) or ts[:7] != month:
            return False
    return True


def count_html_messages(html_file: Path) -> int:
    """Count messages rendered in a DCE HtmlDark export.

    Each message container carries `data-message-id=<snowflake>` (DCE minifies
    attributes, so there are no quotes). Reading bytes keeps this fast on the
    multi-MB HTML of a busy month.
    """
    try:
        data = html_file.read_bytes()
    except OSError:
        return 0
    return len(_HTML_MESSAGE_RE.findall(data))


def _html_uses_american_dates(html_file: Path) -> bool:
    """True if the HTML's dominant date format is US MM/DD/YYYY rather than ISO.

    A pre-`--locale en-CA` export rendered dates American-style and must be
    re-exported to convert to ISO (issue #3), since the date fix only reaches a
    month on re-export. We compare US vs ISO date counts so a single date typed
    into a message never flips an otherwise-ISO page.
    """
    try:
        data = html_file.read_bytes()
    except OSError:
        return False
    return len(_US_DATE_RE.findall(data)) > len(_ISO_DATE_RE.findall(data))


def _month_is_consistent(json_file: Path, html_file: Path) -> bool:
    """True iff the JSON message count equals the count rendered in the HTML.

    The published JSON drives the index/navigation message count; the HTML is
    the page a reader sees. When they disagree (issue #1) the month must be
    re-exported. Unreadable/malformed files return True so we don't force a
    re-export we cannot reason about.
    """
    import json as _json

    try:
        with open(json_file, encoding="utf-8") as f:
            json_count = len(_json.load(f).get("messages") or [])
    except (OSError, _json.JSONDecodeError):
        return True
    return count_html_messages(html_file) == json_count


def count_divergent_months(channel_dir: Path) -> int:
    """Count months in `channel_dir` whose JSON and HTML message counts differ.

    These are the issue-#1 damaged months (the JSON drifted above what the HTML
    renders — e.g. a 758-message month showing a blank page). Used to rank
    backfill priority so the visible damage heals before ordinary backfill.
    """
    if not channel_dir.exists() or not channel_dir.is_dir():
        return 0
    n = 0
    for entry in channel_dir.iterdir():
        if not entry.is_dir() or not is_month_dir_name(entry.name):
            continue
        json_file = entry / f"{entry.name}.json"
        html_file = entry / f"{entry.name}.html"
        if (
            json_file.exists()
            and html_file.exists()
            and not _month_is_consistent(json_file, html_file)
        ):
            n += 1
    return n
