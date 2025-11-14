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
