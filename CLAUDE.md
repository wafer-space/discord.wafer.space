# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Automated Discord log archival system that exports Discord channels to multiple formats (HTML, TXT, JSON, CSV) and publishes them as a static website via GitHub Pages. Built for the wafer.space Discord server with hourly automated updates.

**Architecture**: Discord API → DiscordChatExporter (C#/.NET) → Python Scripts → GitHub Pages

## Common Development Commands

### Running the Complete Pipeline

```bash
# Complete export, organize, and navigation generation
make all

# Run individual steps
make export      # Export Discord channels using DiscordChatExporter
make organize    # Organize exports into public/ directory structure
make navigate    # Generate navigation HTML pages from templates
```

### Testing

```bash
# Run all tests
uv run pytest -v

# Run specific test file
uv run pytest tests/test_export_channels.py -v

# Run tests with specific markers
uv run pytest -m unit -v          # Fast unit tests only
uv run pytest -m integration -v   # Slower integration tests only

# Run single test
uv run pytest tests/test_state.py::TestStateManager::test_update_channel -v
```

### Setup and Dependencies

```bash
# Install Python dependencies
uv pip install -r requirements.txt

# Download DiscordChatExporter CLI (required for exports)
make setup
# This downloads to: bin/discord-exporter/DiscordChatExporter.Cli

# Clean generated files
make clean       # Remove exports/, public/, reset state.json
make clean-all   # Also remove DiscordChatExporter binary
```

### Local Preview

```bash
# Generate exports and preview locally
make all
python -m http.server --directory public 8000
# Visit http://localhost:8000
```

### Bot Testing

```bash
# Test bot access to Discord API (requires DISCORD_BOT_TOKEN)
export DISCORD_BOT_TOKEN="your_token_here"
uv run python scripts/test_bot_access.py
```

## Architecture and Key Components

### Data Flow Pipeline

1. **Export** (`scripts/export_channels.py`):
   - For each channel, computes the channel's earliest possible month from
     its Discord snowflake (no API call needed). Builds a list of months to
     export: always the current month, plus any past month not yet present
     in `public/` with a month-pure JSON.
   - Runs DiscordChatExporter once per (channel, month, format) tuple,
     bracketed by `--after` (microsecond before month start) and `--before`
     (next month's start). For the current month, `--before` is omitted so
     newly-arrived messages are included.
   - Writes per-month outputs to `exports/<server>/<channel>/<YYYY-MM>.<ext>`
     with sibling `<YYYY-MM>_media/` directories for downloaded assets.
   - Discards past months whose JSON has zero messages (saves disk + avoids
     noisy empty entries on the published site).
   - Honors an optional `EXPORT_MAX_RUNTIME_SECONDS` budget so long
     backfills can be interrupted gracefully and resumed on the next run.

2. **Organize** (`scripts/organize_exports.py`):
   - Walks `exports/` for any directory containing `<YYYY-MM>.<ext>` files.
   - Copies each per-month file into
     `public/<server>/<channel>/<YYYY-MM>/<YYYY-MM>.<ext>`. The month comes
     from the **filename**, not from `datetime.now()` — a backfilled
     2026-03 export lands in `2026-03/`, not the current month.
   - Merges JSON files by message ID. During merge, drops any existing
     messages whose timestamp doesn't match the destination month — this
     cleans up the legacy mixed-month files from the pre-refactor era.
   - Refreshes `latest.*` symlinks to point at the newest month present.

3. **Navigate** (`scripts/generate_navigation.py`):
   - Generates navigation index pages using Jinja2 templates.
   - Scans `public/` directory to discover all exported files.
   - Reads each month's JSON from `public/<server>/<channel>/<YYYY-MM>/<YYYY-MM>.json`
     to compute accurate per-archive message counts.
   - Creates hierarchical indexes: site → server → channel/forum → archives.
   - Templates in `templates/` directory.

### Month-based partitioning

`scripts/months.py` contains the primitives:

- `month_bounds(month)` returns the `(after, before)` ISO timestamps that
  bracket exactly one calendar month UTC, accounting for DCE treating both
  bounds as exclusive.
- `snowflake_to_month(channel_id)` decodes a Discord snowflake to its
  creation month — used to determine the earliest possible month for a
  channel without an API call.
- `scan_completed_months(channel_dir)` returns the months in `public/`
  that already have a non-empty HTML export AND a month-pure JSON. Mixed-
  month JSONs (legacy data) are NOT considered complete; they get
  re-exported and replaced.

### State Management

**File**: `scripts/state.py` (StateManager class)
**Persistence**: `state.json`

After the per-month refactor, `state.json` is no longer used to drive
incremental export timestamps — month bounds and `scan_completed_months`
do that work. State is now mostly observational:

- Last successful export timestamp per channel/thread (for monitoring).
- Thread metadata (name, title, archived) — consumed by navigation.
- Forum index generation timestamps.

**Critical**: The `state.json` file is committed to the repository so the
hourly cron sees recent commits and isn't auto-disabled by GitHub's 60-day
inactivity rule.

### Configuration

**File**: `config.toml`

Key sections:
- `[site]`: Website metadata (title, base_url)
- `[servers.{name}]`: Discord server configuration
  - `guild_id`: Discord server ID
  - `include_channels`/`exclude_channels`: Channel filtering with glob patterns
  - `forum_channels`: List of forum channel names (threads exported separately)
- `[export]`: Export settings (formats, partitioning, media download)

### Channel Classification

**File**: `scripts/channel_classifier.py`

Determines channel type from Discord API data:
- Regular text channels
- Forum channels (with threads)
- Voice channels (skipped)
- Categories (organizational only)

### Thread Handling

**File**: `scripts/thread_metadata.py`

Forum channels export threads as separate files:
- Threads discovered via Discord API
- Metadata extracted from HTML exports
- Thread index pages generated per forum
- Supports both active and archived threads

## Project Structure

```
discord-download/
├── scripts/                    # Python pipeline scripts
│   ├── export_channels.py     # Main export orchestration (per-month)
│   ├── organize_exports.py    # File organization (per-month → public)
│   ├── generate_navigation.py # Index page generation
│   ├── months.py              # Month bounds, snowflake decoding, completion scan
│   ├── state.py               # State tracking
│   ├── config.py              # Configuration loading
│   ├── channel_classifier.py  # Channel type detection
│   ├── thread_metadata.py     # Forum thread handling
│   └── test_bot_access.py     # Bot permission testing
├── templates/                  # Jinja2 templates for index pages
│   ├── site_index.html.j2
│   ├── server_index.html.j2
│   ├── channel_index.html.j2
│   └── forum_index.html.j2
├── tests/                      # pytest test suite
├── public/                     # Generated static site (gitignored, deployed to gh-pages)
├── exports/                    # Temporary export storage (gitignored)
├── bin/discord-exporter/       # DiscordChatExporter CLI (gitignored)
├── config.toml                 # Configuration
├── state.json                  # Export state (committed)
├── requirements.txt            # Python dependencies
├── pytest.ini                  # pytest configuration
└── Makefile                    # Development commands
```

## GitHub Actions Workflow

**File**: `.github/workflows/export-and-publish.yml`

Automated hourly exports with deployment:
- Triggers: Hourly cron, manual dispatch, push to master
- Steps: Export → Organize → Navigate → Commit state.json → Deploy to gh-pages
- State persisted by committing `state.json` back to master branch

### Error Handling Policy

**CRITICAL**: This project enforces honest error reporting in GitHub Actions workflows.

**NEVER** use the following error suppression mechanisms:
- `continue-on-error: true` in workflow steps
- `|| true` to mask command failures
- Any other mechanism that hides real failures

**Rationale**: Workflows should fail visibly when there are real problems. Masking errors with `continue-on-error` or `|| true` creates a false sense of success and prevents discovery of underlying issues.

**Instead**: Fix the root causes of failures so workflows pass legitimately. If certain failures are expected and acceptable, modify the scripts to handle them gracefully and exit with success codes when appropriate.

## Key Technical Details

### Python Module Structure

All scripts are in the `scripts/` package. When running scripts:
- From command line: `PYTHONPATH=. uv run python scripts/script_name.py`
- From Makefile: Already sets `PYTHONPATH=.`
- In tests: Import as `from scripts.module import function`

### DiscordChatExporter Integration

The project wraps the DiscordChatExporter CLI (C#/.NET tool):
- Binary location: `bin/discord-exporter/DiscordChatExporter.Cli`
- Command format: See `format_export_command()` in `export_channels.py`
- Valid formats: `HtmlDark`, `HtmlLight`, `PlainText`, `Json`, `Csv`
- Incremental exports: Use `--after` flag with ISO 8601 timestamp

### Date Handling

All timestamps use ISO 8601 format with UTC timezone:
- Python: `datetime.now(timezone.utc).isoformat()`
- Storage: ISO format strings in `state.json`
- Archives: Organized by YYYY-MM directories

### Template Rendering

Jinja2 templates expect specific context variables:
- `site`: Site config from `config.toml`
- `channels`: List of channel dicts with name/archives
- `servers`: List of server names
- `last_updated`: ISO timestamp of generation

See template files for exact context requirements.

## Testing Strategy

Tests use pytest with fixtures for temporary directories:
- **Unit tests**: Individual functions, fast, marked with `@pytest.mark.unit`
- **Integration tests**: Multi-step workflows, slower, marked with `@pytest.mark.integration`
- **Fixtures**: `tmp_path` for isolated file operations
- **Mocking**: Subprocess calls to DiscordChatExporter

Test files mirror `scripts/` structure: `test_{module}.py` for each `{module}.py`.

## Common Issues and Solutions

### Empty Exports
- Verify `DISCORD_BOT_TOKEN` is set correctly
- Check bot has "Message Content Intent" enabled in Discord Developer Portal
- Ensure bot has "Read Message History" permission in channels

### State Not Persisting
- `state.json` must be committed to repository
- GitHub Actions workflow commits state after export
- For local development, state persists automatically on disk

### Navigation Pages Missing
- Run `make navigate` after organizing exports
- Ensure `public/` directory has HTML files (not just JSON/TXT/CSV)
- Check templates exist in `templates/` directory

### Forum Threads Not Appearing
- Forum channels must be listed in `config.toml` `forum_channels` array
- Threads discovered dynamically from Discord API
- Both active and archived threads are exported
