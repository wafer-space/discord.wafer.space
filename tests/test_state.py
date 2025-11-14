import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime
from scripts.state import StateManager

def test_state_manager_creates_empty_state():
    """Test that StateManager creates empty state if file doesn't exist"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        state_path = f.name

    Path(state_path).unlink()  # Remove it

    manager = StateManager(state_path)
    state = manager.load()

    assert state == {}
    # Only unlink if it still exists (it shouldn't after empty state creation)
    if Path(state_path).exists():
        Path(state_path).unlink()

def test_state_manager_loads_existing_state():
    """Test that StateManager loads existing state"""
    initial_state = {
        "wafer-space": {
            "general": {
                "last_export": "2025-01-15T14:00:00Z",
                "last_message_id": "123456"
            }
        }
    }

    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump(initial_state, f)
        state_path = f.name

    manager = StateManager(state_path)
    state = manager.load()

    assert state == initial_state
    Path(state_path).unlink()

def test_state_manager_updates_channel_state():
    """Test updating state for a channel"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({}, f)  # Write empty JSON object
        state_path = f.name

    manager = StateManager(state_path)
    manager.load()

    timestamp = "2025-01-15T15:00:00Z"
    message_id = "789012"

    manager.update_channel("test-server", "general", timestamp, message_id)

    # Check the in-memory state
    assert manager.state["test-server"]["general"]["last_export"] == timestamp
    assert manager.state["test-server"]["general"]["last_message_id"] == message_id

    Path(state_path).unlink()

def test_state_manager_saves_state():
    """Test that state is persisted to disk"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        json.dump({}, f)  # Write empty JSON object
        state_path = f.name

    manager = StateManager(state_path)
    manager.load()
    manager.update_channel("server", "channel", "2025-01-15T15:00:00Z", "123")
    manager.save()

    # Load in new manager instance
    manager2 = StateManager(state_path)
    state = manager2.load()

    assert state["server"]["channel"]["last_export"] == "2025-01-15T15:00:00Z"
    Path(state_path).unlink()
