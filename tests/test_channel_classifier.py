# tests/test_channel_classifier.py
"""Tests for channel classification logic."""

from scripts.channel_classifier import ChannelType, classify_channel

# Test constants
TEST_MAX_THREAD_NAME_LENGTH = 100



def test_classify_regular_channel() -> None:
    """Test classification of regular channel."""
    channel = {"name": "general", "id": "123", "parent_id": None}
    forum_list = ["questions", "ideas"]

    result = classify_channel(channel, forum_list, all_channels=[channel])

    assert result == ChannelType.REGULAR


def test_classify_forum_channel() -> None:
    """Test classification of forum channel."""
    forum = {"name": "questions", "id": "999", "parent_id": None}
    thread: dict[str, str | None] = {"name": "How to start?", "id": "123", "parent_id": "questions"}
    forum_list = ["questions", "ideas"]

    result = classify_channel(forum, forum_list, all_channels=[forum, thread])

    assert result == ChannelType.FORUM


def test_classify_thread_channel() -> None:
    """Test classification of thread channel."""
    thread: dict[str, str | None] = {"name": "How to start?", "id": "123", "parent_id": "questions"}
    forum_list = ["questions", "ideas"]

    result = classify_channel(thread, forum_list, all_channels=[thread])

    assert result == ChannelType.THREAD


def test_classify_thread_without_forum_config() -> None:
    """Test thread classification when parent not in config."""
    thread: dict[str, str | None] = {
        "name": "Some thread",
        "id": "123",
        "parent_id": "random-forum",
    }
    forum_list = ["questions", "ideas"]

    result = classify_channel(thread, forum_list, all_channels=[thread])

    # Should still detect as thread based on parent_id
    assert result == ChannelType.THREAD


def test_sanitize_thread_name_basic() -> None:
    """Test basic thread name sanitization."""
    from scripts.channel_classifier import sanitize_thread_name

    result = sanitize_thread_name("How do I start?")
    assert result == "how-do-i-start"


def test_sanitize_thread_name_special_chars() -> None:
    """Test sanitization with special characters."""
    from scripts.channel_classifier import sanitize_thread_name

    result = sanitize_thread_name("Help! @ #Bot# won't work!!!")
    assert result == "help-bot-wont-work"


def test_sanitize_thread_name_fallback() -> None:
    """Test fallback to thread ID for empty names."""
    from scripts.channel_classifier import sanitize_thread_name

    result = sanitize_thread_name("!!!", thread_id="123456")
    assert result == "thread-123456"


def test_sanitize_thread_name_truncation() -> None:
    """Test long names are truncated."""
    from scripts.channel_classifier import sanitize_thread_name

    long_title = "a" * 150
    result = sanitize_thread_name(long_title)
    assert len(result) == TEST_MAX_THREAD_NAME_LENGTH
