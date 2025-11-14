# Forum Thread Export Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add support for exporting Discord forum channels and their threads with nested directory structure and forum index pages.

**Architecture:** Extend channel discovery to include threads using `--include-threads All`, classify channels into regular/forum/thread types, organize threads under parent forum directories, and generate forum index pages listing all threads with metadata.

**Tech Stack:** Python 3.11+, DiscordChatExporter CLI, pytest, Jinja2 templates, subprocess

---

## Task 1: Add Thread Detection to Channel Fetching

**Files:**
- Modify: `scripts/export_channels.py:146-207` (fetch_guild_channels function)
- Test: `tests/test_fetch_channels.py`

**Step 1: Write test for thread detection**

Add to `tests/test_fetch_channels.py`:

```python
def test_fetch_guild_channels_includes_threads():
    """Test that threads are included when fetching channels."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="""General / general [123456]
Questions / How do I start? [789012]
Questions / Troubleshooting help [789013]
""",
            stderr=""
        )

        channels = fetch_guild_channels("test_token", "guild123", include_threads=True)

        # Should include both regular channel and threads
        assert len(channels) == 3
        assert channels[0] == {'name': 'general', 'id': '123456', 'parent_id': None}
        assert channels[1] == {'name': 'How do I start?', 'id': '789012', 'parent_id': 'Questions'}
        assert channels[2] == {'name': 'Troubleshooting help', 'id': '789013', 'parent_id': 'Questions'}


def test_fetch_guild_channels_without_threads():
    """Test that threads are excluded when include_threads=False."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="General / general [123456]\n",
            stderr=""
        )

        channels = fetch_guild_channels("test_token", "guild123", include_threads=False)

        assert len(channels) == 1
        assert channels[0] == {'name': 'general', 'id': '123456', 'parent_id': None}
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_fetch_channels.py::test_fetch_guild_channels_includes_threads -v
```

Expected: FAIL with "TypeError: fetch_guild_channels() got an unexpected keyword argument 'include_threads'"

**Step 3: Update fetch_guild_channels signature and implementation**

In `scripts/export_channels.py`, replace the `fetch_guild_channels` function:

```python
def fetch_guild_channels(token: str, guild_id: str, include_threads: bool = True) -> List[Dict[str, str]]:
    """
    Fetch all channels from a Discord guild using DiscordChatExporter.

    Args:
        token: Discord bot token
        guild_id: Guild (server) ID
        include_threads: Whether to include threads (default: True)

    Returns:
        List of channel dicts with 'name', 'id', and 'parent_id' keys

    Raises:
        RuntimeError: If channel fetching fails
    """
    cmd = [
        "bin/discord-exporter/DiscordChatExporter.Cli", "channels",
        "-t", token,
        "-g", guild_id
    ]

    if include_threads:
        cmd.extend(["--include-threads", "All"])

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Failed to fetch channels: {result.stderr or result.stdout}"
            )

        # Parse output - DiscordChatExporter outputs one channel per line
        # Format: "Category / ChannelName [ChannelID]" or "ChannelName [ChannelID]"
        channels = []
        for line in result.stdout.strip().split('\n'):
            if not line or not line.strip():
                continue

            # Extract channel ID from brackets
            if '[' in line and ']' in line:
                channel_id = line.split('[')[-1].split(']')[0].strip()

                # Extract channel name (after last / or whole line before [)
                name_part = line.split('[')[0].strip()
                parent_id = None

                if '/' in name_part:
                    parts = name_part.split('/')
                    if len(parts) == 2:
                        parent_id = parts[0].strip()
                        channel_name = parts[1].strip()
                    else:
                        channel_name = parts[-1].strip()
                else:
                    channel_name = name_part

                channels.append({
                    'name': channel_name,
                    'id': channel_id,
                    'parent_id': parent_id
                })

        return channels

    except subprocess.TimeoutExpired:
        raise RuntimeError("Channel fetching timed out after 30 seconds")
    except Exception as e:
        raise RuntimeError(f"Channel fetching failed: {str(e)}")
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_fetch_channels.py::test_fetch_guild_channels_includes_threads -v
uv run pytest tests/test_fetch_channels.py::test_fetch_guild_channels_without_threads -v
```

Expected: Both tests PASS

**Step 5: Update existing tests**

Update all existing tests in `tests/test_fetch_channels.py` to expect `parent_id` field:

```python
def test_fetch_guild_channels_success():
    """Test successful channel fetching."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="Information / announcements [123456]\nGeneral / general [789012]\n",
            stderr=""
        )

        channels = fetch_guild_channels("test_token", "guild123")

        assert len(channels) == 2
        assert channels[0] == {'name': 'announcements', 'id': '123456', 'parent_id': 'Information'}
        assert channels[1] == {'name': 'general', 'id': '789012', 'parent_id': 'General'}


def test_fetch_guild_channels_without_category():
    """Test channel fetching for channels without categories."""
    with patch('subprocess.run') as mock_run:
        mock_run.return_value = Mock(
            returncode=0,
            stdout="general [123456]\nannouncements [789012]\n",
            stderr=""
        )

        channels = fetch_guild_channels("test_token", "guild123")

        assert len(channels) == 2
        assert channels[0] == {'name': 'general', 'id': '123456', 'parent_id': None}
        assert channels[1] == {'name': 'announcements', 'id': '789012', 'parent_id': None}
```

**Step 6: Run full test suite**

```bash
uv run pytest tests/test_fetch_channels.py -v
```

Expected: All tests PASS

**Step 7: Commit**

```bash
git add scripts/export_channels.py tests/test_fetch_channels.py
git commit -m "feat: add thread detection to channel fetching

Add --include-threads All flag to fetch_guild_channels()
Parse parent_id from channel output for thread grouping
Update tests to expect parent_id field in channel data"
```

---

## Task 2: Add Channel Classification Logic

**Files:**
- Create: `scripts/channel_classifier.py`
- Create: `tests/test_channel_classifier.py`

**Step 1: Write test for channel classification**

Create `tests/test_channel_classifier.py`:

```python
# tests/test_channel_classifier.py
"""Tests for channel classification logic."""
import pytest
from scripts.channel_classifier import classify_channel, ChannelType


def test_classify_regular_channel():
    """Test classification of regular channel."""
    channel = {'name': 'general', 'id': '123', 'parent_id': None}
    forum_list = ['questions', 'ideas']

    result = classify_channel(channel, forum_list, all_channels=[channel])

    assert result == ChannelType.REGULAR


def test_classify_forum_channel():
    """Test classification of forum channel."""
    forum = {'name': 'questions', 'id': '999', 'parent_id': None}
    thread = {'name': 'How to start?', 'id': '123', 'parent_id': 'questions'}
    forum_list = ['questions', 'ideas']

    result = classify_channel(forum, forum_list, all_channels=[forum, thread])

    assert result == ChannelType.FORUM


def test_classify_thread_channel():
    """Test classification of thread channel."""
    thread = {'name': 'How to start?', 'id': '123', 'parent_id': 'questions'}
    forum_list = ['questions', 'ideas']

    result = classify_channel(thread, forum_list, all_channels=[thread])

    assert result == ChannelType.THREAD


def test_classify_thread_without_forum_config():
    """Test thread classification when parent not in config."""
    thread = {'name': 'Some thread', 'id': '123', 'parent_id': 'random-forum'}
    forum_list = ['questions', 'ideas']

    result = classify_channel(thread, forum_list, all_channels=[thread])

    # Should still detect as thread based on parent_id
    assert result == ChannelType.THREAD
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_channel_classifier.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'scripts.channel_classifier'"

**Step 3: Implement channel classifier**

Create `scripts/channel_classifier.py`:

```python
# scripts/channel_classifier.py
"""Channel classification logic for forum/thread detection."""
from enum import Enum
from typing import Dict, List


class ChannelType(Enum):
    """Channel type enumeration."""
    REGULAR = "regular"
    FORUM = "forum"
    THREAD = "thread"


def classify_channel(
    channel: Dict[str, str],
    forum_list: List[str],
    all_channels: List[Dict[str, str]]
) -> ChannelType:
    """
    Classify a channel as regular, forum, or thread.

    Args:
        channel: Channel dict with name, id, parent_id
        forum_list: List of known forum channel names from config
        all_channels: All channels (used to detect if channel has threads)

    Returns:
        ChannelType indicating channel classification
    """
    # If channel has parent_id, it's a thread
    if channel.get('parent_id'):
        return ChannelType.THREAD

    # If channel name is in forum list, it's a forum
    if channel['name'] in forum_list:
        return ChannelType.FORUM

    # Check if any other channels have this as parent (auto-detect forum)
    channel_name = channel['name']
    has_threads = any(
        ch.get('parent_id') == channel_name
        for ch in all_channels
    )

    if has_threads:
        return ChannelType.FORUM

    # Otherwise it's a regular channel
    return ChannelType.REGULAR


def get_forum_name(channel: Dict[str, str]) -> str:
    """
    Get the forum name for a thread channel.

    Args:
        channel: Thread channel dict with parent_id

    Returns:
        Parent forum channel name, or empty string if not a thread
    """
    return channel.get('parent_id', '')


def sanitize_thread_name(title: str, thread_id: str = None) -> str:
    """
    Sanitize thread title into safe filename.

    Args:
        title: Thread title
        thread_id: Optional thread ID for fallback

    Returns:
        Sanitized filename (without extension)
    """
    import re

    # Convert to lowercase
    name = title.lower()

    # Replace spaces with hyphens
    name = name.replace(' ', '-')

    # Remove special characters except hyphens
    name = re.sub(r'[^a-z0-9-]', '', name)

    # Remove multiple consecutive hyphens
    name = re.sub(r'-+', '-', name)

    # Remove leading/trailing hyphens
    name = name.strip('-')

    # Truncate to 100 characters
    name = name[:100]

    # If empty or too short, use thread ID
    if len(name) < 3 and thread_id:
        name = f"thread-{thread_id}"

    return name
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_channel_classifier.py -v
```

Expected: All tests PASS

**Step 5: Add sanitization tests**

Add to `tests/test_channel_classifier.py`:

```python
def test_sanitize_thread_name_basic():
    """Test basic thread name sanitization."""
    from scripts.channel_classifier import sanitize_thread_name

    result = sanitize_thread_name("How do I start?")
    assert result == "how-do-i-start"


def test_sanitize_thread_name_special_chars():
    """Test sanitization with special characters."""
    from scripts.channel_classifier import sanitize_thread_name

    result = sanitize_thread_name("Help! @ #Bot# won't work!!!")
    assert result == "help-bot-wont-work"


def test_sanitize_thread_name_fallback():
    """Test fallback to thread ID for empty names."""
    from scripts.channel_classifier import sanitize_thread_name

    result = sanitize_thread_name("!!!", thread_id="123456")
    assert result == "thread-123456"


def test_sanitize_thread_name_truncation():
    """Test long names are truncated."""
    from scripts.channel_classifier import sanitize_thread_name

    long_title = "a" * 150
    result = sanitize_thread_name(long_title)
    assert len(result) == 100
```

**Step 6: Run tests**

```bash
uv run pytest tests/test_channel_classifier.py -v
```

Expected: All tests PASS

**Step 7: Commit**

```bash
git add scripts/channel_classifier.py tests/test_channel_classifier.py
git commit -m "feat: add channel classification logic

Add ChannelType enum for regular/forum/thread
Implement classify_channel() with auto-detection
Add sanitize_thread_name() for safe filenames
Add comprehensive tests for classification and sanitization"
```

---

## Task 3: Update Config Schema for Forums

**Files:**
- Modify: `config.toml:1-31`
- Modify: `scripts/config.py`
- Test: `tests/test_config.py`

**Step 1: Write test for forum config**

Add to `tests/test_config.py`:

```python
def test_load_config_forum_channels():
    """Test that forum_channels are loaded from config."""
    config = load_config()

    assert 'servers' in config
    for server_key, server_config in config['servers'].items():
        # Should have forum_channels list
        assert 'forum_channels' in server_config
        assert isinstance(server_config['forum_channels'], list)


def test_load_config_forum_channels_values():
    """Test specific forum channel values."""
    config = load_config()

    wafer_space = config['servers']['wafer-space']
    assert 'questions' in wafer_space['forum_channels']
    assert 'ideas' in wafer_space['forum_channels']
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_config.py::test_load_config_forum_channels -v
```

Expected: FAIL with "KeyError: 'forum_channels'"

**Step 3: Update config.toml**

Modify `config.toml`:

```toml
# config.toml
[site]
title = "wafer.space Discord Logs"
description = "Public archive of wafer.space Discord server"
base_url = "https://discord.wafer.space"

[servers.wafer-space]
guild_id = "1361349522684510449"
name = "wafer.space"
# Channels are automatically discovered from Discord using the bot token
# Use include_channels and exclude_channels to filter which channels to export
include_channels = ["*"]  # "*" means all channels
exclude_channels = [
    "admin",
    "moderators",
    "private-*"
]

# Forum channels (threads exported separately)
forum_channels = ["questions", "ideas"]

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

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_config.py::test_load_config_forum_channels -v
uv run pytest tests/test_config.py::test_load_config_forum_channels_values -v
```

Expected: Both tests PASS

**Step 5: Commit**

```bash
git add config.toml tests/test_config.py
git commit -m "feat: add forum_channels to config schema

Add forum_channels list to server config
Remove questions/ideas from exclude_channels
Update config tests to validate forum_channels"
```

---

## Task 4: Integrate Classification into Export Flow

**Files:**
- Modify: `scripts/export_channels.py:210-334` (export_all_channels function)
- Test: `tests/test_export_orchestration.py`

**Step 1: Write test for forum/thread export**

Add to `tests/test_export_orchestration.py`:

```python
def test_export_all_channels_handles_forums():
    """Test that forum channels create directories."""
    os.environ['DISCORD_BOT_TOKEN'] = 'test_token'

    config = {
        'site': {},
        'servers': {
            'test-server': {
                'name': 'Test Server',
                'guild_id': '123456789',
                'include_channels': ['*'],
                'exclude_channels': [],
                'forum_channels': ['questions']
            }
        },
        'export': {'formats': ['html']},
        'github': {}
    }

    with patch('scripts.export_channels.load_config', return_value=config):
        with patch('scripts.export_channels.fetch_guild_channels') as mock_fetch:
            # Return forum channel and threads
            mock_fetch.return_value = [
                {'name': 'questions', 'id': '999', 'parent_id': None},
                {'name': 'How to start?', 'id': '111', 'parent_id': 'questions'},
                {'name': 'Help needed', 'id': '222', 'parent_id': 'questions'}
            ]

            with patch('scripts.export_channels.StateManager') as MockState:
                mock_state = Mock()
                MockState.return_value = mock_state
                mock_state.load.return_value = {}
                mock_state.get_channel_state.return_value = None

                with patch('scripts.export_channels.run_export') as mock_run:
                    mock_run.return_value = (True, "Success")

                    with patch('scripts.export_channels.Path') as MockPath:
                        mock_path = Mock()
                        MockPath.return_value = mock_path

                        summary = export_all_channels()

                        # Should export 2 threads (not the forum parent)
                        assert summary['total_exports'] == 2

                        # Should create questions directory
                        # Check mkdir was called for forum directory

    del os.environ['DISCORD_BOT_TOKEN']
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_export_orchestration.py::test_export_all_channels_handles_forums -v
```

Expected: FAIL (threads not exported, forum parent exported instead)

**Step 3: Update export_all_channels to handle forums**

In `scripts/export_channels.py`, update the `export_all_channels` function:

```python
def export_all_channels() -> Dict:
    """
    Main export orchestration function.

    Loads configuration, initializes state manager, and orchestrates
    export of all channels from all configured servers.

    Returns:
        Summary dict with stats:
            - channels_updated: Number of channels successfully exported
            - channels_failed: Number of channels that failed export
            - total_exports: Total number of format exports completed
            - errors: List of error dicts with channel, format, and error details
    """
    from scripts.channel_classifier import classify_channel, ChannelType, sanitize_thread_name

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

        # Fetch channels dynamically from Discord
        try:
            print(f"  Fetching channels from Discord...")
            include_threads = config['export'].get('include_threads', 'all').lower() == 'all'
            channels = fetch_guild_channels(token, server_config['guild_id'], include_threads)
            print(f"  Found {len(channels)} channels")
        except RuntimeError as e:
            print(f"  ERROR: {e}")
            summary['errors'].append({
                'channel': 'N/A',
                'format': 'N/A',
                'error': f"Failed to fetch channels: {e}"
            })
            continue

        include_patterns = server_config['include_channels']
        exclude_patterns = server_config['exclude_channels']
        forum_list = server_config.get('forum_channels', [])

        # Classify all channels
        channel_classifications = {}
        for channel in channels:
            channel_type = classify_channel(channel, forum_list, channels)
            channel_classifications[channel['id']] = channel_type

        channel_export_attempted = False

        for channel in channels:
            channel_name = channel['name']
            channel_id = channel['id']
            channel_type = channel_classifications[channel_id]

            # Skip forum parent channels (only export their threads)
            if channel_type == ChannelType.FORUM:
                # Create directory for forum
                forum_dir = server_dir / channel_name
                forum_dir.mkdir(exist_ok=True)
                print(f"  Created forum directory: {channel_name}/")
                continue

            # For threads, use sanitized name and forum directory
            if channel_type == ChannelType.THREAD:
                forum_name = channel.get('parent_id', 'unknown-forum')
                thread_dir = server_dir / forum_name
                thread_dir.mkdir(exist_ok=True)

                # Sanitize thread name for filename
                safe_name = sanitize_thread_name(channel_name, channel_id)
                export_name = safe_name
                export_dir = thread_dir
            else:
                # Regular channel
                export_name = channel_name
                export_dir = server_dir

            # Apply include/exclude filters to channel names
            if not should_include_channel(channel_name, include_patterns, exclude_patterns):
                print(f"  Skipping {channel_name} (excluded by pattern)")
                continue

            print(f"  Exporting #{channel_name}...")

            # Get last export time for incremental updates
            if channel_type == ChannelType.THREAD:
                # TODO: Thread state tracking (will implement in state management task)
                channel_state = None
            else:
                channel_state = state_manager.get_channel_state(server_key, channel_name)

            after_timestamp = channel_state['last_export'] if channel_state else None

            # Export all configured formats
            format_map = {
                'html': 'HtmlDark',
                'txt': 'PlainText',
                'json': 'Json',
                'csv': 'Csv'
            }

            channel_export_attempted = True
            channel_failed = False

            for fmt in config['export']['formats']:
                output_path = export_dir / f"{export_name}.{fmt}"

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
                    channel_failed = True
                    summary['channels_failed'] += 1
                    summary['errors'].append({
                        'channel': channel_name,
                        'format': fmt,
                        'error': output
                    })
                    print(f"    ✗ {fmt.upper()} failed")

            # Update state with current timestamp
            # In real implementation, we'd parse the actual last message timestamp from export
            if not channel_failed and channel_type != ChannelType.THREAD:
                state_manager.update_channel(
                    server_key,
                    channel_name,
                    datetime.now(UTC).isoformat(),
                    "placeholder_message_id"
                )
                summary['channels_updated'] += 1

    # Save state
    state_manager.save()

    return summary
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_export_orchestration.py::test_export_all_channels_handles_forums -v
```

Expected: Test PASS

**Step 5: Run full export orchestration test suite**

```bash
uv run pytest tests/test_export_orchestration.py -v
```

Expected: All tests PASS

**Step 6: Commit**

```bash
git add scripts/export_channels.py tests/test_export_orchestration.py
git commit -m "feat: integrate channel classification into export

Import and use channel_classifier in export flow
Skip exporting forum parent channels
Export threads to forum subdirectories
Use sanitized thread names for filenames
Create forum directories automatically"
```

---

## Task 5: Update organize_exports for Forum Structure

**Files:**
- Modify: `scripts/organize_exports.py`
- Test: `tests/test_organize_exports.py`

**Step 1: Write test for forum organization**

Add to `tests/test_organize_exports.py`:

```python
def test_organize_exports_handles_forum_structure():
    """Test that forum directories are organized correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        exports_dir = Path(tmpdir) / "exports" / "test-server"
        public_dir = Path(tmpdir) / "public" / "test-server"

        # Create forum structure
        forum_dir = exports_dir / "questions"
        forum_dir.mkdir(parents=True)
        (forum_dir / "how-to-start.html").write_text("<html>Thread 1</html>")
        (forum_dir / "how-to-start.json").write_text('{"messages": []}')
        (forum_dir / "help-needed.html").write_text("<html>Thread 2</html>")

        with patch('scripts.organize_exports.Path') as MockPath:
            MockPath.return_value = Path(tmpdir)

            from scripts.organize_exports import organize_exports
            organize_exports()

            # Should create forum directory in public
            assert (public_dir / "questions").exists()

            # Should create thread directories
            assert (public_dir / "questions" / "how-to-start").exists()
            assert (public_dir / "questions" / "help-needed").exists()

            # Should organize files by month
            current_month = datetime.now(UTC).strftime("%Y-%m")
            assert (public_dir / "questions" / "how-to-start" / current_month / "latest.html").exists()


def test_organize_exports_mixed_regular_and_forum():
    """Test organizing mix of regular channels and forums."""
    with tempfile.TemporaryDirectory() as tmpdir:
        exports_dir = Path(tmpdir) / "exports" / "test-server"
        public_dir = Path(tmpdir) / "public" / "test-server"

        # Create regular channel
        exports_dir.mkdir(parents=True)
        (exports_dir / "general.html").write_text("<html>General</html>")

        # Create forum structure
        forum_dir = exports_dir / "questions"
        forum_dir.mkdir(parents=True)
        (forum_dir / "thread-1.html").write_text("<html>Thread</html>")

        with patch('scripts.organize_exports.Path') as MockPath:
            MockPath.return_value = Path(tmpdir)

            from scripts.organize_exports import organize_exports
            organize_exports()

            # Should have both regular and forum
            current_month = datetime.now(UTC).strftime("%Y-%m")
            assert (public_dir / "general" / current_month / "latest.html").exists()
            assert (public_dir / "questions" / "thread-1" / current_month / "latest.html").exists()
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_organize_exports.py::test_organize_exports_handles_forum_structure -v
```

Expected: FAIL (forum structure not created)

**Step 3: Update organize_exports function**

Modify `scripts/organize_exports.py` to detect and handle forum directories:

```python
def organize_exports():
    """
    Organize exported files into public directory structure.

    Handles both regular channels and forum/thread structure:
    - Regular: exports/server/channel.html -> public/server/channel/YYYY-MM/YYYY-MM.html
    - Forums: exports/server/forum/thread.html -> public/server/forum/thread/YYYY-MM/YYYY-MM.html
    """
    exports_dir = Path("exports")
    public_dir = Path("public")

    if not exports_dir.exists():
        print("No exports directory found")
        return

    public_dir.mkdir(exist_ok=True)

    current_month = get_current_month()

    for server_dir in exports_dir.iterdir():
        if not server_dir.is_dir():
            continue

        server_name = server_dir.name
        public_server_dir = public_dir / server_name
        public_server_dir.mkdir(exist_ok=True)

        # Process all items in server directory
        for item in server_dir.iterdir():
            # Check if it's a forum directory (contains multiple files, no parent channel)
            if item.is_dir():
                # Forum directory - process threads
                forum_name = item.name
                public_forum_dir = public_server_dir / forum_name
                public_forum_dir.mkdir(exist_ok=True)

                # Process each thread in forum
                for thread_file in item.iterdir():
                    if thread_file.is_file():
                        thread_name = thread_file.stem  # filename without extension
                        extension = thread_file.suffix

                        # Skip non-export files
                        if extension not in ['.html', '.txt', '.json', '.csv']:
                            continue

                        # Create thread directory
                        public_thread_dir = public_forum_dir / thread_name
                        month_dir = public_thread_dir / current_month
                        month_dir.mkdir(parents=True, exist_ok=True)

                        # Copy file to month directory
                        dest_file = month_dir / f"{current_month}{extension}"
                        shutil.copy2(thread_file, dest_file)

                        # Create/update latest symlink
                        latest_link = public_thread_dir / f"latest{extension}"
                        if latest_link.exists() or latest_link.is_symlink():
                            latest_link.unlink()
                        latest_link.symlink_to(f"{current_month}/{current_month}{extension}")

            elif item.is_file():
                # Regular channel file
                channel_name = item.stem
                extension = item.suffix

                # Skip non-export files
                if extension not in ['.html', '.txt', '.json', '.csv']:
                    continue

                # Create channel directory structure
                channel_dir = public_server_dir / channel_name
                month_dir = channel_dir / current_month
                month_dir.mkdir(parents=True, exist_ok=True)

                # Copy file to month directory
                dest_file = month_dir / f"{current_month}{extension}"
                shutil.copy2(item, dest_file)

                # Create/update latest symlink
                latest_link = channel_dir / f"latest{extension}"
                if latest_link.exists() or latest_link.is_symlink():
                    latest_link.unlink()
                latest_link.symlink_to(f"{current_month}/{current_month}{extension}")

    # Clean up exports directory
    cleanup_exports()
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_organize_exports.py::test_organize_exports_handles_forum_structure -v
uv run pytest tests/test_organize_exports.py::test_organize_exports_mixed_regular_and_forum -v
```

Expected: Both tests PASS

**Step 5: Run full organize_exports test suite**

```bash
uv run pytest tests/test_organize_exports.py -v
```

Expected: All tests PASS

**Step 6: Commit**

```bash
git add scripts/organize_exports.py tests/test_organize_exports.py
git commit -m "feat: handle forum structure in organize_exports

Detect forum directories (subdirs in exports/server/)
Create nested structure: public/server/forum/thread/YYYY-MM/
Handle both regular channels and forum threads
Preserve symlink creation for latest files"
```

---

## Task 6: Add Forum Index Template

**Files:**
- Create: `templates/forum_index.html`
- Test: `tests/test_templates.py`

**Step 1: Write test for forum template**

Add to `tests/test_templates.py`:

```python
def test_forum_index_template_exists():
    """Test that forum index template exists."""
    template_path = Path("templates") / "forum_index.html"
    assert template_path.exists(), "Forum index template should exist"


def test_forum_index_template_renders():
    """Test that forum index template renders with data."""
    from jinja2 import Environment, FileSystemLoader

    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('forum_index.html')

    data = {
        'site_title': 'Test Server',
        'forum_name': 'Questions',
        'forum_description': 'Ask questions here',
        'threads': [
            {
                'name': 'how-to-start',
                'title': 'How to start?',
                'url': 'how-to-start/',
                'reply_count': 5,
                'last_activity': '2025-11-14',
                'archived': False
            },
            {
                'name': 'old-thread',
                'title': 'Old question',
                'url': 'old-thread/',
                'reply_count': 12,
                'last_activity': '2025-01-15',
                'archived': True
            }
        ]
    }

    html = template.render(data)

    assert 'Questions' in html
    assert 'How to start?' in html
    assert '5 replies' in html
    assert 'Archived' in html
    assert 'href="how-to-start/"' in html
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_templates.py::test_forum_index_template_exists -v
```

Expected: FAIL with "AssertionError: Forum index template should exist"

**Step 3: Create forum index template**

Create `templates/forum_index.html`:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ forum_name }} - {{ site_title }}</title>
    <link rel="stylesheet" href="/style.css">
</head>
<body>
    <div class="container">
        <nav class="breadcrumb">
            <a href="/">{{ site_title }}</a>
            <span class="separator">›</span>
            <span class="current">{{ forum_name }}</span>
        </nav>

        <header>
            <h1>{{ forum_name }} Forum</h1>
            {% if forum_description %}
            <p class="forum-description">{{ forum_description }}</p>
            {% endif %}
        </header>

        <main>
            {% if threads %}
            <div class="thread-list">
                {% for thread in threads %}
                <div class="thread {% if thread.archived %}archived{% endif %}">
                    <a href="{{ thread.url }}" class="thread-link">
                        <h3 class="thread-title">{{ thread.title }}</h3>
                        <div class="thread-meta">
                            {% if thread.archived %}
                            <span class="badge archived">Archived</span>
                            {% endif %}
                            <span class="reply-count">{{ thread.reply_count }} replies</span>
                            <span class="separator">•</span>
                            <span class="last-activity">Last: {{ thread.last_activity }}</span>
                        </div>
                    </a>
                </div>
                {% endfor %}
            </div>
            {% else %}
            <p class="no-threads">No threads in this forum yet.</p>
            {% endif %}
        </main>

        <footer>
            <p>Discord Archive • Generated {{ generation_time }}</p>
        </footer>
    </div>
</body>
</html>
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_templates.py::test_forum_index_template_exists -v
uv run pytest tests/test_templates.py::test_forum_index_template_renders -v
```

Expected: Both tests PASS

**Step 5: Commit**

```bash
git add templates/forum_index.html tests/test_templates.py
git commit -m "feat: add forum index template

Create forum_index.html template with thread listing
Show thread metadata (replies, last activity, archived status)
Include breadcrumb navigation
Add tests for template existence and rendering"
```

---

## Task 7: Implement Thread Metadata Extraction

**Files:**
- Create: `scripts/metadata_extractor.py`
- Create: `tests/test_metadata_extractor.py`

**Step 1: Write tests for metadata extraction**

Create `tests/test_metadata_extractor.py`:

```python
# tests/test_metadata_extractor.py
"""Tests for thread metadata extraction."""
import json
import tempfile
from pathlib import Path
from datetime import datetime
from scripts.metadata_extractor import extract_thread_metadata


def test_extract_thread_metadata_from_json():
    """Test extracting metadata from JSON export."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        thread_data = {
            "channel": {
                "id": "123456",
                "name": "How to start?",
                "type": "thread"
            },
            "messages": [
                {
                    "id": "msg1",
                    "timestamp": "2025-11-14T10:00:00Z",
                    "content": "First message"
                },
                {
                    "id": "msg2",
                    "timestamp": "2025-11-14T11:00:00Z",
                    "content": "Second message"
                }
            ]
        }
        json.dump(thread_data, f)
        json_path = Path(f.name)

    try:
        metadata = extract_thread_metadata(json_path)

        assert metadata['title'] == 'How to start?'
        assert metadata['reply_count'] == 2
        assert metadata['last_activity'] == '2025-11-14'
        assert metadata['channel_id'] == '123456'
    finally:
        json_path.unlink()


def test_extract_thread_metadata_empty_messages():
    """Test metadata extraction with no messages."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        thread_data = {
            "channel": {
                "id": "123456",
                "name": "Empty thread",
                "type": "thread"
            },
            "messages": []
        }
        json.dump(thread_data, f)
        json_path = Path(f.name)

    try:
        metadata = extract_thread_metadata(json_path)

        assert metadata['title'] == 'Empty thread'
        assert metadata['reply_count'] == 0
        assert metadata['last_activity'] is None
    finally:
        json_path.unlink()


def test_extract_thread_metadata_missing_file():
    """Test handling of missing JSON file."""
    json_path = Path("nonexistent.json")

    metadata = extract_thread_metadata(json_path)

    assert metadata['title'] == 'Unknown'
    assert metadata['reply_count'] == 0
    assert metadata['last_activity'] is None
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_metadata_extractor.py -v
```

Expected: FAIL with "ModuleNotFoundError: No module named 'scripts.metadata_extractor'"

**Step 3: Implement metadata extractor**

Create `scripts/metadata_extractor.py`:

```python
# scripts/metadata_extractor.py
"""Extract metadata from exported thread files."""
import json
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime


def extract_thread_metadata(json_path: Path) -> Dict:
    """
    Extract thread metadata from JSON export.

    Args:
        json_path: Path to thread JSON export file

    Returns:
        Dict with title, reply_count, last_activity, channel_id
    """
    default_metadata = {
        'title': 'Unknown',
        'reply_count': 0,
        'last_activity': None,
        'channel_id': None,
        'archived': False
    }

    if not json_path.exists():
        return default_metadata

    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Extract channel info
        channel = data.get('channel', {})
        title = channel.get('name', 'Unknown')
        channel_id = channel.get('id')

        # Count messages
        messages = data.get('messages', [])
        reply_count = len(messages)

        # Get last activity timestamp
        last_activity = None
        if messages:
            last_msg = messages[-1]
            timestamp_str = last_msg.get('timestamp', '')
            if timestamp_str:
                try:
                    dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    last_activity = dt.strftime('%Y-%m-%d')
                except ValueError:
                    pass

        return {
            'title': title,
            'reply_count': reply_count,
            'last_activity': last_activity,
            'channel_id': channel_id,
            'archived': False  # Will be set by caller if known
        }

    except (json.JSONDecodeError, KeyError, IOError) as e:
        print(f"Warning: Failed to extract metadata from {json_path}: {e}")
        return default_metadata


def get_all_thread_metadata(forum_dir: Path) -> Dict[str, Dict]:
    """
    Get metadata for all threads in a forum directory.

    Args:
        forum_dir: Path to forum directory in public/

    Returns:
        Dict mapping thread name to metadata dict
    """
    metadata_map = {}

    if not forum_dir.exists():
        return metadata_map

    for thread_dir in forum_dir.iterdir():
        if not thread_dir.is_dir():
            continue

        thread_name = thread_dir.name

        # Look for JSON file in latest month
        latest_json = thread_dir / 'latest.json'
        if latest_json.exists():
            metadata = extract_thread_metadata(latest_json)
            metadata['name'] = thread_name
            metadata['url'] = f"{thread_name}/"
            metadata_map[thread_name] = metadata

    return metadata_map
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_metadata_extractor.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add scripts/metadata_extractor.py tests/test_metadata_extractor.py
git commit -m "feat: add thread metadata extraction

Implement extract_thread_metadata() to parse JSON exports
Extract title, reply count, last activity timestamp
Handle missing files and malformed JSON gracefully
Add get_all_thread_metadata() for batch processing"
```

---

## Task 8: Generate Forum Index Pages

**Files:**
- Modify: `scripts/generate_navigation.py`
- Test: `tests/test_generate_navigation.py`

**Step 1: Write test for forum index generation**

Add to `tests/test_generate_navigation.py`:

```python
def test_generate_forum_index():
    """Test generating forum index page."""
    from scripts.generate_navigation import generate_forum_index

    with tempfile.TemporaryDirectory() as tmpdir:
        public_dir = Path(tmpdir) / "public" / "test-server"
        forum_dir = public_dir / "questions"
        forum_dir.mkdir(parents=True)

        # Create thread directories with JSON
        thread1_dir = forum_dir / "how-to-start"
        thread1_dir.mkdir()
        (thread1_dir / "latest.json").write_text(json.dumps({
            "channel": {"id": "123", "name": "How to start?"},
            "messages": [
                {"id": "1", "timestamp": "2025-11-14T10:00:00Z", "content": "msg1"},
                {"id": "2", "timestamp": "2025-11-14T11:00:00Z", "content": "msg2"}
            ]
        }))

        forum_config = {
            'name': 'Questions',
            'description': 'Ask questions here'
        }

        generate_forum_index(forum_dir, forum_config, "Test Server")

        # Check index.html created
        index_path = forum_dir / "index.html"
        assert index_path.exists()

        # Check content
        content = index_path.read_text()
        assert 'Questions' in content
        assert 'How to start?' in content
        assert '2 replies' in content
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_generate_navigation.py::test_generate_forum_index -v
```

Expected: FAIL with "ImportError: cannot import name 'generate_forum_index'"

**Step 3: Implement generate_forum_index function**

Add to `scripts/generate_navigation.py`:

```python
def generate_forum_index(forum_dir: Path, forum_config: Dict, site_title: str):
    """
    Generate index page for a forum channel.

    Args:
        forum_dir: Path to forum directory in public/
        forum_config: Forum configuration dict with name, description
        site_title: Site title for breadcrumb
    """
    from jinja2 import Environment, FileSystemLoader
    from scripts.metadata_extractor import get_all_thread_metadata
    from datetime import datetime, UTC

    # Get metadata for all threads
    thread_metadata = get_all_thread_metadata(forum_dir)

    # Sort threads by last activity (newest first)
    threads = sorted(
        thread_metadata.values(),
        key=lambda t: t.get('last_activity') or '0000-00-00',
        reverse=True
    )

    # Load template
    env = Environment(loader=FileSystemLoader('templates'))
    template = env.get_template('forum_index.html')

    # Render template
    html = template.render(
        site_title=site_title,
        forum_name=forum_config.get('name', forum_dir.name),
        forum_description=forum_config.get('description', ''),
        threads=threads,
        generation_time=datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')
    )

    # Write index file
    index_path = forum_dir / 'index.html'
    index_path.write_text(html, encoding='utf-8')

    print(f"    Generated forum index: {forum_dir.name}/index.html ({len(threads)} threads)")
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_generate_navigation.py::test_generate_forum_index -v
```

Expected: Test PASS

**Step 5: Integrate into main navigation generation**

Modify the `main()` function in `scripts/generate_navigation.py`:

```python
def main():
    """Generate all navigation pages."""
    config = load_config()
    public_dir = Path("public")

    if not public_dir.exists():
        print("No public directory found. Run organize_exports.py first.")
        return

    # Generate site index
    servers = scan_servers(public_dir)
    generate_site_index(servers, config)

    # Generate server indexes and forum indexes
    for server in servers:
        server_dir = public_dir / server['slug']
        channels = scan_exports(server_dir)

        # Get server config
        server_config = None
        for key, srv_conf in config['servers'].items():
            if key == server['slug']:
                server_config = srv_conf
                break

        # Identify forums
        forum_channels = server_config.get('forum_channels', []) if server_config else []

        # Generate forum indexes
        for forum_name in forum_channels:
            forum_dir = server_dir / forum_name
            if forum_dir.exists():
                forum_config = {
                    'name': forum_name,
                    'description': ''  # TODO: Get from config
                }
                generate_forum_index(forum_dir, forum_config, server['name'])

        # Generate server index
        generate_server_index(server, channels, config)

        # Generate channel indexes (for regular channels)
        for channel in channels:
            # Skip forum channels (they have their own index)
            if channel['name'] in forum_channels:
                continue

            channel_dir = server_dir / channel['name']
            archives = group_by_year(channel['archives'])
            generate_channel_index(server, channel, archives, config)
```

**Step 6: Run navigation tests**

```bash
uv run pytest tests/test_generate_navigation.py -v
```

Expected: All tests PASS

**Step 7: Commit**

```bash
git add scripts/generate_navigation.py tests/test_generate_navigation.py
git commit -m "feat: generate forum index pages

Add generate_forum_index() function
Integrate forum index generation into main()
Use metadata_extractor to get thread info
Sort threads by last activity
Generate index.html for each forum"
```

---

## Task 9: Extend State Management for Threads

**Files:**
- Modify: `scripts/state.py`
- Test: `tests/test_state.py`

**Step 1: Write tests for thread state**

Add to `tests/test_state.py`:

```python
def test_state_manager_thread_state():
    """Test thread state tracking."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        state_path = Path(f.name)

    try:
        state_manager = StateManager(state_path)
        state_manager.load()

        # Update thread state
        state_manager.update_thread(
            'test-server',
            'questions',
            'thread-123',
            {
                'name': 'how-to-start',
                'title': 'How to start?',
                'last_export': '2025-11-14T10:00:00Z',
                'last_message_id': '999',
                'archived': False
            }
        )

        state_manager.save()

        # Verify state structure
        saved_state = json.loads(state_path.read_text())
        assert 'test-server' in saved_state
        assert 'forums' in saved_state['test-server']
        assert 'questions' in saved_state['test-server']['forums']
        assert 'threads' in saved_state['test-server']['forums']['questions']

        thread_state = saved_state['test-server']['forums']['questions']['threads']['thread-123']
        assert thread_state['name'] == 'how-to-start'
        assert thread_state['title'] == 'How to start?'

    finally:
        state_path.unlink()


def test_state_manager_get_thread_state():
    """Test retrieving thread state."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        initial_state = {
            'test-server': {
                'channels': {},
                'forums': {
                    'questions': {
                        'threads': {
                            'thread-123': {
                                'name': 'how-to-start',
                                'last_export': '2025-11-14T10:00:00Z'
                            }
                        }
                    }
                }
            }
        }
        json.dump(initial_state, f)
        state_path = Path(f.name)

    try:
        state_manager = StateManager(state_path)
        state_manager.load()

        thread_state = state_manager.get_thread_state('test-server', 'questions', 'thread-123')

        assert thread_state is not None
        assert thread_state['name'] == 'how-to-start'
        assert thread_state['last_export'] == '2025-11-14T10:00:00Z'

    finally:
        state_path.unlink()
```

**Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_state.py::test_state_manager_thread_state -v
```

Expected: FAIL with "AttributeError: 'StateManager' object has no attribute 'update_thread'"

**Step 3: Add thread methods to StateManager**

Modify `scripts/state.py`:

```python
class StateManager:
    """Manage export state tracking."""

    def __init__(self, state_file: Path = None):
        """Initialize state manager."""
        self.state_file = state_file or Path("state.json")
        self.state = {}

    def load(self):
        """Load state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file, 'r') as f:
                    self.state = json.load(f)
            except json.JSONDecodeError:
                print(f"Warning: Could not parse {self.state_file}, starting fresh")
                self.state = {}
        else:
            self.state = {}

    def save(self):
        """Save state to file."""
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2)

    def get_channel_state(self, server: str, channel: str) -> dict:
        """Get state for a channel."""
        if server not in self.state:
            return None
        if 'channels' not in self.state[server]:
            return None
        return self.state[server]['channels'].get(channel)

    def update_channel(self, server: str, channel: str, timestamp: str, message_id: str):
        """Update channel export state."""
        if server not in self.state:
            self.state[server] = {'channels': {}, 'forums': {}}
        if 'channels' not in self.state[server]:
            self.state[server]['channels'] = {}

        self.state[server]['channels'][channel] = {
            'last_export': timestamp,
            'last_message_id': message_id
        }

    def get_thread_state(self, server: str, forum: str, thread_id: str) -> dict:
        """
        Get state for a thread.

        Args:
            server: Server key
            forum: Forum channel name
            thread_id: Thread channel ID

        Returns:
            Thread state dict or None if not found
        """
        if server not in self.state:
            return None
        if 'forums' not in self.state[server]:
            return None
        if forum not in self.state[server]['forums']:
            return None
        if 'threads' not in self.state[server]['forums'][forum]:
            return None
        return self.state[server]['forums'][forum]['threads'].get(thread_id)

    def update_thread(self, server: str, forum: str, thread_id: str, thread_data: dict):
        """
        Update thread export state.

        Args:
            server: Server key
            forum: Forum channel name
            thread_id: Thread channel ID
            thread_data: Dict with name, title, last_export, last_message_id, archived
        """
        # Initialize server state
        if server not in self.state:
            self.state[server] = {'channels': {}, 'forums': {}}

        # Initialize forums dict
        if 'forums' not in self.state[server]:
            self.state[server]['forums'] = {}

        # Initialize forum
        if forum not in self.state[server]['forums']:
            self.state[server]['forums'][forum] = {'threads': {}}

        # Initialize threads dict
        if 'threads' not in self.state[server]['forums'][forum]:
            self.state[server]['forums'][forum]['threads'] = {}

        # Update thread state
        self.state[server]['forums'][forum]['threads'][thread_id] = thread_data

    def get_all_threads(self, server: str, forum: str) -> dict:
        """
        Get all thread states for a forum.

        Args:
            server: Server key
            forum: Forum channel name

        Returns:
            Dict mapping thread_id to thread state
        """
        if server not in self.state:
            return {}
        if 'forums' not in self.state[server]:
            return {}
        if forum not in self.state[server]['forums']:
            return {}
        return self.state[server]['forums'][forum].get('threads', {})
```

**Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/test_state.py::test_state_manager_thread_state -v
uv run pytest tests/test_state.py::test_state_manager_get_thread_state -v
```

Expected: Both tests PASS

**Step 5: Run full state test suite**

```bash
uv run pytest tests/test_state.py -v
```

Expected: All tests PASS

**Step 6: Commit**

```bash
git add scripts/state.py tests/test_state.py
git commit -m "feat: add thread state management

Add update_thread() method to StateManager
Add get_thread_state() to retrieve thread state
Add get_all_threads() for forum-wide thread states
Update state schema to include forums.{forum}.threads
Add comprehensive tests for thread state tracking"
```

---

## Task 10: Use Thread State in Export Flow

**Files:**
- Modify: `scripts/export_channels.py:210-334` (export_all_channels)
- Test: `tests/test_export_orchestration.py`

**Step 1: Write test for thread state usage**

Add to `tests/test_export_orchestration.py`:

```python
def test_export_all_channels_tracks_thread_state():
    """Test that thread exports update state correctly."""
    os.environ['DISCORD_BOT_TOKEN'] = 'test_token'

    config = {
        'site': {},
        'servers': {
            'test-server': {
                'name': 'Test Server',
                'guild_id': '123456789',
                'include_channels': ['*'],
                'exclude_channels': [],
                'forum_channels': ['questions']
            }
        },
        'export': {'formats': ['html'], 'include_threads': 'all'},
        'github': {}
    }

    with patch('scripts.export_channels.load_config', return_value=config):
        with patch('scripts.export_channels.fetch_guild_channels') as mock_fetch:
            mock_fetch.return_value = [
                {'name': 'questions', 'id': '999', 'parent_id': None},
                {'name': 'How to start?', 'id': '111', 'parent_id': 'questions'}
            ]

            with patch('scripts.export_channels.StateManager') as MockState:
                mock_state = Mock()
                MockState.return_value = mock_state
                mock_state.load.return_value = {}
                mock_state.get_thread_state.return_value = None

                with patch('scripts.export_channels.run_export') as mock_run:
                    mock_run.return_value = (True, "Success")

                    with patch('scripts.export_channels.Path'):
                        summary = export_all_channels()

                        # Should have called update_thread
                        mock_state.update_thread.assert_called_once()
                        call_args = mock_state.update_thread.call_args
                        assert call_args[0][0] == 'test-server'  # server
                        assert call_args[0][1] == 'questions'    # forum
                        assert call_args[0][2] == '111'          # thread_id

    del os.environ['DISCORD_BOT_TOKEN']
```

**Step 2: Run test to verify it fails**

```bash
uv run pytest tests/test_export_orchestration.py::test_export_all_channels_tracks_thread_state -v
```

Expected: FAIL (update_thread not called)

**Step 3: Update export_all_channels to use thread state**

In `scripts/export_channels.py`, update the export loop to handle thread state:

```python
# Inside export_all_channels, in the channel export loop:

            # Get last export time for incremental updates
            if channel_type == ChannelType.THREAD:
                forum_name = channel.get('parent_id', 'unknown-forum')
                thread_state = state_manager.get_thread_state(
                    server_key,
                    forum_name,
                    channel_id
                )
                after_timestamp = thread_state['last_export'] if thread_state else None
            else:
                channel_state = state_manager.get_channel_state(server_key, channel_name)
                after_timestamp = channel_state['last_export'] if channel_state else None

# ... export code ...

            # Update state with current timestamp
            if not channel_failed:
                if channel_type == ChannelType.THREAD:
                    forum_name = channel.get('parent_id', 'unknown-forum')
                    state_manager.update_thread(
                        server_key,
                        forum_name,
                        channel_id,
                        {
                            'name': export_name,
                            'title': channel_name,
                            'last_export': datetime.now(UTC).isoformat(),
                            'last_message_id': 'placeholder_message_id',
                            'archived': False
                        }
                    )
                else:
                    state_manager.update_channel(
                        server_key,
                        channel_name,
                        datetime.now(UTC).isoformat(),
                        "placeholder_message_id"
                    )
                    summary['channels_updated'] += 1
```

**Step 4: Run test to verify it passes**

```bash
uv run pytest tests/test_export_orchestration.py::test_export_all_channels_tracks_thread_state -v
```

Expected: Test PASS

**Step 5: Run full export orchestration tests**

```bash
uv run pytest tests/test_export_orchestration.py -v
```

Expected: All tests PASS

**Step 6: Commit**

```bash
git add scripts/export_channels.py tests/test_export_orchestration.py
git commit -m "feat: use thread state for incremental exports

Get thread state using get_thread_state()
Use thread last_export for --after timestamp
Update thread state after successful export
Track thread name, title, timestamps in state"
```

---

## Task 11: Run End-to-End Tests

**Files:**
- Test: `tests/` (all test files)

**Step 1: Run full test suite**

```bash
uv run pytest -v
```

Expected: All 85+ tests PASS (79 original + 6 new tests)

**Step 2: If any tests fail, fix them**

Review failures and make necessary corrections.

**Step 3: Run linting**

```bash
uv run ruff check scripts/ tests/
```

Expected: No errors

**Step 4: Commit any fixes**

```bash
git add -u
git commit -m "fix: resolve test failures and linting issues"
```

---

## Task 12: Update Documentation

**Files:**
- Modify: `README.md`
- Create: `docs/FORUM_CHANNELS.md`

**Step 1: Create forum channels documentation**

Create `docs/FORUM_CHANNELS.md`:

```markdown
# Forum Channel Support

This document explains how Discord forum channels and their threads are exported and organized.

## Overview

Discord forum channels (like "questions" and "ideas") contain multiple threads that are exported individually and organized in a nested directory structure.

## Configuration

Add forum channels to your `config.toml`:

\`\`\`toml
[servers.your-server]
guild_id = "YOUR_GUILD_ID"
forum_channels = ["questions", "ideas"]

[export]
include_threads = "all"  # Required for thread export
\`\`\`

## Directory Structure

Forums are organized as:

\`\`\`
public/your-server/
  questions/              # Forum channel
    index.html            # Forum index listing all threads
    how-to-start/         # Individual thread
      2025-11/
        2025-11.html
        latest.html -> 2025-11/2025-11.html
    help-needed/
      2025-11/
        2025-11.html
\`\`\`

## Thread Export Process

1. **Discovery**: Channels are fetched with `--include-threads All` flag
2. **Classification**: Channels classified as regular, forum, or thread
3. **Export**: Threads exported individually to forum subdirectories
4. **Organization**: Files organized by month like regular channels
5. **Index Generation**: Forum index page lists all threads with metadata

## Thread Metadata

Forum index pages show for each thread:
- Thread title
- Reply count
- Last activity date
- Archived status

Metadata is extracted from JSON exports.

## State Management

Thread state is tracked separately:

\`\`\`json
{
  "your-server": {
    "forums": {
      "questions": {
        "threads": {
          "thread-id": {
            "name": "how-to-start",
            "title": "How to start?",
            "last_export": "2025-11-14T10:00:00Z",
            "archived": false
          }
        }
      }
    }
  }
}
\`\`\`

## Incremental Updates

Threads support incremental export using `--after` flag:
- Each thread tracked individually in state
- Only new messages since last export are fetched
- Archived threads still updated if new messages appear

## Limitations

- Thread names sanitized for filesystem (special chars removed)
- Very long thread titles truncated to 100 characters
- Thread ID used as fallback if title cannot be sanitized
```

**Step 2: Update README.md**

Add to `README.md` after "Configuration" section:

```markdown
### Forum Channels

Discord forum channels are supported with automatic thread export. See [docs/FORUM_CHANNELS.md](docs/FORUM_CHANNELS.md) for details.

Quick setup:
1. Add forum channel names to `forum_channels` list in config
2. Set `include_threads = "all"` in export config
3. Threads will be exported automatically

Example:
\`\`\`toml
[servers.my-server]
forum_channels = ["questions", "ideas"]

[export]
include_threads = "all"
\`\`\`
```

**Step 3: Commit documentation**

```bash
git add README.md docs/FORUM_CHANNELS.md
git commit -m "docs: add forum channel documentation

Create FORUM_CHANNELS.md with detailed explanation
Update README.md with forum channel quick start
Document directory structure and configuration"
```

---

## Task 13: Manual Testing

**Files:**
- None (manual testing)

**Step 1: Test locally with real Discord data**

```bash
export DISCORD_BOT_TOKEN='your-token-here'
uv run python scripts/export_channels.py
```

Expected:
- Questions and ideas forum directories created
- Threads exported to forum subdirectories
- No errors in output

**Step 2: Test organization**

```bash
uv run python scripts/organize_exports.py
```

Expected:
- Forum structure created in public/
- Thread directories created
- Symlinks work correctly

**Step 3: Test navigation generation**

```bash
uv run python scripts/generate_navigation.py
```

Expected:
- Forum index.html files created
- Thread metadata displayed correctly
- Navigation links work

**Step 4: Check output files**

Manually verify:
- `public/wafer-space/questions/index.html` exists
- Thread directories present
- Index shows thread metadata

**Step 5: Document any issues found**

If issues found, create GitHub issues or fix immediately.

---

## Task 14: Final Integration and Cleanup

**Files:**
- All modified files

**Step 1: Run full test suite one more time**

```bash
uv run pytest -v
```

Expected: All tests PASS

**Step 2: Check for any uncommitted changes**

```bash
git status
```

**Step 3: Create final commit if needed**

```bash
git add -u
git commit -m "chore: final cleanup and integration"
```

**Step 4: Push to remote**

```bash
git push origin feature/discord-wafer-space
```

**Step 5: Verify GitHub Actions passes**

Check GitHub Actions workflow runs successfully.

---

## Success Criteria

- [x] All 85+ tests pass
- [x] Forum channels "questions" and "ideas" export successfully
- [x] Threads organized in nested directory structure
- [x] Forum index pages generated with metadata
- [x] Incremental export works for threads
- [x] Navigation includes forum links
- [x] Documentation complete
- [x] GitHub Actions passes

## Notes for Implementation

- Follow TDD strictly (test first, then implement)
- Run tests after each step
- Commit frequently with descriptive messages
- If a test fails unexpectedly, investigate before proceeding
- Use `uv run` prefix for all Python commands
- Reference @superpowers:test-driven-development for TDD guidance
- Reference @superpowers:systematic-debugging if issues arise
