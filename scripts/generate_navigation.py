# scripts/generate_navigation.py
"""Generate navigation index pages from exported logs."""
import sys
from pathlib import Path
from typing import List, Dict
from datetime import datetime, timezone
from jinja2 import Environment, FileSystemLoader

# Handle imports for both direct execution and pytest
try:
    from scripts.config import load_config
    from scripts.thread_metadata import extract_thread_metadata
except ModuleNotFoundError:
    from config import load_config
    from thread_metadata import extract_thread_metadata

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

def organize_data(exports: List[Dict], public_dir: Path) -> Dict:
    """
    Organize exports data by server and channel with statistics.

    Args:
        exports: List of export info dicts from scan_exports
        public_dir: Path to public directory for message counting

    Returns:
        Dict mapping server names to server data with channels
    """
    servers_data = {}

    for export in exports:
        server = export['server']
        channel = export['channel']
        date = export['date']

        # Initialize server if not exists
        if server not in servers_data:
            servers_data[server] = {
                'name': server,
                'display_name': server.replace('-', ' ').title(),
                'channels': {}
            }

        # Initialize channel if not exists
        if channel not in servers_data[server]['channels']:
            servers_data[server]['channels'][channel] = {
                'name': channel,
                'archives': []
            }

        # Count messages from JSON file
        json_path = public_dir / server / channel / f"{date}.json"
        message_count = count_messages_from_json(str(json_path))

        servers_data[server]['channels'][channel]['archives'].append({
            'date': date,
            'message_count': message_count
        })

    # Calculate statistics for each server and channel
    for server_data in servers_data.values():
        server_data['channel_count'] = len(server_data['channels'])
        server_data['last_updated'] = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')

        for channel_data in server_data['channels'].values():
            # Sort archives reverse chronologically (newest first)
            channel_data['archives'].sort(key=lambda a: a['date'], reverse=True)
            channel_data['archive_count'] = len(channel_data['archives'])

            # Current month message count (most recent archive)
            if channel_data['archives']:
                channel_data['message_count'] = channel_data['archives'][0]['message_count']
            else:
                channel_data['message_count'] = 0

    return servers_data

def collect_forum_threads(forum_dir: Path) -> List[Dict]:
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
        json_files = list(thread_dir.glob('*/*.json'))
        if not json_files:
            continue

        # Use first JSON file found (usually there's only one per thread)
        json_file = json_files[0]

        # Extract metadata
        metadata = extract_thread_metadata(json_file)
        if metadata:
            threads.append({
                'name': thread_dir.name,
                'title': metadata['title'],
                'url': f"{thread_dir.name}/",
                'reply_count': metadata['reply_count'],
                'last_activity': metadata['last_activity'],
                'archived': metadata['archived']
            })

    # Sort by last activity (newest first)
    threads.sort(key=lambda t: t['last_activity'] or '', reverse=True)

    return threads


def generate_forum_index(
    config: Dict,
    server: Dict,
    forum_name: str,
    threads: List[Dict],
    output_path: Path,
    forum_description: str = None
) -> None:
    """Generate forum index page.

    Args:
        config: Site configuration
        server: Server info dict
        forum_name: Name of the forum
        threads: List of thread metadata dicts
        output_path: Where to write index.html
        forum_description: Optional forum description
    """
    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('forum_index.html.j2')

    html = template.render(
        site=config['site'],
        server=server,
        forum_name=forum_name.title(),  # Capitalize for display
        forum_description=forum_description,
        threads=threads
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)

def main():
    """Entry point for navigation generation."""
    print("Generating navigation pages...")

    try:
        config = load_config()
        public_dir = Path("public")

        if not public_dir.exists():
            print("ERROR: public/ directory not found. Run export first.")
            sys.exit(1)

        # Scan all exports
        print("Scanning exports...")
        exports = scan_exports(public_dir)

        if not exports:
            print("WARNING: No exports found.")
            return

        # Organize data by server and channel
        servers_data = organize_data(exports, public_dir)

        # Generate site index
        print("Generating site index...")
        generate_site_index(
            config,
            list(servers_data.values()),
            public_dir / "index.html"
        )

        # Generate server indexes and channel indexes
        for server_data in servers_data.values():
            print(f"Generating index for {server_data['display_name']}...")

            # Sort channels alphabetically
            channels_list = list(server_data['channels'].values())
            channels_list.sort(key=lambda c: c['name'])

            # Generate server index
            generate_server_index(
                config,
                server_data,
                channels_list,
                public_dir / server_data['name'] / "index.html"
            )

            # Generate channel indexes
            for channel_data in channels_list:
                generate_channel_index(
                    config,
                    server_data,
                    channel_data,
                    channel_data['archives'],
                    public_dir / server_data['name'] / channel_data['name'] / "index.html"
                )

            # Generate forum index pages
            server_name = server_data['name']
            server_config = config.get('servers', {}).get(server_name, {})
            forum_channels = server_config.get('forum_channels', [])

            if forum_channels:
                print(f"Generating forum indexes for {server_data['display_name']}...")

                for forum_name in forum_channels:
                    forum_dir = public_dir / server_name / forum_name

                    if forum_dir.exists() and forum_dir.is_dir():
                        # Collect thread metadata
                        threads = collect_forum_threads(forum_dir)

                        # Generate forum index page
                        generate_forum_index(
                            config,
                            server_data,
                            forum_name,
                            threads,
                            forum_dir / "index.html",
                            forum_description=None  # Could be added to config
                        )

                        print(f"  ✓ Generated forum index: {forum_name} ({len(threads)} threads)")

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
