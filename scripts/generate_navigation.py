# scripts/generate_navigation.py
"""Generate navigation index pages from exported logs."""
import json
from pathlib import Path
from typing import List, Dict
from datetime import datetime, timezone
from jinja2 import Environment, FileSystemLoader

def scan_exports(public_dir: Path) -> List[Dict]:
    """
    Scan public directory for exported files.

    Args:
        public_dir: Path to public directory

    Returns:
        List of export info dicts
    """
    exports = []

    for html_file in public_dir.rglob("*.html"):
        # Skip index files
        if html_file.name == "index.html":
            continue

        # Parse path: public/server/channel/YYYY-MM.html
        parts = html_file.relative_to(public_dir).parts
        if len(parts) >= 3:
            server = parts[0]
            channel = parts[1]
            date = html_file.stem  # YYYY-MM

            exports.append({
                'server': server,
                'channel': channel,
                'date': date,
                'path': str(html_file.relative_to(public_dir))
            })

    return exports

def count_messages_from_json(json_path: str) -> int:
    """
    Count messages in JSON export file.

    Args:
        json_path: Path to JSON file (JSONL format)

    Returns:
        Number of messages
    """
    count = 0
    try:
        with open(json_path, 'r') as f:
            for line in f:
                if line.strip():
                    count += 1
    except FileNotFoundError:
        return 0

    return count

def group_by_year(archives: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Group archives by year.

    Args:
        archives: List of archive dicts with 'date' field

    Returns:
        Dict mapping year to list of archives
    """
    grouped = {}

    for archive in archives:
        year = archive['date'].split('-')[0]
        if year not in grouped:
            grouped[year] = []
        grouped[year].append(archive)

    # Sort each year's archives reverse chronologically
    for year in grouped:
        grouped[year].sort(key=lambda a: a['date'], reverse=True)

    return grouped

def generate_site_index(
    config: Dict,
    servers: List[Dict],
    output_path: Path
) -> None:
    """
    Generate site index page.

    Args:
        config: Site configuration
        servers: List of server info dicts
        output_path: Where to write index.html
    """
    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('site_index.html.j2')

    html = template.render(
        site=config['site'],
        servers=servers,
        last_updated=datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)

def generate_server_index(
    config: Dict,
    server: Dict,
    channels: List[Dict],
    output_path: Path
) -> None:
    """
    Generate server index page.

    Args:
        config: Site configuration
        server: Server info dict
        channels: List of channel info dicts
        output_path: Where to write index.html
    """
    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('server_index.html.j2')

    html = template.render(
        site=config['site'],
        server=server,
        channels=channels
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)

def generate_channel_index(
    config: Dict,
    server: Dict,
    channel: Dict,
    archives: List[Dict],
    output_path: Path
) -> None:
    """
    Generate channel archive index page.

    Args:
        config: Site configuration
        server: Server info dict
        channel: Channel info dict
        archives: List of archive info dicts
        output_path: Where to write index.html
    """
    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('channel_index.html.j2')

    archives_by_year = group_by_year(archives)

    html = template.render(
        site=config['site'],
        server=server,
        channel=channel,
        archives_by_year=archives_by_year
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)
