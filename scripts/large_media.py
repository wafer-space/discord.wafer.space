#!/usr/bin/env python3
# scripts/large_media.py
"""Hold back media files too large for GitHub to host.

GitHub rejects any file larger than 100 MB on push, and GitHub Pages can't
serve files that big either. A single oversized Discord attachment — e.g. a
215 MB compressed GDS dump posted to a channel — therefore blocks the
*entire* ``gh-pages`` deploy: the push is rejected and nothing updates.

This module runs over the built ``public/`` tree after organize/navigate and
before deploy. For each media file above the limit it:

  1. records a metadata sidecar (``<file>.toobig.json``) describing the file,
  2. rewrites the chat HTML/JSON reference so the link points at a *servable*
     URL instead of a soon-to-be-missing local file, and
  3. removes the binary from ``public/`` so the deploy push succeeds —
     optionally moving the bytes into a staging directory so the workflow can
     preserve them in Git LFS on the ``master`` branch.

The servable URL is GitHub's LFS media endpoint
(``media.githubusercontent.com/media/...``), which returns the real bytes of
an LFS-tracked file (unlike GitHub Pages, which only sees the LFS pointer).
A best-effort reconstructed Discord CDN URL is also recorded, but Discord's
signed-URL requirement means bare reconstructed URLs often 403 — the LFS copy
is the reliable one.
"""

from __future__ import annotations

import json
import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import quote

# GitHub's hard push limit is 100 MB and its "large file" warning starts at
# 50 MB. We hold back at 50 MB so the published site and repo stay lean and
# we never approach the hard wall.
DEFAULT_MAX_BYTES = 50 * 1024 * 1024

# Where the preserved bytes live (LFS-tracked) on the master branch, and how
# the published site reaches them.
DEFAULT_REPO = "wafer-space/discord.wafer.space"
DEFAULT_REF = "master"
LFS_PREFIX = "large_media"

_MEDIA_DIR_SUFFIX = "_media"
_SIDECAR_SUFFIX = ".toobig.json"


def iter_oversized_media(public_dir: Path, *, max_bytes: int = DEFAULT_MAX_BYTES) -> Iterator[Path]:
    """Yield media files under ``public_dir`` larger than ``max_bytes``.

    Only files inside a ``*_media`` directory are considered: those are
    downloaded Discord attachments. Month JSON/HTML files are never offloaded
    here even if large — those hold *messages*, which we never drop.
    """
    if not public_dir.exists():
        return
    for path in sorted(public_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name.endswith(_SIDECAR_SUFFIX):
            continue
        if not path.parent.name.endswith(_MEDIA_DIR_SUFFIX):
            continue
        try:
            if path.stat().st_size > max_bytes:
                yield path
        except OSError:
            continue


def reconstruct_discord_cdn_url(
    channel_id: str | None, attachment_id: str | None, file_name: str | None
) -> str | None:
    """Rebuild the canonical Discord CDN URL for an attachment, or None.

    Discord attachment URLs have the stable shape
    ``cdn.discordapp.com/attachments/<channel_id>/<attachment_id>/<file>``.
    The filename segment is percent-encoded. Returns None when any component
    is missing (the JSON was malformed or absent).
    """
    if not (channel_id and attachment_id and file_name):
        return None
    encoded = quote(file_name, safe="")
    return f"https://cdn.discordapp.com/attachments/{channel_id}/{attachment_id}/{encoded}"


def lfs_media_url(lfs_path: str, *, repo: str = DEFAULT_REPO, ref: str = DEFAULT_REF) -> str:
    """Return the media.githubusercontent.com URL that serves an LFS file.

    Unlike GitHub Pages (which serves only the LFS pointer), this endpoint
    redirects to the real object storage and returns the actual bytes.
    """
    encoded_path = quote(lfs_path, safe="/")
    return f"https://media.githubusercontent.com/media/{repo}/{ref}/{encoded_path}"


def _lookup_attachment(json_file: Path, rel_ref: str) -> dict[str, str | None]:
    """Find the attachment whose local ``url`` matches ``rel_ref``.

    Returns a dict with channelId / attachmentId / fileName, each possibly
    None when the JSON is missing, unreadable, or has no matching attachment.
    """
    result: dict[str, str | None] = {"channelId": None, "attachmentId": None, "fileName": None}
    try:
        data = json.loads(json_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return result

    channel_id = (data.get("channel") or {}).get("id")
    result["channelId"] = channel_id
    for message in data.get("messages", []):
        for att in message.get("attachments") or []:
            if att.get("url") == rel_ref:
                result["attachmentId"] = att.get("id")
                result["fileName"] = att.get("fileName")
                return result
    return result


def _rewrite_text_refs(month_dir: Path, month: str, rel_ref: str, replacement: str) -> None:
    """Swap ``rel_ref`` for ``replacement`` in the month's HTML/TXT/CSV files.

    Handles both the literal and percent-encoded forms of the reference, since
    DCE percent-encodes special characters inside ``href`` attributes.
    """
    encoded_ref = quote(rel_ref, safe="/")
    for ext in ("html", "txt", "csv"):
        f = month_dir / f"{month}.{ext}"
        if not f.exists():
            continue
        text = f.read_text(encoding="utf-8", errors="replace")
        new = text.replace(rel_ref, replacement)
        if encoded_ref != rel_ref:
            new = new.replace(encoded_ref, replacement)
        if new != text:
            f.write_text(new, encoding="utf-8")


def _rewrite_json_ref(json_file: Path, rel_ref: str, replacement: str) -> None:
    """Repoint the matching attachment ``url``, preserving the local path."""
    if not json_file.exists():
        return
    try:
        data = json.loads(json_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return
    changed = False
    for message in data.get("messages", []):
        for att in message.get("attachments") or []:
            if att.get("url") == rel_ref:
                att["originalUrl"] = rel_ref
                att["url"] = replacement
                changed = True
    if changed:
        json_file.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _rewrite_local_refs(month_dir: Path, month: str, rel_ref: str, replacement: str) -> None:
    """Point every reference to ``rel_ref`` in the month's files at ``replacement``."""
    _rewrite_text_refs(month_dir, month, rel_ref, replacement)
    _rewrite_json_ref(month_dir / f"{month}.json", rel_ref, replacement)


def _stage_for_lfs(media_file: Path, relative: Path, lfs_staging_dir: Path) -> None:
    """Move the oversized file into the LFS staging tree, preserving layout."""
    dest = lfs_staging_dir / relative
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        dest.unlink()
    shutil.move(str(media_file), str(dest))


def process_oversized_media(  # noqa: PLR0913  # keyword-only repo/ref/prefix config knobs
    public_dir: Path,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    lfs_staging_dir: Path | None = None,
    repo: str = DEFAULT_REPO,
    ref: str = DEFAULT_REF,
    lfs_prefix: str = LFS_PREFIX,
) -> list[dict[str, Any]]:
    """Hold back every oversized media file under ``public_dir``.

    Returns one metadata record per offloaded file. Idempotent: safe to run
    on every export cycle even though the pipeline rebuilds ``public/`` each
    time and the same oversized file reappears.
    """
    records: list[dict[str, Any]] = []
    for media_file in iter_oversized_media(public_dir, max_bytes=max_bytes):
        relative = media_file.relative_to(public_dir)
        media_dir = media_file.parent
        month_dir = media_dir.parent
        month = month_dir.name
        rel_ref = f"{media_dir.name}/{media_file.name}"
        size_bytes = media_file.stat().st_size

        att = _lookup_attachment(month_dir / f"{month}.json", rel_ref)
        lfs_path = f"{lfs_prefix}/{relative.as_posix()}"
        url = lfs_media_url(lfs_path, repo=repo, ref=ref)
        discord_url = reconstruct_discord_cdn_url(
            att["channelId"], att["attachmentId"], att["fileName"]
        )

        record: dict[str, Any] = {
            "fileName": att["fileName"] or media_file.name,
            "sizeBytes": size_bytes,
            "attachmentId": att["attachmentId"],
            "channelId": att["channelId"],
            "originalUrl": rel_ref,
            "lfsPath": lfs_path,
            "lfsUrl": url,
            "discordUrl": discord_url,
        }

        sidecar = media_file.with_name(media_file.name + _SIDECAR_SUFFIX)
        sidecar.write_text(json.dumps(record, indent=2), encoding="utf-8")
        _rewrite_local_refs(month_dir, month, rel_ref, url)

        if lfs_staging_dir is not None:
            _stage_for_lfs(media_file, relative, lfs_staging_dir)
        elif media_file.exists():
            media_file.unlink()

        records.append(record)
    return records


def main() -> None:
    """CLI entry point: hold back oversized media in ``public/``."""
    import os
    import sys

    public_dir = Path("public")
    staging = Path(os.environ.get("LARGE_MEDIA_STAGING", "")) or None
    max_bytes = int(os.environ.get("LARGE_MEDIA_MAX_BYTES", DEFAULT_MAX_BYTES))

    print("Oversized media hold-back")
    print("=" * 50)
    if not public_dir.exists():
        print("No public/ directory; nothing to do.")
        return
    records = process_oversized_media(public_dir, max_bytes=max_bytes, lfs_staging_dir=staging)
    if not records:
        print(f"No media files exceed {max_bytes / 1024 / 1024:.0f} MB.")
        return
    for r in records:
        print(f"  ↳ held back {r['sizeBytes'] / 1024 / 1024:.1f} MB  {r['lfsPath']}")
    print(f"\nHeld back {len(records)} oversized file(s); deploy push will now succeed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
