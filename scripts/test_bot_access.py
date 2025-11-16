#!/usr/bin/env python3
"""Test Discord bot access and permissions."""

import os
import subprocess
import sys


def test_bot_token():
    """Test if bot token is set and can access Discord."""
    token = os.environ.get("DISCORD_BOT_TOKEN")

    if not token:
        print("❌ ERROR: DISCORD_BOT_TOKEN environment variable not set")
        print("\nSet it with:")
        print("  export DISCORD_BOT_TOKEN='your_token_here'")
        return False

    print(f"✓ Bot token found (length: {len(token)})")

    # Test token format
    parts = token.split(".")
    if len(parts) != 3:
        print(
            f"❌ ERROR: Token format incorrect. Expected 3 parts separated by '.', got {len(parts)}"
        )
        print("   Format should be: base64.hmac.signature")
        return False

    print("✓ Token format looks correct (3 parts)")

    # Test if we can list guilds
    print("\nTesting Discord API access...")
    try:
        result = subprocess.run(
            ["bin/discord-exporter/DiscordChatExporter.Cli", "guilds", "-t", token],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            print("❌ ERROR: Cannot access Discord API")
            print(f"\nOutput: {result.stdout}")
            print(f"Error: {result.stderr}")
            return False

        guilds = [line for line in result.stdout.strip().split("\n") if line.strip()]
        print("✓ Successfully accessed Discord API")
        print(f"\nFound {len(guilds)} servers:")
        for guild in guilds:
            print(f"  {guild}")

        return True

    except subprocess.TimeoutExpired:
        print("❌ ERROR: Request timed out")
        return False
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def test_server_access(guild_id):
    """Test if bot can access specific server."""
    token = os.environ.get("DISCORD_BOT_TOKEN")

    print(f"\nTesting access to server {guild_id}...")
    try:
        result = subprocess.run(
            [
                "bin/discord-exporter/DiscordChatExporter.Cli",
                "channels",
                "-t",
                token,
                "-g",
                guild_id,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            print(f"❌ ERROR: Cannot access server {guild_id}")
            print(f"\nOutput: {result.stdout}")
            print(f"Error: {result.stderr}")
            print("\nPossible issues:")
            print("  1. Bot not invited to this server")
            print("  2. Bot lacks required permissions")
            print("  3. Server ID is incorrect")
            return False

        channels = [line for line in result.stdout.strip().split("\n") if line.strip()]
        print("✓ Successfully accessed server")
        print(f"\nFound {len(channels)} channels:")
        for channel in channels[:10]:  # Show first 10
            print(f"  {channel}")
        if len(channels) > 10:
            print(f"  ... and {len(channels) - 10} more")

        return True

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False


def main():
    """Run all diagnostics."""
    print("Discord Bot Access Diagnostics")
    print("=" * 60)

    # Test bot token
    if not test_bot_token():
        sys.exit(1)

    # Test server access
    guild_id = "1361349522684510449"
    if not test_server_access(guild_id):
        print("\n" + "=" * 60)
        print("DIAGNOSIS FAILED")
        print("\nTo fix:")
        print("1. Verify your bot token is correct")
        print("2. Make sure the bot is invited to the server")
        print("3. Ensure these permissions are enabled:")
        print("   - View Channels")
        print("   - Read Message History")
        print("4. Check that Message Content Intent is enabled in")
        print("   the Discord Developer Portal")
        sys.exit(1)

    print("\n" + "=" * 60)
    print("✓ ALL TESTS PASSED")
    print("\nYour bot is properly configured and can access the server!")


if __name__ == "__main__":
    main()
