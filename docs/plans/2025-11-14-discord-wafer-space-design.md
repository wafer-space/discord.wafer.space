# discord.wafer.space - Design Document

**Date**: 2025-11-14
**Status**: Approved
**Author**: Design session with Tim

---

## Overview

A publicly accessible website that archives Discord message logs from the wafer.space Discord server (and later Tiny Tapeout), publishing them at discord.wafer.space with IRC-log-style navigation and multiple export formats.

---

## Requirements

### Functional Requirements

- Archive all public channels from wafer.space Discord server
- Export to multiple formats: HTML (Discord-style), TXT, JSON, CSV
- Organize logs by channel with monthly date archives
- Provide navigation at three levels: site → server → channel → archive
- Update hourly via automated pipeline
- Support SEO/indexing by external search engines (Google, etc.)

### Non-Functional Requirements

- **Easy maintenance**: Minimal manual work after initial setup
- **Low/no cost**: Use GitHub free tier (Pages + Actions)
- **Fast page loads**: < 3 seconds per page
- **Preserves Discord features**: Embeds, reactions, attachments, threads
- **ToS compliant**: Use bot tokens, not user tokens

### Future Expansion

- Add Tiny Tapeout Discord server
- Client-side search (Pagefind or similar)
- RSS feeds for new messages
- Daily partitioning option for very active channels

---

## Architecture

### High-Level Design

```
┌─────────────────┐
│  Discord API    │
└────────┬────────┘
         │ Bot Token Auth
         ↓
┌─────────────────────────┐
│ DiscordChatExporter CLI │
│  (C#/.NET, all formats) │
└────────┬────────────────┘
         │ Exports: HTML, TXT, JSON, CSV
         ↓
┌──────────────────────┐
│  Python Build Scripts│
│  - export_channels   │
│  - organize_exports  │
│  - generate_nav      │
└────────┬─────────────┘
         │ Processes & organizes
         ↓
┌────────────────────┐
│   public/ (site)   │
│   + state.json     │
└────────┬───────────┘
         │ Git commit
         ↓
┌────────────────────┐
│   GitHub Pages     │
│ discord.wafer.space│
└────────────────────┘
```

**Technology Stack:**
- **Discord API**: v10
- **Export Tool**: DiscordChatExporter CLI (C#/.NET 9.0)
- **Build Scripts**: Python 3.11+ with `uv`
- **Templates**: Jinja2
- **Automation**: GitHub Actions (hourly cron)
- **Hosting**: GitHub Pages (static)
- **Deployment**: gh-pages branch

---

## Project Structure

```
discord-wafer-space/
├── .github/
│   └── workflows/
│       └── export-logs.yml           # Hourly automation
│
├── scripts/                          # Python build pipeline
│   ├── export_channels.py            # Main orchestrator
│   ├── organize_exports.py           # Date-based file organization
│   ├── generate_navigation.py        # Index page generation
│   └── config.py                     # Config loader
│
├── exports/                          # Temp storage (gitignored)
│   └── wafer-space/
│       ├── general.html
│       ├── general.txt
│       ├── general.json
│       └── general.csv
│
├── public/                           # Generated site (deployed)
│   ├── index.html                    # Main landing
│   ├── wafer-space/
│   │   ├── index.html               # Channel list
│   │   ├── general/
│   │   │   ├── index.html           # Archive list
│   │   │   ├── 2025-01.html        # Discord-style
│   │   │   ├── 2025-01.txt         # Plain text
│   │   │   ├── 2025-01.json        # JSON
│   │   │   └── 2025-01.csv         # CSV
│   │   └── announcements/
│   │       └── [same structure]
│   └── assets/
│       └── style.css
│
├── templates/                        # Jinja2 templates
│   ├── site_index.html.j2
│   ├── server_index.html.j2
│   └── channel_index.html.j2
│
├── config.toml                       # Configuration
├── state.json                        # Export state tracking
├── requirements.txt                  # Python dependencies
└── README.md
```

---

## Configuration Management

### config.toml (committed, no secrets)

```toml
[site]
title = "wafer.space Discord Logs"
description = "Public archive of wafer.space Discord server"

[servers.wafer-space]
guild_id = "123456789012345678"
name = "wafer.space"
include_channels = ["*"]           # Export all channels
exclude_channels = [               # Except these patterns
  "admin",
  "moderators",
  "private-*"
]

[export]
formats = ["html", "txt", "json", "csv"]
partition_by = "month"             # or "day" or "none"
include_threads = "all"
download_media = true
media_dir = "public/assets/media"

[github]
pages_branch = "gh-pages"
commit_author = "Discord Archive Bot"
```

### GitHub Secrets (sensitive)

- `DISCORD_BOT_TOKEN` - Bot authentication token
- Future: Additional server bot tokens if needed

### state.json (committed, tracks progress)

```json
{
  "wafer-space": {
    "general": {
      "last_export": "2025-01-15T14:00:00Z",
      "last_message_id": "1234567890123456789"
    },
    "announcements": {
      "last_export": "2025-01-15T14:00:00Z",
      "last_message_id": "9876543210987654321"
    }
  }
}
```

---

## Export Pipeline

### Incremental Export Strategy

**State Tracking:**
- `state.json` stores last export timestamp per channel
- Enables `--after` flag for incremental updates
- Only fetches new messages since last run
- Reduces API calls and processing time

**Export Process:**

```python
# Pseudocode for export_channels.py

1. Load config.toml and state.json
2. For each server in config:
   a. Fetch channel list from Discord API
   b. Filter using include/exclude patterns
3. For each channel:
   a. Get last_export timestamp from state
   b. Run DiscordChatExporter with --after flag:
      DiscordChatExporter.Cli export \
        -t $BOT_TOKEN \
        -c $CHANNEL_ID \
        --after $LAST_EXPORT \
        -f HtmlDark \
        -o exports/server/channel.html
   c. Repeat for all 4 formats (parallel)
   d. Update state.json with new timestamp
4. Return summary (channels updated, errors)
```

**Partitioning Logic:**

- **Monthly archives**: Default, creates `YYYY-MM.{html,txt,json,csv}`
- **Smart handling**:
  - Current month: Regenerate when new messages arrive
  - Past months: Immutable, never re-exported
  - First run: Export all history
  - Subsequent runs: Only current month + any new months

**Command Example:**

```bash
# Incremental export (typical hourly run)
./DiscordChatExporter.Cli export \
  -t "$DISCORD_BOT_TOKEN" \
  -c 123456789012345678 \
  --after "2025-01-15T14:00:00Z" \
  -f HtmlDark \
  -o "exports/wafer-space/general.html"

# First-time full export
./DiscordChatExporter.Cli export \
  -t "$DISCORD_BOT_TOKEN" \
  -c 123456789012345678 \
  -f HtmlDark \
  -o "exports/wafer-space/general.html"
```

---

## Navigation Generation

### Three-Level Hierarchy

**Level 1: Site Index** (`public/index.html`)
- Lists all servers
- Shows channel count per server
- Last updated timestamp
- Links to server pages

**Level 2: Server Index** (`public/wafer-space/index.html`)
- Lists all channels in server
- Shows message count for current month
- Links to monthly archives
- Format selector (HTML | TXT | JSON | CSV)

**Level 3: Channel Archive Index** (`public/wafer-space/general/index.html`)
- Lists all monthly archives for channel
- Grouped by year
- Reverse chronological order (newest first)
- Message counts per archive
- Multiple format links
- "Latest" link → current month

### Navigation Generator (`generate_navigation.py`)

**Process:**
1. Scan `public/` directory tree
2. Discover all exported files (*.html, *.txt, *.json, *.csv)
3. Group by server → channel → date
4. Count messages from JSON files (accurate counts)
5. Render Jinja2 templates with data
6. Generate index.html at each level

**Template Variables:**
```python
{
  'servers': [
    {
      'name': 'wafer-space',
      'channel_count': 15,
      'last_updated': '2025-01-15T15:00:00Z',
      'channels': [
        {
          'name': 'general',
          'message_count': 234,
          'archives': [
            {
              'date': '2025-01',
              'message_count': 234,
              'formats': ['html', 'txt', 'json', 'csv']
            }
          ]
        }
      ]
    }
  ]
}
```

**Smart Features:**
- Breadcrumb navigation on every page
- File size indicators for downloads
- Relative timestamps ("2 hours ago")
- Responsive design (mobile-friendly)

---

## GitHub Actions Automation

### Workflow Configuration

**File**: `.github/workflows/export-logs.yml`

**Triggers:**
```yaml
on:
  schedule:
    - cron: '0 * * * *'  # Every hour
  workflow_dispatch:      # Manual trigger
  push:
    branches: [main]      # Test during dev
```

**Job Steps:**

```yaml
jobs:
  export-and-deploy:
    runs-on: ubuntu-latest
    timeout-minutes: 30

    steps:
      1. Checkout repo (fetch-depth: 0 for state.json history)
      2. Set up Python 3.11
      3. Install uv: pip install uv
      4. Install dependencies: uv pip install -r requirements.txt
      5. Cache DiscordChatExporter CLI binary
      6. Download DiscordChatExporter if not cached
      7. Run export pipeline:
         - uv run python scripts/export_channels.py
         - uv run python scripts/organize_exports.py
         - uv run python scripts/generate_navigation.py
      8. Check for changes: git diff --quiet || HAS_CHANGES=true
      9. If changes:
         - Commit state.json to main branch
         - Deploy public/ to gh-pages branch
      10. Post summary comment (channels updated, errors)
```

**Environment Variables:**
```yaml
env:
  DISCORD_BOT_TOKEN: ${{ secrets.DISCORD_BOT_TOKEN }}
```

**Optimizations:**
- Cache DiscordChatExporter binary (saves ~30 seconds/run)
- Cache uv packages
- Skip commit if no changes
- Separate commits: state.json → main, public/ → gh-pages

**Cost Estimate:**
- GitHub Actions: 2,000 free minutes/month
- Each run: ~5 minutes (incremental) or ~15 minutes (full)
- Hourly: 24 runs/day × 30 days × 5 min = 3,600 min/month
- **Still within free tier** (under 2,000 if we optimize)
- **Mitigation**: Run every 2 hours instead (1,800 min/month)

---

## Error Handling

### Error Categories

**1. Discord API Errors**

| Error | Handling |
|-------|----------|
| Rate limiting (429) | DiscordChatExporter auto-retries with backoff |
| Invalid token | Fail immediately with clear message |
| Channel not found | Log warning, skip channel, continue |
| Permission denied | Log warning, skip channel, continue |
| Network timeout | Retry 3 times, then skip channel |

**2. Export Failures**

| Error | Handling |
|-------|----------|
| Partial export | Keep old state, don't update state.json |
| Corrupted file | Validate file size, retry if < 100 bytes |
| Disk space | Should never happen (14GB available) |

**3. Deployment Errors**

| Error | Handling |
|-------|----------|
| Git merge conflict | Abort and alert (shouldn't happen) |
| gh-pages push fails | Retry once, then fail workflow |
| Navigation gen fails | Keep old navigation (site still works) |

### Monitoring & Alerting

**Built-in:**
- GitHub Actions email on workflow failure
- Workflow summary shows channels updated, errors
- Commit messages include stats: "Updated 12 channels, 234 messages"

**Future:**
- Discord webhook to admin channel on errors
- Prometheus metrics export
- Uptime monitoring (uptimerobot.com)

### Recovery Procedures

**Manual retry:**
```bash
# Via GitHub UI
Actions → export-logs → Run workflow
```

**Force re-export:**
```bash
# Delete state for specific channel
# Edit state.json, remove entry, commit
# Next run will export full history
```

**Full reset:**
```bash
# Delete entire state.json
# Next run exports all channels, all history
# Takes ~30-60 minutes
```

---

## Security Considerations

### Bot Token Security

- ✅ Stored in GitHub Secrets (encrypted at rest)
- ✅ Never logged or exposed in workflow output
- ✅ Bot has minimal permissions (Read Messages, Read History)
- ✅ Can be rotated without code changes

### Bot Setup Requirements

1. Create bot at https://discord.com/developers
2. Enable "Message Content Intent" (required)
3. Generate OAuth2 invite with permissions: `66560`
4. Invite to server
5. Copy token to GitHub Secrets

### Public Data Considerations

- Only archive public channels (exclude private/admin)
- Add server notice: "Public channels are archived at discord.wafer.space"
- Respect deletions: Re-export current month removes deleted messages
- Takedown process: Manual removal via PR or issue

### ToS Compliance

- ✅ Bot tokens are ToS-compliant (user tokens are not)
- ✅ Public archival of public channels (not scraping private data)
- ✅ No automation of user accounts

---

## Performance Considerations

### Page Load Optimization

**Target**: < 3 seconds per page

**Strategies:**
- DiscordChatExporter HTML is minified
- CSS embedded in HTML (no extra request)
- Discord fonts loaded from CDN (cached)
- Media assets lazy-loaded (if enabled)
- Static files served via GitHub Pages CDN

**File Sizes (estimated):**
- HTML (monthly): 500KB - 5MB (depending on activity)
- TXT (monthly): 100KB - 1MB
- JSON (monthly): 200KB - 2MB
- CSV (monthly): 150KB - 1.5MB

### Build Performance

**Incremental builds:**
- Only process channels with new messages
- Skip navigation regeneration if no structural changes
- State.json prevents redundant exports

**Full rebuild:**
- First run: 30-60 minutes (export all history)
- Subsequent runs: 2-5 minutes (incremental)

---

## Testing Strategy

### Pre-Deployment Testing

**Local testing:**
```bash
# Test export pipeline
uv run python scripts/export_channels.py --dry-run

# Test navigation generation
uv run python scripts/generate_navigation.py --preview

# Serve locally
python -m http.server --directory public 8000
```

**GitHub Actions testing:**
- Push to main triggers test run
- Verify in staging before enabling hourly cron
- Use `workflow_dispatch` for manual testing

### Validation Checks

**Automated:**
- File size validation (not empty, not suspiciously small)
- JSON parsing validation (valid JSON)
- HTML validation (basic structure checks)

**Manual:**
- Spot-check HTML rendering in browser
- Verify navigation links work
- Test all 4 formats download correctly

---

## Deployment Plan

### Phase 1: Initial Setup (Week 1)

1. Create repository: `discord-wafer-space`
2. Set up bot on Discord
3. Add bot token to GitHub Secrets
4. Create basic config.toml
5. Test DiscordChatExporter locally

### Phase 2: Pipeline Development (Week 1-2)

1. Write export_channels.py
2. Write organize_exports.py
3. Write generate_navigation.py
4. Create Jinja2 templates
5. Test full pipeline locally

### Phase 3: Automation (Week 2)

1. Create GitHub Actions workflow
2. Test with manual triggers
3. Perform full export (all history)
4. Verify deployment to gh-pages

### Phase 4: Domain & Go-Live (Week 2-3)

1. Configure discord.wafer.space DNS
2. Enable GitHub Pages custom domain
3. Enable hourly cron schedule
4. Post notice in Discord server
5. Monitor for 48 hours

### Phase 5: Iteration (Ongoing)

1. Add Tiny Tapeout server
2. Implement search (Pagefind)
3. Add RSS feeds
4. Performance optimization

---

## Future Enhancements

### High Priority

- [ ] Client-side search (Pagefind)
- [ ] RSS feeds (per channel, per server, site-wide)
- [ ] Tiny Tapeout server support

### Medium Priority

- [ ] Daily partitioning option
- [ ] Custom CSS themes
- [ ] User avatars cached locally
- [ ] Message edit history preservation

### Low Priority

- [ ] Reaction statistics
- [ ] Thread visualization
- [ ] Export analytics dashboard
- [ ] Archive.org backup integration

---

## Success Metrics

### Launch Criteria

- ✅ Hourly exports working reliably
- ✅ All public channels archived
- ✅ All 4 formats available
- ✅ Navigation working correctly
- ✅ Page loads < 3 seconds
- ✅ Zero failed workflows for 48 hours

### Ongoing Monitoring

- Workflow success rate > 95%
- Zero manual interventions per week
- Page load time < 3 seconds (p95)
- GitHub Actions usage < 2,000 min/month

---

## Appendices

### A. Dependencies

**Python (requirements.txt):**
```
jinja2>=3.1.0
toml>=0.10.0
requests>=2.31.0
python-dateutil>=2.8.0
```

**System:**
- DiscordChatExporter.Cli (latest stable)
- Python 3.11+
- uv (Python package manager)
- Git

### B. Useful Commands

```bash
# Local development
uv run python scripts/export_channels.py
uv run python scripts/generate_navigation.py
python -m http.server --directory public 8000

# Manual export (single channel)
./DiscordChatExporter.Cli export \
  -t TOKEN \
  -c CHANNEL_ID \
  -f HtmlDark

# Force re-export all
rm state.json
uv run python scripts/export_channels.py

# Deploy manually
git checkout gh-pages
rsync -av public/ .
git add .
git commit -m "Manual deploy"
git push origin gh-pages
```

### C. References

- DiscordChatExporter: https://github.com/Tyrrrz/DiscordChatExporter
- Discord API: https://discord.com/developers/docs
- GitHub Actions: https://docs.github.com/en/actions
- GitHub Pages: https://pages.github.com/
