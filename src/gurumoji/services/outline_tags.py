"""Outline section tags for every utterance; one rule for creation, display and analysis.

The AI outline lists only the utterances it cited as evidence, and a section's
time range is just the span of those citations, so ranges leave gaps and
overlap. Each utterance still gets exactly one section by fixed rules:

1. ``listed``: cited by a section's bullets (the earliest such section if more).
2. ``inferred``: otherwise the section that most recently started at or before
   its start time (the topic stays until the next one starts); before the
   first section, the first section; without a start time, the previous
   utterance's section.

Tags (S01, S02, ...) follow the outline order. They are reading aids derived
from an AI draft, not researcher labels; ``inferred`` stays visible as such.
"""
from __future__ import annotations

import math
from typing import Any

from ..analysis_core import fingerprint

VERSION = "outline-sections-2"
RULE = "listed citation, else latest section started at or before the utterance"


def _number(value: Any) -> float | None:
    return float(value) if type(value) in (int, float) and math.isfinite(value) else None


def outline_sections(raw_sections: Any) -> list[dict[str, Any]]:
    """Usable sections in outline order: a title, a finite start and cited segment IDs."""
    sections = []
    for raw in raw_sections if isinstance(raw_sections, list) else []:
        if not isinstance(raw, dict) or _number(raw.get("start")) is None:
            continue
        end = _number(raw.get("end"))
        sections.append({"title": str(raw.get("title", "")), "start": _number(raw["start"]),
                         "end": end if end is not None else _number(raw["start"]),
                         "segment_ids": [str(value) for value in raw.get("segment_ids") or []]})
    return sections


def assign(sections: list[dict[str, Any]], segments: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    """{segment_id: {"tag", "basis"}} for every segment, by the module rules."""
    if not sections:
        return {}
    tags = [f"S{number:02d}" for number in range(1, len(sections) + 1)]
    cited: dict[str, str] = {}
    for tag, section in zip(tags, sections):
        for segment_id in section["segment_ids"]:
            cited.setdefault(segment_id, tag)
    by_start = sorted(zip(tags, sections), key=lambda pair: (pair[1]["start"], pair[0]))
    result, previous = {}, tags[0]
    for segment in segments:
        segment_id = str(segment.get("id"))
        if segment_id in cited:
            result[segment_id] = {"tag": cited[segment_id], "basis": "listed"}
        else:
            start = _number(segment.get("start"))
            if start is None:
                tag = previous
            else:
                started = [tag for tag, section in by_start if section["start"] <= start]
                tag = started[-1] if started else by_start[0][0]
            result[segment_id] = {"tag": tag, "basis": "inferred"}
        previous = result[segment_id]["tag"]
    return result


RANGE_RULE = "each small heading is a contiguous range of utterances"


def range_assignment(sections: list[dict[str, Any]], segment_ids: list[str]) -> dict[str, Any]:
    """Assignment of a range-partitioned outline: every utterance is inside one heading's range."""
    starts = {section["first_segment_id"]: section["tag"] for section in sections}
    assigned, current = {}, sections[0]["tag"] if sections else None
    for segment_id in segment_ids:
        current = starts.get(segment_id, current)
        assigned[segment_id] = {"tag": current, "basis": "range"}
    return {"version": VERSION, "rule": RANGE_RULE, "segment_ids_sha256": fingerprint(list(segment_ids)),
            "segments": assigned}


def summary(sections: list[dict[str, Any]], assigned: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    rows = []
    for number, section in enumerate(sections, 1):
        tag = f"S{number:02d}"
        values = [entry["basis"] for entry in assigned.values() if entry["tag"] == tag]
        rows.append({"tag": tag, "title": section["title"], "start": section["start"], "end": section["end"],
                     "count": len(values), "listed": values.count("listed"), "inferred": values.count("inferred"),
                     "range": values.count("range")})
    return rows


def creation_assignment(outline_value: dict[str, Any], segments: list[dict[str, Any]]) -> dict[str, Any]:
    """Fields saved with a newly created outline: section tags and the per-utterance map."""
    sections = outline_sections(outline_value.get("sections"))
    assigned = assign(sections, segments)
    return {"version": VERSION, "rule": RULE, "segment_ids_sha256": fingerprint([str(s.get("id")) for s in segments]),
            "segments": assigned}


def outline_assignment(outline_value: Any, segments: list[dict[str, Any]]) -> dict[str, Any] | None:
    """The saved assignment if it still matches the utterances, else recomputed (``derived``)."""
    if not isinstance(outline_value, dict):
        return None
    sections = outline_sections(outline_value.get("sections"))
    if not sections:
        return None
    saved = outline_value.get("section_assignment")
    ids = [str(s.get("id")) for s in segments]
    if (isinstance(saved, dict) and saved.get("version") == VERSION and isinstance(saved.get("segments"), dict)
            and saved.get("segment_ids_sha256") == fingerprint(ids)):
        assigned, derived = saved["segments"], False
    else:
        assigned, derived = assign(sections, segments), True
    return {"version": VERSION, "rule": RULE, "derived": derived,
            "sections": summary(sections, assigned), "segments": assigned}


def outline_tags(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    """Tags for a frozen analysis snapshot's non-excluded evidence, keyed by evidence ID."""
    rows = (((snapshot.get("analysis") or {}).get("session_outline") or {}).get("result") or {}).get("rows") or []
    sections = outline_sections([row for row in rows if isinstance(row, dict) and row.get("title_source") == "outline"])
    if not sections:
        return None
    evidence = [row for row in snapshot.get("evidence", []) if not row.get("excluded")]
    assigned = assign(sections, [{"id": row["utterance_id"], "start": row.get("start")} for row in evidence])
    tags = {row["evidence_id"]: assigned[str(row["utterance_id"])]["tag"] for row in evidence}
    groups = [{"tag": entry["tag"], "title": entry["title"], "count": entry["count"]}
              for entry in summary(sections, {row["evidence_id"]: assigned[str(row["utterance_id"])] for row in evidence})
              if entry["count"]]
    return {"version": VERSION, "outline_hash": fingerprint(sections), "sections": groups, "tags": tags}


def ids_for_tags(index_tags: list[tuple[str, str]], wanted: list[str]) -> list[str]:
    """Evidence IDs of the wanted tags in index order; each ID once."""
    wanted_set = set(wanted)
    return [evidence_id for evidence_id, tag in index_tags if tag in wanted_set]
