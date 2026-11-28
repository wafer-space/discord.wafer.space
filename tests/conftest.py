"""Shared fixtures."""

from collections.abc import Iterator
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def no_discord_api() -> Iterator[None]:
    """Keep every test off the network.

    The export asks the Discord API which channels have new messages. With no
    activity facts it exports every channel the way it did before that lookup
    existed, which is what the older tests expect. Tests of the lookup itself
    patch it again with their own data.
    """
    with patch("scripts.export_channels.fetch_guild_activity", return_value={}):
        yield
