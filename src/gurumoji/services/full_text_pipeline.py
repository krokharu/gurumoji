"""Full-text map stage: the Handler partitions a frozen scope; each chunk is one extract call.

Coverage is structural. A chunk is read when its extract result is accepted;
the model neither chooses what to read nor orders tasks. The output cap, not
the input cap, sizes a chunk: one call returns at most MAX_OBSERVATIONS rows.
"""
from __future__ import annotations


from ..analysis_core import AnalysisContractError, fingerprint

VERSION = "full-text-map-1"
MAX_OBSERVATIONS = 12
MAX_OBSERVATION_IDS = 4
STATEMENT_CHARS = 120
THEME_CHARS = 40
NOTES_CHARS = 200
DEFAULT_BODY_CHARS = 3000
DEFAULT_MAX_ROWS = 60
KINDS = ("pattern", "exception", "unclear")


def _error(message, code):
    return AnalysisContractError(message, code=code)


def plan_chunks(evidence, tags=None, *, input_version, body_chars=DEFAULT_BODY_CHARS, max_rows=DEFAULT_MAX_ROWS):
    """Partition rows in reading order into chunks; whole sections first, then rows, then offsets.

    evidence: [{"evidence_id", "text"}] without excluded rows; tags: {evidence_id: section} or None.
    Every character and every ID (empty text included) lands in exactly one segment.
    """
    if type(body_chars) is not int or body_chars < 1 or type(max_rows) is not int or max_rows < 1:
        raise _error("チャンクの上限は正の整数です。", "map_plan_invalid")
    if not isinstance(input_version, str) or not input_version:
        raise _error("入力版がありません。", "map_plan_invalid")
    ids = [row["evidence_id"] for row in evidence]
    if len(set(ids)) != len(ids):
        raise _error("根拠IDが重複しています。", "map_plan_invalid")
    groups = []
    for row in evidence:
        section = tags.get(row["evidence_id"], "") if tags else ""
        if not groups or groups[-1][0] != section:
            groups.append((section, []))
        groups[-1][1].append(row)
    chunks, current = [], []

    def size(segments):
        return sum(end - start for _, start, end, _ in segments)

    def close():
        if current:
            chunks.append(list(current))
            current.clear()

    for section, rows in groups:
        whole = sum(len(row["text"]) for row in rows)
        if current and (size(current) + whole > body_chars or len(current) + len(rows) > max_rows):
            close()
        for row in rows:
            length = len(row["text"])
            if current and (size(current) + min(length, body_chars) > body_chars or len(current) >= max_rows):
                close()
            if length <= body_chars - size(current):
                current.append((row["evidence_id"], 0, length, section))
                continue
            start = 0
            while start < length:
                if size(current) >= body_chars or len(current) >= max_rows:
                    close()
                end = min(length, start + body_chars - size(current))
                current.append((row["evidence_id"], start, end, section))
                start = end
    close()
    planned = []
    for index, segments in enumerate(chunks):
        body = [[evidence_id, start, end] for evidence_id, start, end, _ in segments]
        planned.append({"chunk_id": "chk_" + fingerprint({"input_version": input_version, "segments": body})[7:23],
                        "index": index, "sections": list(dict.fromkeys(s for *_, s in segments if s)),
                        "segments": body, "chars": sum(end - start for _, start, end in body)})
    plan = {"version": VERSION, "input_version": input_version, "body_chars": body_chars, "max_rows": max_rows,
            "evidence_count": len(ids), "chars": sum(len(row["text"]) for row in evidence), "chunks": planned}
    plan["plan_hash"] = fingerprint(plan)
    return plan


def verify_plan(plan, evidence):
    """The plan still partitions this exact frozen scope (same IDs, lengths and version hash)."""
    body = {key: value for key, value in plan.items() if key != "plan_hash"}
    if fingerprint(body) != plan.get("plan_hash"):
        raise _error("読取り計画のhashが一致しません。", "map_plan_mismatch")
    lengths = {row["evidence_id"]: len(row["text"]) for row in evidence}
    covered = {}
    for chunk in plan["chunks"]:
        for evidence_id, start, end in chunk["segments"]:
            if evidence_id not in lengths or start != covered.get(evidence_id, 0) or end < start:
                raise _error("読取り計画が固定入力と一致しません。", "map_plan_mismatch")
            covered[evidence_id] = end
    if covered != lengths:
        raise _error("読取り計画が固定入力の全範囲を含みません。", "map_plan_mismatch")


def coverage(plan, accepted_chunk_ids):
    """Read state derived only from accepted chunks; an ID is read when all its segments are."""
    accepted = set(accepted_chunk_ids)
    pending = {}
    for chunk in plan["chunks"]:
        for evidence_id, *_ in chunk["segments"]:
            pending.setdefault(evidence_id, set()).add(chunk["chunk_id"])
    read = sum(1 for chunks in pending.values() if chunks <= accepted)
    chars = sum(chunk["chars"] for chunk in plan["chunks"] if chunk["chunk_id"] in accepted)
    remaining = [chunk["chunk_id"] for chunk in plan["chunks"] if chunk["chunk_id"] not in accepted]
    return {"version": VERSION, "plan_hash": plan["plan_hash"], "chunk_count": len(plan["chunks"]),
            "accepted_chunk_count": len(plan["chunks"]) - len(remaining), "evidence_count": plan["evidence_count"],
            "evidence_read_count": read, "chars": plan["chars"], "chars_read": chars,
            "remaining_chunk_ids": remaining, "complete": not remaining}


def chunk_refs(chunk):
    """Call-local short references {ref: evidence_id}, fixed by the chunk's segment order.

    The model never needs the long stable IDs; the Handler maps them back.
    """
    ids = list(dict.fromkeys(evidence_id for evidence_id, *_ in chunk["segments"]))
    return {f"u{index + 1}": evidence_id for index, evidence_id in enumerate(ids)}


def chunk_packet(plan, chunk, evidence, *, research_question, brief="", known_themes=()):
    """Model input of one chunk: the question, an optional expert brief and this chunk's text only."""
    by_id = {row["evidence_id"]: row for row in evidence}
    ref_of = {evidence_id: ref for ref, evidence_id in chunk_refs(chunk).items()}
    rows = []
    for evidence_id, start, end in chunk["segments"]:
        row = by_id[evidence_id]
        rows.append([ref_of[evidence_id], row.get("speaker"), row["text"][start:end],
                     start > 0 or end < len(row["text"])])
    packet = {"version": VERSION, "research_question": research_question, "brief": brief,
              "chunk": {"chunk_id": chunk["chunk_id"], "index": chunk["index"], "of": len(plan["chunks"]),
                        "sections": list(chunk["sections"])},
              "utterances": {"columns": ["ref", "speaker", "text", "partial"], "rows": rows}}
    if known_themes:
        packet["known_themes"] = list(known_themes)
    return packet


def map_schema(chunk, known_themes=()):
    """Generation schema; accept_extract enforces the same limits after decoding.

    A heading is either reused from known_themes (reuse_theme) or newly named (new_theme);
    the two fields keep a note about newness out of the heading itself.
    """
    ids = list(chunk_refs(chunk))
    observation = {"type": "object", "additionalProperties": False,
                   "required": ["evidence_ids", "statement", "kind", "reuse_theme", "new_theme"],
                   "properties": {
                       "evidence_ids": {"type": "array", "minItems": 1, "maxItems": MAX_OBSERVATION_IDS,
                                        "items": {"type": "string", "enum": ids}},
                       "statement": {"type": "string", "minLength": 1, "maxLength": STATEMENT_CHARS},
                       "kind": {"type": "string", "enum": list(KINDS)},
                       "reuse_theme": {"type": "string", "enum": ["", *known_themes]},
                       "new_theme": {"type": "string", "minLength": 0, "maxLength": THEME_CHARS}}}
    return {"type": "object", "additionalProperties": False,
            "required": ["chunk_id", "observations", "uncovered_notes"],
            "properties": {"chunk_id": {"type": "string", "enum": [chunk["chunk_id"]]},
                           "observations": {"type": "array", "maxItems": MAX_OBSERVATIONS, "items": observation},
                           "uncovered_notes": {"type": "string", "maxLength": NOTES_CHARS}}}


def _text(value, limit):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= limit


def accept_extract(chunk, raw, known_themes=()):
    """Accept one extract result for exactly this chunk, or raise; nothing is repaired.

    known_themes is the list the request offered; exactly one of reuse_theme/new_theme names the heading.
    """
    if not isinstance(raw, dict) or set(raw) != {"chunk_id", "observations", "uncovered_notes"}:
        raise _error("抽出結果の形式が不正です。", "map_shape_invalid")
    if raw["chunk_id"] != chunk["chunk_id"]:
        raise _error("抽出結果のチャンクが一致しません。", "map_chunk_mismatch")
    notes = raw["uncovered_notes"]
    if not isinstance(notes, str) or len(notes) > NOTES_CHARS:
        raise _error("未確認メモの形式が不正です。", "map_shape_invalid")
    observations = raw["observations"]
    if not isinstance(observations, list) or len(observations) > MAX_OBSERVATIONS:
        raise _error("観察の件数が上限を超えています。", "map_shape_invalid")
    refs = chunk_refs(chunk)
    for item in observations:
        if not isinstance(item, dict) or set(item) != {"evidence_ids", "statement", "kind", "reuse_theme", "new_theme"}:
            raise _error("観察の形式が不正です。", "map_shape_invalid")
        ids = item["evidence_ids"]
        if (not isinstance(ids, list) or not 1 <= len(ids) <= MAX_OBSERVATION_IDS
                or any(not isinstance(value, str) for value in ids) or len(set(ids)) != len(ids)):
            raise _error("観察の根拠IDが不正です。", "map_shape_invalid")
        if not set(ids) <= set(refs):
            raise _error("観察がチャンク外の根拠IDを参照しています。", "map_evidence_out_of_chunk")
        reuse, new = item["reuse_theme"], item["new_theme"]
        if not isinstance(reuse, str) or not isinstance(new, str) or bool(reuse.strip()) == bool(new.strip()):
            raise _error("見出しは既出の見出しか新しい見出しのどちらか一方だけを書きます。", "map_theme_invalid")
        if reuse.strip() and reuse not in known_themes:
            raise _error("既出として示していない見出しです。", "map_theme_invalid")
        if not _text(item["statement"], STATEMENT_CHARS) or (new.strip() and not _text(new, THEME_CHARS)):
            raise _error("観察の本文または見出しが空か長すぎます。", "map_text_invalid")
        if item["kind"] not in KINDS:
            raise _error("観察の種類が不正です。", "map_shape_invalid")
    mapped = [{"evidence_ids": [refs[ref] for ref in item["evidence_ids"]], "statement": item["statement"],
               "kind": item["kind"], "theme": item["reuse_theme"] or item["new_theme"].strip()}
              for item in observations]
    return {"version": VERSION, "chunk_id": chunk["chunk_id"], "observations": mapped,
            "uncovered_notes": notes, "raw_hash": fingerprint(raw)}
