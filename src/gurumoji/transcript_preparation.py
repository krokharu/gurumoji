"""Local, versioned transcript preparation. GET never writes or certifies evidence."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone


TEXT_STATES = {"unreviewed", "transcript_checked", "audio_verified", "unclear"}
ROLES = {"unknown", "participant", "moderator", "observer"}
FIELDS = [
    "interview_id", "group_id", "input_version", "source_hash", "segment_id",
    "order", "order_verified", "speaker_id", "speaker_verified", "role",
    "start", "end", "source_locator", "source_segment_ids", "original_text",
    "original_status", "text", "text_status", "boundary_verified",
    "previous_segment_id", "next_segment_id", "content_ready", "interaction_ready",
    "analysis_needs_review",
]


def encode(value):
    def safe(item):
        if isinstance(item, float) and not math.isfinite(item):
            return {"invalid_legacy_number": str(item)}
        if isinstance(item, list):
            return [safe(v) for v in item]
        if isinstance(item, dict):
            return {k: safe(v) for k, v in item.items()}
        return item
    return json.dumps(safe(value), ensure_ascii=False, sort_keys=True, allow_nan=False)


def digest(value):
    return hashlib.sha256(encode(value).encode("utf-8")).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def initialize(connection):
    # Additive tables only. Existing originals and IDs are not migrated/replaced.
    connection.execute("""CREATE TABLE IF NOT EXISTS transcript_versions (
        item_id TEXT NOT NULL REFERENCES library_items(id) ON DELETE CASCADE,
        version INTEGER NOT NULL, source_hash TEXT NOT NULL,
        source_json TEXT NOT NULL, origin TEXT NOT NULL, created_at TEXT NOT NULL,
        PRIMARY KEY(item_id, version))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS transcript_preparations (
        item_id TEXT PRIMARY KEY REFERENCES library_items(id) ON DELETE CASCADE,
        revision INTEGER NOT NULL, state_json TEXT NOT NULL)""")
    connection.execute("""CREATE TABLE IF NOT EXISTS transcript_preparation_events (
        item_id TEXT NOT NULL REFERENCES library_items(id) ON DELETE CASCADE,
        revision INTEGER NOT NULL, state_json TEXT NOT NULL, created_at TEXT NOT NULL,
        PRIMARY KEY(item_id, revision))""")
    # initialize_store creates the run catalog before these preparation tables.
    # Keep invalidation inside the same transaction, including multi-interview runs.
    for operation, record in (("INSERT", "NEW"), ("UPDATE", "NEW"), ("DELETE", "OLD")):
        connection.execute(f"""CREATE TRIGGER IF NOT EXISTS preparation_runs_{operation.lower()}
            AFTER {operation} ON transcript_preparations
            BEGIN UPDATE analysis_runs SET stale=1
                WHERE item_id={record}.item_id OR id IN (
                    SELECT run_id FROM analysis_run_members WHERE item_id={record}.item_id);
            END""")


def source(row):
    return {key: json.loads(row[column] or default) for key, column, default in (
        ("segments", "segments_json", "[]"),
        ("speaker_profiles", "speaker_profiles_json", "{}"),
        ("speaker_names", "speaker_names_json", "{}"),
        ("session_profile", "session_profile_json", "{}"),
    )}


def capture(connection, row, origin="saved"):
    """Called inside the existing transcript transaction, before and after edits."""
    value = source(row)
    fingerprint = digest(value)
    latest = connection.execute(
        "SELECT version, source_hash FROM transcript_versions WHERE item_id=? ORDER BY version DESC LIMIT 1",
        (row["id"],),
    ).fetchone()
    if latest and latest["source_hash"] == fingerprint:
        return latest["version"]
    version = latest["version"] + 1 if latest else 1
    connection.execute("INSERT INTO transcript_versions VALUES (?, ?, ?, ?, ?, ?)",
                       (row["id"], version, fingerprint, encode(value), origin, now()))
    return version


def load_state(connection, item_id):
    row = connection.execute("SELECT * FROM transcript_preparations WHERE item_id=?", (item_id,)).fetchone()
    return (int(row["revision"]), json.loads(row["state_json"])) if row else (0, {})


def write_state(connection, item_id, revision, state):
    connection.execute("INSERT INTO transcript_preparations VALUES (?, ?, ?) "
                       "ON CONFLICT(item_id) DO UPDATE SET revision=excluded.revision, state_json=excluded.state_json",
                       (item_id, revision, encode(state)))
    connection.execute("INSERT INTO transcript_preparation_events VALUES (?, ?, ?, ?)",
                       (item_id, revision, encode(state), now()))


def valid_time(segment):
    values = [segment.get("start"), segment.get("end")]
    if segment.get("time_unknown") or any(v is None or v == "" or isinstance(v, bool) for v in values):
        return False
    try:
        start, end = map(float, values)
        return math.isfinite(start) and math.isfinite(end) and 0 <= start <= end
    except (TypeError, ValueError):
        return False


def basis_hash(source_hash, state):
    return digest({"source_hash": source_hash, "records": state.get("records", {}),
                   "order_verified": state.get("order_verified", False)})


def view(connection, row, segments):
    source_value = source(row)
    fingerprint = digest(source_value)
    revision, state = load_state(connection, row["id"])
    current = state.get("source_hash") == fingerprint
    records = state.get("records", {}) if current else {}
    order_verified = current and state.get("order_verified", False)
    versions = [dict(v) for v in connection.execute(
        "SELECT version, source_hash, origin, created_at FROM transcript_versions WHERE item_id=? ORDER BY version",
        (row["id"],))]
    version = versions[-1]["version"] if versions and versions[-1]["source_hash"] == fingerprint else None
    originals = {str(s.get("id")): s for s in json.loads(row["original_segments_json"] or "[]") if s.get("id")}
    original_status = row["original_segments_status"] or "unavailable"
    annotations = json.loads(row["analysis_annotations_json"] or "{}")
    stale = bool(annotations) and state.get("analysis_basis") != basis_hash(fingerprint, state if current else {})
    rows = []
    for index, segment in enumerate(segments):
        sid = segment["id"]
        record = records.get(sid, {})
        text_status = record.get("text_status", "unreviewed")
        speaker = segment.get("speaker")
        known = bool(speaker and speaker != "UNKNOWN")
        content_ready = bool(segment.get("text", "").strip()) and text_status in {"transcript_checked", "audio_verified"} and record.get("boundary_verified", False)
        interaction_ready = bool(content_ready and order_verified and known and record.get("speaker_verified") and record.get("role", "unknown") != "unknown")
        rows.append({
            "interview_id": row["id"], "group_id": source_value["session_profile"].get("interview_group_id") or None,
            "input_version": version, "source_hash": fingerprint, "segment_id": sid,
            "order": index + 1, "order_verified": bool(order_verified),
            "speaker_id": speaker if known else None, "speaker_verified": bool(known and record.get("speaker_verified")),
            "role": record.get("role", "unknown"),
            "start": segment.get("start") if valid_time(segment) else None,
            "end": segment.get("end") if valid_time(segment) else None,
            "source_locator": record.get("source_locator", ""),
            "source_segment_ids": record.get("source_segment_ids", [sid] if sid in originals else []),
            "original_text": originals.get(sid, {}).get("text"), "original_status": original_status if sid in originals else "unavailable",
            "text": segment.get("text", ""), "text_status": text_status,
            "boundary_verified": bool(record.get("boundary_verified")),
            "previous_segment_id": segments[index - 1]["id"] if index else None,
            "next_segment_id": segments[index + 1]["id"] if index + 1 < len(segments) else None,
            "content_ready": bool(content_ready), "interaction_ready": interaction_ready,
            "analysis_needs_review": stale,
        })
    return {
        "schema_version": 1, "revision": revision, "source_hash": fingerprint, "input_version": version,
        "status": "confirmed" if current and state.get("confirmed") else "needs_review" if state and not current else "draft",
        "order_verified": bool(order_verified), "analysis_needs_review": stale,
        "analysis_source_hash": state.get("analysis_source_hash"),
        "participant_count": state.get("participant_count") if current else None,
        "metadata_sources": state.get("metadata_sources", ""),
        "rows": rows, "versions": versions,
        "content_ready_count": sum(r["content_ready"] for r in rows),
        "interaction_ready_count": sum(r["interaction_ready"] for r in rows),
        "known_speaker_count": len({r["speaker_id"] for r in rows if r["speaker_verified"]}),
        "unknown_speaker_turns": sum(not r["speaker_verified"] for r in rows),
    }


class Conflict(Exception):
    pass


def save(connection, row, segments, payload):
    before = view(connection, row, segments)
    if not isinstance(payload, dict):
        raise ValueError("準備データはJSONオブジェクトで指定してください。")
    if type(payload.get("revision")) is not int or not isinstance(payload.get("source_hash"), str):
        raise ValueError("準備revisionとsource_hashが必要です。")
    if payload["revision"] != before["revision"] or payload["source_hash"] != before["source_hash"]:
        raise Conflict("文字起こしまたは確認状態が更新されました。再読み込みしてください。")
    records = payload.get("records", {})
    if not isinstance(records, dict) or len(records) > len(segments):
        raise ValueError("発言の確認データが不正です。")
    ids = {s["id"] for s in segments}
    known_ids = set(ids)
    for version in connection.execute("SELECT source_json FROM transcript_versions WHERE item_id=?", (row["id"],)):
        known_ids.update(s.get("id") for s in json.loads(version[0])["segments"])
    known_ids.update(s.get("id") for s in json.loads(row["original_segments_json"] or "[]"))
    clean = {}
    by_id = {s["id"]: s for s in segments}
    for sid, record in records.items():
        if sid not in ids or not isinstance(record, dict):
            raise ValueError("存在しない発言IDです。")
        status, role = record.get("text_status", "unreviewed"), record.get("role", "unknown")
        if not isinstance(status, str) or not isinstance(role, str) or status not in TEXT_STATES or role not in ROLES:
            raise ValueError("本文の確認状態または役割が不正です。")
        for key in ("speaker_verified", "boundary_verified"):
            if type(record.get(key, False)) is not bool:
                raise ValueError("確認状態は真偽値で指定してください。")
        if record.get("speaker_verified") and by_id[sid].get("speaker") in (None, "", "UNKNOWN"):
            raise ValueError("話者不明の発言を話者確認済みにはできません。")
        if status == "audio_verified":
            from pathlib import Path
            if not row["media_path"] or not Path(row["media_path"]).is_file():
                raise ValueError("音声・動画ファイルがないため音声照合済みにはできません。")
        lineage = record.get("source_segment_ids", [])
        if not isinstance(lineage, list) or len(lineage) > 1000 or any(not isinstance(s, str) or s not in known_ids for s in lineage):
            raise ValueError("分割・結合元の発言IDを確認してください。")
        locator = record.get("source_locator", "")
        if not isinstance(locator, str) or len(locator) > 1000:
            raise ValueError("元データ位置は1000文字以内で指定してください。")
        clean[sid] = {"text_status": status, "role": role, "speaker_verified": record.get("speaker_verified", False),
                      "boundary_verified": record.get("boundary_verified", False), "source_segment_ids": list(dict.fromkeys(lineage)),
                      "source_locator": locator}
    for key in ("order_verified", "confirm", "review_analysis"):
        if type(payload.get(key, False)) is not bool:
            raise ValueError("確認指定は真偽値で指定してください。")
    count = payload.get("participant_count")
    if count is not None and (type(count) is not int or not 0 <= count <= 100000):
        raise ValueError("実参加人数は非負の整数または不明を指定してください。")
    metadata = payload.get("metadata_sources", "")
    if not isinstance(metadata, str) or len(metadata) > 10000:
        raise ValueError("資料・確認根拠は10000文字以内で指定してください。")
    if count is not None and not metadata.strip():
        raise ValueError("実参加人数を記入する場合は、名簿等の確認根拠を記入してください。")
    if payload.get("confirm") and (not segments or any(
        clean.get(s["id"], {}).get("text_status") not in {"transcript_checked", "audio_verified"}
        or not clean.get(s["id"], {}).get("boundary_verified") or not s.get("text", "").strip()
        for s in segments
    )):
        raise ValueError("版の確定には全発言の本文と発言区切りの確認が必要です。話者不明は内容分析の制約として残ります。")
    _, old = load_state(connection, row["id"])
    state = {"source_hash": before["source_hash"], "records": clean, "order_verified": payload.get("order_verified", False),
             "confirmed": payload.get("confirm", False), "participant_count": count, "metadata_sources": metadata,
             "analysis_basis": old.get("analysis_basis"), "analysis_source_hash": old.get("analysis_source_hash")}
    if payload.get("review_analysis"):
        state["analysis_basis"] = basis_hash(before["source_hash"], state)
        state["analysis_source_hash"] = before["source_hash"]
    capture(connection, row, "preparation_baseline")
    write_state(connection, row["id"], before["revision"] + 1, state)
    return view(connection, row, segments)


def bind_analysis(connection, row):
    """Unrelated analysis saves must not silently clear a stale evidence binding."""
    revision, state = load_state(connection, row["id"])
    if state.get("analysis_basis"):
        return
    fingerprint = digest(source(row))
    active = state if state.get("source_hash") == fingerprint else {}
    state["analysis_basis"] = basis_hash(fingerprint, active)
    state["analysis_source_hash"] = fingerprint
    write_state(connection, row["id"], revision + 1, state)
