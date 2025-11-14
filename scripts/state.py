"""State management for tracking export progress."""
import json
from pathlib import Path
from typing import Optional

class StateManager:
    """Manages export state tracking."""

    def __init__(self, state_path: str = "state.json"):
        """
        Initialize state manager.

        Args:
            state_path: Path to state JSON file
        """
        self.state_path = Path(state_path)
        self.state: dict = {}

    def load(self) -> dict:
        """
        Load state from disk.

        Returns:
            State dictionary
        """
        if not self.state_path.exists():
            self.state = {}
            return self.state

        try:
            with open(self.state_path, 'r', encoding='utf-8') as f:
                self.state = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            raise RuntimeError(f"Failed to load state from {self.state_path}: {e}") from e

        return self.state

    def save(self) -> None:
        """Save state to disk."""
        try:
            with open(self.state_path, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, indent=2)
        except OSError as e:
            raise RuntimeError(f"Failed to save state to {self.state_path}: {e}") from e

    def update_channel(
        self,
        server: str,
        channel: str,
        timestamp: str,
        message_id: str
    ) -> None:
        """
        Update state for a channel.

        Args:
            server: Server name/ID
            channel: Channel name/ID
            timestamp: ISO format timestamp of last export
            message_id: ID of last exported message
        """
        if server not in self.state:
            self.state[server] = {}

        self.state[server][channel] = {
            "last_export": timestamp,
            "last_message_id": message_id
        }

    def get_channel_state(
        self,
        server: str,
        channel: str
    ) -> Optional[dict]:
        """
        Get state for a channel.

        Args:
            server: Server name/ID
            channel: Channel name/ID

        Returns:
            Channel state dict or None if not found
        """
        if server not in self.state:
            return None

        return self.state[server].get(channel)
