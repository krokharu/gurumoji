"""Bounded, optional JPEG extraction from an item's permitted saved video."""

from __future__ import annotations

import io
import math
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path

from .ai_data_export import ExportError
from .media_files import is_unc_path, is_video_path

FRAME_BYTES = 2 * 1024 * 1024
TOTAL_BYTES = 32 * 1024 * 1024
BUDGET_SECONDS = 30


def media_identity(path):
    stat = path.stat()
    return {"device": stat.st_dev, "inode": stat.st_ino, "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns, "ctime_ns": stat.st_ctime_ns}


def permitted_media(row, media_directory, path_is_within):
    raw = row["media_path"]
    if not raw:
        raise ExportError("missing_media", 422, frame_status="unavailable")
    path = Path(raw)
    item_id = row["id"]
    if not isinstance(item_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", item_id) or \
            is_unc_path(raw) or media_directory is None or path_is_within is None:
        raise ExportError("media_not_permitted", 422, frame_status="unavailable")
    try:
        base = Path(media_directory()).resolve()
        item_root = (base / item_id).resolve()
        if item_root.parent != base or not path_is_within(path, item_root):
            raise ExportError("media_not_permitted", 422, frame_status="unavailable")
        if not path.is_file():
            raise ExportError("missing_media", 422, frame_status="unavailable")
        if not is_video_path(path):
            raise ExportError("audio_only", 422, frame_status="unsupported")
        return path.resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ExportError("missing_media", 422, frame_status="unavailable") from exc


def verify_media_unchanged(row, path, identity, media_directory, path_is_within):
    try:
        unchanged = permitted_media(row, media_directory, path_is_within) == path and media_identity(path) == identity
    except (OSError, ExportError):
        unchanged = False
    if not unchanged:
        raise ExportError("media_changed", 409, frame_status="failed")


def _run_bounded(args, deadline, check_cancelled):
    """Drain pipes with hard byte caps and a single shared extraction deadline."""
    process = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    buffers = [bytearray(), bytearray()]
    overflow = threading.Event()

    def drain(stream, index, maximum):
        try:
            while True:
                chunk = stream.read(65536)
                if not chunk:
                    break
                if len(buffers[index]) + len(chunk) > maximum:
                    overflow.set()
                    process.kill()
                    break
                buffers[index].extend(chunk)
        finally:
            stream.close()

    threads = [threading.Thread(target=drain, args=(process.stdout, 0, FRAME_BYTES), daemon=True),
               threading.Thread(target=drain, args=(process.stderr, 1, 65536), daemon=True)]
    try:
        for thread in threads:
            thread.start()
        while process.poll() is None:
            if check_cancelled:
                check_cancelled()
            if time.monotonic() >= deadline:
                raise ExportError("frame_timeout", 408, frame_status="failed")
            time.sleep(0.01)
        for thread in threads:
            thread.join(timeout=max(0.01, deadline - time.monotonic()))
        if any(thread.is_alive() for thread in threads) or time.monotonic() >= deadline:
            raise ExportError("frame_timeout", 408, frame_status="failed")
        if overflow.is_set():
            raise ExportError("frame_output_limit", 422, frame_status="failed")
        return process.returncode, bytes(buffers[0]), bytes(buffers[1])
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)
        for thread in threads:
            if thread.ident:
                thread.join(timeout=2)


def extract_frames(row, rows, options, *, media_directory, path_is_within, check_cancelled=None):
    path = permitted_media(row, media_directory, path_is_within)
    try:
        identity = media_identity(path)
    except OSError as exc:
        raise ExportError("missing_media", 422, frame_status="unavailable") from exc
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise ExportError("ffmpeg_unavailable", 422, frame_status="unavailable")
    deadline = time.monotonic() + BUDGET_SECONDS
    items, total = [], 0
    try:
        from PIL import Image

        for number, timestamp in enumerate(options["times"], 1):
            if check_cancelled:
                check_cancelled()
            if time.monotonic() >= deadline:
                raise ExportError("frame_timeout", 408, frame_status="failed")
            verify_media_unchanged(row, path, identity, media_directory, path_is_within)
            dimension = options["max_dimension"]
            result, data, stderr = _run_bounded([
                ffmpeg, "-hide_banner", "-loglevel", "info", "-nostdin", "-copyts",
                "-ss", str(timestamp), "-protocol_whitelist", "file,pipe", "-i", str(path), "-map", "0:v:0", "-an", "-sn", "-dn",
                "-vf", f"scale=w='min({dimension},iw)':h='min({dimension},ih)':force_original_aspect_ratio=decrease,showinfo",
                "-frames:v", "1", "-c:v", "mjpeg", "-q:v", "3", "-f", "image2pipe", "pipe:1",
            ], deadline, check_cancelled)
            if result or not data:
                raise ExportError("frame_extraction_failed", 422, frame_status="partial" if items else "failed")
            if len(data) > FRAME_BYTES or not data.startswith(b"\xff\xd8") or not data.endswith(b"\xff\xd9"):
                raise ExportError("invalid_jpeg", 422, frame_status="partial" if items else "failed")
            with Image.open(io.BytesIO(data)) as image:
                if image.format != "JPEG" or min(image.size) < 1 or max(image.size) > dimension:
                    raise ExportError("frame_dimensions", 422, frame_status="failed")
                image.load()
            total += len(data)
            if total > TOTAL_BYTES:
                raise ExportError("frame_total_limit", 422, frame_status="partial")
            match = re.search(rb"\bpts_time:([+-]?[0-9]+(?:\.[0-9]+)?(?:e[+-]?[0-9]+)?)", stderr)
            actual = float(match[1]) if match else None
            if actual is not None and (not math.isfinite(actual) or actual < 0):
                actual = None
            ids = [turn["segment_id"] for turn in rows if actual is not None and
                   turn["start"] is not None and turn["end"] is not None and
                   turn["start"] <= actual <= turn["end"]]
            items.append({"frame_id": f"f{number:04d}", "requested_time": timestamp,
                          "actual_time": actual, "method": "ffmpeg_showinfo_pts" if actual is not None else "ffmpeg_pts_unavailable",
                          "utterance_ids": ids, "data": data})
        verify_media_unchanged(row, path, identity, media_directory, path_is_within)
        if check_cancelled:
            check_cancelled()
        if time.monotonic() >= deadline:
            raise ExportError("frame_timeout", 408, frame_status="failed")
    except InterruptedError as exc:
        raise ExportError("frame_cancelled", 422, frame_status="cancelled") from exc
    except (OSError, ImportError, ValueError, subprocess.SubprocessError) as exc:
        raise ExportError("frame_extraction_failed", 422, frame_status="partial" if items else "failed") from exc
    return {"status": "complete", "reason": None,
            "media": {"kind": "video", "identity": identity, "identity_hash_domain": "stat_identity"}, "items": items}
