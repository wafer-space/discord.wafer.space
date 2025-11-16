"""Tests for thread metadata extraction."""

import json
import tempfile
from pathlib import Path

from scripts.thread_metadata import extract_thread_metadata


def test_extract_thread_metadata_basic():
    """Test basic thread metadata extraction."""
    # Create temp JSON file with thread data
    thread_json = {
        "guild": {"name": "Test Server"},
        "channel": {"id": "123456", "name": "How do I start?", "type": "GuildPublicThread"},
        "messages": [
            {"id": "1", "timestamp": "2025-11-01T10:00:00Z", "content": "First message"},
            {"id": "2", "timestamp": "2025-11-10T15:30:00Z", "content": "Reply 1"},
            {"id": "3", "timestamp": "2025-11-10T16:00:00Z", "content": "Reply 2"},
        ],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(thread_json, f)
        temp_path = Path(f.name)

    try:
        metadata = extract_thread_metadata(temp_path)

        assert metadata["title"] == "How do I start?"  # type: ignore[index]
        assert metadata["reply_count"] == 3  # type: ignore[index]
        assert metadata["last_activity"] == "2025-11-10"  # type: ignore[index]
        assert metadata["archived"] is False  # type: ignore[index]
    finally:
        temp_path.unlink()


def test_extract_thread_metadata_empty_messages():
    """Test metadata extraction with no messages."""
    thread_json = {"channel": {"name": "Empty Thread"}, "messages": []}

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(thread_json, f)
        temp_path = Path(f.name)

    try:
        metadata = extract_thread_metadata(temp_path)

        assert metadata["title"] == "Empty Thread"  # type: ignore[index]
        assert metadata["reply_count"] == 0  # type: ignore[index]
        assert metadata["last_activity"] is None  # type: ignore[index]
    finally:
        temp_path.unlink()


def test_extract_thread_metadata_archived():
    """Test metadata extraction for archived thread."""
    # Thread with old messages (>6 months = archived)
    thread_json = {
        "channel": {"name": "Old Thread"},
        "messages": [{"id": "1", "timestamp": "2024-01-15T10:00:00Z", "content": "Old message"}],
    }

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump(thread_json, f)
        temp_path = Path(f.name)

    try:
        metadata = extract_thread_metadata(temp_path)

        assert metadata["archived"] is True  # type: ignore[index]
    finally:
        temp_path.unlink()


def test_extract_thread_metadata_missing_file():
    """Test handling of missing JSON file."""
    result = extract_thread_metadata(Path("/nonexistent/file.json"))

    assert result is None


def test_extract_thread_metadata_invalid_json():
    """Test handling of invalid JSON."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("not valid json {")
        temp_path = Path(f.name)

    try:
        result = extract_thread_metadata(temp_path)
        assert result is None
    finally:
        temp_path.unlink()
