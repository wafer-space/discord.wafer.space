# scripts/discord_api.py
"""Read-only Discord REST calls that tell the exporter what has changed.

DiscordChatExporter's channel listing gives names and IDs only. One guild
channel listing plus the thread listings also give each channel's real type
and the ID of its newest message, which is enough to know, without exporting
anything, which channels have nothing new.

Only GET requests are made, with the same bot token the exporter uses.
"""

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

API_BASE = "https://discord.com/api/v10"
USER_AGENT = "DiscordBot (https://github.com/wafer-space/discord.wafer.space, 1.0)"

HTTP_TOO_MANY_REQUESTS = 429
HTTP_FORBIDDEN = 403
HTTP_NOT_FOUND = 404
MAX_RATE_LIMIT_RETRIES = 6
MAX_RETRY_WAIT_SECONDS = 60.0
# A parent channel with more archived threads than this is not finished
# listing; its remaining threads are simply treated as "activity unknown".
MAX_ARCHIVED_PAGES = 50
ARCHIVED_PAGE_SIZE = 100

# https://discord.com/developers/docs/resources/channel#channel-object-channel-types
TYPE_TEXT = 0
TYPE_CATEGORY = 4
TYPE_ANNOUNCEMENT = 5
TYPE_FORUM = 15
TYPE_MEDIA = 16
# Channels that can hold threads.
THREAD_PARENT_TYPES = frozenset({TYPE_TEXT, TYPE_ANNOUNCEMENT, TYPE_FORUM, TYPE_MEDIA})
# Channels with no messages of their own. DiscordChatExporter refuses to
# export a forum directly ("pull its threads and export them individually").
CONTAINER_TYPES = frozenset({TYPE_CATEGORY, TYPE_FORUM, TYPE_MEDIA})

Getter = Callable[[str], Any]


class DiscordApiError(Exception):
    """A Discord API request failed."""

    def __init__(self, status: int, message: str):
        """Record the HTTP status (0 for a transport failure) and a short message."""
        super().__init__(f"HTTP {status}: {message[:200]}" if status else message)
        self.status = status


@dataclass(frozen=True)
class ChannelActivity:
    """What the API says about one channel or thread."""

    channel_type: int
    # None means the API says the channel has no messages, but only when
    # last_message_known is True. Discord documents the field as optional as
    # well as nullable; an absent field says nothing about the channel.
    last_message_id: str | None
    last_message_known: bool = True

    @property
    def is_container(self) -> bool:
        """Whether this is a category or forum, which has no messages to export."""
        return self.channel_type in CONTAINER_TYPES


def make_getter(token: str, sleep: Callable[[float], None] = time.sleep) -> Getter:
    """Return a function that GETs an API path and returns the parsed JSON.

    A 429 is retried after the delay Discord asks for. Every other failure
    raises DiscordApiError.
    """

    def get(path: str) -> Any:
        request = urllib.request.Request(  # noqa: S310  # API_BASE is a constant https URL
            API_BASE + path,
            headers={"Authorization": f"Bot {token}", "User-Agent": USER_AGENT},
            method="GET",
        )
        for _ in range(MAX_RATE_LIMIT_RETRIES):
            try:
                with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
                    return json.loads(response.read())
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", "replace")
                if e.code != HTTP_TOO_MANY_REQUESTS:
                    raise DiscordApiError(e.code, body) from e
                try:
                    wait = float(json.loads(body).get("retry_after", 1.0))
                except (ValueError, TypeError, AttributeError):
                    wait = 1.0
                sleep(min(wait, MAX_RETRY_WAIT_SECONDS) + 0.25)
            except urllib.error.URLError as e:
                raise DiscordApiError(0, f"could not reach discord.com: {e.reason}") from e
            except ValueError as e:
                raise DiscordApiError(0, f"discord.com returned invalid JSON: {e}") from e
        raise DiscordApiError(HTTP_TOO_MANY_REQUESTS, "still rate limited after retries")

    return get


def _record(activity: dict[str, ChannelActivity], channel: Any) -> None:
    """Add one API channel object to the activity map, if it is well formed."""
    if not isinstance(channel, dict) or not channel.get("id"):
        return
    channel_type = channel.get("type")
    if not isinstance(channel_type, int):
        return
    if "last_message_id" not in channel:
        activity[str(channel["id"])] = ChannelActivity(channel_type, None, last_message_known=False)
        return
    last = channel.get("last_message_id")
    activity[str(channel["id"])] = ChannelActivity(channel_type, str(last) if last else None)


def _archived_threads(get: Getter, parent_id: str) -> list[Any]:
    """Return the public archived threads of one channel, newest archive first.

    A channel the bot cannot read (403/404) has no threads the exporter could
    export either, so it yields nothing rather than failing the run.
    """
    threads: list[Any] = []
    before = ""
    for _ in range(MAX_ARCHIVED_PAGES):
        path = f"/channels/{parent_id}/threads/archived/public?limit={ARCHIVED_PAGE_SIZE}{before}"
        try:
            page = get(path)
        except DiscordApiError as e:
            if e.status in (HTTP_FORBIDDEN, HTTP_NOT_FOUND):
                return threads
            raise
        if not isinstance(page, dict):
            return threads
        batch = page.get("threads") or []
        threads.extend(batch)
        if not page.get("has_more") or not batch:
            return threads
        last = batch[-1]
        stamp = (last.get("thread_metadata") or {}).get("archive_timestamp")
        if not stamp:
            return threads
        before = "&before=" + quote(str(stamp), safe="")
    return threads


def fetch_guild_activity(guild_id: str, get: Getter) -> dict[str, ChannelActivity]:
    """Return ``{channel or thread ID: ChannelActivity}`` for a guild.

    Covers every channel in the guild, its active threads, and the public
    archived threads of each channel that can hold threads. A thread missing
    from the result (a private archived thread, say) is "activity unknown",
    and the exporter then exports it as it always has.

    Raises DiscordApiError if the guild's channels or active threads cannot
    be listed.
    """
    activity: dict[str, ChannelActivity] = {}

    channels = get(f"/guilds/{guild_id}/channels")
    if not isinstance(channels, list):
        raise DiscordApiError(0, "guild channel listing was not a list")
    for channel in channels:
        _record(activity, channel)

    active = get(f"/guilds/{guild_id}/threads/active")
    if not isinstance(active, dict):
        raise DiscordApiError(0, "active thread listing was not an object")
    for thread in active.get("threads") or []:
        _record(activity, thread)

    parents = [cid for cid, a in activity.items() if a.channel_type in THREAD_PARENT_TYPES]
    for parent_id in parents:
        for thread in _archived_threads(get, parent_id):
            _record(activity, thread)

    return activity
