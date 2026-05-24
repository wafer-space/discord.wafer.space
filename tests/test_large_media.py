"""Tests for scripts/large_media.py — holding back oversized media.

GitHub rejects any file >100MB on push and GitHub Pages can't serve files
that big, so a single oversized Discord attachment blocks the whole
gh-pages deploy. These tests pin down how we detect such files in the
built ``public/`` tree, record metadata about them, rewrite the chat HTML/
JSON references to a servable URL, and remove the binary from what gets
deployed.
"""

import json
from pathlib import Path

import pytest

from scripts.large_media import (
    DEFAULT_REF,
    DEFAULT_REPO,
    iter_oversized_media,
    lfs_media_url,
    process_oversized_media,
    reconstruct_discord_cdn_url,
)

# A byte budget tiny enough that test fixtures stay small but still exercise
# the ">limit" branch without writing megabytes to disk.
TINY_LIMIT = 100


def _make_month_export(  # noqa: PLR0913  # keyword-only fixture knobs
    channel_dir: Path,
    month: str,
    *,
    media_name: str,
    media_bytes: bytes,
    attachment_id: str = "999",
    channel_id: str = "555",
    orig_name: str = "huge.gds.zst",
) -> Path:
    """Build a realistic per-month export: HTML + JSON + media dir.

    Returns the path to the oversized media file.
    """
    month_dir = channel_dir / month
    media_dir = month_dir / f"{month}_media"
    media_dir.mkdir(parents=True, exist_ok=True)
    media_file = media_dir / media_name
    media_file.write_bytes(media_bytes)

    rel_ref = f"{month}_media/{media_name}"
    (month_dir / f"{month}.html").write_text(
        f'<html><body><a href="{rel_ref}">{orig_name}</a></body></html>',
        encoding="utf-8",
    )
    (month_dir / f"{month}.json").write_text(
        json.dumps(
            {
                "channel": {"id": channel_id, "name": "questions"},
                "messages": [
                    {
                        "id": "1",
                        "timestamp": f"{month}-02T00:00:00+00:00",
                        "attachments": [
                            {
                                "id": attachment_id,
                                "url": rel_ref,
                                "fileName": orig_name,
                                "fileSizeBytes": len(media_bytes),
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return media_file


def test_iter_oversized_media_finds_only_big_files(tmp_path: Path) -> None:
    """iter_oversized_media yields files strictly larger than the limit."""
    pub = tmp_path / "public"
    chan = pub / "srv" / "questions"
    big = _make_month_export(
        chan, "2026-05", media_name="big.zst", media_bytes=b"x" * (TINY_LIMIT + 50)
    )
    # A small sibling media file must NOT be flagged.
    (big.parent / "small.png").write_bytes(b"y" * 10)

    found = list(iter_oversized_media(pub, max_bytes=TINY_LIMIT))
    assert found == [big]


def test_iter_oversized_media_empty_when_all_small(tmp_path: Path) -> None:
    """No oversized files → empty iterator (and missing dir is safe)."""
    pub = tmp_path / "public"
    _make_month_export(pub / "srv" / "q", "2026-05", media_name="ok.png", media_bytes=b"z" * 10)
    assert list(iter_oversized_media(pub, max_bytes=TINY_LIMIT)) == []
    assert list(iter_oversized_media(tmp_path / "nope", max_bytes=TINY_LIMIT)) == []


def test_reconstruct_discord_cdn_url() -> None:
    """Bare CDN URL is rebuilt from channel id, attachment id and filename."""
    url = reconstruct_discord_cdn_url("555", "999", "my file.gds.zst")
    # Filename segment must be URL-encoded (space → %20).
    assert url == "https://cdn.discordapp.com/attachments/555/999/my%20file.gds.zst"


def test_lfs_media_url_builds_servable_url() -> None:
    """The LFS media URL is the media.githubusercontent.com form that serves real bytes."""
    url = lfs_media_url("large_media/srv/questions/2026-05/2026-05_media/big.zst")
    assert url == (
        f"https://media.githubusercontent.com/media/{DEFAULT_REPO}/{DEFAULT_REF}/"
        "large_media/srv/questions/2026-05/2026-05_media/big.zst"
    )


def test_process_removes_file_and_writes_metadata(tmp_path: Path) -> None:
    """An oversized file is removed from public/ and a metadata sidecar written."""
    pub = tmp_path / "public"
    chan = pub / "srv" / "questions"
    media = _make_month_export(
        chan,
        "2026-05",
        media_name="big-AB12.gds.zst",
        media_bytes=b"x" * (TINY_LIMIT + 200),
        attachment_id="42",
        channel_id="7",
        orig_name="big.gds.zst",
    )

    records = process_oversized_media(pub, max_bytes=TINY_LIMIT)

    # The binary must be gone from the deployable tree.
    assert not media.exists()
    # A sidecar recording the file must exist next to where it was.
    sidecar = media.with_name(media.name + ".toobig.json")
    assert sidecar.exists()
    meta = json.loads(sidecar.read_text())
    assert meta["fileName"] == "big.gds.zst"
    assert meta["attachmentId"] == "42"
    assert meta["channelId"] == "7"
    assert meta["sizeBytes"] == TINY_LIMIT + 200
    assert meta["discordUrl"].startswith("https://cdn.discordapp.com/attachments/7/42/")
    assert meta["lfsUrl"].startswith("https://media.githubusercontent.com/media/")
    # And the returned record mirrors the sidecar.
    assert len(records) == 1
    assert records[0]["lfsPath"].endswith("2026-05_media/big-AB12.gds.zst")


def test_process_rewrites_html_and_json_links(tmp_path: Path) -> None:
    """The chat HTML href and JSON attachment url point at the servable LFS URL."""
    pub = tmp_path / "public"
    chan = pub / "srv" / "questions"
    media = _make_month_export(
        chan, "2026-05", media_name="big.zst", media_bytes=b"x" * (TINY_LIMIT + 5)
    )
    month_dir = media.parent.parent

    process_oversized_media(pub, max_bytes=TINY_LIMIT)

    html = (month_dir / "2026-05.html").read_text()
    # The standalone local href must be gone — but note the local relative
    # path also appears *inside* the new LFS URL (.../large_media/.../big.zst),
    # so we check the href attribute form rather than the bare substring.
    assert 'href="2026-05_media/big.zst"' not in html
    assert 'href="https://media.githubusercontent.com/media/' in html

    data = json.loads((month_dir / "2026-05.json").read_text())
    att = data["messages"][0]["attachments"][0]
    assert att["url"].startswith("https://media.githubusercontent.com/media/")
    # Original local path preserved for the record under a new key.
    assert att["originalUrl"] == "2026-05_media/big.zst"


def test_process_stages_bytes_for_lfs_when_dir_given(tmp_path: Path) -> None:
    """When a staging dir is given, the bytes are moved there (preserved for LFS)."""
    pub = tmp_path / "public"
    staging = tmp_path / "large_media"
    chan = pub / "srv" / "questions"
    payload = b"x" * (TINY_LIMIT + 7)
    media = _make_month_export(chan, "2026-05", media_name="big.zst", media_bytes=payload)

    process_oversized_media(pub, max_bytes=TINY_LIMIT, lfs_staging_dir=staging)

    staged = staging / "srv" / "questions" / "2026-05" / "2026-05_media" / "big.zst"
    assert staged.exists()
    assert staged.read_bytes() == payload
    assert not media.exists()


def test_process_is_idempotent_across_runs(tmp_path: Path) -> None:
    """Running twice does not error and leaves a single clean result.

    The export pipeline rebuilds public/ every hour, so the same oversized
    file reappears and must be re-offloaded without crashing or duplicating.
    """
    pub = tmp_path / "public"
    staging = tmp_path / "large_media"
    chan = pub / "srv" / "questions"
    _make_month_export(chan, "2026-05", media_name="big.zst", media_bytes=b"x" * (TINY_LIMIT + 9))

    first = process_oversized_media(pub, max_bytes=TINY_LIMIT, lfs_staging_dir=staging)
    # Simulate the next hourly run rebuilding the same oversized file.
    _make_month_export(chan, "2026-05", media_name="big.zst", media_bytes=b"x" * (TINY_LIMIT + 9))
    second = process_oversized_media(pub, max_bytes=TINY_LIMIT, lfs_staging_dir=staging)

    assert len(first) == 1
    assert len(second) == 1
    staged = staging / "srv" / "questions" / "2026-05" / "2026-05_media" / "big.zst"
    assert staged.exists()


def test_lfs_url_matches_staged_location(tmp_path: Path) -> None:
    """The link the site serves must point at where the bytes actually land.

    The published page links to ``lfsUrl``; the workflow commits the bytes to
    ``large_media/<relpath>`` on master. If these diverge the download 404s, so
    we pin that the staged path (under a staging dir named like the LFS prefix)
    equals the ``lfsPath`` embedded in the URL.
    """
    pub = tmp_path / "public"
    staging = tmp_path / "large_media"  # named to match the default lfs prefix
    chan = pub / "srv" / "questions"
    _make_month_export(chan, "2026-05", media_name="big.zst", media_bytes=b"x" * (TINY_LIMIT + 1))

    [record] = process_oversized_media(pub, max_bytes=TINY_LIMIT, lfs_staging_dir=staging)

    # lfsPath is "large_media/<relpath>"; the bytes must sit at staging/<relpath>.
    rel_under_prefix = record["lfsPath"].split("/", 1)[1]
    assert (staging / rel_under_prefix).exists()
    # And the servable URL must end with exactly that lfsPath.
    assert record["lfsUrl"].endswith(record["lfsPath"])


def test_process_handles_missing_json_gracefully(tmp_path: Path) -> None:
    """A media file with no resolvable attachment metadata is still offloaded.

    We must never let a malformed/absent JSON keep an oversized file in the
    deploy — that would re-break the push. Metadata fields fall back to None.
    """
    pub = tmp_path / "public"
    media_dir = pub / "srv" / "q" / "2026-05" / "2026-05_media"
    media_dir.mkdir(parents=True)
    media = media_dir / "orphan.zst"
    media.write_bytes(b"x" * (TINY_LIMIT + 3))

    records = process_oversized_media(pub, max_bytes=TINY_LIMIT)

    assert not media.exists()
    assert len(records) == 1
    assert records[0]["attachmentId"] is None
    assert records[0]["discordUrl"] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
