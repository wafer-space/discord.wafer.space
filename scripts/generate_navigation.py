# scripts/generate_navigation.py
"""Generate navigation index pages from exported logs."""

import json
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader

# Constants
MIN_PATH_PARTS_FOR_CHANNEL = 3
MIN_PATH_PARTS_FOR_EXPORT = 4  # server, channel, month, file
YYYY_MM_FORMAT_LENGTH = 7  # Length of "YYYY-MM" date format

# The version-controlled static assets (site stylesheet) live OUTSIDE public/
# so they survive the deploy workflow's `rm -rf public` + gh-pages checkout.
ASSETS_SOURCE_DIR = Path(__file__).resolve().parent.parent / "assets"


@dataclass
class ForumInfo:
    """Forum metadata for index generation."""

    name: str
    description: str | None = None


# Handle imports for both direct execution and pytest
try:
    from scripts.config import load_config
    from scripts.thread_metadata import extract_thread_metadata
except ModuleNotFoundError:
    from config import load_config  # type: ignore[import-not-found, no-redef]
    from thread_metadata import extract_thread_metadata  # type: ignore[import-not-found, no-redef]


def scan_exports(public_dir: Path) -> list[dict]:
    """Scan public directory for exported files.

    Args:
        public_dir: Path to public directory

    Returns:
        List of export info dicts
    """
    exports = []

    for html_file in public_dir.rglob("*.html"):
        # Skip index files and latest.html
        if html_file.name in ("index.html", "latest.html"):
            continue

        # Parse path: public/server/[category/]channel/YYYY-MM/YYYY-MM.html
        # The parent directory of the HTML file is the YYYY-MM month directory
        parts = html_file.relative_to(public_dir).parts

        # Need at least: server, channel, month, file
        if len(parts) >= MIN_PATH_PARTS_FOR_EXPORT:
            server = parts[0]
            date = html_file.stem  # YYYY-MM

            # Verify this looks like a month directory (YYYY-MM format)
            month_dir = parts[-2]  # Parent directory of the file
            if len(month_dir) == YYYY_MM_FORMAT_LENGTH and month_dir[4] == "-":
                # Build full channel path (everything between server and month directory)
                channel_parts = parts[1:-2]  # Skip server and month/file
                channel = "/".join(channel_parts)

                exports.append(
                    {
                        "server": server,
                        "channel": channel,
                        "date": date,
                        "path": str(html_file.relative_to(public_dir)),
                    }
                )

    return exports


def count_messages_from_json(json_path: str) -> int:
    """Count messages in JSON export file.

    Args:
        json_path: Path to JSON file (DiscordChatExporter format)

    Returns:
        Number of messages
    """
    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
            messages = data.get("messages", [])
            return len(messages)
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return 0


def group_by_year(archives: list[dict]) -> dict[str, list[dict]]:
    """Group archives by year.

    Args:
        archives: List of archive dicts with 'date' field

    Returns:
        Dict mapping year to list of archives
    """
    grouped: dict[str, list[dict]] = {}

    for archive in archives:
        year = archive["date"].split("-")[0]
        if year not in grouped:
            grouped[year] = []
        grouped[year].append(archive)

    # Sort each year's archives reverse chronologically
    for year in grouped:
        grouped[year].sort(key=lambda a: a["date"], reverse=True)

    return grouped


def has_date_archives(directory: Path) -> bool:
    """Check if directory contains YYYY-MM date subdirectories (channel archives).

    Args:
        directory: Path to check

    Returns:
        True if directory has YYYY-MM subdirectories, False otherwise
    """
    if not directory.exists() or not directory.is_dir():
        return False

    for item in directory.iterdir():
        if item.is_dir():
            # Check if name matches YYYY-MM format
            if len(item.name) == YYYY_MM_FORMAT_LENGTH and item.name[4] == "-":
                try:
                    # Verify it's actually a valid date format
                    year, month = item.name.split("-")
                    if year.isdigit() and month.isdigit():
                        return True
                except ValueError:
                    continue
    return False


def is_category(directory: Path) -> bool:
    """Check if directory is a category (contains channels, not a forum).

    A category contains subdirectories that are channels (have date archives).
    A forum contains subdirectories that are threads (no date archives).

    Args:
        directory: Path to check

    Returns:
        True if directory is a category, False if it's a forum or channel
    """
    if not directory.exists() or not directory.is_dir():
        return False

    # Check if subdirectories are channels (have date archives)
    for item in directory.iterdir():
        if item.is_dir() and item.name not in ["assets"]:
            # If any subdirectory has date archives, this is a category
            if has_date_archives(item):
                return True
    return False


def get_forum_channels(  # noqa: C901  # Complexity needed for directory type detection
    state: dict, server_name: str, public_dir: Path
) -> set[str]:
    """Get forum channel names with directory structure cross-checking.

    Directory type detection:
    - **Category**: Has subdirectories that are channels (with date archives)
    - **Forum**: Has subdirectories that are threads (no top-level date archives)
    - **Channel**: Has top-level YYYY-MM date archives

    Cross-checking rules:
    1. If directory has date archives → it's a CHANNEL, remove from forums
    2. If directory's subdirectories have date archives → it's a CATEGORY, remove from forums
    3. Otherwise, keep as forum if in state.json

    Args:
        state: State dictionary loaded from state.json
        server_name: Server name to look up
        public_dir: Path to public directory for cross-checking

    Returns:
        Set of forum channel names
    """
    # Start with forums from state.json
    forums_from_state = state.get(server_name, {}).get("forums", {})
    forum_names = set(forums_from_state.keys())

    # Cross-check with directory structure
    server_dir = public_dir / server_name
    if server_dir.exists():
        for item in server_dir.iterdir():
            if not item.is_dir() or item.name in ["assets"]:
                continue

            # If it has date archives at top level, it's a CHANNEL
            if has_date_archives(item):
                if item.name in forum_names:
                    print(f"  ⚠ Warning: '{item.name}' is a CHANNEL, not forum")
                forum_names.discard(item.name)
                continue

            # If subdirectories have date archives, it's a CATEGORY
            if is_category(item):
                if item.name in forum_names:
                    print(f"  ⚠ Warning: '{item.name}' is a CATEGORY, not forum")
                forum_names.discard(item.name)

                # Also check channels INSIDE this category
                for child in item.iterdir():
                    if not child.is_dir():
                        continue

                    # Build full path for channels inside categories (category/channel)
                    full_channel_name = f"{item.name}/{child.name}"

                    # If child has date archives, it's a channel (not a forum)
                    if has_date_archives(child):
                        if full_channel_name in forum_names:
                            print(f"  ⚠ Warning: '{full_channel_name}' is a CHANNEL")
                        forum_names.discard(full_channel_name)

                continue

            # Otherwise, it's potentially a forum (has subdirectories that don't have date archives)
            # But only include if it's in state.json (don't auto-detect new forums)

    return forum_names


def copy_static_assets(public_dir: Path) -> None:
    """Emit the version-controlled stylesheet into `public_dir/assets/`.

    The deploy workflow runs `rm -rf public` and then checks out the existing
    gh-pages branch into `public/`, so a stylesheet committed *under* public/
    never survives to the deploy. We keep the canonical copy in the repo's
    top-level `assets/` (outside public/) and emit it here — navigation runs
    after the gh-pages checkout and before the deploy, so this guarantees the
    version-controlled CSS ships every run.

    A failure to copy must NEVER abort navigation (and therefore the deploy);
    the worst acceptable outcome is the previously-deployed stylesheet
    remaining in place. So all errors are swallowed with a warning.
    """
    try:
        src = ASSETS_SOURCE_DIR / "style.css"
        if not src.exists():
            print(f"  ⚠ No stylesheet source at {src}; leaving existing assets in place.")
            return
        dest_dir = public_dir / "assets"
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest_dir / "style.css")
        print(f"  ✓ Emitted stylesheet to {dest_dir / 'style.css'}")
    except OSError as e:
        print(f"  ⚠ Could not emit static assets ({e}); leaving existing assets in place.")


def generate_site_index(config: dict, servers: list[dict], output_path: Path) -> None:
    """Generate site index page.

    Args:
        config: Site configuration
        servers: List of server info dicts
        output_path: Where to write index.html
    """
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("site_index.html.j2")

    html = template.render(
        site=config["site"],
        servers=servers,
        last_updated=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)


def generate_cname_file(config: dict, output_path: Path) -> None:
    """Generate CNAME file for GitHub Pages custom domain.

    Args:
        config: Site configuration
        output_path: Where to write CNAME file
    """
    base_url = config.get("site", {}).get("base_url")
    if not base_url:
        return

    # Extract hostname from base_url
    parsed = urlparse(base_url)
    if parsed.hostname:
        output_path.write_text(f"{parsed.hostname}\n")
        print(f"✓ Generated CNAME file for {parsed.hostname}")


def load_channel_order(public_dir: Path, server_name: str) -> list[str]:
    """Return channel paths in guild order from the export's `_order.json`.

    Empty list if the sidecar is absent or unreadable — navigation then falls
    back to alphabetical ordering, so a missing sidecar degrades gracefully.
    """
    order_file = public_dir / server_name / "_order.json"
    try:
        with open(order_file, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []
    return [e["path"] for e in data if isinstance(e, dict) and e.get("path")]


def group_channels_by_category(channels: list[dict], order: list[str]) -> list[dict]:
    """Group channels under their category, ordered the way the guild is.

    `order` is the list of channel paths in guild order (from the export
    sidecar). Categories appear in the order their first channel appears.
    Channels missing from `order` (e.g. brand new, not yet in the latest
    export) sort to the end of their category alphabetically, so nothing is
    ever dropped. Returns `[{"name": category, "channels": [...]}, ...]`.
    """
    pos = {path: i for i, path in enumerate(order)}
    fallback = len(order)

    groups: dict[str, list[dict]] = {}
    cat_order: list[str] = []
    for ch in sorted(channels, key=lambda c: (pos.get(c["name"], fallback), c["name"])):
        cat = ch.get("category") or ""
        if cat not in groups:
            groups[cat] = []
            cat_order.append(cat)
        groups[cat].append(ch)

    return [{"name": cat, "channels": groups[cat]} for cat in cat_order]


def generate_server_index(
    config: dict,
    server: dict,
    channels: list[dict],
    output_path: Path,
    categories: list[dict] | None = None,
) -> None:
    """Generate server index page.

    Args:
        config: Site configuration
        server: Server info dict
        channels: List of channel info dicts (flat; kept for back-compat)
        output_path: Where to write index.html
        categories: Channels grouped by category in guild order (issue #5);
            the template renders these as labelled sections.
    """
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("server_index.html.j2")

    # Self-sufficient: with no explicit guild order, group channels by their
    # own category field (alphabetical) so the page still renders grouped.
    if categories is None:
        categories = group_channels_by_category(channels, [])

    html = template.render(
        site=config["site"],
        server=server,
        channels=channels,
        categories=categories,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)


def generate_channel_index(  # noqa: PLR0913  # Index generation needs multiple contexts
    config: dict,
    server: dict,
    channel: dict,
    archives: list[dict],
    output_path: Path,
    threads: list[dict] | None = None,
) -> None:
    """Generate channel archive index page.

    Channels can have both message archives and threads. This generates an index
    showing both if they exist.

    Args:
        config: Site configuration
        server: Server info dict
        channel: Channel info dict
        archives: List of archive info dicts for main channel messages
        output_path: Where to write index.html
        threads: Optional list of thread metadata dicts for threads in this channel
    """
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("channel_index.html.j2")

    archives_by_year = group_by_year(archives)

    html = template.render(
        site=config["site"],
        server=server,
        channel=channel,
        archives_by_year=archives_by_year,
        threads=threads or [],
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)


def _read_channel_title(public_dir: Path, server: str, path: str, date: str) -> str:
    """Best-effort human title for a channel/thread from a month JSON.

    DCE records the real Discord channel/thread name in `channel.name`,
    even for an export with zero messages, so this gives the readable
    thread title instead of the URL slug.
    """
    json_path = public_dir / server / path / date / f"{date}.json"
    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)
        name = data.get("channel", {}).get("name")
        if isinstance(name, str) and name:
            return name
    except (OSError, json.JSONDecodeError):
        pass
    return path.split("/")[-1]


def _finalize_archives(archives: list[dict]) -> tuple[list[dict], int, int]:
    """Sort archives newest-first; return (archives, archive_count, total)."""
    archives.sort(key=lambda a: a["date"], reverse=True)
    total = sum(a["message_count"] for a in archives)
    return archives, len(archives), total


def _parent_path(p: str) -> str | None:
    """Parent export path (drop last segment), or None if top-level."""
    return p.rsplit("/", 1)[0] if "/" in p else None


def _category_paths(leaf_paths: set[str]) -> set[str]:
    """Return the depth-1 prefixes that are categories (not channels/threads).

    Discord categories are organizational containers: they never hold
    messages, so they never have a month export of their own. Structurally
    that means a top-level (single-segment) path that is a *prefix* of some
    exported leaf but is NOT itself an exported leaf. Decoding this lets us
    tell "Category/channel" apart from "forum/thread" without an API call.
    """
    categories: set[str] = set()
    for p in leaf_paths:
        first = p.split("/", 1)[0]
        if "/" in p and first not in leaf_paths:
            categories.add(first)
    return categories


def _channel_level_path(leaf: str, categories: set[str]) -> str:
    """Return the channel/forum portion of an exported `leaf` path.

    Strips a leading category segment, then the channel/forum is the first
    remaining segment (under a category that's `category/channel`). Anything
    deeper than the channel/forum is a thread; this returns just the
    channel/forum prefix, which is the nav entry the thread belongs to.

    Examples (with categories = {"Information"}):
      Information/general                     -> Information/general   (channel)
      Information/questions                   -> Information/questions (forum)
      Information/questions/antenna-error     -> Information/questions (thread's forum)
      welcome                                 -> welcome              (uncategorized channel)
    """
    segs = leaf.split("/")
    keep = 2 if segs[0] in categories else 1
    return "/".join(segs[:keep])


def _build_channel_entry(name: str, raw_archives: list[dict]) -> dict:
    """Build a channel/thread stats dict from its raw per-month archives.

    `name` is the full export path (e.g. "Information/general") and is the
    URL key. `display_name` is the leaf segment shown in the UI ("general")
    and `category` is the parent path ("Information", or "" when top-level)
    so templates don't render the category prefix into the channel title.
    """
    archives, archive_count, total = _finalize_archives(raw_archives)
    return {
        "name": name,
        "display_name": name.split("/")[-1],
        "category": _parent_path(name) or "",
        "archives": archives,
        "archive_count": archive_count,
        "message_count": archives[0]["message_count"] if archives else 0,
        "total_messages": total,
    }


def organize_data(exports: list[dict], public_dir: Path) -> dict:
    """Organize exports into servers → channels, with threads nested.

    Classification is by category-aware depth (see `_category_paths` /
    `_channel_level_path`): a leaf path resolves to a channel/forum level,
    and anything deeper than that level is a THREAD nested under it.
    Crucially this nests threads under FORUM channels too — a forum has no
    month export of its own, so we SYNTHESIZE its entry from its threads
    rather than dropping the threads in as top-level channels.

    Each channel dict gains: `archives`, `archive_count`, `message_count`
    (newest archive), `total_messages` (sum across months), and `threads`
    (list of thread dicts: `name` slug, `path`, `title`, `archives`,
    `archive_count`, `total_messages`, `last_activity`).
    """
    # First pass: bucket raw archives per (server, path).
    raw: dict[str, dict[str, dict]] = {}
    for export in exports:
        server = export["server"]
        path = export["channel"]
        date = export["date"]
        raw.setdefault(server, {})
        entry = raw[server].setdefault(path, {"archives": []})
        json_path = public_dir / server / path / date / f"{date}.json"
        entry["archives"].append(
            {"date": date, "message_count": count_messages_from_json(str(json_path))}
        )

    servers_data: dict[str, Any] = {}
    for server, paths in raw.items():
        path_set = set(paths)
        categories = _category_paths(path_set)
        server_data: dict[str, Any] = {
            "name": server,
            "display_name": server.replace("-", " ").title(),
            "channels": {},
            "last_updated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        }

        # Top-level entries = every distinct channel/forum level. A forum has
        # no export of its own, so its entry is synthesized with empty
        # archives; a regular channel reuses its own exported archives.
        for cpath in {_channel_level_path(p, categories) for p in paths}:
            raw_archives = paths[cpath]["archives"] if cpath in paths else []
            entry = _build_channel_entry(cpath, raw_archives)
            entry["threads"] = []
            server_data["channels"][cpath] = entry

        # Anything deeper than its channel level is a thread; nest it.
        for path in paths:
            cpath = _channel_level_path(path, categories)
            if path == cpath:
                continue  # this leaf IS the channel/forum, not a thread
            entry = _build_channel_entry(path, paths[path]["archives"])
            newest_date = entry["archives"][0]["date"] if entry["archives"] else ""
            thread = {
                **entry,
                "name": path.split("/")[-1],
                "path": path,
                "title": _read_channel_title(public_dir, server, path, newest_date),
                "last_activity": newest_date,
            }
            server_data["channels"][cpath]["threads"].append(thread)

        # Sort each channel's threads newest-activity first.
        for chan in server_data["channels"].values():
            chan["threads"].sort(key=lambda t: t["last_activity"], reverse=True)

        server_data["channel_count"] = len(server_data["channels"])
        servers_data[server] = server_data

    return servers_data


def collect_forum_threads(forum_dir: Path) -> list[dict]:
    """Collect metadata for all threads in a forum directory.

    Args:
        forum_dir: Path to forum directory (e.g., public/server/questions/)

    Returns:
        List of thread metadata dictionaries
    """
    threads = []

    # Iterate through thread directories
    for thread_dir in forum_dir.iterdir():
        if not thread_dir.is_dir():
            continue

        # More efficient: use recursive glob to find any JSON in subdirectories
        json_files = list(thread_dir.glob("*/*.json"))
        if not json_files:
            continue

        # Use first JSON file found (usually there's only one per thread)
        json_file = json_files[0]

        # Extract metadata
        metadata = extract_thread_metadata(json_file)
        if metadata:
            threads.append(
                {
                    "name": thread_dir.name,
                    "title": metadata["title"],
                    "url": f"{thread_dir.name}/",
                    "reply_count": metadata["reply_count"],
                    "last_activity": metadata["last_activity"],
                    "archived": metadata["archived"],
                }
            )

    # Sort by last activity (newest first)
    threads.sort(key=lambda t: t["last_activity"] or "", reverse=True)

    return threads


def collect_thread_archives(thread_dir: Path) -> list[dict[str, Any]]:
    """Collect archive files for a thread directory.

    Args:
        thread_dir: Path to thread directory (e.g., public/server/forum/thread-name/)

    Returns:
        List of archive info dicts with date and message_count
    """
    archives: list[dict[str, Any]] = []

    # Scan for date-based subdirectories (YYYY-MM format)
    for date_dir in thread_dir.iterdir():
        if not date_dir.is_dir():
            continue

        # Check if directory name looks like YYYY-MM
        if not (len(date_dir.name) == YYYY_MM_FORMAT_LENGTH and date_dir.name[4] == "-"):
            continue

        date = date_dir.name

        # Check if HTML file exists
        html_file = date_dir / f"{date}.html"
        if not html_file.exists():
            continue

        # Count messages from JSON file
        json_file = date_dir / f"{date}.json"
        message_count = count_messages_from_json(str(json_file)) if json_file.exists() else 0

        # Detect available formats
        formats = []
        for ext in ["txt", "json", "csv"]:
            if (date_dir / f"{date}.{ext}").exists():
                formats.append(ext)

        archives.append({"date": date, "message_count": message_count, "formats": formats})

    # Sort by date (newest first)
    archives.sort(key=lambda a: a["date"], reverse=True)

    return archives


def generate_thread_index(  # noqa: PLR0913  # Thread index generation requires multiple contexts
    config: dict,
    server: dict,
    forum_info: ForumInfo,
    thread_name: str,
    thread_title: str,
    archives: list[dict],
    output_path: Path,
) -> None:
    """Generate thread archive index page.

    Args:
        config: Site configuration
        server: Server info dict
        forum_info: Forum metadata (name for display)
        thread_name: Thread directory name (URL-safe)
        thread_title: Thread display title
        archives: List of archive info dicts
        output_path: Where to write index.html
    """
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("thread_index.html.j2")

    archives_by_year = group_by_year(archives)

    html = template.render(
        site=config["site"],
        server=server,
        forum_name=forum_info.name.title(),  # Capitalize for display
        forum_channel_name=forum_info.name,  # Original case for URLs
        thread_name=thread_name,
        thread_title=thread_title,
        archives_by_year=archives_by_year,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)


def generate_forum_index(
    config: dict,
    server: dict,
    forum_info: ForumInfo,
    threads: list[dict],
    output_path: Path,
) -> None:
    """Generate forum index page.

    Args:
        config: Site configuration
        server: Server info dict
        forum_info: Forum metadata (name and description)
        threads: List of thread metadata dicts
        output_path: Where to write index.html
    """
    env = Environment(loader=FileSystemLoader("templates"))
    template = env.get_template("forum_index.html.j2")

    html = template.render(
        site=config["site"],
        server=server,
        forum_name=forum_info.name.title(),  # Capitalize for display
        forum_channel_name=forum_info.name,  # Original case for URLs
        forum_description=forum_info.description,
        threads=threads,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)


def main() -> None:  # noqa: C901, PLR0912, PLR0915  # Main orchestration function
    """Entry point for navigation generation."""
    print("Generating navigation pages...")

    try:
        config = load_config()
        public_dir = Path("public")

        if not public_dir.exists():
            print("ERROR: public/ directory not found. Run export first.")
            sys.exit(1)

        # Thread vs channel is now derived structurally in organize_data
        # (a path whose parent is also an exported path is a thread), so
        # state.json is no longer consulted for forum detection.

        # Scan all exports
        print("Scanning exports...")
        exports = scan_exports(public_dir)

        if not exports:
            print("WARNING: No exports found.")
            return

        # Organize data by server and channel
        servers_data = organize_data(exports, public_dir)

        # Emit the version-controlled stylesheet (see copy_static_assets for
        # why this can't just be committed under public/).
        copy_static_assets(public_dir)

        # Generate site index
        print("Generating site index...")
        generate_site_index(config, list(servers_data.values()), public_dir / "index.html")

        # Generate CNAME file for custom domain
        generate_cname_file(config, public_dir / "CNAME")

        # Generate server indexes, channel indexes, and per-thread indexes.
        # Threads are nested in each channel's `threads` list (organize_data),
        # so a thread is NEVER listed as a top-level channel.
        for server_data in servers_data.values():
            print(f"Generating index for {server_data['display_name']}...")

            server_name = server_data["name"]
            channels_list = list(server_data["channels"].values())
            channels_list.sort(key=lambda c: c["name"])

            # A "forum-style" channel has threads but no top-level messages
            # of its own; the server index renders it as a thread hub.
            for channel in channels_list:
                channel["is_forum"] = channel["total_messages"] == 0 and len(channel["threads"]) > 0
                channel["thread_count"] = len(channel["threads"])

            # Group channels by category in the guild's own order (issue #5);
            # falls back to the alphabetical channels_list when no sidecar.
            order = load_channel_order(public_dir, server_name)
            categories = group_channels_by_category(channels_list, order)

            generate_server_index(
                config,
                server_data,
                channels_list,
                public_dir / server_name / "index.html",
                categories=categories,
            )

            thread_pages = 0
            for channel_data in channels_list:
                channel_dir = public_dir / server_name / channel_data["name"]
                threads = channel_data["threads"]

                generate_channel_index(
                    config,
                    server_data,
                    channel_data,
                    channel_data["archives"],
                    channel_dir / "index.html",
                    threads=threads or None,
                )

                # Each thread gets its own index page listing its archives.
                # We reuse the channel-index template with the thread as a
                # channel-like entity (name = full path so links resolve).
                for thread in threads:
                    thread_view = {
                        "name": thread["path"],
                        "display_name": thread["title"],
                        "category": _parent_path(thread["path"]) or "",
                        "is_thread": True,
                        "title": thread["title"],
                        "threads": [],
                    }
                    generate_channel_index(
                        config,
                        server_data,
                        thread_view,
                        thread["archives"],
                        public_dir / server_name / thread["path"] / "index.html",
                        threads=None,
                    )
                    thread_pages += 1

            print(
                f"  ✓ {len(channels_list)} channels, {thread_pages} threads "
                f"for {server_data['display_name']}"
            )

        print(f"\n✓ Generated {len(servers_data)} server indexes")
        print("✓ Site index at public/index.html")

    except FileNotFoundError as e:
        print(f"FATAL ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
