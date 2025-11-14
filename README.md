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
