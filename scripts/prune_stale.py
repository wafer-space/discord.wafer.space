# scripts/prune_stale.py
"""Remove the duplicate directories that channel and category renames leave behind.

Published paths are built from category and channel names. When either is
renamed, the next export writes to a new directory and the old one stays:
the same channel, published twice, with the old copy frozen at the rename.
The old copy also keeps any message that has since been deleted on Discord,
because only the live directory is re-exported.

This step finds directories that hold a channel ID which is also published
somewhere newer (the same rule ``generate_feeds`` uses), and for each one:

- reports it, always;
- when ``[export] prune_stale_paths = true``, removes its exports and leaves
  a small ``index.html`` that redirects to the live directory.

A stale directory is only removed if every month it has messages for also
exists in the live directory, so pruning never removes the only copy of a
month. Directories that fail that test are reported and kept.

Run it after organize and before navigation, so the index pages are built
from what is left.
"""

import json
import shutil
import sys
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import quote

from scripts.config import load_config
from scripts.generate_feeds import MONTH_RE, Channel, month_files, pick_canonical, scan_server

# Files in a channel directory that belong to its exports. Anything else
# (notably the directories of threads, which are pruned on their own merits)
# is left alone.
EXPORT_FILES = ("latest.html", "latest.txt", "latest.json", "latest.csv", "feed.atom")
REPORT_LIMIT = 20


@dataclass
class StaleDir:
    """One out-of-date directory for a channel that is published elsewhere."""

    path: str  # POSIX path relative to the server directory
    live_path: str
    channel_name: str
    # Months with messages here that the live directory does not have at all.
    months_only_here: list[str]

    @property
    def prunable(self) -> bool:
        """Whether the live directory covers everything this one holds."""
        return not self.months_only_here


def _message_count(json_path: Path) -> int | None:
    """Number of messages in a month export, or None if it cannot be read."""
    try:
        data: Any = json.loads(json_path.read_text(encoding="utf-8"))
        return len(data.get("messages") or [])
    except (OSError, ValueError, AttributeError, TypeError):
        return None


def find_stale(server_dir: Path) -> list[StaleDir]:
    """Return every stale directory under a server, with what blocks its removal."""
    stale = []
    for channel in pick_canonical(scan_server(server_dir)):
        live_months = {month for month, _path in month_files(server_dir / channel.path)}
        for path in channel.stale_paths:
            only_here = []
            for month, json_path in month_files(server_dir / path):
                count = _message_count(json_path)
                # An unreadable month is treated as holding messages: keep it.
                if (count is None or count > 0) and month not in live_months:
                    only_here.append(month)
            stale.append(StaleDir(path, channel.path, _display_name(channel), only_here))
    return sorted(stale, key=lambda s: s.path)


def _display_name(channel: Channel) -> str:
    return channel.name or channel.path


def redirect_page(base_url: str, server: str, stale: StaleDir) -> str:
    """HTML for the page left in a pruned directory, pointing at the live one."""
    target = f"{base_url.rstrip('/')}/{quote(server)}/{quote(stale.live_path, safe='/')}/"
    href = escape(target, quote=True)
    name = escape(stale.channel_name)
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n'
        '    <meta charset="UTF-8">\n'
        f'    <meta http-equiv="refresh" content="0; url={href}">\n'
        f'    <link rel="canonical" href="{href}">\n'
        f"    <title>{name} has moved</title>\n"
        "</head>\n<body>\n"
        f'    <p>This channel was renamed. Its archive is now at <a href="{href}">{href}</a>.</p>\n'
        "</body>\n</html>\n"
    )


def prune(server_dir: Path, stale: StaleDir, page: str) -> None:
    """Remove a stale directory's exports and leave the redirect page.

    Only this directory's own month directories and export files are removed.
    Other subdirectories stay: a thread directory under a renamed channel is
    judged separately, and may itself be the thread's live path.
    """
    directory = server_dir / stale.path
    for child in directory.iterdir():
        if child.is_dir() and MONTH_RE.match(child.name):
            shutil.rmtree(child)
        elif child.name in EXPORT_FILES and (child.is_file() or child.is_symlink()):
            child.unlink()
    (directory / "index.html").write_text(page, encoding="utf-8")


def prune_server(public_dir: Path, server: str, base_url: str, *, enabled: bool) -> tuple[int, int]:
    """Report, and when enabled remove, the stale directories of one server.

    Returns ``(directories that are or would be pruned, directories kept)``.
    """
    server_dir = public_dir / server
    stale = find_stale(server_dir)
    prunable = [s for s in stale if s.prunable]
    kept = [s for s in stale if not s.prunable]

    verb = "Pruning" if enabled else "Would prune"
    print(f"  {server}: {len(stale)} stale directories ({len(prunable)} covered by a live copy)")
    for item in prunable[:REPORT_LIMIT]:
        print(f"    {verb}: {item.path}  →  {item.live_path}")
    if len(prunable) > REPORT_LIMIT:
        print(f"    ... and {len(prunable) - REPORT_LIMIT} more")
    for item in kept:
        months = ", ".join(item.months_only_here)
        print(f"    Keeping: {item.path} (only copy of {months}; live path is {item.live_path})")

    if enabled:
        for item in prunable:
            prune(server_dir, item, redirect_page(base_url, server, item))
    return len(prunable), len(kept)


def main() -> None:
    """Entry point: report or prune stale directories for every configured server."""
    config = load_config()
    public_dir = Path("public")
    if not public_dir.exists():
        print("ERROR: public/ directory not found. Run export first.")
        sys.exit(1)

    enabled = bool(config.get("export", {}).get("prune_stale_paths", False))
    base_url = str(config.get("site", {}).get("base_url") or "")
    if enabled and not base_url:
        print("ERROR: [site] base_url must be set in config.toml to write redirect pages.")
        sys.exit(1)

    mode = "enabled" if enabled else "report only; set [export] prune_stale_paths = true to remove"
    print(f"Checking for directories left behind by renames ({mode})...")
    for server in config.get("servers", {}):
        if (public_dir / server).is_dir():
            prune_server(public_dir, server, base_url, enabled=enabled)


if __name__ == "__main__":
    main()
