"""Field-level view of a stored result: what exists, and exact fields within a budget.

A large saved result is never cut at an arbitrary character. Its fields are
listed with their sizes, the requested ones are delivered whole while they fit
the budget, and anything not delivered is named as not retrieved. The stored
bytes and hash stay untouched; this only shapes what a task is given.
"""
from __future__ import annotations

import json
import copy
from typing import Any

SEPARATOR = "/"
MAX_REQUESTED = 12
BUDGET = 16000
MAX_LISTED = 60
_MAX_DEPTH = 3
_ENVELOPE = 200  # room for the part descriptor inside one delivery


def _size(value: Any) -> int:
    return len(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def leaves(content: Any, prefix: str = "", depth: int = 0):
    """(path, value) of every field; nested objects are opened up to three levels."""
    if not isinstance(content, dict):
        return
    for key, value in content.items():
        if not isinstance(key, str) or SEPARATOR in key:
            continue  # not addressable; it stays in the stored result
        path = prefix + key
        if isinstance(value, dict) and value and depth < _MAX_DEPTH and all(
                isinstance(k, str) and SEPARATOR not in k for k in value):
            yield from leaves(value, path + SEPARATOR, depth + 1)
        else:
            yield path, value


def manifest(content: Any) -> list[dict[str, Any]]:
    """[{"field", "characters"}] in document order, limited to MAX_LISTED entries."""
    return [{"field": path, "characters": _size(value)} for path, value in leaves(content)][:MAX_LISTED]


def split_request(spec: str) -> tuple[str, int]:
    """'path' or 'path@offset' -> (path, offset); an invalid offset is refused by the caller."""
    path, _, offset = spec.partition("@")
    return path, int(offset) if offset.isdigit() else (-1 if offset else 0)


def known_fields(content: Any) -> set[str]:
    return {path for path, _ in leaves(content)}


def select(content: Any, requested: list[str], *, budget: int = BUDGET) -> dict[str, Any]:
    """Deliver requested fields whole while they fit; report what was and was not retrieved.

    A field larger than the budget is delivered as a part with its next offset,
    never as a silent prefix; 'path@offset' continues it.
    """
    by_path = dict(leaves(content))
    delivered: dict[str, Any] = {}
    retrieved, pending = [], []
    remaining = budget
    for spec in requested:
        path, offset = split_request(spec)
        value = by_path[path]
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        whole = offset == 0 and len(encoded) <= remaining
        if whole:
            delivered[path] = value
            retrieved.append({"field": path, "offset": 0, "characters": len(encoded), "complete": True})
            remaining -= len(encoded)
            continue
        if remaining < budget:
            # Something is already delivered: wait for a delivery of its own instead of cutting this field.
            pending.append({"field": path, "reason": "budget", "from_offset": offset,
                            "characters_left": max(0, len(encoded) - offset)})
            continue
        if offset >= len(encoded) > 0:
            pending.append({"field": path, "reason": "offset_out_of_range", "from_offset": offset,
                            "characters_left": 0})
            continue
        if remaining <= _ENVELOPE:
            pending.append({"field": path, "reason": "budget", "from_offset": offset,
                            "characters_left": max(0, len(encoded) - offset)})
            continue
        stop = min(len(encoded), offset + remaining - _ENVELOPE)
        def descriptor(end):
            return {"text": encoded[offset:end], "offset": offset, "total_characters": len(encoded),
                    "next_offset": end if end < len(encoded) else None}
        # The substring is itself a JSON string. Its quotes/backslashes can
        # expand again, so account for the real descriptor rather than only
        # counting characters in the original encoded field.
        lower, upper = offset, stop
        while lower < upper:
            middle = (lower + upper + 1) // 2
            if _size(descriptor(middle)) <= remaining:
                lower = middle
            else:
                upper = middle - 1
        part = encoded[offset:lower]
        if not part:
            pending.append({"field": path, "reason": "budget", "from_offset": offset,
                            "characters_left": max(0, len(encoded) - offset)})
            continue
        key = f"{path}@{offset}"
        delivered[key] = descriptor(lower)
        retrieved.append({"field": path, "offset": offset, "characters": len(part),
                          "complete": offset + len(part) >= len(encoded)})
        remaining -= _size(delivered[key])
    named = {split_request(spec)[0] for spec in requested}
    return {"fields": delivered, "retrieved": retrieved, "pending": pending,
            "not_requested": [row for row in manifest(content) if row["field"] not in named]}


def reference(content: Any, *, result_id: str, raw_hash: str, raw_text: str) -> dict[str, Any]:
    """What a large result tells its reader: identity, size and the fields it did not deliver."""
    listed = manifest(content)
    return {"result_id": result_id, "raw_hash": raw_hash, "characters": len(raw_text),
            "utf8_bytes": len(raw_text.encode("utf-8")),
            "fields": listed, "fields_listed": len(listed),
            "delivered": ["summary", "claims"], "claims_total": len(content.get("claims", []))
            if isinstance(content, dict) and isinstance(content.get("claims"), list) else 0,
            "retrieve_with": "kind=clarification, result_id, initial_sections=[field names]",
            "full_result_preserved": True, "reference_is_body_read": False}


def offload(content: Any, *, result_id: str, raw_hash: str, raw_text: str | None = None,
            budget: int = 0) -> dict[str, Any]:
    """A bounded view of any saved result, including a small result in a large workset.

    Only whole summary/claims fields that fit are previews. Every original field
    remains addressable by result ID/hash, and citation IDs remain available.
    This is a delivery projection, never a replacement for the stored result.
    """
    raw_text = raw_text if raw_text is not None else json.dumps(
        content, ensure_ascii=False, separators=(",", ":"))
    info = reference(content, result_id=result_id, raw_hash=raw_hash, raw_text=raw_text)
    # The harness workset must expose every field, including beyond the legacy
    # default manifest limit, so later requests cannot silently lose a field.
    info["fields"] = [{"field": path, "characters": _size(value)} for path, value in leaves(content)]
    info["fields_listed"] = len(info["fields"])
    info["delivered"] = []
    projected = {"omitted_full_result": True, "result_fields": info}
    remaining = max(0, budget)
    for name in ("summary", "claims"):
        if isinstance(content, dict) and name in content and _size(content[name]) <= remaining:
            projected[name] = copy.deepcopy(content[name])
            info["delivered"].append(name)
            remaining -= _size(content[name])
    citations = []
    def collect(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key == "evidence_ids" and isinstance(value, list):
                    citations.extend(item for item in value if isinstance(item, str))
                elif key == "evidence_id" and isinstance(value, str):
                    citations.append(value)
                else:
                    collect(value)
        elif isinstance(node, list):
            for value in node:
                collect(value)
    collect(content)
    info["evidence_ids"] = list(dict.fromkeys(citations))
    info["not_retrieved"] = [row for row in info["fields"] if row["field"] not in info["delivered"]]
    return projected
