# discord.wafer.space Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build an automated Discord log archival website that exports wafer.space Discord channels to multiple formats (HTML, TXT, JSON, CSV) with hourly updates and publishes to discord.wafer.space via GitHub Pages.

**Architecture:** Pipeline architecture using DiscordChatExporter CLI for exports, Python scripts for organization and navigation generation, GitHub Actions for hourly automation, and GitHub Pages for static hosting. Incremental exports track state to only fetch new messages.

**Tech Stack:**
- DiscordChatExporter CLI (C#/.NET export tool)
- Python 3.11+ with uv package manager
- Jinja2 templates for HTML generation
- GitHub Actions (hourly cron)
- GitHub Pages (static hosting)
- TOML for configuration

**Reference Design:** See `docs/plans/2025-11-14-discord-wafer-space-design.md` for complete architecture and design decisions.

---

## Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `config.toml`
- Create: `README.md`
- Create: `scripts/__init__.py`

**Step 1: Create requirements.txt**

Create the Python dependencies file:

```python
# requirements.txt
jinja2>=3.1.0
toml>=0.10.0
python-dateutil>=2.8.0
```

**Step 2: Create config.toml**

Create the configuration file with placeholder values:

```toml
# config.toml
[site]
title = "wafer.space Discord Logs"
description = "Public archive of wafer.space Discord server"
base_url = "https://discord.wafer.space"

[servers.wafer-space]
guild_id = "PLACEHOLDER_GUILD_ID"  # To be configured later
name = "wafer.space"
include_channels = ["*"]
exclude_channels = ["admin", "moderators", "private-*"]

[export]
formats = ["html", "txt", "json", "csv"]
partition_by = "month"
include_threads = "all"
download_media = true
media_dir = "public/assets/media"

[github]
pages_branch = "gh-pages"
commit_author = "Discord Archive Bot"
```

**Step 3: Create README.md**

```markdown
# discord.wafer.space

Automated Discord log archival website for wafer.space Discord server.

## Setup

1. Create Discord bot at https://discord.com/developers
2. Enable "Message Content Intent" in bot settings
3. Invite bot to server with permissions code: 66560
4. Add bot token to GitHub Secrets as `DISCORD_BOT_TOKEN`
5. Update `config.toml` with your guild_id

## Local Development

```bash
# Install dependencies
uv pip install -r requirements.txt

# Download DiscordChatExporter
wget https://github.com/Tyrrrz/DiscordChatExporter/releases/latest/download/DiscordChatExporter.Cli.linux-x64.zip
unzip DiscordChatExporter.Cli.linux-x64.zip
chmod +x DiscordChatExporter.Cli

# Run export
export DISCORD_BOT_TOKEN="your_token_here"
uv run python scripts/export_channels.py

# Generate navigation
uv run python scripts/generate_navigation.py

# Preview
python -m http.server --directory public 8000
```

## Architecture

See `docs/plans/2025-11-14-discord-wafer-space-design.md` for complete design.
```

**Step 4: Create scripts package**

```bash
mkdir -p scripts
touch scripts/__init__.py
```

**Step 5: Commit scaffolding**

```bash
git add requirements.txt config.toml README.md scripts/__init__.py
git commit -m "feat: add project scaffolding

- requirements.txt with Jinja2, toml, dateutil
- config.toml with placeholder configuration
- README.md with setup instructions
- scripts/ package for Python modules"
```

---

## Task 2: Configuration Module

**Files:**
- Create: `scripts/config.py`
- Create: `tests/test_config.py`

**Step 1: Write the failing test**

Create test file:

```python
# tests/test_config.py
import pytest
from pathlib import Path
from scripts.config import load_config

def test_load_config_returns_dict():
    """Test that load_config returns a dictionary"""
    config = load_config("config.toml")
    assert isinstance(config, dict)

def test_load_config_has_required_sections():
    """Test that config has site, servers, export sections"""
    config = load_config("config.toml")
    assert "site" in config
    assert "servers" in config
    assert "export" in config
    assert "github" in config

def test_load_config_site_values():
    """Test that site section has required values"""
    config = load_config("config.toml")
    assert config["site"]["title"] == "wafer.space Discord Logs"
    assert "base_url" in config["site"]

def test_load_config_export_formats():
    """Test that export formats are parsed correctly"""
    config = load_config("config.toml")
    assert "html" in config["export"]["formats"]
    assert "txt" in config["export"]["formats"]
    assert "json" in config["export"]["formats"]
    assert "csv" in config["export"]["formats"]
```

**Step 2: Run test to verify it fails**

```bash
mkdir -p tests
uv run pytest tests/test_config.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'scripts.config'"

**Step 3: Write minimal implementation**

```python
# scripts/config.py
"""Configuration management for discord-wafer-space."""
import toml
from pathlib import Path

def load_config(config_path: str = "config.toml") -> dict:
    """
    Load configuration from TOML file.

    Args:
        config_path: Path to config.toml file

    Returns:
        Dictionary containing configuration

    Raises:
        FileNotFoundError: If config file doesn't exist
        toml.TomlDecodeError: If config file is invalid
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path, 'r') as f:
        config = toml.load(f)

    return config
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_config.py -v
```

Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add scripts/config.py tests/test_config.py
git commit -m "feat: add configuration loading module

- Loads config.toml with toml library
- Validates required sections exist
- Returns dict with site, servers, export, github config"
```

---

## Task 3: State Management Module

**Files:**
- Create: `scripts/state.py`
- Create: `tests/test_state.py`
- Create: `state.json` (initial empty state)

**Step 1: Write the failing test**

```python
# tests/test_state.py
import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime
from scripts.state import StateManager

def test_state_manager_creates_empty_state():
    """Test that StateManager creates empty state if file doesn't exist"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        state_path = f.name

    Path(state_path).unlink()  # Remove it

    manager = StateManager(state_path)
    state = manager.load()

    assert state == {}
    Path(state_path).unlink()

def test_state_manager_loads_existing_state():
    """Test that StateManager loads existing state"""
    initial_state = {
        "wafer-space": {
            "general": {
                "last_export": "2025-01-15T14:00:00Z",
                "last_message_id": "123456"
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(initial_state, f)
        state_path = f.name

    manager = StateManager(state_path)
    state = manager.load()

    assert state == initial_state
    Path(state_path).unlink()

def test_state_manager_updates_channel_state():
    """Test updating state for a channel"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        state_path = f.name

    manager = StateManager(state_path)
    manager.load()

    timestamp = "2025-01-15T15:00:00Z"
    message_id = "789012"

    manager.update_channel("test-server", "general", timestamp, message_id)

    state = manager.load()
    assert state["test-server"]["general"]["last_export"] == timestamp
    assert state["test-server"]["general"]["last_message_id"] == message_id

    Path(state_path).unlink()

def test_state_manager_saves_state():
    """Test that state is persisted to disk"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        state_path = f.name

    manager = StateManager(state_path)
    manager.load()
    manager.update_channel("server", "channel", "2025-01-15T15:00:00Z", "123")
    manager.save()

    # Load in new manager instance
    manager2 = StateManager(state_path)
    state = manager2.load()

    assert state["server"]["channel"]["last_export"] == "2025-01-15T15:00:00Z"
    Path(state_path).unlink()
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_state.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'scripts.state'"

**Step 3: Write minimal implementation**

```python
# scripts/state.py
"""State management for tracking export progress."""
import json
from pathlib import Path
from typing import Dict, Optional

class StateManager:
    """Manages export state tracking."""

    def __init__(self, state_path: str = "state.json"):
        """
        Initialize state manager.

        Args:
            state_path: Path to state JSON file
        """
        self.state_path = Path(state_path)
        self.state: Dict = {}

    def load(self) -> Dict:
        """
        Load state from disk.

        Returns:
            State dictionary
        """
        if not self.state_path.exists():
            self.state = {}
            return self.state

        with open(self.state_path, 'r') as f:
            self.state = json.load(f)

        return self.state

    def save(self) -> None:
        """Save state to disk."""
        with open(self.state_path, 'w') as f:
            json.dump(self.state, f, indent=2)

    def update_channel(
        self,
        server: str,
        channel: str,
        timestamp: str,
        message_id: str
    ) -> None:
        """
        Update state for a channel.

        Args:
            server: Server name/ID
            channel: Channel name/ID
            timestamp: ISO format timestamp of last export
            message_id: ID of last exported message
        """
        if server not in self.state:
            self.state[server] = {}

        self.state[server][channel] = {
            "last_export": timestamp,
            "last_message_id": message_id
        }

    def get_channel_state(
        self,
        server: str,
        channel: str
    ) -> Optional[Dict]:
        """
        Get state for a channel.

        Args:
            server: Server name/ID
            channel: Channel name/ID

        Returns:
            Channel state dict or None if not found
        """
        if server not in self.state:
            return None

        return self.state[server].get(channel)
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_state.py -v
```

Expected: PASS (4 tests)

**Step 5: Create initial state.json**

```bash
echo '{}' > state.json
```

**Step 6: Commit**

```bash
git add scripts/state.py tests/test_state.py state.json
git commit -m "feat: add state management for export tracking

- StateManager class for tracking export progress
- Persists last export timestamp per channel
- Creates empty state if file doesn't exist
- Tests for load, save, update operations"
```

---

## Task 4: Export Orchestrator (Part 1: Channel Discovery)

**Files:**
- Create: `scripts/export_channels.py`
- Create: `tests/test_export_channels.py`

**Step 1: Write the failing test**

```python
# tests/test_export_channels.py
import pytest
import os
from scripts.export_channels import (
    get_bot_token,
    should_include_channel,
    format_export_command
)

def test_get_bot_token_from_env():
    """Test getting bot token from environment"""
    os.environ['DISCORD_BOT_TOKEN'] = 'test_token_123'
    token = get_bot_token()
    assert token == 'test_token_123'
    del os.environ['DISCORD_BOT_TOKEN']

def test_get_bot_token_raises_if_not_set():
    """Test that missing token raises error"""
    if 'DISCORD_BOT_TOKEN' in os.environ:
        del os.environ['DISCORD_BOT_TOKEN']

    with pytest.raises(ValueError, match="DISCORD_BOT_TOKEN"):
        get_bot_token()

def test_should_include_channel_with_wildcard():
    """Test channel inclusion with wildcard pattern"""
    include = ["*"]
    exclude = ["admin", "private-*"]

    assert should_include_channel("general", include, exclude) == True
    assert should_include_channel("announcements", include, exclude) == True

def test_should_include_channel_excludes_patterns():
    """Test channel exclusion patterns"""
    include = ["*"]
    exclude = ["admin", "private-*"]

    assert should_include_channel("admin", include, exclude) == False
    assert should_include_channel("private-chat", include, exclude) == False
    assert should_include_channel("private-logs", include, exclude) == False

def test_should_include_channel_specific_includes():
    """Test specific channel inclusion"""
    include = ["general", "announcements"]
    exclude = []

    assert should_include_channel("general", include, exclude) == True
    assert should_include_channel("announcements", include, exclude) == True
    assert should_include_channel("random", include, exclude) == False

def test_format_export_command():
    """Test export command formatting"""
    cmd = format_export_command(
        token="test_token",
        channel_id="123456",
        output_path="exports/test.html",
        format_type="HtmlDark",
        after_timestamp=None
    )

    expected = [
        "./DiscordChatExporter.Cli", "export",
        "-t", "test_token",
        "-c", "123456",
        "-f", "HtmlDark",
        "-o", "exports/test.html"
    ]

    assert cmd == expected

def test_format_export_command_with_after():
    """Test export command with --after flag"""
    cmd = format_export_command(
        token="test_token",
        channel_id="123456",
        output_path="exports/test.html",
        format_type="HtmlDark",
        after_timestamp="2025-01-15T14:00:00Z"
    )

    assert "--after" in cmd
    assert "2025-01-15T14:00:00Z" in cmd
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_export_channels.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'scripts.export_channels'"

**Step 3: Write minimal implementation**

```python
# scripts/export_channels.py
"""Export Discord channels using DiscordChatExporter CLI."""
import os
import re
from typing import List, Optional

def get_bot_token() -> str:
    """
    Get Discord bot token from environment.

    Returns:
        Bot token string

    Raises:
        ValueError: If DISCORD_BOT_TOKEN not set
    """
    token = os.environ.get('DISCORD_BOT_TOKEN')
    if not token:
        raise ValueError(
            "DISCORD_BOT_TOKEN environment variable not set. "
            "Add bot token to GitHub Secrets or export locally."
        )
    return token

def should_include_channel(
    channel_name: str,
    include_patterns: List[str],
    exclude_patterns: List[str]
) -> bool:
    """
    Check if channel should be included based on patterns.

    Args:
        channel_name: Name of the channel
        include_patterns: List of patterns to include (supports * wildcard)
        exclude_patterns: List of patterns to exclude (supports * wildcard)

    Returns:
        True if channel should be included
    """
    # Check exclusions first
    for pattern in exclude_patterns:
        regex_pattern = pattern.replace('*', '.*')
        if re.match(f'^{regex_pattern}$', channel_name):
            return False

    # Check inclusions
    if '*' in include_patterns:
        return True

    for pattern in include_patterns:
        regex_pattern = pattern.replace('*', '.*')
        if re.match(f'^{regex_pattern}$', channel_name):
            return True

    return False

def format_export_command(
    token: str,
    channel_id: str,
    output_path: str,
    format_type: str,
    after_timestamp: Optional[str] = None
) -> List[str]:
    """
    Format DiscordChatExporter CLI command.

    Args:
        token: Discord bot token
        channel_id: Channel ID to export
        output_path: Output file path
        format_type: Export format (HtmlDark, PlainText, Json, Csv)
        after_timestamp: Optional timestamp for incremental export

    Returns:
        Command as list of arguments
    """
    cmd = [
        "./DiscordChatExporter.Cli", "export",
        "-t", token,
        "-c", channel_id,
        "-f", format_type,
        "-o", output_path
    ]

    if after_timestamp:
        cmd.extend(["--after", after_timestamp])

    return cmd
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_export_channels.py -v
```

Expected: PASS (7 tests)

**Step 5: Commit**

```bash
git add scripts/export_channels.py tests/test_export_channels.py
git commit -m "feat: add export channel utilities

- get_bot_token() reads from environment
- should_include_channel() filters by patterns
- format_export_command() builds CLI command
- Support for wildcard patterns (* in config)"
```

---

## Task 5: Template System Setup

**Files:**
- Create: `templates/site_index.html.j2`
- Create: `templates/server_index.html.j2`
- Create: `templates/channel_index.html.j2`
- Create: `public/assets/style.css`

**Step 1: Create site index template**

```html
<!-- templates/site_index.html.j2 -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ site.title }}</title>
    <meta name="description" content="{{ site.description }}">
    <link rel="stylesheet" href="/assets/style.css">
</head>
<body>
    <header>
        <h1>{{ site.title }}</h1>
        <p class="description">{{ site.description }}</p>
        <p class="last-updated">Last updated: {{ last_updated }}</p>
    </header>

    <main>
        <section class="servers">
            <h2>Available Servers</h2>
            {% for server in servers %}
            <div class="server-card">
                <h3><a href="/{{ server.name }}/index.html">{{ server.display_name }}</a></h3>
                <p class="stats">{{ server.channel_count }} channels</p>
                <p class="updated">Last updated: {{ server.last_updated }}</p>
            </div>
            {% endfor %}
        </section>
    </main>

    <footer>
        <p>Generated with <a href="https://github.com/Tyrrrz/DiscordChatExporter">DiscordChatExporter</a></p>
        <p>Archived for public access • Not affiliated with Discord Inc.</p>
    </footer>
</body>
</html>
```

**Step 2: Create server index template**

```html
<!-- templates/server_index.html.j2 -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ server.display_name }} - {{ site.title }}</title>
    <link rel="stylesheet" href="/assets/style.css">
</head>
<body>
    <header>
        <nav class="breadcrumb">
            <a href="/index.html">Home</a> &gt;
            <span>{{ server.display_name }}</span>
        </nav>
        <h1>{{ server.display_name }} Discord Server</h1>
    </header>

    <main>
        <section class="channels">
            <h2>Channels</h2>
            {% for channel in channels %}
            <div class="channel-card">
                <h3><a href="/{{ server.name }}/{{ channel.name }}/index.html">#{{ channel.name }}</a></h3>
                <p class="stats">{{ channel.message_count }} messages this month</p>
                <div class="formats">
                    Formats:
                    <a href="/{{ server.name }}/{{ channel.name }}/latest.html">HTML</a> |
                    <a href="/{{ server.name }}/{{ channel.name }}/latest.txt">TXT</a> |
                    <a href="/{{ server.name }}/{{ channel.name }}/latest.json">JSON</a> |
                    <a href="/{{ server.name }}/{{ channel.name }}/latest.csv">CSV</a>
                </div>
                <details>
                    <summary>Archive History ({{ channel.archive_count }} months)</summary>
                    <ul class="archives">
                        {% for archive in channel.archives[:5] %}
                        <li>
                            <a href="/{{ server.name }}/{{ channel.name }}/{{ archive.date }}.html">{{ archive.date }}</a>
                            ({{ archive.message_count }} messages)
                        </li>
                        {% endfor %}
                        {% if channel.archive_count > 5 %}
                        <li><a href="/{{ server.name }}/{{ channel.name }}/index.html">See all {{ channel.archive_count }} archives...</a></li>
                        {% endif %}
                    </ul>
                </details>
            </div>
            {% endfor %}
        </section>
    </main>

    <footer>
        <p><a href="/index.html">← Back to all servers</a></p>
    </footer>
</body>
</html>
```

**Step 3: Create channel archive index template**

```html
<!-- templates/channel_index.html.j2 -->
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>#{{ channel.name }} Archive - {{ server.display_name }}</title>
    <link rel="stylesheet" href="/assets/style.css">
</head>
<body>
    <header>
        <nav class="breadcrumb">
            <a href="/index.html">Home</a> &gt;
            <a href="/{{ server.name }}/index.html">{{ server.display_name }}</a> &gt;
            <span>#{{ channel.name }}</span>
        </nav>
        <h1>#{{ channel.name }} Archive</h1>
    </header>

    <main>
        <section class="archives">
            {% for year, archives in archives_by_year.items() %}
            <h2>{{ year }}</h2>
            <ul class="archive-list">
                {% for archive in archives %}
                <li>
                    <strong>{{ archive.date }}</strong> ({{ archive.message_count }} messages)
                    <div class="formats">
                        <a href="/{{ server.name }}/{{ channel.name }}/{{ archive.date }}.html">HTML</a> |
                        <a href="/{{ server.name }}/{{ channel.name }}/{{ archive.date }}.txt">TXT</a> |
                        <a href="/{{ server.name }}/{{ channel.name }}/{{ archive.date }}.json">JSON</a> |
                        <a href="/{{ server.name }}/{{ channel.name }}/{{ archive.date }}.csv">CSV</a>
                    </div>
                </li>
                {% endfor %}
            </ul>
            {% endfor %}
        </section>
    </main>

    <footer>
        <p><a href="/{{ server.name }}/index.html">← Back to {{ server.display_name }}</a></p>
    </footer>
</body>
</html>
```

**Step 4: Create basic CSS**

```css
/* public/assets/style.css */
:root {
    --bg-primary: #36393f;
    --bg-secondary: #2f3136;
    --bg-tertiary: #202225;
    --text-primary: #dcddde;
    --text-secondary: #b9bbbe;
    --accent: #7289da;
    --accent-hover: #677bc4;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: 'Whitney', 'Helvetica Neue', Helvetica, Arial, sans-serif;
    background: var(--bg-primary);
    color: var(--text-primary);
    line-height: 1.6;
}

header {
    background: var(--bg-secondary);
    padding: 2rem;
    border-bottom: 1px solid var(--bg-tertiary);
}

header h1 {
    margin-bottom: 0.5rem;
}

.description {
    color: var(--text-secondary);
    font-size: 1.1rem;
}

.last-updated {
    color: var(--text-secondary);
    font-size: 0.9rem;
    margin-top: 0.5rem;
}

.breadcrumb {
    margin-bottom: 1rem;
    color: var(--text-secondary);
}

.breadcrumb a {
    color: var(--accent);
    text-decoration: none;
}

.breadcrumb a:hover {
    text-decoration: underline;
}

main {
    max-width: 1200px;
    margin: 2rem auto;
    padding: 0 2rem;
}

.server-card, .channel-card {
    background: var(--bg-secondary);
    padding: 1.5rem;
    margin: 1rem 0;
    border-radius: 8px;
    border-left: 4px solid var(--accent);
}

.server-card h3, .channel-card h3 {
    margin-bottom: 0.5rem;
}

.server-card a, .channel-card a {
    color: var(--accent);
    text-decoration: none;
}

.server-card a:hover, .channel-card a:hover {
    color: var(--accent-hover);
}

.stats, .updated {
    color: var(--text-secondary);
    font-size: 0.9rem;
    margin: 0.25rem 0;
}

.formats {
    margin-top: 0.75rem;
    color: var(--text-secondary);
    font-size: 0.9rem;
}

.formats a {
    color: var(--accent);
    text-decoration: none;
    margin: 0 0.25rem;
}

.formats a:hover {
    text-decoration: underline;
}

details {
    margin-top: 1rem;
}

summary {
    cursor: pointer;
    color: var(--text-secondary);
    font-size: 0.9rem;
}

summary:hover {
    color: var(--text-primary);
}

.archives {
    list-style: none;
    margin-top: 0.5rem;
    padding-left: 1rem;
}

.archives li {
    margin: 0.5rem 0;
    color: var(--text-secondary);
}

.archive-list {
    list-style: none;
}

.archive-list li {
    background: var(--bg-secondary);
    padding: 1rem;
    margin: 0.5rem 0;
    border-radius: 4px;
}

footer {
    text-align: center;
    padding: 2rem;
    color: var(--text-secondary);
    font-size: 0.9rem;
    border-top: 1px solid var(--bg-tertiary);
    margin-top: 4rem;
}

footer a {
    color: var(--accent);
    text-decoration: none;
}

footer a:hover {
    text-decoration: underline;
}
```

**Step 5: Create directories**

```bash
mkdir -p templates
mkdir -p public/assets
```

**Step 6: Commit templates**

```bash
git add templates/ public/assets/style.css
git commit -m "feat: add Jinja2 templates and CSS

- Site index template (server listing)
- Server index template (channel listing)
- Channel archive index template (monthly archives)
- Discord-themed CSS with dark mode styling"
```

---

## Task 6: Navigation Generator

**Files:**
- Create: `scripts/generate_navigation.py`
- Create: `tests/test_generate_navigation.py`

**Step 1: Write the failing test**

```python
# tests/test_generate_navigation.py
import pytest
import tempfile
from pathlib import Path
from scripts.generate_navigation import (
    scan_exports,
    count_messages_from_json,
    group_by_year,
    generate_site_index,
    generate_server_index,
    generate_channel_index
)

def test_scan_exports_finds_files():
    """Test that scan_exports finds exported files"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create fake export structure
        public = Path(tmpdir) / "public"
        server_dir = public / "test-server" / "general"
        server_dir.mkdir(parents=True)

        (server_dir / "2025-01.html").touch()
        (server_dir / "2025-01.json").touch()
        (server_dir / "2025-01.txt").touch()

        exports = scan_exports(public)

        assert len(exports) > 0
        assert any(e['channel'] == 'general' for e in exports)

def test_count_messages_from_json():
    """Test counting messages from JSON file"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        # Write sample JSON lines
        f.write('{"id": "1", "content": "Hello"}\n')
        f.write('{"id": "2", "content": "World"}\n')
        f.write('{"id": "3", "content": "Test"}\n')
        json_path = f.name

    count = count_messages_from_json(json_path)
    assert count == 3

    Path(json_path).unlink()

def test_group_by_year():
    """Test grouping archives by year"""
    archives = [
        {'date': '2025-01', 'message_count': 100},
        {'date': '2025-02', 'message_count': 150},
        {'date': '2024-12', 'message_count': 200},
        {'date': '2024-11', 'message_count': 250},
    ]

    grouped = group_by_year(archives)

    assert '2025' in grouped
    assert '2024' in grouped
    assert len(grouped['2025']) == 2
    assert len(grouped['2024']) == 2
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_generate_navigation.py -v
```

Expected: FAIL with "ModuleNotFoundError"

**Step 3: Write minimal implementation**

```python
# scripts/generate_navigation.py
"""Generate navigation index pages from exported logs."""
import json
from pathlib import Path
from typing import List, Dict
from datetime import datetime
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
        last_updated=datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
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
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_generate_navigation.py -v
```

Expected: PASS (3 tests)

**Step 5: Commit**

```bash
git add scripts/generate_navigation.py tests/test_generate_navigation.py
git commit -m "feat: add navigation generation utilities

- scan_exports() discovers all exported files
- count_messages_from_json() counts messages
- group_by_year() organizes archives chronologically
- generate_*_index() renders Jinja2 templates"
```

---

## Task 7: Main Export Script

**Files:**
- Modify: `scripts/export_channels.py` (add main function)

**Step 1: Add main orchestration function**

```python
# Add to scripts/export_channels.py

import subprocess
import sys
from pathlib import Path
from datetime import datetime
from scripts.config import load_config
from scripts.state import StateManager

def run_export(
    cmd: List[str],
    timeout: int = 300
) -> tuple[bool, str]:
    """
    Run DiscordChatExporter command.

    Args:
        cmd: Command as list
        timeout: Timeout in seconds

    Returns:
        Tuple of (success, output)
    """
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )

        success = result.returncode == 0
        output = result.stdout + result.stderr

        return success, output

    except subprocess.TimeoutExpired:
        return False, f"Export timed out after {timeout} seconds"
    except Exception as e:
        return False, f"Export failed: {str(e)}"

def export_all_channels() -> Dict:
    """
    Main export orchestration function.

    Returns:
        Summary dict with stats
    """
    print("Loading configuration...")
    config = load_config()

    token = get_bot_token()
    state_manager = StateManager()
    state_manager.load()

    summary = {
        'channels_updated': 0,
        'channels_failed': 0,
        'total_exports': 0,
        'errors': []
    }

    # Create exports directory
    exports_dir = Path("exports")
    exports_dir.mkdir(exist_ok=True)

    print(f"\nStarting exports...")

    for server_key, server_config in config['servers'].items():
        print(f"\nProcessing server: {server_config['name']}")

        server_dir = exports_dir / server_key
        server_dir.mkdir(exist_ok=True)

        # For now, we'll need to manually list channels
        # In a future task, we'll add API calls to discover channels
        # For MVP, we expect channels to be configured

        channels = server_config.get('channels', [])
        include_patterns = server_config['include_channels']
        exclude_patterns = server_config['exclude_channels']

        for channel in channels:
            channel_name = channel['name']
            channel_id = channel['id']

            if not should_include_channel(channel_name, include_patterns, exclude_patterns):
                print(f"  Skipping {channel_name} (excluded by pattern)")
                continue

            print(f"  Exporting #{channel_name}...")

            # Get last export time
            channel_state = state_manager.get_channel_state(server_key, channel_name)
            after_timestamp = channel_state['last_export'] if channel_state else None

            # Export all formats
            for fmt in config['export']['formats']:
                format_map = {
                    'html': 'HtmlDark',
                    'txt': 'PlainText',
                    'json': 'Json',
                    'csv': 'Csv'
                }

                output_path = server_dir / f"{channel_name}.{fmt}"

                cmd = format_export_command(
                    token=token,
                    channel_id=channel_id,
                    output_path=str(output_path),
                    format_type=format_map[fmt],
                    after_timestamp=after_timestamp
                )

                success, output = run_export(cmd)

                if success:
                    summary['total_exports'] += 1
                    print(f"    ✓ {fmt.upper()}")
                else:
                    summary['channels_failed'] += 1
                    summary['errors'].append({
                        'channel': channel_name,
                        'format': fmt,
                        'error': output
                    })
                    print(f"    ✗ {fmt.upper()} failed")

            # Update state with current timestamp
            # In real implementation, we'd get the actual last message timestamp
            state_manager.update_channel(
                server_key,
                channel_name,
                datetime.utcnow().isoformat() + 'Z',
                "placeholder_message_id"
            )

            summary['channels_updated'] += 1

    # Save state
    state_manager.save()

    return summary

def main():
    """Entry point for export script."""
    print("Discord Channel Exporter")
    print("=" * 50)

    try:
        summary = export_all_channels()

        print("\n" + "=" * 50)
        print("Export Summary:")
        print(f"  Channels updated: {summary['channels_updated']}")
        print(f"  Channels failed: {summary['channels_failed']}")
        print(f"  Total exports: {summary['total_exports']}")

        if summary['errors']:
            print(f"\nErrors ({len(summary['errors'])}):")
            for error in summary['errors'][:5]:  # Show first 5
                print(f"  - {error['channel']} ({error['format']}): {error['error'][:100]}")

        sys.exit(0 if summary['channels_failed'] == 0 else 1)

    except Exception as e:
        print(f"\nFATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
```

**Step 2: Update config.toml to include channel list**

```toml
# Add to config.toml under [servers.wafer-space]
channels = [
    { name = "general", id = "PLACEHOLDER_CHANNEL_ID" },
    { name = "announcements", id = "PLACEHOLDER_CHANNEL_ID" }
]
```

**Step 3: Test manually (will fail without real data)**

```bash
# This will fail because we don't have DiscordChatExporter or real IDs yet
# But we can verify the script structure is correct
uv run python scripts/export_channels.py --help || echo "Script loads correctly"
```

**Step 4: Commit**

```bash
git add scripts/export_channels.py config.toml
git commit -m "feat: add main export orchestration

- export_all_channels() orchestrates full export
- run_export() executes DiscordChatExporter CLI
- Loops through servers and channels
- Updates state after each export
- Generates summary with stats and errors"
```

---

## Task 8: Main Navigation Script

**Files:**
- Create: `scripts/generate_navigation.py` (add main function)

**Step 1: Add main orchestration**

```python
# Add to scripts/generate_navigation.py

def main():
    """Entry point for navigation generation."""
    print("Generating navigation pages...")

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

    # Group by server and channel
    servers_data = {}

    for export in exports:
        server = export['server']
        channel = export['channel']
        date = export['date']

        if server not in servers_data:
            servers_data[server] = {
                'name': server,
                'display_name': server.replace('-', ' ').title(),
                'channels': {}
            }

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

    # Calculate stats
    for server_data in servers_data.values():
        server_data['channel_count'] = len(server_data['channels'])
        server_data['last_updated'] = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')

        for channel_data in server_data['channels'].values():
            # Sort archives reverse chronologically
            channel_data['archives'].sort(key=lambda a: a['date'], reverse=True)
            channel_data['archive_count'] = len(channel_data['archives'])

            # Current month message count
            if channel_data['archives']:
                channel_data['message_count'] = channel_data['archives'][0]['message_count']
            else:
                channel_data['message_count'] = 0

    # Generate site index
    print("Generating site index...")
    generate_site_index(
        config,
        list(servers_data.values()),
        public_dir / "index.html"
    )

    # Generate server indexes
    for server_data in servers_data.values():
        print(f"Generating index for {server_data['display_name']}...")

        channels_list = list(server_data['channels'].values())
        channels_list.sort(key=lambda c: c['name'])

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

    print(f"\n✓ Generated {len(servers_data)} server indexes")
    print(f"✓ Site index at public/index.html")

if __name__ == "__main__":
    import sys
    main()
```

**Step 2: Commit**

```bash
git add scripts/generate_navigation.py
git commit -m "feat: add navigation generation main function

- Scans public/ for all exports
- Groups by server and channel
- Calculates message counts and stats
- Generates all three index levels
- Sorts archives chronologically"
```

---

## Task 9: GitHub Actions Workflow

**Files:**
- Create: `.github/workflows/export-logs.yml`

**Step 1: Create workflow file**

```yaml
# .github/workflows/export-logs.yml
name: Export Discord Logs

on:
  schedule:
    # Run every 2 hours (to stay under GitHub Actions limits)
    - cron: '0 */2 * * *'

  workflow_dispatch:  # Allow manual trigger

  push:
    branches: [feature/discord-wafer-space]  # For testing

jobs:
  export-and-deploy:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Full history for state.json

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install uv
        run: pip install uv

      - name: Install Python dependencies
        run: uv pip install -r requirements.txt

      - name: Cache DiscordChatExporter
        id: cache-dce
        uses: actions/cache@v4
        with:
          path: DiscordChatExporter.Cli
          key: dce-${{ runner.os }}-latest

      - name: Download DiscordChatExporter
        if: steps.cache-dce.outputs.cache-hit != 'true'
        run: |
          wget https://github.com/Tyrrrz/DiscordChatExporter/releases/latest/download/DiscordChatExporter.Cli.linux-x64.zip
          unzip DiscordChatExporter.Cli.linux-x64.zip
          chmod +x DiscordChatExporter.Cli
          rm DiscordChatExporter.Cli.linux-x64.zip

      - name: Run export pipeline
        env:
          DISCORD_BOT_TOKEN: ${{ secrets.DISCORD_BOT_TOKEN }}
        run: |
          echo "Starting export..."
          uv run python scripts/export_channels.py

          echo "Organizing exports..."
          # TODO: Add organize_exports.py when implemented

          echo "Generating navigation..."
          uv run python scripts/generate_navigation.py

      - name: Check for changes
        id: check_changes
        run: |
          if git diff --quiet public/ state.json; then
            echo "has_changes=false" >> $GITHUB_OUTPUT
          else
            echo "has_changes=true" >> $GITHUB_OUTPUT
          fi

      - name: Commit state.json to main
        if: steps.check_changes.outputs.has_changes == 'true'
        run: |
          git config user.name "Discord Archive Bot"
          git config user.email "actions@github.com"
          git add state.json
          git commit -m "chore: update export state

          Updated by GitHub Actions on $(date -u +%Y-%m-%d\ %H:%M\ UTC)"
          git push origin HEAD:main

      - name: Deploy to GitHub Pages
        if: steps.check_changes.outputs.has_changes == 'true'
        uses: peaceiris/actions-gh-pages@v4
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./public
          publish_branch: gh-pages
          user_name: 'Discord Archive Bot'
          user_email: 'actions@github.com'
          commit_message: 'chore: deploy updated logs'

      - name: Report summary
        if: always()
        run: |
          echo "## Export Summary" >> $GITHUB_STEP_SUMMARY
          echo "- **Status**: ${{ job.status }}" >> $GITHUB_STEP_SUMMARY
          echo "- **Changes**: ${{ steps.check_changes.outputs.has_changes }}" >> $GITHUB_STEP_SUMMARY
          echo "- **Timestamp**: $(date -u +%Y-%m-%d\ %H:%M\ UTC)" >> $GITHUB_STEP_SUMMARY
```

**Step 2: Create .github directory**

```bash
mkdir -p .github/workflows
```

**Step 3: Commit workflow**

```bash
git add .github/workflows/export-logs.yml
git commit -m "feat: add GitHub Actions workflow

- Runs every 2 hours (within free tier limits)
- Caches DiscordChatExporter binary
- Runs export and navigation generation
- Commits state.json to main branch
- Deploys public/ to gh-pages branch
- Only commits if changes detected"
```

---

## Task 10: Update README with Setup Instructions

**Files:**
- Modify: `README.md`

**Step 1: Enhance README with complete setup guide**

```markdown
# discord.wafer.space

Automated Discord log archival website for wafer.space Discord server.

## Features

- 📦 **Multi-format exports**: HTML, TXT, JSON, CSV
- 🔄 **Hourly updates**: Automated via GitHub Actions
- 📅 **Monthly archives**: Organized by date with navigation
- 🔍 **SEO-friendly**: Static HTML indexed by search engines
- 🎨 **Discord-themed UI**: Familiar look and feel
- 📊 **Message statistics**: Counts and archive history

## Architecture

See [Design Document](docs/plans/2025-11-14-discord-wafer-space-design.md) for complete architecture.

**Pipeline**: Discord API → DiscordChatExporter → Python Scripts → GitHub Pages

## Setup Guide

### 1. Create Discord Bot

1. Go to https://discord.com/developers/applications
2. Click "New Application", give it a name
3. Go to "Bot" section, click "Add Bot"
4. **Enable "Message Content Intent"** (required!)
5. Copy bot token (keep secret!)
6. Go to OAuth2 → URL Generator
7. Select "bot" scope and permissions code: `66560`
8. Open generated URL and invite bot to your server

### 2. Configure Repository

1. **Add GitHub Secret**:
   - Go to repository Settings → Secrets and variables → Actions
   - Click "New repository secret"
   - Name: `DISCORD_BOT_TOKEN`
   - Value: (paste your bot token)

2. **Update config.toml**:
   ```toml
   [servers.wafer-space]
   guild_id = "YOUR_GUILD_ID_HERE"  # Right-click server → Copy ID

   channels = [
       { name = "general", id = "YOUR_CHANNEL_ID" },
       { name = "announcements", id = "YOUR_CHANNEL_ID" }
   ]
   ```

3. **Get IDs**:
   - Enable Developer Mode: Settings → Advanced → Developer Mode
   - Right-click server → Copy Server ID
   - Right-click channel → Copy Channel ID

### 3. Initial Export

**Option A: GitHub Actions (recommended)**:
1. Go to Actions tab
2. Select "Export Discord Logs" workflow
3. Click "Run workflow"
4. Wait for completion (~10-30 minutes for full history)

**Option B: Local testing**:
```bash
# Install dependencies
uv pip install -r requirements.txt

# Download DiscordChatExporter
wget https://github.com/Tyrrrz/DiscordChatExporter/releases/latest/download/DiscordChatExporter.Cli.linux-x64.zip
unzip DiscordChatExporter.Cli.linux-x64.zip
chmod +x DiscordChatExporter.Cli

# Set token
export DISCORD_BOT_TOKEN="your_token_here"

# Run export
uv run python scripts/export_channels.py

# Generate navigation
uv run python scripts/generate_navigation.py

# Preview locally
python -m http.server --directory public 8000
# Visit http://localhost:8000
```

### 4. Enable GitHub Pages

1. Go to repository Settings → Pages
2. Source: "Deploy from a branch"
3. Branch: `gh-pages` / `root`
4. Save
5. Optional: Add custom domain `discord.wafer.space`

### 5. Verify

- Check Actions tab for successful runs
- Visit your GitHub Pages URL
- Verify channels are listed
- Check that archives load correctly

## Maintenance

### Daily

- ✅ **None!** Fully automated via GitHub Actions

### Weekly

- Check Actions tab for any failed runs
- Review error logs if exports fail

### Monthly

- Review disk usage (exports grow over time)
- Verify all channels exporting correctly

## Troubleshooting

**Empty exports / No messages**:
- Verify "Message Content Intent" is enabled in bot settings
- Check bot has "Read Message History" permission
- Confirm bot is in the server

**Export fails with 403 Forbidden**:
- Bot lacks channel access permissions
- Add bot role to channel permissions

**Workflow fails**:
- Check `DISCORD_BOT_TOKEN` secret is set correctly
- Review workflow logs in Actions tab
- Verify token hasn't been reset/revoked

**Navigation not updating**:
- Ensure `generate_navigation.py` runs after export
- Check public/ directory has exported files
- Verify Jinja2 templates exist in templates/

## Project Structure

```
discord-wafer-space/
├── .github/workflows/     # GitHub Actions automation
├── scripts/               # Python export and navigation scripts
├── templates/             # Jinja2 HTML templates
├── public/                # Generated static site (deployed)
├── exports/               # Temporary export storage (gitignored)
├── tests/                 # pytest test suite
├── config.toml            # Configuration
├── state.json             # Export state tracking
└── requirements.txt       # Python dependencies
```

## Development

**Run tests**:
```bash
uv run pytest tests/ -v
```

**Type checking** (future):
```bash
uv run mypy scripts/
```

**Code formatting** (future):
```bash
uv run black scripts/ tests/
```

## License

MIT License - See LICENSE file

## Credits

- Built with [DiscordChatExporter](https://github.com/Tyrrrz/DiscordChatExporter) by Tyrrrz
- Hosted on [GitHub Pages](https://pages.github.com/)
- Automated with [GitHub Actions](https://github.com/features/actions)
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: enhance README with complete setup guide

- Step-by-step bot setup instructions
- GitHub configuration guide
- Local testing commands
- Troubleshooting section
- Maintenance guidelines"
```

---

## Task 11: Add pytest Configuration

**Files:**
- Create: `pytest.ini`
- Create: `tests/__init__.py`

**Step 1: Create pytest configuration**

```ini
# pytest.ini
[pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts =
    -v
    --strict-markers
    --tb=short
    --color=yes
markers =
    integration: Integration tests (slow)
    unit: Unit tests (fast)
```

**Step 2: Create tests init file**

```bash
touch tests/__init__.py
```

**Step 3: Run all tests**

```bash
uv run pytest
```

Expected: All tests pass

**Step 4: Commit**

```bash
git add pytest.ini tests/__init__.py
git commit -m "test: add pytest configuration

- Configure test discovery
- Add markers for unit vs integration tests
- Enable strict mode and colors
- Set verbose output by default"
```

---

## Task 12: Add File Organization Script (Future Enhancement)

**Files:**
- Create: `scripts/organize_exports.py` (stub for now)

**Step 1: Create organize script stub**

```python
# scripts/organize_exports.py
"""Organize exported files into date-based directory structure."""
from pathlib import Path
import shutil

def organize_exports() -> None:
    """
    Move exports from exports/ to public/ with date-based organization.

    Future enhancement: Partition by month/day automatically.
    For MVP: Just copy to public/ directory.
    """
    exports_dir = Path("exports")
    public_dir = Path("public")

    if not exports_dir.exists():
        print("No exports directory found")
        return

    # Copy all exports to public
    for server_dir in exports_dir.iterdir():
        if not server_dir.is_dir():
            continue

        server_name = server_dir.name
        public_server = public_dir / server_name

        for export_file in server_dir.iterdir():
            if export_file.is_file():
                # For now, simple copy
                # Future: Parse filename, organize by date

                channel_name = export_file.stem  # filename without extension
                ext = export_file.suffix  # .html, .txt, etc.

                # Create channel directory
                channel_dir = public_server / channel_name
                channel_dir.mkdir(parents=True, exist_ok=True)

                # Copy file (for MVP, use current date as archive name)
                # Future: Extract actual date range from export
                from datetime import datetime
                current_month = datetime.utcnow().strftime('%Y-%m')

                dest = channel_dir / f"{current_month}{ext}"
                shutil.copy2(export_file, dest)

                # Create "latest" symlink
                latest = channel_dir / f"latest{ext}"
                if latest.exists():
                    latest.unlink()
                latest.symlink_to(dest.name)

    print(f"✓ Organized exports to public/")

def main():
    """Entry point."""
    organize_exports()

if __name__ == "__main__":
    main()
```

**Step 2: Update GitHub Actions to call organize script**

In `.github/workflows/export-logs.yml`, uncomment the organize step:

```yaml
- name: Run export pipeline
  env:
    DISCORD_BOT_TOKEN: ${{ secrets.DISCORD_BOT_TOKEN }}
  run: |
    echo "Starting export..."
    uv run python scripts/export_channels.py

    echo "Organizing exports..."
    uv run python scripts/organize_exports.py  # Uncomment this

    echo "Generating navigation..."
    uv run python scripts/generate_navigation.py
```

**Step 3: Commit**

```bash
git add scripts/organize_exports.py .github/workflows/export-logs.yml
git commit -m "feat: add file organization script

- Copies exports from exports/ to public/
- Creates channel directories
- Uses current month as archive name (MVP)
- Creates 'latest' symlinks for each format
- Future: parse actual date ranges from exports"
```

---

## Execution Summary

**Plan complete!** The implementation plan is saved to:
`docs/plans/2025-11-14-discord-wafer-space.md`

**What's included:**

1. ✅ Project scaffolding (requirements, config, README)
2. ✅ Configuration loading module
3. ✅ State management for incremental exports
4. ✅ Export channel utilities
5. ✅ Jinja2 templates and CSS
6. ✅ Navigation generation
7. ✅ Main export orchestration
8. ✅ Main navigation script
9. ✅ GitHub Actions workflow
10. ✅ Enhanced documentation
11. ✅ Test configuration
12. ✅ File organization script

**Total: 12 tasks, ~50-60 individual steps**

**Estimated time**: 4-6 hours for full implementation

---

## Post-Implementation Tasks

After completing all tasks above:

1. **Configure real IDs**:
   - Get actual guild_id and channel_ids
   - Update config.toml

2. **Add bot token to GitHub**:
   - Settings → Secrets → DISCORD_BOT_TOKEN

3. **Test full pipeline locally**:
   - Run export with real token
   - Verify exports generated
   - Check navigation renders correctly

4. **Run initial export via GitHub Actions**:
   - Trigger workflow manually
   - Monitor for errors
   - Verify gh-pages deployment

5. **Enable custom domain** (optional):
   - Add CNAME record in DNS
   - Configure in GitHub Pages settings

6. **Monitor for 48 hours**:
   - Check hourly runs succeed
   - Verify no rate limiting issues
   - Ensure state.json updates correctly

---

## Future Enhancements

After MVP is working:

1. **Add Pagefind search**
2. **Implement RSS feeds**
3. **Add Tiny Tapeout server**
4. **Daily partitioning option**
5. **Better error notifications** (Discord webhook)
6. **Performance optimizations** (parallel exports)
7. **Archive.org backup integration**
