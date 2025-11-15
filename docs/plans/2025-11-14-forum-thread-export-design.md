# Forum Thread Export Design

**Date**: 2025-11-14
**Status**: Approved
**Author**: Claude Code with user validation

## Overview

This design adds support for exporting Discord forum channels and their threads to the discord-download system. Forum channels (like "questions" and "ideas") contain multiple threads that need to be exported individually and organized with index pages for navigation.

## Requirements

- Export all threads in forum channels, including archived threads
- Organize threads in nested directory structure under parent forum
- Generate forum index pages listing all threads with metadata
- Support incremental updates for threads
- Maintain existing export workflow for regular channels

## Architecture

### 1. Channel Classification and Detection

**Forum Channel Identification**:
Use configuration-based approach with automatic discovery as fallback:

```toml
[servers.wafer-space]
guild_id = "1361349522684510449"
include_channels = ["*"]
exclude_channels = ["admin", "moderators", "private-*"]
forum_channels = ["questions", "ideas"]  # Explicitly mark forums
```

**Thread Detection**:
When `fetch_guild_channels()` runs with `--include-threads All`, DiscordChatExporter returns both regular channels and threads. Threads include parent channel metadata.

**Data Structure**:
```python
{
    'name': 'thread-title',
    'id': '1234567890',
    'parent_id': '9999999999',  # ID of parent forum channel
    'is_thread': True,
    'is_archived': False
}
```

### 2. Export Organization

**Directory Structure**:
```
exports/wafer-space/
  general.html              # Regular channel
  announcements.html        # Regular channel
  questions/                # Forum channel directory
    how-do-i-start.html     # Thread export
    troubleshooting.html    # Thread export
  ideas/                    # Another forum
    feature-request.html    # Thread export
```

**Public Directory Structure**:
```
public/wafer-space/
  general/
    2025-11/
      latest.html -> 2025-11.html
  questions/                # Forum channel
    index.html              # Forum index page
    how-do-i-start/         # Thread directory
      2025-11/
        latest.html -> 2025-11.html
```

**Export Flow**:

1. `fetch_guild_channels()` fetches all channels and threads with `--include-threads All`
2. Categorize into:
   - Regular channels → export normally
   - Forum channels → create directory, skip parent export
   - Thread channels → export under parent forum directory
3. Export each thread individually using its channel ID
4. Generate forum index pages after all threads exported

### 3. File Naming

**Thread Filenames**:
- Primary: Sanitized thread title (e.g., "How do I start?" → "how-do-i-start")
- Fallback: Thread ID if title has special characters or duplicates
- Format: `{sanitized-title}.{format}` or `thread-{id}.{format}`

**Sanitization Rules**:
- Lowercase
- Replace spaces with hyphens
- Remove special characters except hyphens
- Truncate to reasonable length (100 chars)
- Add numeric suffix for duplicates

### 4. Navigation and Index Generation

**Forum Index Page** (`questions/index.html`):

```html
<h1>Questions Forum</h1>
<p class="forum-description">Ask questions about the project</p>

<div class="thread-list">
  <div class="thread">
    <a href="how-do-i-start/">
      <h3>How do I start?</h3>
      <span class="meta">5 replies • Last: 2025-11-10</span>
    </a>
  </div>

  <div class="thread archived">
    <a href="old-question/">
      <h3>Old Question</h3>
      <span class="meta">Archived • 12 replies • Last: 2025-01-15</span>
    </a>
  </div>
</div>
```

**Thread Metadata**:
Extract from JSON exports:
- Thread title (from channel name)
- Reply count (message count from JSON)
- Last activity timestamp (latest message timestamp)
- Archived status (from channel data)

**Navigation Hierarchy**:
```
Server Index (wafer-space/index.html)
  ├─ Regular Channels (general/, announcements/)
  └─ Forum Channels (questions/index.html, ideas/index.html)
       └─ Threads (how-do-i-start/, troubleshooting/)
            └─ Archive Pages (2025-11/latest.html)
```

**Breadcrumb Navigation**:
- Regular channel: Server > Channel > Archive
- Forum thread: Server > Forum > Thread > Archive

### 5. State Management

**State Structure**:

```json
{
  "wafer-space": {
    "channels": {
      "general": {
        "last_export": "2025-11-14T10:00:00Z",
        "last_message_id": "999"
      }
    },
    "forums": {
      "questions": {
        "last_index_update": "2025-11-14T10:00:00Z",
        "threads": {
          "1234567890": {
            "name": "how-do-i-start",
            "last_export": "2025-11-14T10:00:00Z",
            "last_message_id": "888",
            "archived": false,
            "title": "How do I start?"
          },
          "9876543210": {
            "name": "old-question",
            "last_export": "2025-01-15T10:00:00Z",
            "last_message_id": "777",
            "archived": true,
            "title": "Old Question"
          }
        }
      }
    }
  }
}
```

**Incremental Export Logic**:
1. Regular channels: Use existing `--after` timestamp
2. New threads: Auto-detected when `fetch_guild_channels()` returns new thread IDs not in state
3. Existing threads: Use `--after` timestamp from thread's last_export
4. Archived threads: Still export incrementally if new messages appear

**State Updates**:
- After thread export: Update thread entry with new timestamp and message ID
- After forum index generation: Update forum's last_index_update
- Track failed exports separately for retry

**Error Handling**:
- Thread export failure: Mark in state, continue with other threads
- Forum index failure: Log error but don't block other exports
- Missing parent forum: Skip thread or export to fallback directory

### 6. Implementation Components

**Modified Functions**:

1. **`fetch_guild_channels()`** (scripts/export_channels.py):
   - Add `--include-threads All` flag
   - Parse thread metadata from output
   - Return channels with parent_id, is_thread, is_archived fields

2. **`export_all_channels()`** (scripts/export_channels.py):
   - Classify channels into regular, forum, thread
   - Create forum directories
   - Export threads to parent forum directory
   - Skip exporting forum parent channel itself

3. **`organize_exports()`** (scripts/organize_exports.py):
   - Detect forum directories (multiple files, no parent)
   - Create nested structure in public/
   - Handle thread directory organization
   - Update symlinks for nested paths

4. **`generate_navigation()`** (scripts/generate_navigation.py):
   - Identify forum channels
   - Generate forum index pages
   - Extract thread metadata from JSON exports
   - Update server index to link to forum indexes
   - Add breadcrumb support for nested navigation

**New Functions**:

1. **`sanitize_thread_name(title: str) -> str`**:
   - Convert thread title to safe filename
   - Handle duplicates and special characters

2. **`extract_thread_metadata(json_path: Path) -> Dict`**:
   - Parse JSON export for thread info
   - Return title, reply count, last activity

3. **`generate_forum_index(forum_name: str, threads: List[Dict]) -> str`**:
   - Create HTML index for forum
   - List threads with metadata
   - Mark archived threads

4. **`classify_channel(channel: Dict, forum_list: List[str]) -> str`**:
   - Return 'regular', 'forum', or 'thread'
   - Based on config and parent_id

### 7. Configuration Changes

**New Config Options** (config.toml):

```toml
[servers.wafer-space]
guild_id = "1361349522684510449"
name = "wafer.space"
include_channels = ["*"]
exclude_channels = ["admin", "moderators", "private-*"]

# New: Explicitly list forum channels
forum_channels = ["questions", "ideas"]

# Optional: Per-forum settings
[servers.wafer-space.forums.questions]
description = "Ask questions about the project"
include_archived = true

[servers.wafer-space.forums.ideas]
description = "Share your ideas for new features"
include_archived = true
```

**Export Configuration**:
- `include_threads` config value is used to add `--include-threads All` to commands
- Forum channels no longer need to be in exclude_channels

### 8. Testing Strategy

**Unit Tests**:

1. **Thread Detection**:
   - `test_fetch_guild_channels_with_threads()` - Verify thread parsing
   - `test_classify_channel_types()` - Test forum/regular/thread classification
   - `test_sanitize_thread_name()` - Check filename sanitization

2. **Export Organization**:
   - `test_export_forum_creates_directory()` - Verify directory structure
   - `test_export_thread_to_forum_directory()` - Check correct parent
   - `test_thread_filename_generation()` - Validate naming logic

3. **Forum Index Generation**:
   - `test_generate_forum_index()` - Verify index HTML creation
   - `test_extract_thread_metadata()` - Check metadata parsing
   - `test_forum_index_archived_threads()` - Archived marking

4. **State Management**:
   - `test_thread_state_tracking()` - Individual thread state
   - `test_incremental_thread_export()` - --after flag for threads
   - `test_new_thread_detection()` - Detect new threads

**Integration Tests**:

1. `test_forum_export_end_to_end()`:
   - Mock server with forum channels
   - Export all threads
   - Verify directory structure
   - Check index generation
   - Validate navigation links

## Implementation Phases

### Phase 1: Thread Detection and Export
- Modify `fetch_guild_channels()` to include threads
- Add channel classification logic
- Update export to handle threads

### Phase 2: Directory Organization
- Create forum directory structure in exports/
- Update `organize_exports()` for nested structure
- Handle thread file naming

### Phase 3: Forum Index Generation
- Implement metadata extraction from JSON
- Create forum index template
- Generate index pages

### Phase 4: Navigation Updates
- Update `generate_navigation()` for forums
- Add breadcrumb support
- Update server index

### Phase 5: State Management
- Extend state.json schema
- Implement thread state tracking
- Add incremental export for threads

## Edge Cases and Error Handling

1. **Empty Forums**: Forum with no threads creates index with empty message
2. **Thread Name Conflicts**: Add numeric suffix to duplicates
3. **Missing Parent Forum**: Log warning, skip thread or use fallback directory
4. **API Rate Limits**: Batch thread exports with delays if needed
5. **Archived Thread Updates**: Still export if new messages appear
6. **Thread Deletion**: Mark as deleted in state, preserve exported files
7. **Invalid Thread Titles**: Fall back to thread-{id} naming

## Success Criteria

- [ ] Forum channels "questions" and "ideas" export successfully
- [ ] All threads (active and archived) exported
- [ ] Forum index pages generated with correct metadata
- [ ] Nested navigation works (Server > Forum > Thread)
- [ ] Incremental exports work for individual threads
- [ ] All tests pass (79+ tests total)
- [ ] Documentation updated
