#!/usr/bin/env python3
"""Render a small, local Markdown context packet from one Obsidian Vault.

Notes are named by Vault-relative path and stable IDs; absolute local paths are
never printed. Templates and archives are skipped unless explicitly included.
"""

from __future__ import annotations

import argparse
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path


MAX_FILE_CHARS = 262_144
FRONTMATTER = re.compile(r"\A﻿?---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)
TITLE = re.compile(r"^#\s+(.+?)\s*$", re.MULTILINE)
HEADING = re.compile(r"^#{1,6}\s+.*$", re.MULTILINE)
CJK = re.compile(r"[ぁ-んァ-ヶ一-龯ー]+")
TEMPLATE_DIRS = {"90-Templates"}
ARCHIVE_DIRS = {"99-Archive"}
FIELD_WEIGHTS = (("title", 8.0), ("metadata", 3.0), ("body", 1.0))


@dataclass(frozen=True)
class Term:
    text: str
    bigrams: tuple[str, ...]


@dataclass
class Note:
    relative: str
    metadata: dict[str, str]
    title: str
    body: str
    fields: dict[str, str]
    score: float = 0.0


def terms(query: str) -> list[Term]:
    """One scored term per query word; long CJK words may also match by bigrams."""
    result = []
    for word in dict.fromkeys(part.casefold() for part in re.findall(r"[\wぁ-んァ-ヶ一-龯ー]+", query)):
        if len(word) < 2:
            continue
        bigrams = ()
        if len(word) > 3 and CJK.fullmatch(word):
            bigrams = tuple(dict.fromkeys(word[index:index + 2] for index in range(len(word) - 1)))
        result.append(Term(word, bigrams))
    return result


def strength(term: Term, text: str) -> float:
    if term.text in text:
        return 1.0
    if not term.bigrams:
        return 0.0
    share = sum(part in text for part in term.bigrams) / len(term.bigrams)
    return 0.5 * share if share >= 0.5 else 0.0


def parse_metadata(text: str) -> tuple[dict[str, str], str]:
    match = FRONTMATTER.match(text)
    if not match:
        return {}, text
    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line or line.startswith((" ", "-")):
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip().strip("'\"")
    return metadata, text[match.end():]


def read_note(path: Path, vault: Path) -> Note:
    text = path.read_text(encoding="utf-8", errors="replace")[:MAX_FILE_CHARS]
    metadata, body = parse_metadata(text)
    match = TITLE.search(body)
    title = metadata.get("title") or (match.group(1) if match else path.stem)
    fields = {"title": title.casefold(), "metadata": " ".join(metadata.values()).casefold(),
              "body": body.casefold()}
    return Note(path.relative_to(vault).as_posix(), metadata, title, body, fields)


def exclusion(note: Note, include_templates: bool, include_archived: bool) -> str:
    folders = set(note.relative.split("/")[:-1])
    if not include_templates and folders & TEMPLATE_DIRS:
        return "template"
    if not include_archived and (folders & ARCHIVE_DIRS or note.metadata.get("status", "").casefold() == "archived"):
        return "archive"
    return ""


def rank(notes: list[Note], query_terms: list[Term]) -> list[Note]:
    """Weight each query term once per note, discounted when most notes contain it."""
    strengths = [{term.text: max(weight * strength(term, note.fields[field]) for field, weight in FIELD_WEIGHTS)
                  for term in query_terms} for note in notes]
    idf = {term.text: math.log((len(notes) + 1) / (sum(1 for values in strengths if values[term.text]) + 1)) + 1
           for term in query_terms}
    for note, values in zip(notes, strengths):
        note.score = round(sum(value * idf[key] for key, value in values.items()), 2)
    return sorted((note for note in notes if note.score > 0), key=lambda note: (-note.score, note.relative))


def excerpt(note: Note, query_terms: list[Term], limit: int) -> str:
    summary = note.metadata.get("summary", "").strip()
    if summary:
        return summary[:limit]
    lower = note.body.casefold()
    needles = [term.text for term in query_terms] or []
    positions = [lower.find(value) for value in needles if lower.find(value) >= 0]
    if not positions:
        positions = [lower.find(part) for term in query_terms for part in term.bigrams if lower.find(part) >= 0]
    if not positions:
        return note.body.strip()[:limit]
    position = min(positions)
    starts = [match.start() for match in HEADING.finditer(note.body) if match.start() <= position]
    start = starts[-1] if starts else max(0, position - limit // 3)
    value = note.body[start:start + limit].strip()
    return re.sub(r"\n{3,}", "\n\n", value)


def provenance(note: Note) -> str:
    meta = note.metadata
    return (f"{meta.get('note_id') or 'no-note-id'} / revision {meta.get('revision') or '-'}"
            f" / source_hash {meta.get('source_hash') or '-'} / status {meta.get('status') or '-'}")


def packet(vault: Path, query: str, max_notes: int, max_chars: int,
           include_templates: bool, include_archived: bool) -> str:
    query_terms = terms(query)
    notes: list[Note] = []
    skipped = {"template": 0, "archive": 0}
    for path in sorted(vault.rglob("*.md")):
        if any(part.startswith(".") for part in path.relative_to(vault).parts):
            continue
        note = read_note(path, vault)
        reason = exclusion(note, include_templates, include_archived)
        if reason:
            skipped[reason] += 1
            continue
        notes.append(note)
    ranked = rank(notes, query_terms) if query_terms else []
    selected = ranked[:max_notes]
    lines = [f"Request: {query}", f"Vault: {vault.name}", "", "Selected sources:"]
    lines.extend(f"- {provenance(note)} — {note.relative} (score {note.score:g})" for note in selected)
    if not selected:
        lines.append("- none. Read 00-Home.md or 00-Index.md and refine the query.")
    lines.extend(["", "Evidence:"])
    remaining = max_chars - sum(len(line) + 1 for line in lines) - 240
    loaded = 0
    for note in selected:
        if remaining <= 0:
            break
        header = f"### {note.title} ({note.relative})\n"
        content = excerpt(note, query_terms, max(300, min(2_000, remaining - len(header))))
        block = header + content + "\n"
        if len(block) > remaining:
            block = block[:remaining].rstrip() + "\n"
        lines.append(block)
        remaining -= len(block) + 1
        loaded += 1
    omitted = []
    if len(selected) > loaded:
        omitted.append(f"{len(selected) - loaded} selected notes beyond --max-chars")
    if len(ranked) > len(selected):
        omitted.append(f"{len(ranked) - len(selected)} lower-ranked matching notes")
    if skipped["template"]:
        omitted.append(f"{skipped['template']} template notes (--include-templates)")
    if skipped["archive"]:
        omitted.append(f"{skipped['archive']} archived notes (--include-archived)")
    if omitted:
        lines.extend(["Not loaded:", *("- " + value for value in omitted)])
    rendered = "\n".join(lines).rstrip() + "\n"
    return rendered[:max_chars]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vault", required=True, type=Path)
    parser.add_argument("--query", required=True)
    parser.add_argument("--max-notes", type=int, default=4)
    parser.add_argument("--max-chars", type=int, default=8_000)
    parser.add_argument("--include-templates", action="store_true")
    parser.add_argument("--include-archived", action="store_true")
    args = parser.parse_args()
    vault = args.vault.resolve()
    if not vault.is_dir():
        parser.error(f"vault does not exist: {args.vault}")
    if args.max_notes < 1 or args.max_chars < 500:
        parser.error("--max-notes must be positive and --max-chars must be at least 500")
    print(packet(vault, args.query, args.max_notes, args.max_chars,
                 args.include_templates, args.include_archived), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
