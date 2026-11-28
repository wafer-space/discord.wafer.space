# scripts/export_plan.py
"""Decide which months of a channel actually need exporting.

The exporter used to re-export the current month of every channel and thread
on every run, and to retry every empty past month forever. Given the ID of a
channel's newest message (from the Discord API) and what is already
published, most of that work can be proven unnecessary:

- No message can exist after the month of the channel's newest message.
- If this cache recorded exporting the channel when its newest message was
  the one the API reports now, nothing new has arrived since.
- A past month that exported empty was empty a few days ago. That is also
  what a transient permission problem looks like, so the record expires.

Edits and deletions do not change a channel's newest message ID, so an
unchanged channel that was active this month is still re-exported once the
published copy is older than the configured refresh interval.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from scripts.discord_api import ChannelActivity
from scripts.months import month_bounds, month_range_iter, snowflake_to_month

CACHE_FILE = "_export_state.json"
CACHE_SCHEMA = 2
DEFAULT_REFRESH_HOURS = 0.0
DEFAULT_EMPTY_RECHECK_DAYS = 7.0
# A published past month is trusted as complete in every format only if its
# JSON was exported this long after the month ended. DiscordChatExporter is
# run once per format, so a copy taken around the month boundary can hold a
# message in its JSON that its HTML (exported first) lacks.
SETTLED_AFTER = timedelta(days=1)

PHASE_CURRENT = "current"
PHASE_BACKFILL = "backfill"


@dataclass
class CacheEntry:
    """What earlier runs learned about one channel."""

    # Newest message ID the API reported when the channel was last exported.
    last_message_id: str | None = None
    exported_at: str | None = None
    # Past months that exported with zero messages: month -> when recorded.
    empty_months: dict[str, str] = field(default_factory=dict)

    def known_empty(self, now: datetime, recheck_days: float) -> set[str]:
        """Past months recorded empty recently enough not to be tried again.

        A record older than ``recheck_days`` (or with an unreadable time) has
        expired and the month is exported again; 0 disables the record.
        """
        if recheck_days <= 0:
            return set()
        cutoff = now - timedelta(days=recheck_days)
        fresh = set()
        for month, recorded_at in self.empty_months.items():
            stamp = _parse_time(recorded_at)
            if stamp is not None and stamp > cutoff:
                fresh.add(month)
        return fresh


class ExportCache:
    """Per-server record of export facts that the published files cannot show.

    Stored next to the exports (``public/<server>/_export_state.json``) so it
    is published and restored together with them: a run that fails to deploy
    also fails to publish its claims about what it exported.
    """

    def __init__(self, path: Path):
        """Create an empty cache backed by ``path``; call load() to read it."""
        self.path = path
        self.entries: dict[str, CacheEntry] = {}

    def load(self) -> None:
        """Read the cache. A missing or unreadable file is an empty cache."""
        self.entries = {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data.get("schema") != CACHE_SCHEMA:
                return  # An older layout is discarded, not misread.
            channels = data["channels"]
            for channel_id, raw in channels.items():
                empty = raw.get("empty_months") or {}
                self.entries[str(channel_id)] = CacheEntry(
                    last_message_id=raw.get("last_message_id") or None,
                    exported_at=raw.get("exported_at") or None,
                    empty_months={str(m): str(t) for m, t in sorted(empty.items())},
                )
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            # Losing the cache only costs one round of re-exports.
            self.entries = {}

    def get(self, channel_id: str) -> CacheEntry | None:
        """Return the entry for a channel, or None if nothing is recorded."""
        return self.entries.get(channel_id)

    def record_export(self, channel_id: str, last_message_id: str | None, now: datetime) -> None:
        """Record that the channel was exported while its newest message was this ID."""
        entry = self.entries.setdefault(channel_id, CacheEntry())
        entry.last_message_id = last_message_id
        entry.exported_at = now.isoformat()

    def record_empty(self, channel_id: str, month: str, now: datetime) -> None:
        """Record that a past month exported with zero messages at ``now``."""
        entry = self.entries.setdefault(channel_id, CacheEntry())
        entry.empty_months = dict(sorted({**entry.empty_months, month: now.isoformat()}.items()))

    def save(self) -> None:
        """Write the cache. Best-effort: a write failure must not abort the export."""
        data = {
            "schema": CACHE_SCHEMA,
            "channels": {
                channel_id: {
                    "last_message_id": entry.last_message_id,
                    "exported_at": entry.exported_at,
                    "empty_months": entry.empty_months,
                }
                for channel_id, entry in sorted(self.entries.items())
            },
        }
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        except (OSError, TypeError) as e:
            print(f"  ⚠ could not write {self.path}: {e}")


def _read_month_json(public_channel_dir: Path, month: str) -> dict[str, Any] | None:
    """Return the published export for a month, or None if absent or unreadable."""
    try:
        data = json.loads((public_channel_dir / month / f"{month}.json").read_text("utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    return data if isinstance(data, dict) else None


def published_month_holds_messages(public_channel_dir: Path, month: str) -> bool:
    """Whether the published export for ``month`` holds at least one message."""
    data = _read_month_json(public_channel_dir, month)
    return bool(data and data.get("messages"))


def published_month_settled(public_channel_dir: Path, month: str) -> bool:
    """Whether the published copy of a past ``month`` was taken after it closed.

    Such a copy was exported with a fixed ``--before`` bound in every format,
    so no message can be in its JSON and missing from its HTML.
    """
    exported_at = published_exported_at(public_channel_dir, month)
    if exported_at is None:
        return False
    month_end = datetime.fromisoformat(month_bounds(month)[1])
    return exported_at >= month_end + SETTLED_AFTER


def published_exported_at(public_channel_dir: Path, month: str) -> datetime | None:
    """When the published export for ``month`` was taken, if it says."""
    data = _read_month_json(public_channel_dir, month)
    return _parse_time(data.get("exportedAt")) if data else None


def _parse_time(value: Any) -> datetime | None:
    """Parse an ISO timestamp; DiscordChatExporter writes 7 fractional digits."""
    if not isinstance(value, str) or not value:
        return None
    head, dot, rest = value.partition(".")
    if dot:
        digits = len(rest) - len(rest.lstrip("0123456789"))
        value = f"{head}.{rest[:digits][:6]}{rest[digits:]}"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else None


def _refresh_due(
    entry: CacheEntry | None,
    public_channel_dir: Path,
    current_month: str,
    now: datetime,
    refresh_hours: float,
) -> bool:
    """Whether an unchanged channel is due a re-export to pick up edits and deletions."""
    if refresh_hours <= 0:
        return True
    exported_at = _parse_time(entry.exported_at) if entry else None
    exported_at = exported_at or published_exported_at(public_channel_dir, current_month)
    return exported_at is None or now - exported_at > timedelta(hours=refresh_hours)


def plan_months(  # noqa: PLR0913  # A pure function of everything known about the channel
    phase: str,
    channel_id: str,
    activity: ChannelActivity,
    entry: CacheEntry | None,
    *,
    public_channel_dir: Path,
    completed: set[str],
    current_month: str,
    now: datetime,
    refresh_hours: float = DEFAULT_REFRESH_HOURS,
    empty_recheck_days: float = DEFAULT_EMPTY_RECHECK_DAYS,
) -> list[str]:
    """Return the months to export for one channel in one phase.

    ``PHASE_CURRENT`` returns the current month or nothing. ``PHASE_BACKFILL``
    returns past months, oldest first. ``completed`` is the set of past months
    already published correctly (``scan_completed_months``).

    The caller must not pass an activity whose ``last_message_known`` is
    False: without the newest message ID nothing can be proven unchanged.
    """
    newest = activity.last_message_id
    if not newest or not newest.isdigit():
        return []  # The API says the channel has never had a message.
    # A clock ahead of ours must not invent a future month.
    last_month = min(snowflake_to_month(newest), current_month)

    # Only this cache proves the current month up to date: the published JSON
    # can hold a message its HTML lacks, because HTML is exported first.
    recorded = entry is not None and entry.last_message_id == newest

    if phase == PHASE_CURRENT:
        if last_month != current_month:
            return []  # Nothing has been posted this month.
        if recorded and not _refresh_due(
            entry, public_channel_dir, current_month, now, refresh_hours
        ):
            return []
        return [current_month]

    empty = entry.known_empty(now, empty_recheck_days) if entry else set()
    months = [
        month
        for month in month_range_iter(snowflake_to_month(channel_id), last_month)
        if month != current_month and month not in completed and month not in empty
    ]
    # The month holding the newest message looks complete as soon as it has
    # any export, even one taken before the month's last messages arrived
    # (a channel that went quiet just after a month rolled over). Export it
    # once more unless it is known to be complete.
    up_to_date = recorded or published_month_settled(public_channel_dir, last_month)
    if last_month != current_month and not up_to_date and last_month not in months:
        months.append(last_month)
    return months
