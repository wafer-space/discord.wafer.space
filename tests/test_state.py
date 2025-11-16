import json
import tempfile
from pathlib import Path

from scripts.state import StateManager


def test_state_manager_creates_empty_state():
    """Test that StateManager creates empty state if file doesn't exist"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
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
            "general": {"last_export": "2025-01-15T14:00:00Z", "last_message_id": "123456"}
        }
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(initial_state, f)
        state_path = f.name

    manager = StateManager(state_path)
    state = manager.load()

    assert state == initial_state
    Path(state_path).unlink()


def test_state_manager_updates_channel_state():
    """Test updating state for a channel"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
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
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
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


def test_state_manager_updates_thread_state():
    """Test that thread state is updated correctly."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("{}")
        state_file = f.name

    try:
        manager = StateManager(state_file)
        manager.load()

        # Update thread state
        manager.update_thread_state(
            server="test-server",
            forum="questions",
            thread_id="123456",
            thread_name="how-to-start",
            thread_title="How to start?",
            last_message_id="999",
            archived=False,
        )

        # Verify thread state was saved
        state = manager.get_thread_state("test-server", "questions", "123456")

        assert state is not None
        assert state["name"] == "how-to-start"
        assert state["title"] == "How to start?"
        assert state["last_message_id"] == "999"
        assert state["archived"] is False
        assert "last_export" in state
    finally:
        Path(state_file).unlink()


def test_state_manager_gets_thread_state():
    """Test retrieving thread state."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        state_data = {
            "test-server": {
                "forums": {
                    "questions": {
                        "threads": {
                            "123456": {
                                "name": "how-to-start",
                                "title": "How to start?",
                                "last_export": "2025-11-14T10:00:00Z",
                                "last_message_id": "999",
                                "archived": False,
                            }
                        }
                    }
                }
            }
        }
        json.dump(state_data, f)
        state_file = f.name

    try:
        manager = StateManager(state_file)
        manager.load()
        state = manager.get_thread_state("test-server", "questions", "123456")

        assert state["name"] == "how-to-start"
        assert state["title"] == "How to start?"
        assert state["last_message_id"] == "999"
    finally:
        Path(state_file).unlink()


def test_state_manager_thread_state_returns_none_if_missing():
    """Test that get_thread_state returns None for non-existent threads."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("{}")
        state_file = f.name

    try:
        manager = StateManager(state_file)
        manager.load()
        state = manager.get_thread_state("test-server", "questions", "123456")

        assert state is None
    finally:
        Path(state_file).unlink()


def test_state_manager_updates_forum_index_timestamp():
    """Test updating forum index update timestamp."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("{}")
        state_file = f.name

    try:
        manager = StateManager(state_file)
        manager.load()

        manager.update_forum_index_timestamp("test-server", "questions")

        # Verify forum has last_index_update
        state = manager.state
        assert "test-server" in state
        assert "forums" in state["test-server"]
        assert "questions" in state["test-server"]["forums"]
        assert "last_index_update" in state["test-server"]["forums"]["questions"]
    finally:
        Path(state_file).unlink()
