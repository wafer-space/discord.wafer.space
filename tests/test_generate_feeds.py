"""Tests for index.json and Atom feed generation."""

import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest
from jinja2 import Environment, FileSystemLoader

from scripts.generate_feeds import (
    CHANNEL_FEED_LIMIT,
    INFERRED_FORUM_TYPE,
    generate_for_server,
    load_channel,
    parse_time,
    pick_canonical,
    scan_server,
    url_for,
)

ATOM = {"a": "http://www.w3.org/2005/Atom"}
SITE = {"base_url": "https://logs.example"}
SERVER = {"name": "Example", "guild_id": "100"}


def _message(message_id: int, content: str = "hello", **extra: Any) -> dict[str, Any]:
    day = 1 + message_id % 27
    return {
        "id": str(message_id),
        "type": "Default",
        "timestamp": f"2026-11-{day:02d}T10:00:00.000+00:00",
        "timestampEdited": None,
        "content": content,
        "author": {"name": "alice", "nickname": "Alice"},
        "attachments": [],
        **extra,
    }


def _write_month(  # noqa: PLR0913  # A fixture export has this many independent facts
    server_dir: Path,
    path: str,
    month: str,
    channel: dict[str, Any],
    messages: list[Any],
    *,
    exported_at: str = "2026-11-25T22:24:08.3064344+00:00",
) -> None:
    month_dir = server_dir / path / month
    month_dir.mkdir(parents=True, exist_ok=True)
    info = {"topic": None, "category": None, "categoryId": None, **channel}
    export = {
        "guild": {"id": "100", "name": "Example"},
        "channel": info,
        "exportedAt": exported_at,
        "messages": messages,
        "messageCount": len(messages),
    }
    (month_dir / f"{month}.json").write_text(json.dumps(export), encoding="utf-8")


def _text_channel(channel_id: str, name: str, category: str = "Info") -> dict[str, Any]:
    return {"id": channel_id, "type": "GuildTextChat", "name": name, "category": category}


def _thread(channel_id: str, name: str, parent_id: str, parent: str) -> dict[str, Any]:
    return {
        "id": channel_id,
        "type": "GuildPublicThread",
        "name": name,
        "category": parent,
        "categoryId": parent_id,
    }


def _entries(feed_path: Path) -> list[ET.Element]:
    return ET.parse(feed_path).getroot().findall("a:entry", ATOM)  # noqa: S314  # our own output


def _text(element: ET.Element, tag: str) -> str:
    found = element.find(f"a:{tag}", ATOM)
    assert found is not None and found.text is not None
    return found.text


@pytest.fixture
def server_dir(tmp_path: Path) -> Path:
    """A public/<server> directory with one channel, one thread and one forum post."""
    root = tmp_path / "public" / "example"
    _write_month(
        root,
        "Info/general",
        "2026-10",
        _text_channel("1", "general"),
        [_message(10, "october")],
        exported_at="2026-11-01T00:10:00+00:00",
    )
    _write_month(
        root,
        "Info/general",
        "2026-11",
        _text_channel("1", "general"),
        [_message(20, "first"), _message(21, "second")],
    )
    _write_month(
        root,
        "Info/general/side-topic",
        "2026-11",
        _thread("2", "Side topic", "1", "general"),
        [_message(30, "in the thread")],
    )
    _write_month(
        root,
        "Info/questions/how-do-i",
        "2026-11",
        _thread("4", "How do I?", "3", "questions"),
        [_message(40, "a forum post")],
    )
    return root


def _generate(server_dir: Path) -> dict[str, Any]:
    generate_for_server(server_dir.parent, server_dir.name, SERVER, SITE)
    index: dict[str, Any] = json.loads((server_dir / "index.json").read_text(encoding="utf-8"))
    return index


def _by_id(index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {c["id"]: c for c in index["channels"]}


@pytest.mark.unit
class TestHelpers:
    def test_parse_time_accepts_seven_fraction_digits(self) -> None:
        parsed = parse_time("2026-11-25T22:24:08.3064344+00:00")
        assert parsed is not None
        assert parsed.microsecond == 306434  # noqa: PLR2004

    def test_parse_time_rejects_garbage(self) -> None:
        assert parse_time("yesterday") is None
        assert parse_time(None) is None

    def test_url_for_percent_encodes_each_part(self) -> None:
        url = url_for("https://logs.example/", "example", "ℹ️ - Info/general")
        assert url == "https://logs.example/example/%E2%84%B9%EF%B8%8F%20-%20Info/general"


@pytest.mark.unit
class TestIndex:
    def test_lists_every_channel_by_id(self, server_dir: Path) -> None:
        index = _generate(server_dir)
        assert index["schema"] == 1
        assert index["server"] == {
            "key": "example",
            "name": "Example",
            "guild_id": "100",
            "url": "https://logs.example/example/",
            "feed": "https://logs.example/example/feed.atom",
        }
        assert set(_by_id(index)) == {"1", "2", "3", "4"}

    def test_channel_entry_aggregates_its_months(self, server_dir: Path) -> None:
        general = _by_id(_generate(server_dir))["1"]
        assert general["path"] == "Info/general"
        assert general["category"] == "Info"
        assert general["parent_id"] is None
        assert general["months"] == ["2026-10", "2026-11"]
        assert general["message_count"] == 3  # noqa: PLR2004
        assert general["last_message_id"] == "21"
        assert general["url"] == "https://logs.example/example/Info/general/"
        assert general["latest_json"] == general["url"] + "latest.json"
        assert general["month_json"] == general["url"] + "{month}/{month}.json"

    def test_thread_points_at_its_parent(self, server_dir: Path) -> None:
        thread = _by_id(_generate(server_dir))["2"]
        assert thread["parent_id"] == "1"
        assert thread["category"] is None

    def test_forum_is_inferred_from_its_posts(self, server_dir: Path) -> None:
        forum = _by_id(_generate(server_dir))["3"]
        assert forum["type"] == INFERRED_FORUM_TYPE
        assert forum["path"] == "Info/questions"
        assert forum["category"] == "Info"
        assert forum["months"] == []
        assert "latest_json" not in forum

    def test_updated_at_is_newest_export_not_now(self, server_dir: Path) -> None:
        assert _generate(server_dir)["updated_at"] == "2026-11-25T22:24:08.3064344+00:00"

    def test_output_is_identical_across_runs(self, server_dir: Path) -> None:
        _generate(server_dir)
        outputs = sorted([*server_dir.rglob("feed.atom"), server_dir / "index.json"])
        first = {p: p.read_bytes() for p in outputs}
        _generate(server_dir)
        assert {p: p.read_bytes() for p in outputs} == first


@pytest.mark.unit
class TestRenames:
    def test_renamed_channel_keeps_one_entry_with_stale_path(self, server_dir: Path) -> None:
        # The same channel ID exported earlier under its old category name.
        _write_month(
            server_dir,
            "Old Info/general",
            "2026-09",
            _text_channel("1", "general", category="Old Info"),
            [_message(5, "before the rename")],
            exported_at="2026-09-30T00:00:00+00:00",
        )
        general = _by_id(_generate(server_dir))["1"]
        assert general["path"] == "Info/general"
        assert general["stale_paths"] == ["Old Info/general"]
        # The old directory's index page links to feed.atom, so it has one,
        # and it is the live feed rather than a second, diverging one.
        live = (server_dir / "Info/general/feed.atom").read_bytes()
        assert (server_dir / "Old Info/general/feed.atom").read_bytes() == live

    def test_renamed_forum_records_its_old_directory(self, server_dir: Path) -> None:
        _write_month(
            server_dir,
            "Info/old-questions/how-do-i",
            "2026-08",
            _thread("4", "How do I?", "3", "old-questions"),
            [_message(4, "older copy")],
            exported_at="2026-08-31T00:00:00+00:00",
        )
        forum = _by_id(_generate(server_dir))["3"]
        assert forum["path"] == "Info/questions"
        assert forum["stale_paths"] == ["Info/old-questions"]
        assert (server_dir / "Info/old-questions/feed.atom").is_file()

    def test_pick_canonical_prefers_newest_export(self, server_dir: Path) -> None:
        _write_month(
            server_dir,
            "Zed/general",
            "2026-11",
            _text_channel("1", "general", category="Zed"),
            [_message(22, "newer export")],
            exported_at="2026-11-26T00:00:00+00:00",
        )
        chosen = {c.id: c for c in pick_canonical(scan_server(server_dir))}
        assert chosen["1"].path == "Zed/general"
        assert chosen["1"].stale_paths == ["Info/general"]


@pytest.mark.unit
class TestFeeds:
    def test_server_feed_is_newest_first_across_channels(self, server_dir: Path) -> None:
        _generate(server_dir)
        entries = _entries(server_dir / "feed.atom")
        ids = [_text(e, "id").rsplit("/", 1)[1] for e in entries]
        assert ids == ["40", "30", "21", "20", "10"]

    def test_channel_feed_includes_its_threads(self, server_dir: Path) -> None:
        _generate(server_dir)
        titles = [_text(e, "title") for e in _entries(server_dir / "Info/general/feed.atom")]
        assert titles[0] == "Alice in #general › Side topic: in the thread"
        assert titles[1] == "Alice in #general: second"
        assert len(titles) == 4  # noqa: PLR2004

    def test_forum_feed_carries_its_posts(self, server_dir: Path) -> None:
        _generate(server_dir)
        titles = [_text(e, "title") for e in _entries(server_dir / "Info/questions/feed.atom")]
        assert titles == ["Alice in #questions › How do I?: a forum post"]

    def test_entry_links_to_the_message_in_the_html_archive(self, server_dir: Path) -> None:
        _generate(server_dir)
        entry = _entries(server_dir / "Info/general/side-topic/feed.atom")[0]
        link = entry.find("a:link", ATOM)
        assert link is not None
        assert link.get("href") == (
            "https://logs.example/example/Info/general/side-topic/2026-11/2026-11.html"
            "#chatlog__message-container-30"
        )
        assert _text(entry, "id") == "tag:discord.com,2015:message/2/30"

    def test_system_messages_stay_out_of_feeds_but_are_counted(self, server_dir: Path) -> None:
        _write_month(
            server_dir,
            "Info/general",
            "2026-11",
            _text_channel("1", "general"),
            [_message(20, "kept"), _message(23, "pinned a message", type="ChannelPinnedMessage")],
        )
        general = _by_id(_generate(server_dir))["1"]
        assert general["message_count"] == 3  # noqa: PLR2004
        assert general["last_message_id"] == "23"
        titles = [_text(e, "title") for e in _entries(server_dir / "Info/general/feed.atom")]
        assert not any("pinned" in t for t in titles)

    def test_content_is_escaped_and_control_characters_dropped(self, server_dir: Path) -> None:
        _write_month(
            server_dir,
            "Info/general",
            "2026-11",
            _text_channel("1", "general"),
            [_message(20, 'a <b> & "c"\x0b ]]> end')],
        )
        _generate(server_dir)
        entry = _entries(server_dir / "Info/general/feed.atom")[1]
        assert _text(entry, "content") == 'a <b> & "c" ]]> end'

    def test_attachment_path_becomes_an_absolute_url(self, server_dir: Path) -> None:
        attachment = {"url": "2026-11_media/my plot-1A2B3.png", "fileName": "my plot.png"}
        _write_month(
            server_dir,
            "Info/general",
            "2026-11",
            _text_channel("1", "general"),
            [_message(20, "", attachments=[attachment])],
        )
        _generate(server_dir)
        entry = _entries(server_dir / "Info/general/feed.atom")[1]
        assert _text(entry, "title") == "Alice in #general: (attachment)"
        assert _text(entry, "content") == (
            "[attachment: my plot.png] https://logs.example/example/Info/general/"
            "2026-11/2026-11_media/my%20plot-1A2B3.png"
        )

    def test_long_message_title_is_truncated_but_content_is_whole(self, server_dir: Path) -> None:
        long_text = "word " * 60
        _write_month(
            server_dir,
            "Info/general",
            "2026-11",
            _text_channel("1", "general"),
            [_message(20, long_text)],
        )
        _generate(server_dir)
        entry = _entries(server_dir / "Info/general/feed.atom")[1]
        assert _text(entry, "title").endswith("…")
        assert len(_text(entry, "title")) < len(long_text)
        assert _text(entry, "content") == long_text.strip()

    def test_channel_feed_is_capped(self, server_dir: Path) -> None:
        many = [_message(1000 + i, f"m{i}") for i in range(CHANNEL_FEED_LIMIT + 25)]
        _write_month(server_dir, "Info/busy", "2026-11", _text_channel("9", "busy"), many)
        _generate(server_dir)
        entries = _entries(server_dir / "Info/busy/feed.atom")
        assert len(entries) == CHANNEL_FEED_LIMIT
        assert _text(entries[0], "id").endswith(f"/{1000 + CHANNEL_FEED_LIMIT + 24}")

    def test_directory_holding_only_threads_gets_the_parent_feed(self, server_dir: Path) -> None:
        # The exporter publishes the channel's months under "marketing" but
        # its threads under "📢-marketing", which has an index page and no
        # export of its own.
        _write_month(
            server_dir,
            "Info/marketing",
            "2026-11",
            _text_channel("5", "📢-marketing"),
            [_message(60, "channel message")],
        )
        _write_month(
            server_dir,
            "Info/📢-marketing/launch-plan",
            "2026-11",
            _thread("6", "Launch plan", "5", "📢-marketing"),
            [_message(61, "thread message")],
        )
        index = _generate(server_dir)
        holder = server_dir / "Info/📢-marketing/feed.atom"
        assert holder.is_file()
        assert holder.read_bytes() == (server_dir / "Info/marketing/feed.atom").read_bytes()
        texts = {_text(e, "content") for e in _entries(holder)}
        assert texts == {"channel message", "thread message"}
        # It is a copy, not a new channel.
        assert "Info/📢-marketing" not in {c["path"] for c in index["channels"]}

    def test_empty_channel_still_gets_a_valid_feed(self, server_dir: Path) -> None:
        _write_month(server_dir, "Info/quiet", "2026-11", _text_channel("8", "quiet"), [])
        _generate(server_dir)
        root = ET.parse(server_dir / "Info/quiet/feed.atom").getroot()  # noqa: S314  # our own output
        assert root.findall("a:entry", ATOM) == []
        assert _text(root, "updated") == "1970-01-01T00:00:00+00:00"


@pytest.mark.unit
class TestBadInput:
    def test_unreadable_month_is_skipped_not_fatal(
        self, server_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        broken = server_dir / "Info/general/2026-12"
        broken.mkdir()
        (broken / "2026-12.json").write_text("{", encoding="utf-8")
        channel = load_channel(server_dir / "Info/general", server_dir)
        assert channel is not None
        assert channel.months == ["2026-10", "2026-11"]
        assert "skipping unreadable export" in capsys.readouterr().out

    def test_odd_values_in_a_readable_export_are_skipped_not_fatal(
        self, server_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _write_month(
            server_dir,
            "Info/general",
            "2026-12",
            {**_text_channel("1", "general"), "topic": 7, "category": ["Info"]},
            [
                _message(50, "author is a string", author="alice"),
                _message(51, "attachments is a dict", attachments={"url": "x.png"}),
                _message(52, "attachment entries are odd", attachments=["x.png", {"url": 3}]),
                {**_message(53), "content": None, "timestampEdited": 12, "timestamp": None},
                {**_message(54), "id": None},
                {**_message(55), "id": {"nested": True}},
                "not a message",
                None,
            ],
            exported_at="2026-12-02T00:00:00+00:00",
        )
        index = _generate(server_dir)
        general = _by_id(index)["1"]
        assert general["months"][-1] == "2026-12"
        assert general["topic"] is None
        feed = server_dir / "Info/general/feed.atom"
        texts = [e.findtext("a:content", "", ATOM) for e in _entries(feed)]
        assert "author is a string" in texts
        assert "attachments is a dict" in texts
        assert "attachment entries are odd" in texts
        out = capsys.readouterr().out
        malformed = 4  # ids None and a dict, a string, and None
        assert out.count("skipping malformed message") == malformed

    def test_messages_that_are_not_a_list_skip_the_month(
        self, server_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        broken = server_dir / "Info/general/2026-12"
        broken.mkdir()
        export = {"channel": _text_channel("1", "general"), "messages": {"id": "9"}}
        (broken / "2026-12.json").write_text(json.dumps(export), encoding="utf-8")
        channel = load_channel(server_dir / "Info/general", server_dir)
        assert channel is not None
        assert channel.months == ["2026-10", "2026-11"]
        assert "messages is not a list" in capsys.readouterr().out

    def test_media_sidecar_json_is_not_a_channel(self, server_dir: Path) -> None:
        media = server_dir / "Info/general/2026-11/2026-11_media"
        media.mkdir()
        (media / "big.gds.toobig.json").write_text('{"size": 1}', encoding="utf-8")
        assert set(_by_id(_generate(server_dir))) == {"1", "2", "3", "4"}


@pytest.mark.unit
class TestTemplates:
    def test_index_pages_advertise_the_feed(self) -> None:
        env = Environment(loader=FileSystemLoader("templates"))
        server = {"name": "example", "display_name": "Example"}
        site = {"title": "Logs", "description": ""}
        server_html = env.get_template("server_index.html.j2").render(
            site=site, server=server, channels=[], categories=[], last_updated=""
        )
        assert 'type="application/atom+xml"' in server_html
        assert 'href="feed.atom"' in server_html
        assert 'href="index.json"' in server_html
        channel_html = env.get_template("channel_index.html.j2").render(
            site=site,
            server=server,
            channel={"name": "Info/general", "display_name": "general"},
            archives_by_year={},
            threads=None,
            last_updated="",
        )
        assert 'href="feed.atom"' in channel_html
        forum_html = env.get_template("forum_index.html.j2").render(
            site=site, server=server, forum_name="questions", threads=[], last_updated=""
        )
        assert 'href="feed.atom"' in forum_html
        thread_html = env.get_template("thread_index.html.j2").render(
            site=site,
            server=server,
            forum_name="questions",
            thread_title="How do I?",
            archives_by_year={},
            last_updated="",
        )
        assert 'href="feed.atom"' in thread_html
