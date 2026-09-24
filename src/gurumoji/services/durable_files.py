"""Durable file placement primitives.

Every output the user can lose -- a transcript, a thumbnail, an edit staging
tree -- is written to a sibling temporary file and moved into place only once
its bytes are on disk.  The Windows and POSIX move paths differ enough that
they are kept side by side here rather than spread across the callers.

``_ORIGINAL_OS_REPLACE`` is captured at import so the move helpers can tell a
genuine platform rename from one a test has replaced.
"""

from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import ntpath
import os
import re
import secrets
import shutil
import stat
import sys
import uuid
from pathlib import Path
from typing import Any, Callable

_ORIGINAL_OS_REPLACE = os.replace


def path_is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def windows_case_insensitive_text(value: str) -> str:
    if os.name == 'nt':
        return ntpath.normcase(value)
    # Python's Unicode lower() performs multi-code-point expansions that the
    # Windows invariant mapping does not. Keep those characters unexpanded.
    return ''.join(
        lowered if len(lowered := character.lower()) == 1 else character
        for character in value
    )


def sync_directory_metadata(directory: Path, *, required: bool = False) -> None:
    # POSIX requires an explicit directory sync for durable rename metadata.
    if os.name == 'nt':
        return
    directory_fd: int | None = None
    try:
        directory_fd = os.open(str(directory), os.O_RDONLY)
        os.fsync(directory_fd)
    except OSError as exc:
        unsupported = {
            errno.EINVAL,
            getattr(errno, 'ENOTSUP', errno.EINVAL),
            getattr(errno, 'EOPNOTSUPP', errno.EINVAL),
        }
        if required and exc.errno not in unsupported:
            raise
    finally:
        if directory_fd is not None:
            os.close(directory_fd)


def sync_file_data(path: Path) -> None:
    with path.open('r+b') as stream:
        stream.flush()
        os.fsync(stream.fileno())


def sync_rename_metadata(
    source: Path,
    destination: Path,
    *,
    required: bool = False,
) -> None:
    sync_directory_metadata(source.parent, required=required)
    if destination.parent != source.parent:
        sync_directory_metadata(destination.parent, required=required)


def windows_extended_path(path: Path) -> str:
    supplied = os.fspath(path)
    if supplied.lower().startswith('\\\\.\\'):
        raise OSError('Windows device namespace paths are not supported.')
    raw = os.path.abspath(supplied)
    lowered = raw.lower()
    if lowered.startswith('\\\\.\\'):
        raise OSError('Windows device namespace paths are not supported.')
    if lowered.startswith('\\\\?\\'):
        extended_tail = raw[4:]
        if not (
            re.match(r'^[A-Za-z]:\\', extended_tail)
            or extended_tail.lower().startswith('unc\\')
        ):
            raise OSError('Unsupported Windows extended namespace path.')
        return raw
    if raw.startswith('\\\\'):
        return '\\\\?\\UNC\\' + raw.lstrip('\\')
    return '\\\\?\\' + raw


def windows_move_file_write_through(
    source: Path,
    destination: Path,
    *,
    replace_existing: bool,
) -> None:
    move_file_ex = ctypes.WinDLL('kernel32', use_last_error=True).MoveFileExW
    move_file_ex.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint32]
    move_file_ex.restype = ctypes.c_int
    flags = 0x8 | (0x1 if replace_existing else 0)
    if not move_file_ex(
        windows_extended_path(source),
        windows_extended_path(destination),
        flags,
    ):
        raise ctypes.WinError(ctypes.get_last_error())


def posix_move_no_replace(source: Path, destination: Path) -> None:
    rename_function = None
    rename_flags = 0
    if sys.platform.startswith('linux'):
        rename_function = getattr(ctypes.CDLL(None, use_errno=True), 'renameat2', None)
        rename_flags = 0x1
    elif sys.platform == 'darwin':
        rename_function = getattr(ctypes.CDLL(None, use_errno=True), 'renamex_np', None)
        rename_flags = 0x4
    if rename_function is not None:
        rename_function.argtypes = (
            [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
            if sys.platform.startswith('linux')
            else [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        )
        rename_function.restype = ctypes.c_int
        encoded_source = os.fsencode(source)
        encoded_destination = os.fsencode(destination)
        result = (
            rename_function(-100, encoded_source, -100, encoded_destination, rename_flags)
            if sys.platform.startswith('linux')
            else rename_function(encoded_source, encoded_destination, rename_flags)
        )
        if result == 0:
            return
        failure = ctypes.get_errno()
        if failure not in {errno.ENOSYS, errno.EINVAL, errno.ENOTSUP}:
            raise OSError(failure, os.strerror(failure), str(destination))
    if source.is_file() and not source.is_symlink():
        os.link(source, destination)
        source.unlink()
        return
    raise OSError(
        errno.ENOTSUP,
        'Atomic no-replace directory rename is not supported on this platform.',
        str(destination),
    )


def durable_move(
    source: Path,
    destination: Path,
    *,
    replace_existing: bool = True,
) -> None:
    source = Path(source)
    destination = Path(destination)
    if os.name == 'nt' and os.replace is _ORIGINAL_OS_REPLACE:
        windows_move_file_write_through(
            source,
            destination,
            replace_existing=replace_existing,
        )
    elif (
        os.name != 'nt'
        and not replace_existing
        and os.replace is _ORIGINAL_OS_REPLACE
    ):
        posix_move_no_replace(source, destination)
    else:
        if not replace_existing and (
            destination.exists() or destination.is_symlink()
        ):
            raise FileExistsError(str(destination))
        os.replace(source, destination)
    sync_rename_metadata(source, destination, required=True)


def durable_write_json(target: Path, payload: dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f'.{target.name}.{uuid.uuid4().hex}.tmp')
    try:
        with temporary.open('w', encoding='utf-8', newline='\n') as stream:
            json.dump(payload, stream, ensure_ascii=False, separators=(',', ':'))
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        durable_move(temporary, target)
        with target.open('r+b') as stream:
            os.fsync(stream.fileno())
        sync_directory_metadata(target.parent)
    finally:
        temporary.unlink(missing_ok=True)


def file_matches_fingerprint(path: Path, expected_sha256: str, expected_size: int) -> bool:
    if not path.is_file() or path.is_symlink():
        return False
    try:
        if path.stat().st_size != expected_size:
            return False
        return secrets.compare_digest(file_sha256(path), expected_sha256)
    except OSError:
        return False


def path_is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(os.path, 'isjunction', None)
    if callable(is_junction) and is_junction(path):
        return True
    try:
        attributes = int(getattr(path.lstat(), 'st_file_attributes', 0) or 0)
    except OSError:
        return False
    reparse_flag = int(getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400))
    return bool(attributes & reparse_flag)


def path_has_reparse_ancestor(path: Path) -> bool:
    absolute = Path(os.path.abspath(os.fspath(path)))
    parts = absolute.parts
    if not parts:
        return False
    current = Path(parts[0])
    start = 1
    if not absolute.anchor:
        current = Path()
        start = 0
    for part in parts[start:]:
        current = current / part
        try:
            current.lstat()
        except FileNotFoundError:
            continue
        except OSError:
            return True
        if path_is_link_or_reparse(current):
            return True
    return False


def ensure_staging_tree_has_no_reparse_points(staging_root: Path) -> None:
    if path_is_link_or_reparse(staging_root):
        raise OSError('An edit staging directory is a symbolic link or reparse point.')
    if not staging_root.is_dir():
        raise OSError('An edit staging path is not a directory.')
    for current, directory_names, file_names in os.walk(
        staging_root, topdown=True, followlinks=False
    ):
        for name in [*directory_names, *file_names]:
            candidate = Path(current) / name
            if path_is_link_or_reparse(candidate):
                raise OSError('An edit staging tree contains a symbolic link or reparse point.')


def path_entry_exists(path: Path) -> bool:
    return path.exists() or path.is_symlink()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def temporary_output_path(target: Path) -> Path:
    """Create a collision-resistant sibling name that preserves file suffix."""
    return target.with_name(f".{target.stem}.{uuid.uuid4().hex}.tmp{target.suffix}")


def atomic_write_text(target: Path, value: str, *, encoding: str = "utf-8") -> Path:
    """Replace one text output only after its complete temporary file is durable."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = temporary_output_path(target)
    try:
        with temporary.open('w', encoding=encoding) as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        durable_move(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def atomic_write_bytes(target: Path, value: bytes) -> Path:
    """Replace a binary file only after its sibling temporary file is complete."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = temporary_output_path(target)
    try:
        with temporary.open('wb') as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        durable_move(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


def atomic_copy_file(
    source: Path,
    target: Path,
    check_cancelled: Callable[[], None] | None = None,
    *,
    replace_existing: bool = True,
) -> Path:
    """Copy a media file without exposing a partial final destination."""
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = temporary_output_path(target)
    try:
        if check_cancelled is not None:
            check_cancelled()
        with source.open("rb") as input_stream, temporary.open("wb") as output_stream:
            while True:
                chunk = input_stream.read(1024 * 1024)
                if not chunk:
                    break
                output_stream.write(chunk)
                if check_cancelled is not None:
                    check_cancelled()
            output_stream.flush()
            os.fsync(output_stream.fileno())
        shutil.copystat(source, temporary)
        with temporary.open('r+b') as output_stream:
            os.fsync(output_stream.fileno())
        if check_cancelled is not None:
            check_cancelled()
        durable_move(
            temporary,
            target,
            replace_existing=replace_existing,
        )
        if check_cancelled is not None:
            check_cancelled()
    finally:
        temporary.unlink(missing_ok=True)
    return target
