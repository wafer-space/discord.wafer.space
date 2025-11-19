# tests/test_message_counting_bug.py
"""Test demonstrating Issue #4: message count discrepancy bug."""

import json
import tempfile
from pathlib import Path

import pytest

from scripts.generate_navigation import count_messages_from_json
from scripts.thread_metadata import extract_thread_metadata

# Test constants
EXPECTED_MESSAGE_COUNT = 5


@pytest.mark.unit
def test_count_messages_from_json_with_real_discord_format() -> None:
    """Test that count_messages_from_json works with actual DiscordChatExporter JSON format.

    This test demonstrates Issue #4: the function counts lines instead of messages,
    causing incorrect message counts on archive index pages.
    """
    # Create a sample JSON export mimicking DiscordChatExporter format
    sample_export = {
        "guild": {"id": "123", "name": "Test Server"},
        "channel": {"id": "456", "name": "test-thread", "type": "PublicThread"},
        "messages": [
            {"id": "1", "timestamp": "2025-11-01T10:00:00Z", "content": "Message 1"},
            {"id": "2", "timestamp": "2025-11-01T10:01:00Z", "content": "Message 2"},
            {"id": "3", "timestamp": "2025-11-01T10:02:00Z", "content": "Message 3"},
            {"id": "4", "timestamp": "2025-11-01T10:03:00Z", "content": "Message 4"},
            {"id": "5", "timestamp": "2025-11-01T10:04:00Z", "content": "Message 5"},
        ]
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(sample_export, f, indent=2)  # Pretty-printed like DCE exports
        temp_path = f.name

    try:
        # The broken function counts lines (37 lines for this formatted JSON)
        line_count = count_messages_from_json(temp_path)

        # The correct count should be EXPECTED_MESSAGE_COUNT (number of messages)
        # This test SHOULD FAIL with the current implementation
        assert line_count == EXPECTED_MESSAGE_COUNT, (
            f"count_messages_from_json() should return {EXPECTED_MESSAGE_COUNT} messages, "
            f"but got {line_count} (counting lines instead of messages)"
        )

    finally:
        Path(temp_path).unlink()


@pytest.mark.unit
def test_extract_thread_metadata_counts_correctly() -> None:
    """Verify that extract_thread_metadata() counts messages correctly."""
    sample_export = {
        "guild": {"id": "123", "name": "Test Server"},
        "channel": {"id": "456", "name": "test-thread", "type": "PublicThread"},
        "messages": [
            {"id": "1", "timestamp": "2025-11-01T10:00:00Z", "content": "Message 1"},
            {"id": "2", "timestamp": "2025-11-01T10:01:00Z", "content": "Message 2"},
            {"id": "3", "timestamp": "2025-11-01T10:02:00Z", "content": "Message 3"},
            {"id": "4", "timestamp": "2025-11-01T10:03:00Z", "content": "Message 4"},
            {"id": "5", "timestamp": "2025-11-01T10:04:00Z", "content": "Message 5"},
        ]
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(sample_export, f, indent=2)
        temp_path = f.name

    try:
        metadata = extract_thread_metadata(Path(temp_path))
        assert metadata is not None
        assert (
            metadata["reply_count"] == EXPECTED_MESSAGE_COUNT
        ), f"extract_thread_metadata should count {EXPECTED_MESSAGE_COUNT} messages"

    finally:
        Path(temp_path).unlink()
