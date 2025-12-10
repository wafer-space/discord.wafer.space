#!/usr/bin/env python3
"""Merge state.json during git rebase conflicts.

When two workflow runs both modify state.json, git can't auto-merge because
the same JSON lines are changed. However, since each channel's state is
independent (just timestamps), we can safely merge by keeping the newer
timestamp for each channel/thread.

Usage:
    uv run python scripts/merge_state.py

This script:
1. Reads the conflicted state.json with conflict markers
2. Extracts both versions (ours and theirs) from git index
3. Merges by keeping the newer timestamp for each entry
4. Writes the merged result
5. Stages the file for git to continue the rebase
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def parse_timestamp(ts: str | None) -> datetime | None:
    """Parse ISO timestamp string to datetime."""
    if not ts:
        return None
    try:
        # Handle both +00:00 and Z formats
        ts = ts.replace("Z", "+00:00")
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def merge_thread_data(ours: dict, theirs: dict) -> dict:
    """Merge thread data, keeping newer timestamps."""
    result = {}
    all_keys = set(ours.keys()) | set(theirs.keys())

    for key in all_keys:
        our_data = ours.get(key, {})
        their_data = theirs.get(key, {})

        if not our_data:
            result[key] = their_data
        elif not their_data:
            result[key] = our_data
        else:
            # Both have data - compare timestamps
            our_ts = parse_timestamp(our_data.get("last_export"))
            their_ts = parse_timestamp(their_data.get("last_export"))

            if our_ts is None:
                result[key] = their_data
            elif their_ts is None:
                result[key] = our_data
            elif their_ts > our_ts:
                result[key] = their_data
            else:
                result[key] = our_data

    return result


def merge_forum_data(ours: dict, theirs: dict) -> dict:
    """Merge forum data, recursively merging threads."""
    result = {}
    all_keys = set(ours.keys()) | set(theirs.keys())

    for key in all_keys:
        our_data = ours.get(key, {})
        their_data = theirs.get(key, {})

        if not our_data:
            result[key] = their_data
        elif not their_data:
            result[key] = our_data
        else:
            # Both have data - merge nested structures
            result[key] = {}
            if "threads" in our_data or "threads" in their_data:
                result[key]["threads"] = merge_thread_data(
                    our_data.get("threads", {}), their_data.get("threads", {})
                )
            if "last_index_generation" in our_data or "last_index_generation" in their_data:
                our_ts = parse_timestamp(our_data.get("last_index_generation"))
                their_ts = parse_timestamp(their_data.get("last_index_generation"))
                if their_ts and (not our_ts or their_ts > our_ts):
                    result[key]["last_index_generation"] = their_data.get("last_index_generation")
                elif our_ts:
                    result[key]["last_index_generation"] = our_data.get("last_index_generation")

    return result


def merge_channel_data(ours: dict, theirs: dict) -> dict:
    """Merge channel data, keeping newer timestamps."""
    result = {}
    all_keys = set(ours.keys()) | set(theirs.keys())

    for key in all_keys:
        our_data = ours.get(key, {})
        their_data = theirs.get(key, {})

        if not our_data:
            result[key] = their_data
        elif not their_data:
            result[key] = our_data
        else:
            # Both have data - compare timestamps
            our_ts = parse_timestamp(our_data.get("last_export"))
            their_ts = parse_timestamp(their_data.get("last_export"))

            if our_ts is None:
                result[key] = their_data
            elif their_ts is None:
                result[key] = our_data
            elif their_ts > our_ts:
                result[key] = their_data
            else:
                result[key] = our_data

    return result


def merge_server_data(ours: dict, theirs: dict) -> dict:
    """Merge server data, handling forums and channels."""
    result = {}

    # Merge forums
    if "forums" in ours or "forums" in theirs:
        result["forums"] = merge_forum_data(ours.get("forums", {}), theirs.get("forums", {}))

    # Merge channels
    if "channels" in ours or "channels" in theirs:
        result["channels"] = merge_channel_data(
            ours.get("channels", {}), theirs.get("channels", {})
        )

    return result


def merge_states(ours: dict, theirs: dict) -> dict:
    """Merge two state.json structures."""
    result = {}
    all_servers = set(ours.keys()) | set(theirs.keys())

    for server in all_servers:
        our_data = ours.get(server, {})
        their_data = theirs.get(server, {})

        if not our_data:
            result[server] = their_data
        elif not their_data:
            result[server] = our_data
        else:
            result[server] = merge_server_data(our_data, their_data)

    return result


def get_versions_from_git() -> tuple[dict, dict]:
    """Get ours and theirs versions directly from git."""
    # During a rebase:
    # - :2:state.json is "ours" (the branch we're rebasing onto - remote)
    # - :3:state.json is "theirs" (the commit being rebased - our changes)

    try:
        ours_result = subprocess.run(
            ["git", "show", ":2:state.json"],
            capture_output=True,
            text=True,
            check=True,
        )
        ours = json.loads(ours_result.stdout)
    except subprocess.CalledProcessError:
        print("Warning: Could not get :2:state.json, using empty dict")
        ours = {}

    try:
        theirs_result = subprocess.run(
            ["git", "show", ":3:state.json"],
            capture_output=True,
            text=True,
            check=True,
        )
        theirs = json.loads(theirs_result.stdout)
    except subprocess.CalledProcessError:
        print("Warning: Could not get :3:state.json, using empty dict")
        theirs = {}

    return ours, theirs


def main() -> int:
    """Main entry point."""
    state_file = Path("state.json")

    if not state_file.exists():
        print("Error: state.json not found")
        return 1

    content = state_file.read_text()

    # Check if there's actually a conflict
    if "<<<<<<<" not in content:
        print("No conflict markers found in state.json, nothing to merge")
        return 0

    print("Found conflict in state.json, attempting automatic merge...")

    # Get both versions from git
    ours, theirs = get_versions_from_git()

    if not ours and not theirs:
        print("Error: Could not extract either version from git")
        return 1

    # Merge the states
    merged = merge_states(ours, theirs)

    # Write the merged result
    state_file.write_text(json.dumps(merged, indent=2) + "\n")

    # Stage the resolved file
    subprocess.run(["git", "add", "state.json"], check=True)

    print("Successfully merged state.json")
    print(f"  - Ours had {count_entries(ours)} entries")
    print(f"  - Theirs had {count_entries(theirs)} entries")
    print(f"  - Merged has {count_entries(merged)} entries")

    return 0


def count_entries(state: dict) -> int:
    """Count total entries (channels + threads) in state."""
    count = 0
    for server_data in state.values():
        if isinstance(server_data, dict):
            if "channels" in server_data:
                count += len(server_data["channels"])
            if "forums" in server_data:
                for forum_data in server_data["forums"].values():
                    if isinstance(forum_data, dict) and "threads" in forum_data:
                        count += len(forum_data["threads"])
    return count


if __name__ == "__main__":
    sys.exit(main())
