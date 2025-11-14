"""State management for tracking export progress."""
import json
from pathlib import Path
from typing import Dict, Optional

class StateManager:
    """Manages export state tracking."""

    def __init__(self, state_path: str = "state.json"):
        """
        Initialize state manager.

        Args:
            state_path: Path to state JSON file
        """
        self.state_path = Path(state_path)
        self.state: Dict = {}

    def load(self) -> Dict:
        """
        Load state from disk.

        Returns:
            State dictionary
        """
        if not self.state_path.exists():
            self.state = {}
            return self.state

        with open(self.state_path, 'r') as f:
            self.state = json.load(f)

        return self.state

    def save(self) -> None:
        """Save state to disk."""
        with open(self.state_path, 'w') as f:
            json.dump(self.state, f, indent=2)

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
    ) -> Optional[Dict]:
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
