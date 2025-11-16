# scripts/channel_classifier.py
"""Channel classification logic for forum/thread detection."""

from enum import Enum


class ChannelType(Enum):
    """Channel type enumeration."""

    REGULAR = "regular"
    FORUM = "forum"
    THREAD = "thread"


def classify_channel(
    channel: dict[str, str], forum_list: list[str], all_channels: list[dict[str, str]]
) -> ChannelType:
    """Classify a channel as regular, forum, or thread.

    Args:
        channel: Channel dict with name, id, parent_id
        forum_list: List of known forum channel names from config
        all_channels: All channels (used to detect if channel has threads)

    Returns:
        ChannelType indicating channel classification
    """
    # If channel has parent_id, it's a thread
    if channel.get("parent_id"):
        return ChannelType.THREAD

    # If channel name is in forum list, it's a forum
    if channel["name"] in forum_list:
        return ChannelType.FORUM

    # Check if any other channels have this as parent (auto-detect forum)
    channel_name = channel["name"]
    has_threads = any(ch.get("parent_id") == channel_name for ch in all_channels)

    if has_threads:
        return ChannelType.FORUM

    # Otherwise it's a regular channel
    return ChannelType.REGULAR


def get_forum_name(channel: dict[str, str]) -> str:
    """Get the forum name for a thread channel.

    Args:
        channel: Thread channel dict with parent_id

    Returns:
        Parent forum channel name, or empty string if not a thread
    """
    return channel.get("parent_id", "")


def sanitize_thread_name(title: str, thread_id: str = None) -> str:
    """Sanitize thread title into safe filename.

    Args:
        title: Thread title
        thread_id: Optional thread ID for fallback

    Returns:
        Sanitized filename (without extension)
    """
    import re

    # Convert to lowercase
    name = title.lower()

    # Replace spaces with hyphens
    name = name.replace(" ", "-")

    # Remove special characters except hyphens
    name = re.sub(r"[^a-z0-9-]", "", name)

    # Remove multiple consecutive hyphens
    name = re.sub(r"-+", "-", name)

    # Remove leading/trailing hyphens
    name = name.strip("-")

    # Truncate to 100 characters
    name = name[:100]

    # If empty or too short, use thread ID
    if len(name) < 3 and thread_id:
        name = f"thread-{thread_id}"

    return name
