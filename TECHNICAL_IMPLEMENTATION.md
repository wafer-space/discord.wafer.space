# DiscordChatExporter - Technical Implementation Details

Research conducted: 2025-11-11

---

## Overview

**DiscordChatExporter** is a mature, open-source application written in **C#/.NET** for exporting Discord chat history to multiple formats. It consists of both a command-line interface (CLI) and a graphical user interface (GUI).

**Repository**: https://github.com/Tyrrrz/DiscordChatExporter
**Stars**: 9,600+
**License**: MIT
**Author**: Tyrrrz (Oleksii Holub)
**Commits**: 1,375+
**Status**: Active maintenance mode

---

## Technology Stack

### Core Technologies

**Programming Language**: C# (91.0% of codebase)
**Framework**: .NET 9.0
**Language Version**: C# preview (latest features)
**Runtime**: .NET Core (cross-platform)

### Architecture

The project uses a modular .NET solution structure with 4 main components:

1. **DiscordChatExporter.Core** - Core export functionality and Discord API client
2. **DiscordChatExporter.Cli** - Command-line interface
3. **DiscordChatExporter.Gui** - Desktop GUI (Windows WPF)
4. **DiscordChatExporter.Cli.Tests** - Test suite

---

## Project Structure

```
DiscordChatExporter/
├── DiscordChatExporter.Core/           # Core library
│   ├── Discord/                        # Discord API client
│   │   ├── DiscordClient.cs           # HTTP client for Discord API
│   │   ├── Data/                       # Data models
│   │   │   ├── Message.cs
│   │   │   ├── Channel.cs
│   │   │   ├── Guild.cs
│   │   │   └── Embeds/
│   │   └── Dump/                       # Data dump handling
│   ├── Exporting/                      # Export engine
│   │   ├── ChannelExporter.cs
│   │   ├── MessageExporter.cs
│   │   ├── HtmlMessageWriter.cs
│   │   ├── JsonMessageWriter.cs
│   │   ├── PlainTextMessageWriter.cs
│   │   ├── CsvMessageWriter.cs
│   │   ├── PreambleTemplate.cshtml     # HTML header (1,040 lines)
│   │   ├── MessageGroupTemplate.cshtml # Message rendering (668 lines)
│   │   ├── PostambleTemplate.cshtml    # HTML footer (24 lines)
│   │   ├── HtmlMarkdownVisitor.cs      # Markdown to HTML
│   │   └── Partitioning/               # File splitting logic
│   ├── Markdown/                       # Markdown parser
│   └── Utils/                          # Utilities
├── DiscordChatExporter.Cli/            # CLI application
├── DiscordChatExporter.Gui/            # GUI application (WPF)
├── DiscordChatExporter.Cli.Tests/      # Tests
├── DiscordChatExporter.sln             # Solution file
├── Directory.Build.props               # Shared build config
├── DiscordChatExporter.Cli.dockerfile  # Docker image
└── docker-entrypoint.sh                # Docker startup script
```

---

## Key Dependencies

### Core Library Dependencies

From `DiscordChatExporter.Core.csproj`:

| Package | Version | Purpose |
|---------|---------|---------|
| **AsyncKeyedLock** | 7.1.7 | Async locking primitives for rate limiting |
| **Gress** | 2.1.1 | Progress reporting |
| **JsonExtensions** | 1.2.0 | JSON utilities |
| **Polly** | 8.6.4 | Resilience and transient fault handling |
| **RazorBlade** | 0.10.0 | Razor template compilation |
| **Superpower** | 3.1.0 | Text parsing combinators |
| **WebMarkupMin.Core** | 2.19.1 | HTML/CSS minification |
| **YoutubeExplode** | 6.5.6 | YouTube embed handling |

### CLI Dependencies

From `DiscordChatExporter.Cli.csproj`:

| Package | Version | Purpose |
|---------|---------|---------|
| **CliFx** | 2.3.6 | Command-line framework |
| **Spectre.Console** | 0.53.0 | Rich terminal UI (progress bars, colors) |
| **Gress** | 2.1.1 | Progress reporting |
| **Deorcify** | 1.1.0 | Build tool |
| **Microsoft.NET.ILLink.Tasks** | 9.0.10 | IL trimming for smaller binaries |

---

## HTML Export Implementation

### Templating Engine: Razor

DiscordChatExporter uses **RazorBlade** for HTML generation - a lightweight Razor template engine that doesn't require ASP.NET.

**Key Templates** (`.cshtml` files):

1. **PreambleTemplate.cshtml** (1,040 lines)
   - HTML document structure (`<!DOCTYPE>`, `<head>`, `<body>`)
   - CSS styling (embedded, ~800+ lines)
   - Discord font loading (gg sans family)
   - Theme support (dark/light)
   - JavaScript for interactivity
   - SVG icon definitions

2. **MessageGroupTemplate.cshtml** (668 lines)
   - Message rendering logic
   - User avatars and names
   - Message content with markdown
   - Embeds (images, videos, links)
   - Reactions
   - Attachments
   - System notifications
   - Thread messages
   - Message replies

3. **PostambleTemplate.cshtml** (24 lines)
   - Closing HTML tags
   - Export metadata footer

### Template Example Structure

```csharp
@using System
@using System.Threading.Tasks
@inherits RazorBlade.HtmlTemplate

@functions {
    public required ExportContext Context { get; init; }
    public required string ThemeName { get; init; }
}

<!DOCTYPE html>
<html lang="en">
<head>
    <title>@Context.Request.Guild.Name - @Context.Request.Channel.Name</title>
    <style>
        /* Embedded CSS with Discord-like styling */
    </style>
</head>
<body>
    <!-- Message content rendered here -->
</body>
</html>
```

### Markdown Processing

**HtmlMarkdownVisitor.cs** converts Discord markdown to HTML:
- Bold, italic, strikethrough
- Code blocks with syntax highlighting
- Inline code
- Block quotes
- Spoilers
- User/channel/role mentions
- Custom emoji
- Timestamps

**PlainTextMarkdownVisitor.cs** strips markdown for plain text export.

---

## Discord API Integration

### API Client: DiscordClient.cs

**Base URL**: `https://discord.com/api/v10/`

**Authentication**:
```csharp
// Bot token
request.Headers.TryAddWithoutValidation(
    "Authorization",
    $"Bot {token}"
);

// User token
request.Headers.TryAddWithoutValidation(
    "Authorization",
    token
);
```

**Key Features**:
- HTTP/2 support
- Automatic rate limit handling (using Polly)
- Resilience patterns (retry, circuit breaker)
- Progress reporting (using Gress)
- Async/await throughout
- Cancellation token support

### Rate Limiting

Uses **Polly** resilience library for:
- Exponential backoff on 429 (Too Many Requests)
- Retry on transient errors (500, 502, 503, 504)
- Respect Discord's rate limit headers
- Automatic throttling

```csharp
// Rate limit preference enum
public enum RateLimitPreference
{
    RespectAll,      // Respect all rate limits
    IgnoreBackoff    // Ignore backoff suggestions
}
```

### Data Models

Strongly-typed C# models for Discord entities:
- `Message` - Message content, author, timestamp, embeds
- `Channel` - Channel info, type, permissions
- `Guild` - Server info, name, icon
- `User` - User profile, avatar, discriminator
- `Member` - Server-specific user data (nickname, roles)
- `Embed` - Rich embeds (images, videos, fields)
- `Attachment` - File attachments
- `Reaction` - Message reactions
- `Sticker` - Discord stickers

---

## Export Formats

### 1. HTML Export

**Writer**: `HtmlMessageWriter.cs`

**Process**:
1. Render `PreambleTemplate` (header, CSS, fonts)
2. Group messages by author/time
3. For each group, render `MessageGroupTemplate`
4. Render `PostambleTemplate` (footer)
5. Minify HTML (using WebMarkupMin)
6. Write to file

**Features**:
- Self-contained (embedded CSS, fonts via CDN)
- Dark/light themes
- Discord-like appearance
- Offline viewable (with `--media` flag)
- Responsive design
- Syntax highlighting for code blocks

### 2. JSON Export

**Writer**: `JsonMessageWriter.cs`

**Format**: Line-delimited JSON (JSONL)
```json
{
  "id": "1234567890",
  "type": "Default",
  "timestamp": "2024-01-01T12:00:00+00:00",
  "content": "Hello world",
  "author": {
    "id": "9876543210",
    "name": "Username",
    "discriminator": "1234",
    "isBot": false
  },
  "attachments": [],
  "embeds": [],
  "reactions": []
}
```

**Features**:
- Complete metadata preservation
- Easy parsing
- Compact format
- Suitable for data analysis

### 3. Plain Text Export

**Writer**: `PlainTextMessageWriter.cs`

**Format**:
```
[2024-01-01 12:00:00 PM] Username#1234
Hello world

[2024-01-01 12:01:15 PM] AnotherUser#5678
This is a reply
```

**Features**:
- Minimal file size
- Human-readable
- Easy to search with grep
- Markdown stripped

### 4. CSV Export

**Writer**: `CsvMessageWriter.cs`

**Columns**:
- Author ID
- Author
- Date
- Content
- Attachments
- Reactions

**Features**:
- Spreadsheet-compatible
- Easy data analysis in Excel/Sheets
- UTF-8 encoding

---

## Export Engine

### ChannelExporter.cs

Main orchestrator for channel exports:

**Process Flow**:
```
1. Initialize ExportContext
   ├─ Load guild/channel metadata
   ├─ Load members (for nickname resolution)
   └─ Create message writer (HTML/JSON/TXT/CSV)

2. Fetch Messages from Discord API
   ├─ Paginate through message history
   ├─ Apply date filters (--after, --before)
   ├─ Apply content filters (--filter)
   └─ Handle rate limits

3. Process Messages
   ├─ Group messages by author/time
   ├─ Download media assets (if --media)
   ├─ Resolve mentions
   └─ Parse markdown

4. Write to File
   ├─ Apply partitioning (if -p)
   ├─ Render templates (HTML)
   ├─ Serialize data (JSON/CSV)
   └─ Minify output (HTML)

5. Progress Reporting
   └─ Real-time progress bar (Spectre.Console)
```

### Partitioning

**Partitioner Types**:
- `MessageCountPartitioner` - Split by message count
- `FileSizePartitioner` - Split by file size (MB)
- `NullPartitioner` - No partitioning (default)

**Implementation**: Dynamically creates multiple output files with sequential numbering.

---

## Media Asset Handling

### ExportAssetDownloader.cs

**Features**:
- Downloads referenced media (avatars, attachments, images)
- Reuse previously downloaded assets (`--reuse-media`)
- Custom media directory (`--media-dir`)
- Asset URL resolution (Discord CDN → local paths)
- Concurrent downloads with rate limiting

**Asset Types**:
- User avatars
- Guild icons
- Channel icons
- Attachments (images, videos, files)
- Embed images/thumbnails
- Emoji images
- Stickers

**URL Rewriting**:
```
Discord CDN URL:
https://cdn.discordapp.com/attachments/123/456/image.png

Local URL (with --media):
./media/attachments/123/456/image.png
```

---

## CLI Framework: CliFx

Uses **CliFx** for command-line parsing and execution.

**Features**:
- Declarative command definition (attributes)
- Automatic help generation
- Type-safe parameter binding
- Progress reporting integration
- Error handling

**Command Structure**:
```csharp
[Command("export")]
public class ExportCommand : ICommand
{
    [CommandOption("token", 't', IsRequired = true)]
    public string Token { get; init; }

    [CommandOption("channel", 'c', IsRequired = true)]
    public Snowflake ChannelId { get; init; }

    // ... more options

    public async ValueTask ExecuteAsync(IConsole console)
    {
        // Export logic
    }
}
```

---

## GUI Implementation (Windows Only)

**Technology**: WPF (Windows Presentation Foundation)
**XAML**: Declarative UI
**MVVM Pattern**: Model-View-ViewModel architecture

**Key Features**:
- Drag-and-drop channel selection
- Visual export configuration
- Real-time progress display
- Settings persistence
- Token management

**Note**: GUI is Windows-only. CLI works on all platforms.

---

## Build Configuration

### Directory.Build.props

Shared build properties across all projects:
```xml
<PropertyGroup>
  <TargetFramework>net9.0</TargetFramework>
  <Version>999.9.9-dev</Version>
  <Company>Tyrrrz</Company>
  <Copyright>Copyright (c) Oleksii Holub</Copyright>
  <LangVersion>preview</LangVersion>
  <Nullable>enable</Nullable>
  <TreatWarningsAsErrors>true</TreatWarningsAsErrors>
</PropertyGroup>
```

**Key Settings**:
- Target: .NET 9.0
- C# Language: Preview (latest features)
- Nullable reference types: Enabled
- Warnings as errors: Yes (strict)

### Publishing

**CLI Publishing**:
```xml
<PropertyGroup>
  <PublishTrimmed>true</PublishTrimmed>
  <CopyOutputSymbolsToPublishDirectory>false</CopyOutputSymbolsToPublishDirectory>
</PropertyGroup>
```

**Features**:
- IL trimming (smaller binaries)
- Single-file deployment
- Platform-specific builds (win-x64, linux-x64, osx-x64, osx-arm64)

---

## Docker Implementation

### Dockerfile

**Base Image**: `mcr.microsoft.com/dotnet/runtime:9.0` (inferred from .NET 9.0)

**Multi-stage build**:
1. Build stage: Compile application
2. Runtime stage: Create minimal runtime image

**Platforms**:
- `linux/amd64`
- `linux/arm64`

### docker-entrypoint.sh

Wrapper script that:
- Sets up environment
- Handles volume permissions
- Executes CLI with passed arguments

**Usage**:
```bash
docker run --rm \
  -v /path:/out \
  tyrrrz/discordchatexporter:stable \
  export -t TOKEN -c CHANNEL_ID
```

---

## Code Quality

### Static Analysis

- **CSharpier**: Code formatting (automatic)
- **Nullable reference types**: Compile-time null safety
- **Warnings as errors**: Zero-tolerance for warnings

### Testing

**Test Framework**: xUnit (inferred from test project)
**Test Project**: `DiscordChatExporter.Cli.Tests`

**Test Coverage**: CLI command integration tests

---

## Performance Optimizations

1. **Async/Await Throughout**: Non-blocking I/O
2. **HTTP/2**: Multiplexed connections
3. **Streaming Responses**: Low memory footprint
4. **IL Trimming**: Smaller binary sizes
5. **Progress Reporting**: Non-blocking UI updates
6. **Concurrent Downloads**: Parallel asset fetching (with rate limiting)
7. **HTML Minification**: Smaller output files

---

## Example: HTML Export Flow

```
User Command:
./DiscordChatExporter.Cli export -t TOKEN -c CHANNEL_ID -f HtmlDark

↓

1. CLI (CliFx)
   └─ Parse arguments → ExportCommand

2. ExportCommand.ExecuteAsync()
   └─ Create ExportRequest

3. ChannelExporter.ExportAsync()
   ├─ Initialize DiscordClient
   ├─ Fetch channel metadata
   ├─ Fetch guild metadata
   ├─ Fetch members (for @mentions)
   └─ Create HtmlMessageWriter

4. DiscordClient.GetMessagesAsync()
   ├─ HTTP GET /channels/{id}/messages
   ├─ Apply filters (date, content)
   ├─ Handle pagination
   └─ Handle rate limits (Polly)

5. MessageExporter.ExportAsync()
   ├─ Group messages by author/time
   ├─ Download assets (if --media)
   └─ Write message groups

6. HtmlMessageWriter.WriteAsync()
   ├─ Render PreambleTemplate.cshtml
   ├─ For each group:
   │   ├─ Render MessageGroupTemplate.cshtml
   │   ├─ Convert markdown → HTML
   │   └─ Resolve asset URLs
   ├─ Render PostambleTemplate.cshtml
   └─ Minify HTML (WebMarkupMin)

7. Write to disk
   └─ Output file: channel.html

8. Display completion
   └─ Spectre.Console progress bar
```

---

## Discord API Endpoints Used

Based on `DiscordClient.cs`:

- `GET /users/@me` - Get current user (token validation)
- `GET /users/@me/guilds` - List accessible guilds
- `GET /users/@me/channels` - List DM channels
- `GET /guilds/{guild.id}` - Get guild info
- `GET /guilds/{guild.id}/channels` - List guild channels
- `GET /guilds/{guild.id}/members` - Get guild members
- `GET /guilds/{guild.id}/roles` - Get guild roles
- `GET /channels/{channel.id}` - Get channel info
- `GET /channels/{channel.id}/messages` - Get messages (paginated)
- `GET /channels/{channel.id}/threads/archived/public` - Get archived threads

**Rate Limits**: Handled automatically via Polly resilience policies.

---

## Extending DiscordChatExporter

### Adding a New Export Format

1. Create new writer class implementing `MessageWriter.cs`
2. Implement `WriteMessageAsync()` method
3. Add format to `ExportFormat.cs` enum
4. Register in `ChannelExporter.cs` factory

**Example Skeleton**:
```csharp
public class CustomMessageWriter : MessageWriter
{
    public override async ValueTask WritePreambleAsync(
        CancellationToken cancellationToken = default)
    {
        // Write header
    }

    public override async ValueTask WriteMessageAsync(
        Message message,
        CancellationToken cancellationToken = default)
    {
        // Write message in custom format
    }

    public override async ValueTask WritePostambleAsync(
        CancellationToken cancellationToken = default)
    {
        // Write footer
    }
}
```

### Custom Markdown Rendering

Extend `HtmlMarkdownVisitor.cs` or create custom visitor implementing markdown parsing.

---

## Published Examples

### Discord Log Archive Websites

While DiscordChatExporter is widely used, publicly published Discord log websites are relatively rare due to privacy concerns. However, some examples exist:

**1. Archive.org Archives**
- Some users upload DiscordChatExporter exports to Archive.org
- Tagged with `DiscordChatExporter`
- Often from public/open-source project servers

**2. Discord Data Viewers**
- **Discord Explorer** (https://discord-explorer.netlify.app/) - View exported channels
- **Discord Data Package Explorer** (https://ddpe.netlify.app/) - View GDPR exports
- These are viewers for already-exported data, not live log websites

**3. Research/Investigation Usage**
- **Bellingcat** uses DiscordChatExporter for OSINT investigations
- Documented in their toolkit: https://bellingcat.gitbook.io/toolkit/more/all-tools/discord-chat-exporter

**4. Project Documentation Archives**
- Some open-source projects archive public Discord support channels
- Usually hosted on project websites or GitHub Pages
- Often require authentication or are behind access controls

### Why Few Public Examples?

**Privacy Concerns**:
- Even "public" Discord servers have privacy expectations
- User consent issues
- GDPR compliance
- Discord ToS restrictions on data sharing

**Technical Barriers**:
- No built-in index/navigation (each channel = separate file)
- No built-in search (requires integration like Pagefind)
- Manual effort to organize and publish

**Recommendation**: For public Discord log websites, follow the architecture outlined in `WEB_PUBLISHING_GUIDE.md` (DiscordChatExporter + custom scripting + search integration).

---

## Alternatives and Related Tools

### Other Discord Export Tools (for comparison)

**Discord History Tracker** (Python/SQLite):
- Desktop app with database storage
- Uses similar Discord API approach
- Different architecture (database-first vs file-first)

**discord-dl** (Go):
- Similar functionality
- Built-in web server for viewing
- Less mature than DiscordChatExporter

**chat-exporter** (Python/discord.py):
- Library for Discord bots
- HTML-only export
- Less feature-complete

**Why DiscordChatExporter is Popular**:
1. Most mature and feature-complete
2. Active maintenance
3. Excellent documentation
4. Multiple export formats
5. Cross-platform
6. Docker support
7. Professional HTML output

---

## Technical Strengths

1. ✅ **Modern C#/.NET**: Latest language features, cross-platform
2. ✅ **Modular Architecture**: Clean separation of concerns
3. ✅ **Robust API Client**: Proper rate limiting, error handling
4. ✅ **Beautiful HTML Output**: Discord-like styling via Razor templates
5. ✅ **Multiple Formats**: HTML, JSON, CSV, TXT
6. ✅ **Progress Reporting**: Real-time feedback via Spectre.Console
7. ✅ **Docker Support**: Easy deployment
8. ✅ **IL Trimming**: Small, self-contained binaries
9. ✅ **Null Safety**: Compile-time null checking
10. ✅ **Comprehensive**: Handles all Discord features (embeds, reactions, threads)

---

## Technical Limitations

1. ❌ **No Incremental Updates**: Full re-export each time (but can use `--after`)
2. ❌ **No Built-in Index**: Requires custom scripting for navigation
3. ❌ **No Built-in Search**: Need to integrate external tools (Pagefind, Lunr.js)
4. ❌ **GUI Windows-Only**: CLI works everywhere, but GUI is WPF
5. ❌ **No Real-time Monitoring**: Batch exports only (not continuous)
6. ❌ **CDN Dependency**: HTML exports load fonts from CDN (unless `--media`)
7. ⚠️ **Large HTML Files**: Can become large for long channels (use partitioning)

---

## Development Setup

### Prerequisites
- .NET 9.0 SDK
- Visual Studio 2022 or Rider (optional)
- Git

### Building from Source

```bash
git clone https://github.com/Tyrrrz/DiscordChatExporter.git
cd DiscordChatExporter

# Restore dependencies
dotnet restore

# Build all projects
dotnet build

# Run CLI
dotnet run --project DiscordChatExporter.Cli -- --help

# Run tests
dotnet test

# Publish (self-contained)
dotnet publish DiscordChatExporter.Cli \
  -c Release \
  -r linux-x64 \
  --self-contained \
  -p:PublishSingleFile=true
```

---

## Summary

**DiscordChatExporter** is a professionally-built C#/.NET application that:

- Uses Discord API v10 for data retrieval
- Employs Razor templates (RazorBlade) for HTML generation
- Implements robust rate limiting via Polly
- Provides CLI via CliFx and GUI via WPF
- Supports 4 export formats: HTML, JSON, CSV, TXT
- Handles all Discord features: markdown, embeds, reactions, threads
- Includes Docker support for containerized deployments
- Uses modern C# features: nullable reference types, async/await
- Generates self-contained, offline-viewable HTML exports

**For Web Publishing**: The HTML exports are static files suitable for web hosting, but require additional tooling (index generation, search integration) to create a full public log website similar to IRC logging systems. See `WEB_PUBLISHING_GUIDE.md` for implementation details.

**Technical Excellence**: The codebase demonstrates professional software engineering practices with clean architecture, comprehensive error handling, and production-ready quality.
