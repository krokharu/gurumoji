"""Generate the Claude Code copies of the agent skills and roles from .agents/.

.agents/ is the source of truth shared with other coding tools. Claude Code
only discovers skills and subagents under .claude/, so this script writes
copies there:

    .agents/skills/<name>/**   ->  .claude/skills/<name>/**   (tool-specific agents/ folder skipped)
    .agents/agents/<name>.md   ->  .claude/agents/<name>.md

    python scripts/sync_agent_assets.py check   # exit 1 when a copy is missing, stale or edited
    python scripts/sync_agent_assets.py apply   # rewrite the copies

Markdown links are rewritten so they still resolve from the new location;
text mentions of .agents/skills/ and .agents/agents/ point at the copies.
Generated Markdown carries a marker comment, and only marked files or files
inside a synced skill folder are ever removed. .claude/rules/ is not
written because Claude Code loads it at every session start, while
.agents/rules/ is read on demand.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]
SOURCE = PurePosixPath(".agents")
TARGET = PurePosixPath(".claude")
SKIPPED_SKILL_FOLDERS = {"agents"}
MARKER = "<!-- 生成物: {source} から scripts/sync_agent_assets.py で生成。直接編集しない -->\n"
MARKER_PREFIX = "<!-- 生成物: "
LINK = re.compile(r"\]\(([^)\s]+)\)")
TEXT_PATHS = ((".agents/skills/", ".claude/skills/"), (".agents/agents/", ".claude/agents/"))


def _files(root: Path, folder: PurePosixPath) -> list[PurePosixPath]:
    base = root / folder
    if not base.is_dir():
        return []
    return sorted(PurePosixPath(path.relative_to(root).as_posix()) for path in base.rglob("*")
                  if path.is_file() and "__pycache__" not in path.parts and path.suffix not in {".pyc", ".pyo"})


def source_map(root: Path) -> dict[PurePosixPath, PurePosixPath]:
    """Map each source file to its generated copy (both relative to root)."""
    mapping = {}
    for path in _files(root, SOURCE / "skills"):
        relative = path.relative_to(SOURCE / "skills")
        if len(relative.parts) > 2 and relative.parts[1] in SKIPPED_SKILL_FOLDERS:
            continue
        mapping[path] = TARGET / "skills" / relative
    for path in _files(root, SOURCE / "agents"):
        if path.suffix == ".md" and len(path.relative_to(SOURCE / "agents").parts) == 1:
            mapping[path] = TARGET / "agents" / path.name
    return mapping


def _relative(target: PurePosixPath, start: PurePosixPath) -> str:
    return os.path.relpath(target.as_posix(), start.as_posix() or ".").replace("\\", "/")


def _rewrite_link(link: str, source: PurePosixPath, copy: PurePosixPath,
                  mapping: dict[PurePosixPath, PurePosixPath]) -> str:
    path, hash_mark, anchor = link.partition("#")
    if not path or "://" in path or path.startswith(("mailto:", "/")):
        return link
    resolved = PurePosixPath(os.path.normpath((source.parent / path).as_posix()).replace("\\", "/"))
    destination = mapping.get(resolved, resolved)
    return _relative(destination, copy.parent) + hash_mark + anchor


def _replace_text(text: str) -> str:
    for old, new in TEXT_PATHS:
        text = text.replace(old, new)
    return text


def render_markdown(text: str, source: PurePosixPath, copy: PurePosixPath,
                    mapping: dict[PurePosixPath, PurePosixPath]) -> str:
    parts, position = [], 0
    for match in LINK.finditer(text):
        parts.append(_replace_text(text[position:match.start()]))
        parts.append("](" + _rewrite_link(match.group(1), source, copy, mapping) + ")")
        position = match.end()
    parts.append(_replace_text(text[position:]))
    body = "".join(parts)
    marker = MARKER.format(source=source.as_posix())
    if body.startswith("---\n"):
        end = body.find("\n---\n", 4)
        if end != -1:
            split = end + len("\n---\n")
            return body[:split] + marker + body[split:]
    return marker + body


def expected(root: Path) -> dict[PurePosixPath, bytes]:
    mapping = source_map(root)
    result = {}
    for source, copy in mapping.items():
        data = (root / source).read_bytes()
        if source.suffix == ".md":
            data = render_markdown(data.decode("utf-8"), source, copy, mapping).encode("utf-8")
        result[copy] = data
    return result


def _is_generated(path: Path) -> bool:
    try:
        return MARKER_PREFIX in path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False


def stale(root: Path, wanted: dict[PurePosixPath, bytes]) -> list[PurePosixPath]:
    """Generated files under .claude/ that no source produces any more."""
    synced_skills = {copy.parts[2] for copy in wanted if copy.parts[1] == "skills"}
    candidates = set()
    for path in _files(root, TARGET / "skills"):
        skill = path.parts[2]
        if skill in synced_skills or _is_generated(root / TARGET / "skills" / skill / "SKILL.md"):
            candidates.add(path)
    for path in _files(root, TARGET / "agents"):
        if _is_generated(root / path):
            candidates.add(path)
    return sorted(candidates - set(wanted))


def differences(root: Path = ROOT) -> list[str]:
    wanted = expected(root)
    problems = []
    for copy, data in sorted(wanted.items()):
        path = root / copy
        if not path.is_file():
            problems.append(f"missing: {copy}")
        elif path.read_bytes() != data:
            problems.append(f"differs: {copy}")
    problems.extend(f"stale: {path}" for path in stale(root, wanted))
    return problems


def apply(root: Path = ROOT) -> list[str]:
    wanted = expected(root)
    changed = []
    for copy, data in sorted(wanted.items()):
        path = root / copy
        if path.is_file() and path.read_bytes() == data:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        changed.append(f"written: {copy}")
    for copy in stale(root, wanted):
        (root / copy).unlink()
        changed.append(f"removed: {copy}")
    return changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=("check", "apply"))
    args = parser.parse_args(argv)
    lines = differences() if args.command == "check" else apply()
    for line in lines:
        print(line)
    if args.command == "check":
        print("up to date" if not lines else "run: python scripts/sync_agent_assets.py apply")
        return 1 if lines else 0
    print(f"{len(lines)} change(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
