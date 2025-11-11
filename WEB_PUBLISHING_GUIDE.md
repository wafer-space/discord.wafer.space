# Discord Log Web Publishing Guide

**Goal**: Create a publicly accessible website (like discord.wafer.space) that archives Discord messages similar to traditional IRC log viewers (irc2html, pisg).

**Research Date**: 2025-11-11

---

## Table of Contents

1. [Architecture Options](#architecture-options)
2. [Comparison to IRC Logging Systems](#comparison-to-irc-logging-systems)
3. [Recommended Solutions](#recommended-solutions)
4. [Implementation Guide](#implementation-guide)
5. [Search Integration](#search-integration)
6. [Automation & Continuous Publishing](#automation--continuous-publishing)
7. [Hosting Options](#hosting-options)
8. [Privacy & Ethics](#privacy--ethics)

---

## Architecture Options

### Option 1: Static Site (Recommended) ⭐⭐⭐⭐⭐

**Architecture**: DiscordChatExporter → Python Scripts → Pagefind → Static Hosting

**Components**:
- **DiscordChatExporter CLI**: Export channels to HTML/JSON
- **Custom Python scripts**: Generate index pages and navigation
- **Pagefind**: Client-side search (only 8KB initial load!)
- **GitHub Pages/Netlify**: Free static hosting
- **GitHub Actions**: Automated daily updates

**Pros**:
- ✅ Completely static (no server needed)
- ✅ Free hosting (GitHub Pages, Netlify)
- ✅ Fast and scalable (CDN-backed)
- ✅ Simple deployment (git push)
- ✅ SEO-friendly
- ✅ Python-based scripting
- ✅ Low maintenance

**Cons**:
- ⚠️ Requires custom scripting (~20-40 hours)
- ⚠️ Basic UI (not Discord-like)

**Best For**: Most use cases, especially if you want low maintenance and free hosting

---

### Option 2: Static Site Generator ⭐⭐⭐⭐

**Architecture**: DiscordChatExporter → Hugo/Eleventy → Pagefind → Static Hosting

**Components**:
- **DiscordChatExporter CLI**: Export to JSON/HTML
- **Hugo or Eleventy**: Professional static site generator
- **Pagefind**: Search indexing
- **Netlify/Vercel**: Advanced hosting with CI/CD

**Pros**:
- ✅ Professional templates and theming
- ✅ Built-in RSS, sitemaps, taxonomy
- ✅ Better navigation structure
- ✅ Large community and plugins
- ✅ Very fast builds (Hugo)

**Cons**:
- ⚠️ Steeper learning curve
- ⚠️ More complex pipeline
- ⚠️ Hugo uses Go templates (not Python)

**Best For**: If you want professional features and are comfortable with SSG templating

---

### Option 3: Dynamic Web Application ⭐⭐⭐

**Architecture**: DiscordChatExporter → MongoDB → Node.js → React Frontend

**Tool**: DiscordChatExporter-frontend

**Components**:
- **DiscordChatExporter CLI**: Export to JSON
- **MongoDB**: Message database and indexing
- **Node.js backend**: API server
- **React frontend**: Discord-like UI
- **Docker**: Container deployment

**Pros**:
- ✅ Professional Discord-style UI
- ✅ Real search with autocomplete
- ✅ Best user experience
- ✅ Optimized for massive archives

**Cons**:
- ❌ Not static (requires VPS/server)
- ❌ Infrastructure costs (~$5-20/month)
- ❌ More complex deployment
- ❌ Requires MongoDB + Node.js maintenance

**Best For**: Organizations with budget for hosting and need for Discord-like UI

**References**:
- GitHub: https://github.com/slatinsky/DiscordChatExporter-frontend

---

## Comparison to IRC Logging Systems

### Traditional IRC Log Features

**irclog2html** provided:
- ✅ Date-based navigation (prev/next links)
- ✅ Automatic index generation (`logs2html.py`)
- ✅ Search box option (`--searchbox` flag)
- ✅ Multiple output styles
- ✅ Batch processing
- ✅ Stable "latest" link

**References**:
- irclog2html: https://github.com/mgedmin/irclog2html
- PyPI: https://pypi.org/project/irclog2html/

### What Discord Tools Lack

Most Discord export tools generate individual channel files but **do not automatically create**:
- ❌ Index pages listing all channels
- ❌ Date-based navigation (daily/monthly archives)
- ❌ Cross-channel navigation
- ❌ Search interfaces
- ❌ "Latest messages" landing pages

**Solution**: Combine Discord export tools with custom scripting or static site generators.

### Feature Comparison Table

| Feature | irclog2html | DiscordChatExporter | Gap | Solution |
|---------|-------------|---------------------|-----|----------|
| Daily logs | ✅ Yes | ⚠️ Manual partitioning | Small | Use `--after`/`--before` flags |
| Index generation | ✅ logs2html.py | ❌ No | **Critical** | **Custom Python script** |
| Date navigation | ✅ Prev/next | ❌ No | **Critical** | **SSG templates or scripting** |
| Search box | ✅ --searchbox | ❌ No | **Critical** | **Pagefind integration** |
| Channel list | ✅ Yes | ❌ No | **Critical** | **Custom index.html** |
| Batch processing | ✅ Yes | ✅ Yes | None | ✅ Built-in |
| Static output | ✅ Yes | ✅ Yes | None | ✅ Built-in |
| "Latest" link | ✅ Yes | ❌ No | Nice-to-have | Symlink or script |

---

## Recommended Solutions

### 🥇 Recommended: Static Site with Python Scripts

**Perfect for**: discord.wafer.space use case

**Tech Stack**:
- DiscordChatExporter CLI (export)
- Python scripts (navigation/index generation)
- Pagefind (search)
- GitHub Pages or Netlify (hosting)
- GitHub Actions (automation)

**Estimated Setup Time**: 1-2 weeks for MVP

**Directory Structure**:
```
discord-wafer-space/
├── .github/
│   └── workflows/
│       └── export.yml          # Automated export workflow
├── exports/                     # Raw DiscordChatExporter exports
│   ├── server-name/
│   │   ├── general.html
│   │   ├── announcements.html
│   │   └── ...
├── public/                      # Generated static site
│   ├── index.html              # Main landing page
│   ├── channels/               # Channel pages
│   │   ├── general/
│   │   │   ├── 2025-01.html
│   │   │   └── 2025-02.html
│   ├── pagefind/               # Search index (auto-generated)
│   └── assets/
│       └── style.css
├── scripts/
│   ├── export.py               # Export Discord channels
│   ├── generate_index.py       # Generate navigation/indexes
│   └── build.py                # Build pipeline orchestrator
├── templates/                   # HTML templates (Jinja2)
│   ├── index.html.jinja2
│   ├── channel_list.html.jinja2
│   └── archive.html.jinja2
└── config.toml                 # Configuration file
```

---

## Implementation Guide

### Phase 1: Basic Export (Week 1)

#### Step 1: Set Up Discord Bot

1. Go to https://discord.com/developers/applications
2. Click "New Application"
3. Go to "Bot" section, create bot
4. Enable "Message Content Intent" in Bot settings
5. Copy bot token (keep secure!)
6. Generate invite URL with permissions code: `66560`
7. Invite bot to your Discord server

#### Step 2: Install DiscordChatExporter

Download from releases:
- **Windows/macOS/Linux**: https://github.com/Tyrrrz/DiscordChatExporter/releases
- **Docker**: `docker pull tyrrrz/discordchatexporter:stable`
- **Arch Linux**: `yay -S discord-chat-exporter-cli`

#### Step 3: Test Export

```bash
# Export single channel
./DiscordChatExporter.Cli export \
  -t YOUR_BOT_TOKEN \
  -c CHANNEL_ID \
  -f HtmlDark \
  -o exports/test.html

# Export all channels in a server
./DiscordChatExporter.Cli exportguild \
  -t YOUR_BOT_TOKEN \
  -g SERVER_ID \
  -f HtmlDark \
  -o "exports/%G/%C.html" \
  --include-threads All
```

**Finding IDs**:
- Enable Developer Mode in Discord (User Settings > Advanced)
- Right-click on server/channel → Copy ID

---

### Phase 2: Index Generation (Week 1-2)

#### Create Python Index Generator

**File**: `scripts/generate_index.py`

```python
#!/usr/bin/env python3
"""
Generate index pages for Discord log archives.
"""

import os
import json
from pathlib import Path
from datetime import datetime
from jinja2 import Template

def scan_exports(export_dir):
    """
    Scan export directory for HTML files.
    Returns list of {server, channel, date, path}.
    """
    channels = []
    export_path = Path(export_dir)

    for html_file in export_path.rglob("*.html"):
        # Parse filename: exports/server-name/channel-name.html
        parts = html_file.parts
        if len(parts) >= 3:
            channels.append({
                'server': parts[-2],
                'channel': html_file.stem,
                'path': str(html_file.relative_to(export_path)),
                'modified': datetime.fromtimestamp(html_file.stat().st_mtime)
            })

    return sorted(channels, key=lambda x: (x['server'], x['channel']))

def generate_index(channels, output_file):
    """
    Generate index.html with channel listing.
    """
    template = Template("""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Discord Logs Archive</title>
    <link rel="stylesheet" href="/assets/style.css">
</head>
<body>
    <header>
        <h1>Discord Logs Archive</h1>
        <div id="search"></div>
    </header>

    <main>
        {% for server, server_channels in channels_by_server.items() %}
        <section class="server">
            <h2>{{ server }}</h2>
            <ul class="channel-list">
                {% for channel in server_channels %}
                <li>
                    <a href="/{{ channel.path }}">
                        # {{ channel.channel }}
                    </a>
                    <span class="date">Last updated: {{ channel.modified.strftime('%Y-%m-%d') }}</span>
                </li>
                {% endfor %}
            </ul>
        </section>
        {% endfor %}
    </main>

    <footer>
        <p>Generated on {{ now.strftime('%Y-%m-%d %H:%M:%S UTC') }}</p>
    </footer>

    <!-- Pagefind Search -->
    <link href="/pagefind/pagefind-ui.css" rel="stylesheet">
    <script src="/pagefind/pagefind-ui.js"></script>
    <script>
        window.addEventListener('DOMContentLoaded', (event) => {
            new PagefindUI({ element: "#search", showSubResults: true });
        });
    </script>
</body>
</html>
    """)

    # Group channels by server
    channels_by_server = {}
    for channel in channels:
        server = channel['server']
        if server not in channels_by_server:
            channels_by_server[server] = []
        channels_by_server[server].append(channel)

    html = template.render(
        channels_by_server=channels_by_server,
        now=datetime.utcnow()
    )

    Path(output_file).write_text(html)
    print(f"Generated {output_file}")

if __name__ == "__main__":
    channels = scan_exports("exports")
    generate_index(channels, "public/index.html")
```

**Install dependencies**:
```bash
uv pip install jinja2
```

**Run**:
```bash
uv run python scripts/generate_index.py
```

---

### Phase 3: Add Search (Week 2)

#### Install Pagefind

Pagefind is a fast, low-bandwidth static search library.

**Installation**:
```bash
# Using npm
npm install -g pagefind

# Or using Python
pip install pagefind
```

**Usage**:
```bash
# After generating your static site
npx pagefind --site public

# Or with Python
python3 -m pagefind --site public
```

This generates a `public/pagefind/` directory with search indexes.

**Integration**:
The index.html template above already includes Pagefind integration:
- Search UI appears in `<div id="search"></div>`
- Loads automatically on page load
- Searches across all HTML content

**References**:
- Pagefind: https://pagefind.app/
- Documentation: https://pagefind.app/docs/

---

### Phase 4: Styling (Week 2)

#### Create Basic CSS

**File**: `public/assets/style.css`

```css
/* Discord Logs Archive Styles */

:root {
    --bg-primary: #36393f;
    --bg-secondary: #2f3136;
    --text-primary: #dcddde;
    --text-secondary: #b9bbbe;
    --accent: #7289da;
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
    border-bottom: 1px solid #202225;
}

header h1 {
    color: var(--text-primary);
    margin-bottom: 1rem;
}

main {
    max-width: 1200px;
    margin: 2rem auto;
    padding: 0 2rem;
}

.server {
    margin-bottom: 3rem;
}

.server h2 {
    color: var(--accent);
    margin-bottom: 1rem;
    font-size: 1.5rem;
}

.channel-list {
    list-style: none;
}

.channel-list li {
    background: var(--bg-secondary);
    margin: 0.5rem 0;
    padding: 1rem;
    border-radius: 4px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.channel-list a {
    color: var(--text-primary);
    text-decoration: none;
    font-weight: 500;
}

.channel-list a:hover {
    color: var(--accent);
}

.date {
    color: var(--text-secondary);
    font-size: 0.875rem;
}

footer {
    text-align: center;
    padding: 2rem;
    color: var(--text-secondary);
    font-size: 0.875rem;
}

/* Pagefind Search Styling */
#search {
    margin-top: 1rem;
}
```

---

### Phase 5: Automation (Week 3)

#### Create Export Script

**File**: `scripts/export.sh`

```bash
#!/bin/bash
# Export Discord channels using DiscordChatExporter

set -e  # Exit on error

# Configuration
BOT_TOKEN="${DISCORD_BOT_TOKEN}"
SERVER_ID="${DISCORD_SERVER_ID}"
OUTPUT_DIR="exports"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Export all channels
./DiscordChatExporter.Cli exportguild \
    -t "$BOT_TOKEN" \
    -g "$SERVER_ID" \
    -f HtmlDark \
    -o "$OUTPUT_DIR/%G/%C.html" \
    --include-threads All \
    --dateformat "yyyy-MM-dd"

echo "Export completed successfully!"
```

Make executable:
```bash
chmod +x scripts/export.sh
```

---

#### Create Build Script

**File**: `scripts/build.py`

```python
#!/usr/bin/env python3
"""
Build pipeline for Discord log website.
"""

import subprocess
import sys
from pathlib import Path

def run_command(cmd, description):
    """Run shell command and handle errors."""
    print(f"\n{'='*60}")
    print(f"{description}...")
    print(f"{'='*60}\n")

    result = subprocess.run(cmd, shell=True)
    if result.returncode != 0:
        print(f"ERROR: {description} failed!")
        sys.exit(1)

    print(f"\n✓ {description} completed\n")

def main():
    # Ensure we're in project root
    project_root = Path(__file__).parent.parent

    # Step 1: Export Discord channels
    run_command(
        "./scripts/export.sh",
        "Exporting Discord channels"
    )

    # Step 2: Generate index pages
    run_command(
        "uv run python scripts/generate_index.py",
        "Generating index pages"
    )

    # Step 3: Copy exports to public directory
    run_command(
        "rsync -av --delete exports/ public/channels/",
        "Copying exports to public directory"
    )

    # Step 4: Generate search index
    run_command(
        "npx pagefind --site public",
        "Generating search index"
    )

    print("\n" + "="*60)
    print("BUILD COMPLETE!")
    print("="*60)
    print("\nYou can now:")
    print("  - Test locally: python3 -m http.server --directory public 8000")
    print("  - Deploy to hosting: git push origin gh-pages")

if __name__ == "__main__":
    main()
```

Make executable:
```bash
chmod +x scripts/build.py
```

**Run build**:
```bash
uv run python scripts/build.py
```

---

#### Set Up GitHub Actions

**File**: `.github/workflows/export.yml`

```yaml
name: Export Discord Logs

on:
  schedule:
    # Run daily at 2 AM UTC
    - cron: '0 2 * * *'

  # Allow manual triggering
  workflow_dispatch:

jobs:
  export-and-deploy:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install uv
        run: pip install uv

      - name: Install Python dependencies
        run: uv pip install -r requirements.txt

      - name: Download DiscordChatExporter
        run: |
          wget https://github.com/Tyrrrz/DiscordChatExporter/releases/latest/download/DiscordChatExporter.Cli.linux-x64.zip
          unzip DiscordChatExporter.Cli.linux-x64.zip -d .
          chmod +x DiscordChatExporter.Cli

      - name: Export Discord channels
        env:
          DISCORD_BOT_TOKEN: ${{ secrets.DISCORD_BOT_TOKEN }}
          DISCORD_SERVER_ID: ${{ secrets.DISCORD_SERVER_ID }}
        run: ./scripts/export.sh

      - name: Build static site
        run: uv run python scripts/build.py

      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v3
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: ./public
          cname: discord.wafer.space  # Optional: custom domain
```

**Set up secrets**:
1. Go to your GitHub repository
2. Settings → Secrets and variables → Actions
3. Add secrets:
   - `DISCORD_BOT_TOKEN`: Your Discord bot token
   - `DISCORD_SERVER_ID`: Your Discord server ID

---

### Phase 6: Deployment (Week 3)

#### Option A: GitHub Pages

1. **Enable GitHub Pages**:
   - Repository Settings → Pages
   - Source: Deploy from a branch
   - Branch: `gh-pages` / `root`

2. **Custom Domain** (optional):
   - Add CNAME record: `discord.wafer.space` → `username.github.io`
   - Add domain in GitHub Pages settings

3. **Deploy**:
   ```bash
   # Manual deployment
   git checkout -b gh-pages
   uv run python scripts/build.py
   git add public/
   git commit -m "Deploy Discord logs"
   git push origin gh-pages
   ```

#### Option B: Netlify

1. **Connect repository**:
   - Go to https://app.netlify.com/
   - New site from Git → Connect GitHub repository

2. **Configure build**:
   - Build command: `uv run python scripts/build.py`
   - Publish directory: `public`

3. **Environment variables**:
   - Add `DISCORD_BOT_TOKEN` and `DISCORD_SERVER_ID`

4. **Custom domain**:
   - Site settings → Domain management
   - Add custom domain: `discord.wafer.space`
   - Follow DNS configuration instructions

---

## Search Integration

### Pagefind (Recommended) ⭐

**Why Pagefind?**
- Only 8KB initial load
- Fragmented indexes (loads on demand)
- No server required
- Fast indexing (2496 pages in ~2.4 seconds)
- Built-in UI

**Installation**:
```bash
npm install -g pagefind
```

**Basic Usage**:
```bash
# After generating static site
npx pagefind --site public
```

**Advanced Configuration**:

Create `pagefind.yml`:
```yaml
source: public
bundle_dir: pagefind

glob: "**/*.{html}"

exclude_selectors:
  - "nav"
  - "footer"
  - ".date"

force_language: en
```

**Custom UI**:
```html
<link href="/pagefind/pagefind-ui.css" rel="stylesheet">
<script src="/pagefind/pagefind-ui.js"></script>

<div id="search"></div>

<script>
  new PagefindUI({
    element: "#search",
    showSubResults: true,
    excerptLength: 30
  });
</script>
```

**References**:
- Website: https://pagefind.app/
- Docs: https://pagefind.app/docs/

---

### Alternative: Lunr.js

**Installation**:
```bash
npm install lunr
```

**Pros**:
- Pure JavaScript
- Established ecosystem

**Cons**:
- Larger index size
- Loads entire index upfront
- Slower for large sites

**References**:
- Implementation guide: https://opensource.com/article/21/11/client-side-javascript-search-lunrjs

---

## Automation & Continuous Publishing

### Cron-Based Export (Linux/macOS)

**Create crontab entry**:
```bash
crontab -e
```

**Add schedule**:
```cron
# Export Discord logs daily at 2 AM
0 2 * * * cd /path/to/discord-wafer-space && ./scripts/build.py > /tmp/discord-export.log 2>&1
```

---

### GitHub Actions Schedule

**Trigger types**:
```yaml
on:
  # Daily at noon UTC
  schedule:
    - cron: '0 12 * * *'

  # Manual trigger
  workflow_dispatch:

  # On push to main
  push:
    branches: [main]
```

**Important**: GitHub Actions cron may run ~15 minutes late during high load.

---

### Incremental Updates

Use `--after` flag to only fetch new messages:

```bash
# Get timestamp of last export
LAST_EXPORT=$(date -r exports/server/channel.html +%Y-%m-%dT%H:%M:%S)

# Export only new messages
./DiscordChatExporter.Cli export \
  -t TOKEN \
  -c CHANNEL_ID \
  --after "$LAST_EXPORT"
```

**Automation wrapper**: https://github.com/woranov/discord-export

---

## Hosting Options

### Comparison Table

| Platform | Free Tier | Build Minutes | Bandwidth | Custom Domain | HTTPS | Best For |
|----------|-----------|---------------|-----------|---------------|-------|----------|
| **GitHub Pages** | ✅ Unlimited | N/A (manual) | ✅ Unlimited | ✅ Yes | ✅ Auto | Simple sites |
| **Netlify** | ✅ 300/month | 300 build min | 100 GB/mo | ✅ Yes | ✅ Auto | CI/CD integration |
| **Vercel** | ✅ 100/day | 45 min each | 100 GB/mo | ✅ Yes | ✅ Auto | Complex frameworks |
| **Cloudflare Pages** | ✅ Unlimited | 500 builds/mo | ✅ Unlimited | ✅ Yes | ✅ Auto | High traffic |

---

### GitHub Pages Setup

**Enable Pages**:
1. Repository Settings → Pages
2. Source: Deploy from a branch
3. Branch: `gh-pages` / root

**Custom Domain**:
1. Add CNAME file: `echo "discord.wafer.space" > public/CNAME`
2. Configure DNS: `CNAME discord.wafer.space username.github.io`
3. Enable HTTPS in GitHub settings (automatic)

**References**:
- GitHub Pages docs: https://pages.github.com/

---

### Netlify Setup

**Connect Repository**:
1. https://app.netlify.com/ → New site from Git
2. Choose repository
3. Configure build:
   - Build command: `uv run python scripts/build.py`
   - Publish directory: `public`

**Environment Variables**:
1. Site settings → Environment variables
2. Add `DISCORD_BOT_TOKEN` and `DISCORD_SERVER_ID`

**Custom Domain**:
1. Site settings → Domain management
2. Add domain: `discord.wafer.space`
3. Configure DNS (Netlify provides instructions)

**References**:
- Netlify docs: https://docs.netlify.com/

---

## Privacy & Ethics

### Best Practices Checklist

- [ ] ✅ **Public servers only**: Only archive servers with public invite links
- [ ] ✅ **Get permission**: Explicit consent from server owners
- [ ] ✅ **Add disclosure**: Notify server members that logs are publicly archived
- [ ] ✅ **Respect deletions**: Consider implementing tombstones for deleted messages
- [ ] ✅ **Use bot token**: Never use selfbots (ToS violation)
- [ ] ✅ **GDPR compliance**: Provide data rights for EU users
- [ ] ✅ **Takedown process**: Have a process for handling takedown requests
- [ ] ✅ **Anonymize when needed**: Redact sensitive information

### Recommended Server Notice

Post in your Discord server:

```
📝 Archive Notice

This server's public channels are archived and published at:
https://discord.wafer.space

- Only public channels are archived
- Messages may be visible to non-members
- Deleted messages are removed within 24 hours
- For takedown requests, contact: [email]

By posting in public channels, you consent to archival.
```

### Legal Considerations

- **Discord Terms of Service**: Use authorized bot accounts only
- **GDPR**: EU users have data protection rights
- **DMCA**: Have takedown process for copyrighted content
- **Privacy expectations**: Even "public" Discord servers have different expectations than the open web

### References

- Discord Ethics Guide: https://darcmode.org/ethics-101/
- Discord Privacy Policy: https://discord.com/privacy

---

## Implementation Timeline

### Week 1: MVP
- [ ] Set up Discord bot
- [ ] Install DiscordChatExporter
- [ ] Test exports (3-5 channels)
- [ ] Create basic index.html
- [ ] Deploy to GitHub Pages (manual)

### Week 2: Search & Automation
- [ ] Integrate Pagefind search
- [ ] Create Python index generator
- [ ] Add CSS styling
- [ ] Set up GitHub Actions
- [ ] Test automated deployment

### Week 3: Polish
- [ ] Custom domain setup
- [ ] Add date-based archives
- [ ] Improve navigation
- [ ] Error monitoring
- [ ] Documentation

### Week 4: Enhancements
- [ ] RSS feeds
- [ ] "Latest messages" view
- [ ] Analytics integration
- [ ] Performance optimization

---

## Estimated Effort

- **Simple solution** (DiscordChatExporter + Python script + Pagefind): **20-40 hours**
- **Medium solution** (+ Hugo/Eleventy + improved navigation): **40-80 hours**
- **Advanced solution** (+ custom templates + RSS + features): **80-160 hours**

---

## Key Success Factors

1. ✅ **Start simple**: Get basic HTML exports working first
2. ✅ **Test incrementally**: Verify each component before moving on
3. ✅ **Use Python**: Avoid bash for complex logic (per your preferences)
4. ✅ **Automate early**: Set up GitHub Actions from the start
5. ✅ **Monitor regularly**: Check that automated exports continue working
6. ✅ **Plan for growth**: Consider database storage if expecting millions of messages

---

## Troubleshooting

### Common Issues

**Bot can't read messages**:
- ✅ Enable "Message Content Intent" in bot settings
- ✅ Ensure bot has "Read Message History" permission
- ✅ Bot must be member of server

**Rate limiting errors**:
- ⏱️ Discord limits to 50 requests/second
- ⏱️ DiscordChatExporter handles this automatically
- ⏱️ Large servers may take hours to export

**Search not working**:
- 🔍 Run `npx pagefind --site public` after generating HTML
- 🔍 Ensure pagefind files are deployed with site
- 🔍 Check browser console for errors

**GitHub Actions failing**:
- 🔐 Verify secrets are set correctly
- 🔐 Check token has required permissions
- 📝 Review workflow logs for specific errors

---

## Additional Resources

- **DiscordChatExporter**: https://github.com/Tyrrrz/DiscordChatExporter
- **Pagefind**: https://pagefind.app/
- **GitHub Actions**: https://docs.github.com/en/actions
- **Netlify Docs**: https://docs.netlify.com/
- **Hugo**: https://gohugo.io/
- **Eleventy**: https://www.11ty.dev/

---

## Next Steps

To get started:

1. **Set up Discord bot** (15 minutes)
2. **Export test channel** (10 minutes)
3. **Create basic index** (1-2 hours)
4. **Add Pagefind** (30 minutes)
5. **Deploy to GitHub Pages** (30 minutes)

**Total to MVP**: ~4-5 hours of work

Once MVP is working, iterate on navigation, styling, and automation.

Good luck with discord.wafer.space! 🚀
