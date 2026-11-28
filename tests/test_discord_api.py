"""Tests for the read-only Discord API lookups."""

import io
import json
import urllib.error
from email.message import Message
from typing import Any
from unittest.mock import patch

import pytest

from scripts.discord_api import (
    ChannelActivity,
    DiscordApiError,
    fetch_guild_activity,
    make_getter,
)


class FakeApi:
    """Answers API paths from a table and records what was asked."""

    def __init__(self, responses: dict[str, Any]):
        self.responses = responses
        self.calls: list[str] = []

    def __call__(self, path: str) -> Any:
        self.calls.append(path)
        response = self.responses.get(path)
        if isinstance(response, Exception):
            raise response
        if response is None:
            raise DiscordApiError(404, "unknown path in test")
        return response


def _thread(thread_id: str, last: str | None, archived_at: str | None = None) -> dict[str, Any]:
    thread: dict[str, Any] = {"id": thread_id, "type": 11, "last_message_id": last}
    if archived_at:
        thread["thread_metadata"] = {"archive_timestamp": archived_at}
    return thread


@pytest.mark.unit
class TestFetchGuildActivity:
    def test_collects_channels_active_and_archived_threads(self) -> None:
        api = FakeApi(
            {
                "/guilds/1/channels": [
                    {"id": "10", "type": 4, "name": "Info"},
                    {"id": "11", "type": 0, "last_message_id": "900"},
                    {"id": "12", "type": 15, "last_message_id": "950"},
                    {"id": "13", "type": 2, "last_message_id": None},
                ],
                "/guilds/1/threads/active": {"threads": [_thread("20", "910")]},
                "/channels/11/threads/archived/public?limit=100": {
                    "threads": [_thread("21", "800", "2026-01-01T00:00:00+00:00")],
                    "has_more": False,
                },
                "/channels/12/threads/archived/public?limit=100": {"threads": []},
            }
        )
        activity = fetch_guild_activity("1", api)
        assert activity == {
            # No last_message_id key at all: unknown, not "no messages".
            "10": ChannelActivity(4, None, last_message_known=False),
            "11": ChannelActivity(0, "900"),
            "12": ChannelActivity(15, "950"),
            # An explicit null: the channel has no messages.
            "13": ChannelActivity(2, None),
            "20": ChannelActivity(11, "910"),
            "21": ChannelActivity(11, "800"),
        }
        # Only channels that can hold threads are asked for archived threads.
        assert not any(c.startswith(("/channels/10/", "/channels/13/")) for c in api.calls)

    def test_forum_and_category_are_containers(self) -> None:
        assert ChannelActivity(15, "1").is_container
        assert ChannelActivity(16, "1").is_container
        assert ChannelActivity(4, None).is_container
        assert not ChannelActivity(0, "1").is_container
        assert not ChannelActivity(11, "1").is_container

    def test_archived_threads_are_paged_by_archive_timestamp(self) -> None:
        first = "/channels/11/threads/archived/public?limit=100"
        second = first + "&before=2026-02-01T00%3A00%3A00%2B00%3A00"
        api = FakeApi(
            {
                "/guilds/1/channels": [{"id": "11", "type": 0, "last_message_id": "1"}],
                "/guilds/1/threads/active": {"threads": []},
                first: {
                    "threads": [_thread("21", "5", "2026-02-01T00:00:00+00:00")],
                    "has_more": True,
                },
                second: {
                    "threads": [_thread("22", "4", "2026-01-01T00:00:00+00:00")],
                    "has_more": False,
                },
            }
        )
        activity = fetch_guild_activity("1", api)
        assert {"21", "22"} <= set(activity)
        assert api.calls[-2:] == [first, second]

    def test_unreadable_parent_is_skipped_not_fatal(self) -> None:
        api = FakeApi(
            {
                "/guilds/1/channels": [
                    {"id": "11", "type": 0, "last_message_id": "1"},
                    {"id": "12", "type": 0, "last_message_id": "2"},
                ],
                "/guilds/1/threads/active": {"threads": []},
                "/channels/11/threads/archived/public?limit=100": DiscordApiError(403, "no"),
                "/channels/12/threads/archived/public?limit=100": {"threads": [_thread("30", "3")]},
            }
        )
        assert set(fetch_guild_activity("1", api)) == {"11", "12", "30"}

    def test_other_archived_errors_propagate(self) -> None:
        api = FakeApi(
            {
                "/guilds/1/channels": [{"id": "11", "type": 0}],
                "/guilds/1/threads/active": {"threads": []},
                "/channels/11/threads/archived/public?limit=100": DiscordApiError(500, "boom"),
            }
        )
        with pytest.raises(DiscordApiError):
            fetch_guild_activity("1", api)

    def test_failed_channel_listing_raises(self) -> None:
        api = FakeApi({"/guilds/1/channels": DiscordApiError(401, "bad token")})
        with pytest.raises(DiscordApiError) as raised:
            fetch_guild_activity("1", api)
        assert raised.value.status == 401  # noqa: PLR2004

    def test_malformed_entries_are_ignored(self) -> None:
        api = FakeApi(
            {
                "/guilds/1/channels": [
                    "not an object",
                    {"type": 0},
                    {"id": "11", "type": "text"},
                    {"id": "12", "type": 0, "last_message_id": 77},
                ],
                "/guilds/1/threads/active": {"threads": None},
                "/channels/12/threads/archived/public?limit=100": ["unexpected"],
            }
        )
        assert fetch_guild_activity("1", api) == {"12": ChannelActivity(0, "77")}

    def test_non_list_channel_listing_is_an_error(self) -> None:
        with pytest.raises(DiscordApiError):
            fetch_guild_activity("1", FakeApi({"/guilds/1/channels": {"message": "nope"}}))


def _http_error(code: int, body: Any) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        "https://discord.com/api/v10/x",
        code,
        "err",
        Message(),
        io.BytesIO(json.dumps(body).encode()),
    )


class _Response:
    def __init__(self, payload: bytes):
        self.payload = payload

    def read(self) -> bytes:
        return self.payload

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_exc: object) -> None:
        return None


@pytest.mark.unit
class TestGetter:
    def test_sends_bot_token_and_get_only(self) -> None:
        with patch("urllib.request.urlopen", return_value=_Response(b'{"ok": true}')) as opened:
            assert make_getter("tok")("/guilds/1/channels") == {"ok": True}
        request = opened.call_args.args[0]
        assert request.full_url == "https://discord.com/api/v10/guilds/1/channels"
        assert request.get_method() == "GET"
        assert request.get_header("Authorization") == "Bot tok"

    def test_rate_limit_is_retried_after_the_requested_delay(self) -> None:
        sleeps: list[float] = []
        results = [_http_error(429, {"retry_after": 2.0}), _Response(b"[1]")]
        with patch("urllib.request.urlopen", side_effect=results):
            assert make_getter("tok", sleep=sleeps.append)("/x") == [1]
        assert sleeps == [2.25]

    def test_null_retry_after_falls_back_to_one_second(self) -> None:
        sleeps: list[float] = []
        results = [_http_error(429, {"retry_after": None}), _Response(b"[]")]
        with patch("urllib.request.urlopen", side_effect=results):
            make_getter("tok", sleep=sleeps.append)("/x")
        assert sleeps == [1.25]

    def test_gives_up_when_still_rate_limited(self) -> None:
        always = [_http_error(429, {"retry_after": 0}) for _ in range(10)]
        with patch("urllib.request.urlopen", side_effect=always):
            with pytest.raises(DiscordApiError) as raised:
                make_getter("tok", sleep=lambda _s: None)("/x")
        assert raised.value.status == 429  # noqa: PLR2004

    def test_http_error_carries_status(self) -> None:
        with patch("urllib.request.urlopen", side_effect=_http_error(403, {"message": "no"})):
            with pytest.raises(DiscordApiError) as raised:
                make_getter("tok")("/x")
        assert raised.value.status == 403  # noqa: PLR2004

    def test_transport_failure_is_reported_not_raised_raw(self) -> None:
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("dns")):
            with pytest.raises(DiscordApiError) as raised:
                make_getter("tok")("/x")
        assert raised.value.status == 0
        assert "could not reach discord.com" in str(raised.value)

    def test_invalid_json_is_reported(self) -> None:
        with patch("urllib.request.urlopen", return_value=_Response(b"<html>")):
            with pytest.raises(DiscordApiError):
                make_getter("tok")("/x")
