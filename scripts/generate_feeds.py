# scripts/generate_feeds.py
"""Generate a machine-readable index and Atom feeds for the published archive.

Reads the per-month JSON exports already present in ``public/`` and writes,
for each server:

- ``public/<server>/index.json``: every channel and thread, keyed by its
  Discord ID, with its path, URLs, months, message count and last message.
- ``public/<server>/feed.atom``: the newest messages across the server.
- ``public/<server>/<channel path>/feed.atom``: the newest messages in that
  channel and in its threads (for a forum: in its posts).

It makes no Discord API calls and never changes an export, so it can only
publish what the JSON exports in ``public/`` already publish.
"""

import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from html import escape
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import quote

from scripts.config import load_config

INDEX_SCHEMA = 1
CHANNEL_FEED_LIMIT = 100
SERVER_FEED_LIMIT = 200
TITLE_SNIPPET_CHARS = 80

MONTH_RE = re.compile(r"^\d{4}-\d{2}$")
# DiscordChatExporter writes 7 fractional digits in exportedAt; Python 3.11's
# fromisoformat accepts at most 6.
FRACTION_RE = re.compile(r"(\.\d{6})\d+")
# Characters XML 1.0 cannot carry, even escaped.
XML_ILLEGAL_RE = re.compile("[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")

THREAD_TYPES = frozenset({"GuildPublicThread", "GuildPrivateThread", "GuildNewsThread"})
# Message types that carry something a person wrote. Joins, pins, renames and
# "thread created" notices stay out of the feeds.
FEED_MESSAGE_TYPES = frozenset({"Default", "Reply"})
# Type recorded for a forum, which has no export of its own: it is inferred
# from the posts published beneath it.
INFERRED_FORUM_TYPE = "GuildForum"


@dataclass
class Message:
    """The fields of one exported message that the feeds need."""

    id: str
    timestamp: str
    edited: str | None
    author: str
    content: str
    attachments: list[tuple[str, str]]  # (file name, url as written in the export)
    month: str

    @property
    def sort_key(self) -> int:
        """Discord IDs are snowflakes: numeric order is creation order."""
        return int(self.id) if self.id.isdigit() else 0


@dataclass
class Channel:
    """One channel, thread or forum as published under one directory."""

    id: str
    name: str
    type: str
    topic: str | None
    category: str | None
    parent_id: str | None
    path: str  # POSIX path relative to the server directory
    months: list[str] = field(default_factory=list)
    message_count: int = 0
    last_message_id: str | None = None
    last_message_at: str | None = None
    exported_at: str | None = None
    recent: list[Message] = field(default_factory=list)
    stale_paths: list[str] = field(default_factory=list)

    @property
    def is_thread(self) -> bool:
        """Whether this record is a thread or forum post."""
        return self.type in THREAD_TYPES


def parse_time(value: str | None) -> datetime | None:
    """Parse an export timestamp, or return None when it is absent or malformed."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(FRACTION_RE.sub(r"\1", value))
    except ValueError:
        return None


def _newer(a: str | None, b: str | None) -> bool:
    """Whether timestamp ``a`` is strictly later than ``b``. Absent is oldest."""
    ta, tb = parse_time(a), parse_time(b)
    if ta is None:
        return False
    return tb is None or ta > tb


def _slim_message(raw: dict[str, Any], month: str) -> Message | None:
    """Reduce an exported message to a Message, or None if it has no ID."""
    message_id = str(raw.get("id") or "")
    if not message_id:
        return None
    author = raw.get("author") or {}
    attachments = [
        (str(a.get("fileName") or a.get("url")), str(a["url"]))
        for a in raw.get("attachments") or []
        if isinstance(a, dict) and a.get("url")
    ]
    return Message(
        id=message_id,
        timestamp=str(raw.get("timestamp") or ""),
        edited=raw.get("timestampEdited") or None,
        author=str(author.get("nickname") or author.get("name") or "unknown"),
        content=str(raw.get("content") or ""),
        attachments=attachments,
        month=month,
    )


def month_files(channel_dir: Path) -> list[tuple[str, Path]]:
    """Return ``(month, json path)`` for each month exported in a directory."""
    found = []
    for child in channel_dir.iterdir():
        if child.is_dir() and MONTH_RE.match(child.name):
            json_path = child / f"{child.name}.json"
            if json_path.is_file():
                found.append((child.name, json_path))
    return sorted(found)


def _read_month(json_path: Path) -> tuple[dict[str, Any], list[Any], str | None] | None:
    """Return ``(channel info, messages, exportedAt)`` from one month export.

    A file that cannot be parsed is reported and skipped (None), so one bad
    file does not hide the rest of the channel.
    """
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
        info = data["channel"]
        if not isinstance(info, dict):
            raise TypeError("channel is not an object")
        return info, list(data.get("messages") or []), data.get("exportedAt")
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"  WARNING: skipping unreadable export {json_path}: {e}")
        return None


def _absorb_messages(channel: Channel, raw_messages: list[Any], month: str) -> None:
    """Fold one month's messages into the channel's totals and recent list."""
    channel.message_count += len(raw_messages)
    last_id = channel.last_message_id or ""
    last_key = int(last_id) if last_id.isdigit() else -1
    for raw in raw_messages:
        message = _slim_message(raw, month) if isinstance(raw, dict) else None
        if message is None:
            continue
        if message.sort_key > last_key:
            last_key = message.sort_key
            channel.last_message_id = message.id
            channel.last_message_at = message.timestamp or None
        if raw.get("type") in FEED_MESSAGE_TYPES:
            channel.recent.append(message)
    channel.recent = sorted(channel.recent, key=lambda m: m.sort_key)[-SERVER_FEED_LIMIT:]


def load_channel(channel_dir: Path, server_dir: Path) -> Channel | None:
    """Build a Channel from the month exports in one directory.

    Returns None when the directory holds no readable month export.
    """
    channel: Channel | None = None
    for month, json_path in month_files(channel_dir):
        loaded = _read_month(json_path)
        if loaded is None:
            continue
        info, raw_messages, exported_at = loaded

        channel_type = str(info.get("type") or "")
        is_thread = channel_type in THREAD_TYPES
        if channel is None:
            channel = Channel(
                id=str(info.get("id") or ""),
                name=channel_dir.name,
                type=channel_type,
                topic=None,
                category=None,
                parent_id=None,
                path=channel_dir.relative_to(server_dir).as_posix(),
            )
        # The newest month wins for facts that change over time (renames,
        # moved categories). Months arrive oldest first.
        channel.name = str(info.get("name") or channel.name)
        channel.type = channel_type or channel.type
        channel.topic = info.get("topic") or None
        # For a thread the exporter records its parent channel in the
        # "category" fields.
        parent_id = info.get("categoryId") if is_thread else None
        channel.parent_id = str(parent_id) if parent_id else None
        channel.category = None if is_thread else (info.get("category") or None)
        channel.months.append(month)
        if _newer(exported_at, channel.exported_at):
            channel.exported_at = exported_at
        _absorb_messages(channel, raw_messages, month)

    if channel is None or not channel.id:
        return None
    return channel


def scan_server(server_dir: Path) -> list[Channel]:
    """Load every directory under a server that holds month exports."""
    channels = []
    for directory in sorted(p for p in server_dir.rglob("*") if p.is_dir()):
        if MONTH_RE.match(directory.name) or directory.name.endswith("_media"):
            continue
        channel = load_channel(directory, server_dir)
        if channel is not None:
            channels.append(channel)
    return channels


def pick_canonical(channels: list[Channel]) -> list[Channel]:
    """Keep one record per Discord ID; note the other paths as stale.

    Paths are built from category and channel names, so a rename leaves the
    old directory behind next to the new one. The directory with the most
    recent export is the live one.
    """
    by_id: dict[str, list[Channel]] = {}
    for channel in channels:
        by_id.setdefault(channel.id, []).append(channel)

    canonical = []
    for records in by_id.values():
        best = records[0]
        for record in records[1:]:
            newer = _newer(record.exported_at, best.exported_at)
            tie = not _newer(best.exported_at, record.exported_at)
            if newer or (tie and (record.months[-1:], record.path) > (best.months[-1:], best.path)):
                best = record
        best.stale_paths = sorted(r.path for r in records if r is not best)
        canonical.append(best)
    return sorted(canonical, key=lambda c: c.path)


def infer_forums(scanned: list[Channel], known_ids: set[str]) -> list[Channel]:
    """Create a record for each forum, which has posts but no export of its own.

    A forum's posts are exported as threads in directories beneath the forum's
    directory, and each carries the forum's ID as its parent. ``scanned`` is
    every published directory, including ones left behind by a rename, so the
    forum's old directories are found too.
    """
    exported_paths = {c.path for c in scanned}
    # forum id -> {directory: newest export seen beneath it}
    candidates: dict[str, dict[str, str | None]] = {}
    for thread in scanned:
        if not thread.is_thread or not thread.parent_id or thread.parent_id in known_ids:
            continue
        parent_path = PurePosixPath(thread.path).parent.as_posix()
        if parent_path in (".", "") or parent_path in exported_paths:
            continue
        paths = candidates.setdefault(thread.parent_id, {})
        if parent_path not in paths or _newer(thread.exported_at, paths[parent_path]):
            paths[parent_path] = thread.exported_at

    forums = []
    for forum_id, paths in candidates.items():
        live = sorted(paths)[0]
        for path in sorted(paths):
            if _newer(paths[path], paths[live]):
                live = path
        forums.append(
            Channel(
                id=forum_id,
                name=PurePosixPath(live).name,
                type=INFERRED_FORUM_TYPE,
                topic=None,
                # A forum directly under a category directory; no export
                # states the category, so the directory name stands in.
                category=PurePosixPath(live).parent.name or None,
                parent_id=None,
                path=live,
                exported_at=paths[live],
                stale_paths=sorted(p for p in paths if p != live),
            )
        )
    return forums


def url_for(base_url: str, *parts: str) -> str:
    """Join path parts onto base_url, percent-encoding each one."""
    path = "/".join(quote(p.strip("/"), safe="/") for p in parts if p.strip("/"))
    return f"{base_url.rstrip('/')}/{path}"


def _channel_url(base_url: str, server: str, channel: Channel) -> str:
    return url_for(base_url, server, channel.path) + "/"


def build_index(
    base_url: str, server: str, server_config: dict[str, Any], channels: list[Channel]
) -> dict[str, Any]:
    """Build the index.json document for one server."""
    entries = []
    for channel in channels:
        url = _channel_url(base_url, server, channel)
        entry: dict[str, Any] = {
            "id": channel.id,
            "name": channel.name,
            "type": channel.type,
            "category": channel.category,
            "parent_id": channel.parent_id,
            "topic": channel.topic,
            "path": channel.path,
            "url": url,
            "feed": url + "feed.atom",
            "months": channel.months,
            "message_count": channel.message_count,
            "last_message_id": channel.last_message_id,
            "last_message_at": channel.last_message_at,
            "exported_at": channel.exported_at,
            "stale_paths": channel.stale_paths,
        }
        if channel.months:
            entry["latest_json"] = url + "latest.json"
            entry["month_json"] = url + "{month}/{month}.json"
        entries.append(entry)

    exported = [c.exported_at for c in channels if c.exported_at]
    updated_at = None
    for value in exported:
        if _newer(value, updated_at):
            updated_at = value
    server_url = url_for(base_url, server) + "/"
    return {
        "schema": INDEX_SCHEMA,
        "server": {
            "key": server,
            "name": server_config.get("name") or server,
            "guild_id": str(server_config.get("guild_id") or ""),
            "url": server_url,
            "feed": server_url + "feed.atom",
        },
        # The newest export in the archive, not the time this file was built,
        # so an unchanged archive produces an identical file.
        "updated_at": updated_at,
        "channels": entries,
    }


def _xml(text: str) -> str:
    """Escape text for XML content or a quoted attribute."""
    return escape(XML_ILLEGAL_RE.sub("", text), quote=True)


def _where(channel: Channel, by_id: dict[str, Channel]) -> str:
    """Human name for where a message was posted."""
    parent = by_id.get(channel.parent_id or "")
    if channel.is_thread and parent is not None:
        return f"#{parent.name} › {channel.name}"
    return f"#{channel.name}"


def _entry_xml(
    message: Message, channel: Channel, by_id: dict[str, Channel], base_url: str, server: str
) -> str:
    """Render one message as an Atom entry."""
    channel_url = _channel_url(base_url, server, channel)
    month_url = f"{channel_url}{message.month}/"
    page_url = f"{month_url}{message.month}.html#chatlog__message-container-{message.id}"

    snippet = " ".join(message.content.split())
    if len(snippet) > TITLE_SNIPPET_CHARS:
        snippet = snippet[: TITLE_SNIPPET_CHARS - 1].rstrip() + "…"
    if not snippet:
        snippet = "(attachment)" if message.attachments else "(no text)"
    title = f"{message.author} in {_where(channel, by_id)}: {snippet}"

    body = message.content
    for file_name, url in message.attachments:
        # The exporter rewrites downloaded attachments to paths relative to
        # the month directory.
        absolute = url if "://" in url else month_url + quote(url, safe="/")
        body += f"\n[attachment: {file_name}] {absolute}"

    updated = message.edited or message.timestamp
    return (
        "  <entry>\n"
        f"    <id>tag:discord.com,2015:message/{_xml(channel.id)}/{_xml(message.id)}</id>\n"
        f"    <title>{_xml(title)}</title>\n"
        f'    <link rel="alternate" type="text/html" href="{_xml(page_url)}"/>\n'
        f"    <published>{_xml(message.timestamp)}</published>\n"
        f"    <updated>{_xml(updated)}</updated>\n"
        f"    <author><name>{_xml(message.author)}</name></author>\n"
        f'    <category term="{_xml(channel.id)}" label="{_xml(_where(channel, by_id))}"/>\n'
        f'    <content type="text">{_xml(body.strip())}</content>\n'
        "  </entry>\n"
    )


def build_feed(  # noqa: PLR0913  # A feed needs its identity plus the lookup context
    title: str,
    feed_url: str,
    html_url: str,
    items: list[tuple[Message, Channel]],
    *,
    by_id: dict[str, Channel],
    base_url: str,
    server: str,
    limit: int,
) -> str:
    """Render the newest ``limit`` messages as an Atom 1.0 document."""
    newest = sorted(items, key=lambda item: item[0].sort_key, reverse=True)[:limit]
    updated = None
    for message, _channel in newest:
        stamp = message.edited or message.timestamp
        if _newer(stamp, updated):
            updated = stamp
    # Atom requires <updated>. An empty feed gets the Unix epoch so the file
    # is still valid and still identical from run to run.
    updated = updated or "1970-01-01T00:00:00+00:00"

    parts = [
        '<?xml version="1.0" encoding="utf-8"?>\n',
        '<feed xmlns="http://www.w3.org/2005/Atom">\n',
        f"  <id>{_xml(feed_url)}</id>\n",
        f"  <title>{_xml(title)}</title>\n",
        f"  <updated>{_xml(updated)}</updated>\n",
        f'  <link rel="self" type="application/atom+xml" href="{_xml(feed_url)}"/>\n',
        f'  <link rel="alternate" type="text/html" href="{_xml(html_url)}"/>\n',
    ]
    parts.extend(_entry_xml(m, c, by_id, base_url, server) for m, c in newest)
    parts.append("</feed>\n")
    return "".join(parts)


def generate_for_server(
    public_dir: Path, server: str, server_config: dict[str, Any], site: dict[str, Any]
) -> tuple[int, int]:
    """Write index.json and every feed for one server.

    Returns ``(channels indexed, feeds written)``.
    """
    server_dir = public_dir / server
    base_url = str(site.get("base_url") or "")
    display = str(server_config.get("name") or server)

    scanned = scan_server(server_dir)
    channels = pick_canonical(scanned)
    channels.extend(infer_forums(scanned, {c.id for c in channels}))
    channels.sort(key=lambda c: c.path)
    by_id = {c.id: c for c in channels}

    index = build_index(base_url, server, server_config, channels)
    (server_dir / "index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    children: dict[str, list[Channel]] = {}
    for channel in channels:
        if channel.parent_id:
            children.setdefault(channel.parent_id, []).append(channel)

    feeds = 0
    for channel in channels:
        members = [channel, *children.get(channel.id, [])]
        items = [(m, member) for member in members for m in member.recent]
        url = _channel_url(base_url, server, channel)
        feed = build_feed(
            f"{_where(channel, by_id)} - {display} Discord",
            url + "feed.atom",
            url,
            items,
            by_id=by_id,
            base_url=base_url,
            server=server,
            limit=CHANNEL_FEED_LIMIT,
        )
        # A renamed channel's old directory still has an index page that
        # links to feed.atom, so it gets the same feed as the live path.
        for path in [channel.path, *channel.stale_paths]:
            (server_dir / path / "feed.atom").write_text(feed, encoding="utf-8")
            feeds += 1

    server_url = url_for(base_url, server) + "/"
    everything = [(m, c) for c in channels for m in c.recent]
    (server_dir / "feed.atom").write_text(
        build_feed(
            f"{display} Discord",
            server_url + "feed.atom",
            server_url,
            everything,
            by_id=by_id,
            base_url=base_url,
            server=server,
            limit=SERVER_FEED_LIMIT,
        ),
        encoding="utf-8",
    )
    return len(channels), feeds + 1


def main() -> None:
    """Entry point: generate index.json and feeds for every configured server."""
    print("Generating index.json and Atom feeds...")
    config = load_config()
    public_dir = Path("public")
    if not public_dir.exists():
        print("ERROR: public/ directory not found. Run export first.")
        sys.exit(1)

    site = config.get("site", {})
    if not site.get("base_url"):
        print("ERROR: [site] base_url must be set in config.toml to build feed URLs.")
        sys.exit(1)

    for server, server_config in config.get("servers", {}).items():
        if not (public_dir / server).is_dir():
            print(f"  {server}: nothing published yet, skipping")
            continue
        channel_count, feed_count = generate_for_server(public_dir, server, server_config, site)
        print(f"  ✓ {server}: {channel_count} channels indexed, {feed_count} feeds")


if __name__ == "__main__":
    main()
