"""Retention trash for the media of deleted conversations (DATA-01).

Deleting a conversation in the app is not the same operation as erasing its
original recording (storage-policy). The media folder is therefore moved to
``<data>/trash/<stamp>-<item_id>/`` with a ``trash.json`` manifest, and removed
for good only after the retention period, at startup.
"""

from __future__ import annotations

import json
import re
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from .durable_files import durable_write_json

TRASH_MANIFEST = "trash.json"
_ENTRY_NAME = re.compile(r"\d{8}T\d{6}Z-.+")


def _utc(value: datetime | None) -> datetime:
    return (value or datetime.now(timezone.utc)).astimezone(timezone.utc)


def trash_media(
    trash_root: Path,
    item_id: str,
    source_name: str,
    assets: list[Path],
    *,
    retention_days: int,
    move: Callable[..., None],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Move ``assets`` into a new trash entry and return its manifest.

    The manifest is written before any move so that an interrupted move still
    leaves an entry the purge step can date.
    """
    deleted_at = _utc(now)
    entry = Path(trash_root) / f"{deleted_at:%Y%m%dT%H%M%SZ}-{item_id}"
    suffix = 1
    while entry.exists():
        suffix += 1
        entry = Path(trash_root) / f"{deleted_at:%Y%m%dT%H%M%SZ}-{item_id}-{suffix}"
    entry.mkdir(parents=True)
    manifest = {
        "item_id": item_id,
        "source_name": source_name,
        "deleted_at": deleted_at.isoformat(timespec="seconds"),
        "expires_at": (deleted_at + timedelta(days=retention_days)).isoformat(timespec="seconds"),
        "contents": [asset.name for asset in assets],
    }
    durable_write_json(entry / TRASH_MANIFEST, manifest)
    for asset in assets:
        move(asset, entry / asset.name, replace_existing=False)
    return {**manifest, "path": entry}


def purge_expired_trash(
    trash_root: Path,
    retention_days: int,
    *,
    now: datetime | None = None,
) -> list[str]:
    """Erase trash entries older than the retention period; return warnings.

    Entries without a readable manifest are kept: their age is unknown, and
    they may be something a person placed there.
    """
    root = Path(trash_root)
    if not root.is_dir():
        return []
    current = _utc(now)
    warnings: list[str] = []
    for entry in sorted(root.iterdir()):
        if entry.is_symlink() or not entry.is_dir() or not _ENTRY_NAME.fullmatch(entry.name):
            continue
        try:
            manifest = json.loads((entry / TRASH_MANIFEST).read_text(encoding="utf-8"))
            deleted_at = datetime.fromisoformat(str(manifest["deleted_at"]))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            warnings.append(f"Trash entry without a readable manifest retained: {entry.name} ({exc})")
            continue
        if deleted_at.tzinfo is None:
            deleted_at = deleted_at.replace(tzinfo=timezone.utc)
        if current - deleted_at < timedelta(days=retention_days):
            continue
        try:
            shutil.rmtree(entry)
        except OSError as exc:
            warnings.append(f"Could not erase expired trash entry {entry.name}: {exc}")
    return warnings
