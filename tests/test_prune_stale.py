"""Tests for removing directories left behind by channel and category renames."""

import json
from pathlib import Path
from typing import Any

import pytest

from scripts.generate_feeds import generate_for_server
from scripts.prune_stale import find_stale, prune_server

BASE_URL = "https://logs.example"


def _write_month(  # noqa: PLR0913  # A fixture export has this many independent facts
    server_dir: Path,
    path: str,
    month: str,
    channel_id: str,
    message_ids: list[str],
    *,
    exported_at: str,
    channel_type: str = "GuildTextChat",
    parent_id: str | None = None,
) -> None:
    month_dir = server_dir / path / month
    month_dir.mkdir(parents=True, exist_ok=True)
    export: dict[str, Any] = {
        "channel": {
            "id": channel_id,
            "type": channel_type,
            "name": Path(path).name,
            "category": None,
            "categoryId": parent_id,
        },
        "exportedAt": exported_at,
        "messages": [{"id": m, "type": "Default"} for m in message_ids],
    }
    (month_dir / f"{month}.json").write_text(json.dumps(export), encoding="utf-8")
    (month_dir / f"{month}.html").write_text("<html>export</html>", encoding="utf-8")
    media = month_dir / f"{month}_media"
    media.mkdir(exist_ok=True)
    (media / "image.png").write_bytes(b"png")


OLD = "2026-06-01T00:00:00+00:00"
NEW = "2026-11-01T00:00:00+00:00"


@pytest.fixture
def server_dir(tmp_path: Path) -> Path:
    """A channel renamed from Old/general to New/general, published under both."""
    root = tmp_path / "public" / "example"
    for month in ("2026-04", "2026-05"):
        _write_month(root, "Old/general", month, "1", ["10", "11"], exported_at=OLD)
        _write_month(root, "New/general", month, "1", ["10", "11"], exported_at=NEW)
    _write_month(root, "New/general", "2026-10", "1", ["20"], exported_at=NEW)
    (root / "Old/general/latest.json").write_text("{}", encoding="utf-8")
    (root / "Old/general/index.html").write_text("old index", encoding="utf-8")
    return root


def _prune(server_dir: Path, *, enabled: bool) -> tuple[int, int]:
    return prune_server(server_dir.parent, server_dir.name, BASE_URL, enabled=enabled)


@pytest.mark.unit
class TestFindStale:
    def test_renamed_channel_is_found_and_covered(self, server_dir: Path) -> None:
        stale = find_stale(server_dir)
        assert [(s.path, s.live_path, s.prunable) for s in stale] == [
            ("Old/general", "New/general", True)
        ]

    def test_month_missing_from_the_live_copy_blocks_removal(self, server_dir: Path) -> None:
        _write_month(server_dir, "Old/general", "2026-03", "1", ["5"], exported_at=OLD)
        (stale,) = find_stale(server_dir)
        assert stale.months_only_here == ["2026-03"]
        assert not stale.prunable

    def test_empty_month_missing_from_the_live_copy_does_not_block(self, server_dir: Path) -> None:
        _write_month(server_dir, "Old/general", "2026-03", "1", [], exported_at=OLD)
        (stale,) = find_stale(server_dir)
        assert stale.prunable

    def test_unreadable_month_blocks_removal(self, server_dir: Path) -> None:
        # Readable enough to identify the channel, but with no message list.
        broken = server_dir / "Old/general/2026-03"
        broken.mkdir()
        (broken / "2026-03.json").write_text(
            json.dumps({"channel": {"id": "1", "type": "GuildTextChat"}, "messages": 7}),
            encoding="utf-8",
        )
        (stale,) = find_stale(server_dir)
        assert stale.months_only_here == ["2026-03"]

    def test_message_deleted_since_the_rename_does_not_block(self, server_dir: Path) -> None:
        # The live copy is authoritative: a message that only the frozen old
        # copy still has was deleted on Discord.
        _write_month(server_dir, "Old/general", "2026-05", "1", ["10", "11", "12"], exported_at=OLD)
        (stale,) = find_stale(server_dir)
        assert stale.prunable

    def test_channel_published_once_is_not_stale(self, server_dir: Path) -> None:
        _write_month(server_dir, "New/other", "2026-10", "2", ["30"], exported_at=NEW)
        assert [s.path for s in find_stale(server_dir)] == ["Old/general"]


@pytest.mark.unit
class TestPrune:
    def test_report_only_changes_nothing(self, server_dir: Path) -> None:
        before = sorted(p for p in server_dir.rglob("*"))
        assert _prune(server_dir, enabled=False) == (1, 0)
        assert sorted(p for p in server_dir.rglob("*")) == before
        assert (server_dir / "Old/general/index.html").read_text() == "old index"

    def test_enabled_removes_exports_and_leaves_a_redirect(self, server_dir: Path) -> None:
        assert _prune(server_dir, enabled=True) == (1, 0)
        old = server_dir / "Old/general"
        assert sorted(p.name for p in old.iterdir()) == ["index.html"]
        page = (old / "index.html").read_text(encoding="utf-8")
        assert 'content="0; url=https://logs.example/example/New/general/"' in page
        assert 'rel="canonical" href="https://logs.example/example/New/general/"' in page

    def test_live_copy_is_untouched(self, server_dir: Path) -> None:
        live = server_dir / "New/general"
        before = {p: p.read_bytes() for p in live.rglob("*") if p.is_file()}
        _prune(server_dir, enabled=True)
        assert {p: p.read_bytes() for p in live.rglob("*") if p.is_file()} == before

    def test_uncovered_directory_is_kept_even_when_enabled(self, server_dir: Path) -> None:
        _write_month(server_dir, "Old/general", "2026-03", "1", ["5"], exported_at=OLD)
        assert _prune(server_dir, enabled=True) == (0, 1)
        assert (server_dir / "Old/general/2026-03/2026-03.json").is_file()
        assert (server_dir / "Old/general/2026-04/2026-04.json").is_file()
        assert (server_dir / "Old/general/index.html").read_text() == "old index"

    def test_thread_directory_under_a_pruned_channel_survives(self, server_dir: Path) -> None:
        # A thread that was never re-exported under the new name: the only
        # copy of it lives beneath the old channel directory.
        _write_month(
            server_dir,
            "Old/general/side-topic",
            "2026-05",
            "2",
            ["40"],
            exported_at=OLD,
            channel_type="GuildPublicThread",
            parent_id="1",
        )
        assert _prune(server_dir, enabled=True) == (1, 0)
        assert (server_dir / "Old/general/side-topic/2026-05/2026-05.json").is_file()
        assert not (server_dir / "Old/general/2026-05").exists()

    def test_second_run_finds_nothing(self, server_dir: Path) -> None:
        _prune(server_dir, enabled=True)
        assert _prune(server_dir, enabled=True) == (0, 0)

    def test_pruned_path_leaves_the_index(self, server_dir: Path) -> None:
        site = {"base_url": BASE_URL}
        generate_for_server(server_dir.parent, server_dir.name, {"name": "Example"}, site)
        index = json.loads((server_dir / "index.json").read_text(encoding="utf-8"))
        assert index["channels"][0]["stale_paths"] == ["Old/general"]

        _prune(server_dir, enabled=True)
        generate_for_server(server_dir.parent, server_dir.name, {"name": "Example"}, site)
        index = json.loads((server_dir / "index.json").read_text(encoding="utf-8"))
        assert [(c["path"], c["stale_paths"]) for c in index["channels"]] == [("New/general", [])]
        assert not (server_dir / "Old/general/feed.atom").exists()
