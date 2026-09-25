"""Bottom layer shared by the store and every Vault writer (ARCH-02).

Paths inside a Vault, atomic writes, Markdown escaping and frontmatter reading
live here so that analysis_store, obsidian_layout, obsidian_finishing,
vault_registry and vault_note_policy import one module below them instead of
each other. This module imports nothing from the package except the durable
file primitives.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

import yaml


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def research_vault_root(database_file: Path) -> Path:
    """<data>/obsidian/ResearchVault: the one definition used by every writer (ARCH-03)."""
    return Path(database_file).parent / "obsidian" / "ResearchVault"


def safe_path(root: Path, relative: str) -> Path:
    if not relative or "\\" in relative or ":" in relative:
        raise ValueError("保存パスが正しくありません。")
    parts = Path(relative).parts
    if Path(relative).is_absolute() or any(part in {"..", "."} for part in parts):
        raise ValueError("保存先の外は参照できません。")
    # Detect links in each component, including the configured root itself.
    target = root / relative
    for part in [root, *root.parents, *target.parents, target]:
        if part.is_symlink() or getattr(part, "is_junction", lambda: False)():
            raise ValueError("リンクを経由する保存先には書き出せません。")
    if not target.resolve().is_relative_to(root.resolve()):
        raise ValueError("保存先の外は参照できません。")
    return target


def write_atomic(path: Path, data: bytes, *, create_only: bool = False) -> None:
    """Vault and store writes share services.durable_files (ARCH-04, OBS-17).

    ``create_only`` publishes the complete file without replacing a concurrently
    created note (FileExistsError).
    """
    from .services.durable_files import write_bytes_atomically
    write_bytes_atomically(path, data, create_only=create_only)


def markdown(value) -> str:
    text = html.escape(str(value or ""), quote=False)
    return re.sub(r"([\\`*_{}\[\]()#+.!|^~$])", r"\\\1", text)


FRONTMATTER_LIMIT = 64000
_FRONTMATTER_BLOCK = re.compile(r"\A---\n(.*?)\n---(?:\n|$)", re.S)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Read a note's leading properties with one rule for every reader (OBS-06).

    The delimiter, size limit and error messages are shared; each caller still
    decides how to normalise the text first, because researcher notes and
    generated notes are not treated alike.
    """
    if not text.startswith("---\n"):
        return {}, text
    match = _FRONTMATTER_BLOCK.match(text)
    if not match:
        raise ValueError("ノート先頭のプロパティの区切りが不正です。--- の区切りを確認してください。")
    if len(match[1]) > FRONTMATTER_LIMIT:
        raise ValueError(f"ノート先頭のプロパティが大きすぎます（上限{FRONTMATTER_LIMIT}文字）。")
    try:
        props = yaml.safe_load(match[1]) or {}
    except yaml.YAMLError as exc:
        raise ValueError("ノート先頭のプロパティを読み取れませんでした。") from exc
    if not isinstance(props, dict):
        raise ValueError("ノートのプロパティは項目名と値で指定してください。")
    return props, text[match.end():]
