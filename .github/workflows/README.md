# GitHub Actions Workflows

## export-and-publish.yml

This workflow automates the Discord channel export and GitHub Pages publishing process.

### Triggers

The workflow runs on three different triggers:

1. **Schedule (Hourly)**: `0 * * * *` - Runs automatically every hour at the top of the hour
2. **Manual Trigger**: `workflow_dispatch` - Can be manually triggered from the Actions tab
3. **Push to Testing Branch**: Triggers on pushes to `feature/discord-wafer-space` for testing

### Permissions

The workflow requires the following permissions:
- `contents: write` - To commit state.json back to the repository
- `pages: write` - To deploy to GitHub Pages
- `id-token: write` - For GitHub Pages deployment

### Workflow Steps

#### 1. Checkout repository
- Uses `actions/checkout@v4`
- Fetches full git history (`fetch-depth: 0`) needed for state.json tracking

#### 2. Set up Python
- Uses `actions/setup-python@v5`
- Installs Python 3.11 (required for the scripts)

#### 3. Install uv
- Installs the `uv` package manager via pip
- Used for all subsequent Python package management

#### 4. Install Python dependencies
- Runs `uv pip install --system -r requirements.txt`
- Installs jinja2, toml, python-dateutil

#### 5. Cache DiscordChatExporter
- Uses `actions/cache@v4`
- Caches the DiscordChatExporter.Cli binary to speed up subsequent runs
- Cache key: `dce-{os}-latest`

#### 6. Download DiscordChatExporter
- Only runs if cache miss (`cache-hit != 'true'`)
- Downloads latest Linux x64 binary from GitHub releases
- Unzips and makes executable

#### 7. Run export script
- Sets `DISCORD_BOT_TOKEN` from GitHub Secrets
- Executes `scripts/export_channels.py`
- Uses `continue-on-error: true` to allow workflow to proceed even if export fails
- Saves outcome in `steps.export.outcome`

#### 8. Run navigation generator
- Executes `scripts/generate_navigation.py`
- Generates site index, server indexes, and channel indexes
- Uses `continue-on-error: true` to allow proceeding even if generation fails
- Runs regardless of export step outcome

#### 9. Check for changes
- Compares `public/` and `state.json` against last commit
- Sets `has_changes` output variable (true/false)
- Uses `2>/dev/null` to suppress errors if files don't exist yet

#### 10. Commit state.json to main
- Only runs if changes were detected
- Commits updated `state.json` with export timestamps
- Pushes to main branch
- Uses `continue-on-error: true` to prevent deployment failure on commit issues

#### 11. Deploy to GitHub Pages
- Only runs if changes were detected
- Uses `peaceiris/actions-gh-pages@v4`
- Publishes `./public` directory to `gh-pages` branch
- Uses `continue-on-error: true` for resilience

#### 12. Report summary
- Always runs (`if: always()`)
- Writes summary to GitHub Actions step summary
- Includes job status, step outcomes, change detection status, and timestamp

### Error Handling

The workflow uses `continue-on-error: true` on critical steps to ensure:
- Partial failures don't block the entire workflow
- Navigation can still be generated even if export partially fails
- Deployment can proceed even if state commit fails
- Summary is always reported

### Environment Variables

Required secrets (set in repository settings):
- `DISCORD_BOT_TOKEN` - Discord bot token with Message Content Intent enabled

Automatically provided:
- `GITHUB_TOKEN` - GitHub token for Pages deployment (auto-injected)

### Outputs

The workflow produces:
1. **state.json** - Committed to main branch with last export timestamps
2. **public/** - Deployed to gh-pages branch, served via GitHub Pages
3. **Step Summary** - Visible in Actions tab after each run

### Rate Limits

- **GitHub Actions**: Free tier includes 2,000 minutes/month for public repos
- **Hourly schedule**: ~730 runs/month
- **Estimated runtime**: 5-15 minutes per run
- **Monthly usage**: ~3,650-10,950 minutes (exceeds free tier for private repos)
- **Recommendation**: For private repos, reduce to every 2-4 hours

### Testing

To test the workflow:

1. **Manual trigger**: Go to Actions → Export and Publish Discord Logs → Run workflow
2. **Push to feature branch**: Push to `feature/discord-wafer-space`
3. **Check logs**: View detailed logs in Actions tab
4. **Verify deployment**: Check gh-pages branch and GitHub Pages URL

### Troubleshooting

**Workflow fails on "Run export script"**:
- Verify `DISCORD_BOT_TOKEN` secret is set
- Check bot has Message Content Intent enabled
- Ensure bot is in the server and has channel access

**No changes detected**:
- Normal if no new messages since last export
- Incremental exports use `state.json` to track last export time

**Deployment fails**:
- Verify GitHub Pages is enabled
- Check `gh-pages` branch exists (created on first successful run)
- Ensure repository settings allow Actions to deploy Pages

**State commit fails**:
- May occur on concurrent runs or branch protection
- Not critical - state will be updated on next successful run
