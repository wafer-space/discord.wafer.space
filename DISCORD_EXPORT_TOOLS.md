# Discord Message Export and Archival Tools

Research conducted: 2025-11-11

## Overview

This document compares tools for downloading message history from Discord servers and exporting them in various formats (text, HTML, JSON, CSV). The research focuses on tools suitable for creating publicly accessible archives similar to traditional IRC log systems.

## Quick Comparison Table

| Tool | Text Format | HTML Format | CLI | GUI | Platform | Open Source | ToS Compliant* | Web Publishing |
|------|-------------|-------------|-----|-----|----------|-------------|----------------|----------------|
| **DiscordChatExporter** | ✅ TXT | ✅ Dark/Light | ✅ | ✅ (Win) | Win/Mac/Linux/Docker | ✅ MIT | ✅ (bot token) | ⭐⭐⭐ + scripting |
| **Discord History Tracker** | ✅ TXT | ✅ HTML | ❌ | ✅ | Win/Mac/Linux | ✅ MIT | ❌ (user token) | ⭐ Database-focused |
| **DiscordChatExporterPy** | ❌ | ✅ HTML | ❌ | ❌ | Python/Bot | ✅ GitHub | ✅ (bot) | ⭐⭐ Single channels |
| **DiscordChatExporter-frontend** | ❌ JSON | ✅ Web UI | ✅ | ✅ | Docker | ✅ GitHub | ✅ (bot) | ⭐⭐⭐⭐ Dynamic |
| **discord-html-transcripts** | ❌ | ✅ HTML | ❌ | ❌ | Node.js/Bot | ✅ GitHub | ✅ (bot) | ⭐⭐ Single channels |
| **discord-dl** | ❌ JSON | ✅ Web UI | ✅ | ❌ | Go | ✅ GitHub | ⚠️ ToS warning | ⭐⭐ Requires server |
| **Discrub Extension** | ❌ CSV | ✅ HTML | ❌ | ✅ | Browser | ✅ GitHub | ❌ (user token) | ⭐ Small exports |
| **message-scraper** | ✅ TXT/MD | ✅ HTML | ✅ | ❌ | Node.js | ✅ GitHub | ❌ ⚠️ ToS violation | ⭐⭐ Educational |
| **Discord GDPR Export** | ❌ CSV | ❌ | ❌ | ✅ | Official | N/A | ✅ Official | ❌ Personal data only |

\*ToS Compliance Note: User tokens violate Discord ToS. Bot tokens are compliant.

**Additional Format Support**:
- DiscordChatExporter: Also supports JSON and CSV
- Discrub: Also supports JSON
- message-scraper: Also supports Markdown

---

## Detailed Tool Reviews

### 1. DiscordChatExporter (by Tyrrrz) ⭐ RECOMMENDED

**Repository**: https://github.com/Tyrrrz/DiscordChatExporter

**Description**: The most popular and mature open-source application for exporting Discord chat logs. Supports both GUI (Windows) and CLI (all platforms).

**Export Formats**: HTML (dark/light themes), TXT, CSV, JSON

**Key Features**:
- ✅ Comprehensive Discord feature support (markdown, attachments, embeds, emoji, reactions)
- ✅ Both GUI and CLI interfaces
- ✅ Cross-platform (Windows, macOS, Linux, Docker)
- ✅ Batch operations (export entire servers)
- ✅ Self-contained exports with offline viewing
- ✅ Bot token support (ToS compliant)
- ✅ Active maintenance (7,000+ stars)
- ✅ Excellent documentation

**Limitations**:
- ❌ No built-in index page generation
- ❌ No built-in search functionality
- ❌ GUI only on Windows (CLI available on all platforms)
- ⚠️ User tokens violate ToS (use bot tokens instead)

**Installation**:
```bash
# Download from releases
# https://github.com/Tyrrrz/DiscordChatExporter/releases

# Docker
docker pull tyrrrz/discordchatexporter:stable

# Arch Linux
yay -S discord-chat-exporter-cli

# NixOS
nix-env -iA nixpkgs.discordchatexporter-cli
```

**Usage Examples**:
```bash
# Export single channel
./DiscordChatExporter.Cli export -t TOKEN -c CHANNEL_ID -f HtmlDark

# Export all channels in a server
./DiscordChatExporter.Cli exportguild -t TOKEN -g SERVER_ID --include-threads All

# Export with date range
./DiscordChatExporter.Cli export -t TOKEN -c CHANNEL_ID \
  --after "2024-01-01" --before "2024-12-31" \
  -o "exports/%G/%C.html"
```

**Best For**:
- High-quality, feature-complete exports
- Long-term archival with offline viewing
- Batch exporting entire servers
- Research and documentation
- Web publishing (with custom scripting)

---

### 2. Discord History Tracker (DHT)

**Repository**: https://github.com/chylex/Discord-History-Tracker
**Website**: https://dht.chylex.com

**Description**: Desktop application that saves Discord chat history into a local SQLite database with an offline HTML viewer.

**Export Formats**: SQLite database, HTML viewer, TXT, JSON

**Key Features**:
- ✅ Offline HTML viewer with Discord-style layout
- ✅ SQLite database for SQL queries
- ✅ Cross-platform desktop app
- ✅ Browser script version available
- ✅ Local storage (privacy-focused)

**Limitations**:
- ❌ Database-focused rather than standalone exports
- ❌ Less feature-rich than DiscordChatExporter
- ❌ Minimal documentation
- ⚠️ Building requires .NET 9 SDK

**Best For**:
- Users who want to query message history using SQL
- Long-term tracking with incremental updates
- Database-driven analysis

**Current Version**: v47.2

---

### 3. DiscordChatExporterPy (chat-exporter)

**Repository**: https://github.com/mahtoid/DiscordChatExporterPy
**PyPI**: https://pypi.org/project/chat-exporter/

**Description**: Python library for discord.py bots that exports Discord channels to HTML files.

**Export Formats**: HTML only

**Key Features**:
- ✅ Python-based (discord.py integration)
- ✅ Discord-styled HTML transcripts
- ✅ Customization options (time format, timezone, date ranges)
- ✅ Easy pip installation
- ✅ Python 3.6+ support

**Limitations**:
- ❌ HTML only (no TXT, CSV, or JSON)
- ❌ Requires discord.py bot framework
- ❌ No standalone CLI
- ❌ Single-channel processing

**Installation**:
```bash
pip install chat-exporter
```

**Usage Example**:
```python
import chat_exporter

@bot.command()
async def save(ctx):
    transcript = await chat_exporter.export(
        ctx.channel,
        limit=100,
        tz_info="America/New_York"
    )

    with open("transcript.html", "w", encoding="utf-8") as f:
        f.write(transcript)
```

**Best For**:
- Python developers building Discord bots
- Programmatic export control within bot code
- Projects using discord.py or forks

---

### 4. DiscordChatExporter-frontend

**Repository**: https://github.com/slatinsky/DiscordChatExporter-frontend

**Description**: Web interface for browsing DiscordChatExporter JSON exports with search functionality.

**Export Formats**: Requires JSON input, provides web UI

**Key Features**:
- ✅ Professional Discord-like UI
- ✅ Built-in search with autocomplete
- ✅ Optimized for large exports
- ✅ MongoDB indexing for fast searches
- ✅ Self-hosting capability

**Limitations**:
- ❌ Not static (requires MongoDB + Node.js server)
- ❌ Complex deployment (Docker required)
- ❌ JSON-only format support
- ❌ Resource intensive (AVX CPU required)
- ❌ Ports required: 21011, 27017, 58000

**Best For**:
- Organizations with server infrastructure
- Large-scale archives requiring search
- Professional Discord-like interface

**Not Suitable For**: Static hosting (GitHub Pages, Netlify)

---

### 5. discord-html-transcripts

**Repository**: https://github.com/ItzDerock/discord-html-transcripts
**NPM**: https://www.npmjs.com/package/discord-html-transcripts

**Description**: Node.js library for Discord.js bots that generates static HTML transcripts using React SSR.

**Export Formats**: HTML only

**Key Features**:
- ✅ True static HTML output (React SSR)
- ✅ Discord bot integration
- ✅ Rich formatting support
- ✅ XSS protection
- ✅ Customizable styling

**Limitations**:
- ❌ Single-channel only (no batch processing)
- ❌ No navigation structure
- ❌ Requires Discord.js bot
- ❌ Discord.js v14/v15 only

**Installation**:
```bash
npm install discord-html-transcripts
```

**Best For**:
- Discord.js bot developers
- Occasional channel transcripts (support tickets, event logs)

---

### 6. discord-dl

**Repository**: https://github.com/Yakabuff/discord-dl

**Description**: Go-based archiving tool with SQLite storage and built-in web server.

**Export Formats**: SQLite database, JSON, Web API

**Key Features**:
- ✅ Built-in web interface
- ✅ Real-time listening mode (bot only)
- ✅ SQLite database storage
- ✅ Channel-specific monitoring

**Limitations**:
- ⚠️ Violates ToS if using selfbot
- ❌ Not static (requires web server)
- ❌ Limited documentation
- ❌ No authentication/access controls mentioned

**Best For**:
- Real-time monitoring with authorized bot
- Users comfortable managing database + web server

---

### 7. Discrub Browser Extension

**Repository**: https://github.com/prathercc/discrub-ext

**Description**: Chrome/Firefox extension for editing, deleting, and exporting Discord messages.

**Export Formats**: HTML, CSV, JSON

**Key Features**:
- ✅ Multiple export formats
- ✅ Browser-based (no installation)
- ✅ Message manipulation (edit/delete)
- ✅ Advanced filtering

**Limitations**:
- ❌ Desktop browsers only
- ❌ Rate limiting constraints
- ⚠️ Uses user tokens (ToS violation)
- ❌ Extension dependency

**Best For**:
- Quick browser-based exports
- Message management in addition to export
- Small-scale exports

---

### 8. xHyroM's message-scraper

**Repository**: https://github.com/xHyroM/message-scraper

**Description**: Fast TypeScript tool for extracting Discord messages to HTML, Markdown, or TXT.

**Export Formats**: HTML, Markdown, TXT

**Key Features**:
- ✅ Multiple text formats (including Markdown)
- ✅ TypeScript/Node.js
- ✅ Fast performance

**Limitations**:
- ❌ **Explicit ToS violation warning**
- ❌ "Educational purposes only"
- ❌ High account termination risk
- ❌ Minimal documentation
- ❌ Requires Node.js v16+

**Installation**:
```bash
npm ci
npm run build
npm run start
```

**⚠️ WARNING**: README explicitly states "Self botting violates the Discord ToS, you do it at your own risk"

**Best For**: Educational/research purposes only (if you accept account risk)

---

### 9. Discord Official GDPR Export

**How to Request**: User Settings > Privacy & Safety > Request Data

**Description**: Discord's official data export package (GDPR compliance).

**Export Formats**: JSON, CSV

**Key Features**:
- ✅ Official and ToS-compliant
- ✅ Comprehensive account data
- ✅ No third-party tools required
- ✅ Completely safe

**Limitations**:
- ❌ Up to 30-day wait
- ❌ Only YOUR sent messages (not entire conversations)
- ❌ Raw data format (no formatted HTML)
- ❌ No viewer included
- ❌ Single snapshot (not ongoing archival)

**What's Included**:
- Account information and avatar
- Your activity on Discord
- Your sent messages
- Server membership information

**References**:
- Official Guide: https://support.discord.com/hc/en-us/articles/360004027692
- Data Package Details: https://support.discord.com/hc/en-us/articles/360004957991

**Best For**:
- Personal data backup
- GDPR compliance needs
- Completely risk-free official exports

---

## Authentication & Security

### User Tokens vs Bot Tokens

**User Tokens**:
- ❌ Violate Discord Terms of Service
- ❌ Risk account termination
- ❌ Obtained via browser developer tools
- ⚠️ Use at your own risk

**Bot Tokens** (Recommended):
- ✅ Compliant with Discord ToS
- ✅ No account risk
- ✅ Proper authentication method
- ✅ Obtained via Discord Developer Portal

### Creating a Bot for Exports

1. Go to https://discord.com/developers/applications
2. Create New Application
3. Go to Bot section, create bot
4. Enable "Message Content Intent" (required for reading messages)
5. Copy bot token
6. Invite bot to server with permissions code: `66560`
7. Use bot token with export tools

---

## Rate Limiting Considerations

Discord enforces API rate limits:
- **Global limit**: 50 requests/second
- **Per-route limits**: Vary by endpoint
- **Large servers**: May take hours to export completely
- **Tools handle this**: DiscordChatExporter automatically respects rate limits

---

## Legal & Ethical Considerations

### Best Practices

- ✅ Only archive public servers (or get explicit permission)
- ✅ Obtain consent from server owners
- ✅ Respect privacy expectations
- ✅ Use bot tokens (not selfbots)
- ✅ Consider GDPR compliance for EU users
- ✅ Implement takedown request process
- ✅ Add clear disclosure that logs are archived

### Privacy Guidelines

- Only export public channels
- Redact sensitive information when appropriate
- Respect deleted messages (consider tombstones)
- Provide opt-out mechanisms
- Be transparent about archiving practices

### References

- Discord Ethics Guide: https://darcmode.org/ethics-101/
- Discord Privacy Policy: https://discord.com/privacy

---

## Recommendations by Use Case

### For Web Publishing (Public Logs Website)
**Recommended**: DiscordChatExporter + Custom scripting + Search engine
- See WEB_PUBLISHING_GUIDE.md for detailed implementation

### For Personal Archival
**Recommended**: DiscordChatExporter (HTML + JSON formats)
- Use bot token for ToS compliance
- Export to multiple formats for redundancy

### For SQL Analysis
**Recommended**: Discord History Tracker
- SQLite database format
- Query message history with SQL

### For Python Bot Integration
**Recommended**: DiscordChatExporterPy (chat-exporter)
- Native discord.py integration
- Programmatic export control

### For Official Personal Data
**Recommended**: Discord GDPR Export
- Completely safe and official
- No account risk

---

## Version Information

- **DiscordChatExporter**: Latest release from https://github.com/Tyrrrz/DiscordChatExporter/releases
- **Discord History Tracker**: v47.2
- **Research Date**: 2025-11-11

---

## Additional Resources

- DiscordChatExporter Documentation: https://github.com/Tyrrrz/DiscordChatExporter/tree/master/.docs
- Discord Developer Portal: https://discord.com/developers
- Discord API Documentation: https://discord.com/developers/docs
