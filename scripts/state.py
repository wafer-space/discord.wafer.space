"""State management for tracking export progress."""

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast


@dataclass
class ThreadInfo:
    """Thread metadata for state tracking."""

    thread_id: str
    thread_name: str
    thread_title: str
    last_message_id: str | None = None
    archived: bool = False


class StateManager:
    """Manages export state tracking."""

    def __init__(self, state_path: str = "state.json"):
        """Initialize state manager.

        Args:
            state_path: Path to state JSON file
        """
        self.state_path = Path(state_path)
        self.state: dict[str, Any] = {}

    def load(self) -> dict[str, Any]:
        """Load state from disk.

        Returns:
            State dictionary
        """
        if not self.state_path.exists():
            self.state = {}
            return self.state

        try:
            with open(self.state_path, encoding="utf-8") as f:
                self.state = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Failed to load state from {self.state_path}: {e}") from e

        return self.state

    def save(self) -> None:
        """Save state to disk."""
        try:
            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(self.state, f, indent=2)
        except OSError as e:
            raise RuntimeError(f"Failed to save state to {self.state_path}: {e}") from e

    def update_channel(self, server: str, channel: str, timestamp: str, message_id: str) -> None:
        """Update state for a channel.

        Args:
            server: Server name/ID
            channel: Channel name/ID
            timestamp: ISO format timestamp of last export
            message_id: ID of last exported message
        """
        if server not in self.state:
            self.state[server] = {}

        self.state[server][channel] = {"last_export": timestamp, "last_message_id": message_id}

        self.save()

    def get_channel_state(self, server: str, channel: str) -> dict[str, Any] | None:
        """Get state for a channel.

        Args:
            server: Server name/ID
            channel: Channel name/ID

        Returns:
            Channel state dict or None if not found
        """
        if server not in self.state:
            return None

        result = self.state[server].get(channel)
        return cast("dict[str, Any] | None", result)

    def update_thread_state(self, server: str, forum: str, thread_info: ThreadInfo) -> None:
        """Update state for a specific thread.

        Args:
            server: Server name
            forum: Forum name
            thread_info: Thread metadata
        """
        if server not in self.state:
            self.state[server] = {}

        if "forums" not in self.state[server]:
            self.state[server]["forums"] = {}

        if forum not in self.state[server]["forums"]:
            self.state[server]["forums"][forum] = {"threads": {}}

        if "threads" not in self.state[server]["forums"][forum]:
            self.state[server]["forums"][forum]["threads"] = {}

        self.state[server]["forums"][forum]["threads"][thread_info.thread_id] = {
            "name": thread_info.thread_name,
            "title": thread_info.thread_title,
            "last_export": datetime.now(timezone.utc).isoformat(),
            "last_message_id": thread_info.last_message_id,
            "archived": thread_info.archived,
        }

        self.save()

    def get_thread_state(self, server: str, forum: str, thread_id: str) -> dict[str, Any] | None:
        """Get state for a specific thread.

        Args:
            server: Server name
            forum: Forum name
            thread_id: Thread channel ID

        Returns:
            Thread state dict or None if not found
        """
        result = (
            self.state.get(server, {})
            .get("forums", {})
            .get(forum, {})
            .get("threads", {})
            .get(thread_id)
        )
        return cast("dict[str, Any] | None", result)

    def update_forum_index_timestamp(self, server: str, forum: str) -> None:
        """Update the last index generation timestamp for a forum.

        Args:
            server: Server name
            forum: Forum name
        """
        if server not in self.state:
            self.state[server] = {}

        if "forums" not in self.state[server]:
            self.state[server]["forums"] = {}

        if forum not in self.state[server]["forums"]:
            self.state[server]["forums"][forum] = {}

        self.state[server]["forums"][forum]["last_index_update"] = datetime.now(
            timezone.utc
        ).isoformat()

        self.save()
