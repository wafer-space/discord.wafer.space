"""Thread metadata extraction from JSON exports."""
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path


def extract_thread_metadata(json_path: Path) -> dict | None:
    """Extract metadata from a thread JSON export.

    Args:
        json_path: Path to the JSON export file

    Returns:
        Dictionary with:
        - title: Thread title
        - reply_count: Number of messages
        - last_activity: Date of last message (YYYY-MM-DD) or None
        - archived: Boolean indicating if thread appears archived

        Returns None if file doesn't exist or is invalid.
    """
    # Check if file exists
    if not json_path.exists():
        return None

    try:
        # Load JSON
        with open(json_path, encoding='utf-8') as f:
            data = json.load(f)

        # Extract title from channel name
        title = data.get('channel', {}).get('name', 'Untitled')

        # Get messages
        messages = data.get('messages', [])
        reply_count = len(messages)

        # Get last activity
        last_activity = None
        if messages:
            # Get timestamp from last message
            last_msg = messages[-1]
            timestamp_str = last_msg.get('timestamp')
            if timestamp_str:
                # Parse ISO format timestamp
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                last_activity = timestamp.strftime('%Y-%m-%d')

        # Determine if archived (>6 months old)
        archived = False
        if messages and last_activity:
            last_dt = datetime.fromisoformat(last_activity + 'T00:00:00+00:00')
            age = datetime.now(timezone.utc) - last_dt
            archived = age > timedelta(days=180)

        return {
            'title': title,
            'reply_count': reply_count,
            'last_activity': last_activity,
            'archived': archived
        }

    except (json.JSONDecodeError, KeyError, ValueError):
        # Return None for any parsing errors
        return None
