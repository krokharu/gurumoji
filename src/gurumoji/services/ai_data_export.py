"""Read-only adapters for local AI data exports.

The caller owns the SQLite read transaction. No versions, state or files are
created here; the established preparation export is the provenance source.
"""

from __future__ import annotations

import json
import math

from .. import transcript_preparation as preparation
from ..text_utils import json_load


SPEAKER_ATTRIBUTES = {"organization", "department", "job_title", "session_role", "session_role_source"}
SEGMENT_KEYS = {"id", "speaker", "text", "start", "end", "time_unknown"}


class ExportError(Exception):
    def __init__(self, reason, status=400, *, frame_status=None):
        super().__init__(reason)
        self.reason = reason
        self.status = status
        self.frame_status = frame_status


def validate_export_request(value):
    """Close the request language and reject all bounds before DB/media work."""
    if not isinstance(value, dict) or set(value) - {
        "include_names", "speaker_attributes", "expected_source_hash", "expected_revision", "frames"
    }:
        raise ExportError("invalid_request")
    names = value.get("include_names", False)
    attrs = value.get("speaker_attributes", [])
    if type(names) is not bool or not isinstance(attrs, list) or any(
        not isinstance(a, str) or a not in SPEAKER_ATTRIBUTES for a in attrs
    ) or len(set(attrs)) != len(attrs):
        raise ExportError("invalid_selection")
    expected_hash, revision = value.get("expected_source_hash"), value.get("expected_revision")
    if expected_hash is not None and not isinstance(expected_hash, str):
        raise ExportError("invalid_source_hash")
    if revision is not None and (type(revision) is not int or revision < 0):
        raise ExportError("invalid_revision")
    frames = value.get("frames", {})
    if not isinstance(frames, dict) or set(frames) - {
        "enabled", "start", "end", "interval", "max_frames", "max_dimension"
    } or type(frames.get("enabled", False)) is not bool:
        raise ExportError("invalid_frames")
    enabled = frames.get("enabled", False)
    if not enabled:
        if set(frames) - {"enabled"}:
            raise ExportError("disabled_frame_options")
        frames = {"enabled": False}
    else:
        for key in ("start", "end", "interval"):
            number = frames.get(key)
            try:
                finite = type(number) in (int, float) and math.isfinite(number)
            except OverflowError:
                finite = False
            if not finite:
                raise ExportError("invalid_frame_number")
        start, end, interval = (frames[k] for k in ("start", "end", "interval"))
        maximum, dimension = frames.get("max_frames", 24), frames.get("max_dimension", 1280)
        if start < 0 or end < start or end - start > 600 or interval < 1 or \
                type(maximum) is not int or not 1 <= maximum <= 24 or \
                type(dimension) is not int or not 16 <= dimension <= 1280:
            raise ExportError("frame_bounds")
        # Count before constructing any list. Never silently truncate a request.
        count = math.floor((end - start) / interval) + 1
        if count > maximum:
            raise ExportError("frame_count")
        times = [start + k * interval for k in range(count)]
        if any(not math.isfinite(t) or t > end for t in times) or len(set(times)) != count:
            raise ExportError("invalid_frame_number")
        frames = {"enabled": True, "times": times, "max_dimension": dimension}
    return {"include_names": names, "speaker_attributes": attrs,
            "expected_source_hash": expected_hash, "expected_revision": revision, "frames": frames}


def _label(segment):
    value = segment.get("speaker")
    return value if isinstance(value, str) and value else None


def _segments(segments):
    return [{k: v for k, v in s.items() if k in SEGMENT_KEYS} for s in segments]


def ai_export_payload(row, segments, prepared, selection):
    """Project saved metadata; keep original source hashes in their own domain."""
    current = preparation.source(row)
    sources = [current] + [v["source"] for v in prepared["versions"]]
    labels = set()
    for source in sources:
        labels.update(filter(None, (_label(s) for s in source["segments"])))
        labels.update(k for k in source["speaker_profiles"] if isinstance(k, str) and k)
    labels.update(filter(None, (_label(s) for s in prepared["original_segments"])))
    numbers = {label: i + 1 for i, label in enumerate(sorted(labels))}
    attrs, names = selection["speaker_attributes"], selection["include_names"]

    def profile(value, label):
        value = value if isinstance(value, dict) else {}
        result = {k: value[k] for k in attrs if k in value}
        result["speaker_label"] = label
        if names and isinstance(value.get("display_name"), str):
            result["display_name"] = value["display_name"]
        return result

    speakers = []
    for label in sorted(labels):
        saved = current["speaker_profiles"].get(label, {})
        saved = saved if isinstance(saved, dict) else {}
        display = saved.get("display_name") or current["speaker_names"].get(label)
        speakers.append({"speaker_no": numbers[label], "raw_label": label,
                         "display_name": display if names and isinstance(display, str) else None,
                         "attributes": {k: saved[k] for k in attrs if k in saved}})
    for version in prepared["versions"]:
        source = version["source"]
        filtered = {"segments": _segments(source["segments"]),
                    "speaker_profiles": {label: profile(v, label) for label, v in source["speaker_profiles"].items()},
                    "session_profile": source["session_profile"]}
        if names:
            filtered["speaker_names"] = {k: v for k, v in source["speaker_names"].items() if isinstance(v, str)}
        version["source"] = filtered
    prepared["original_segments"] = _segments(prepared["original_segments"])
    for turn, segment in zip(prepared["rows"], segments):
        label = _label(segment)
        turn.update(raw_speaker_label=label, speaker_no=numbers.get(label))
    # The established rows digest remains in the original preparation.FIELDS
    # domain. Dot's file hashes cover the filtered, augmented export bytes.
    outline = json.loads(row["outline_json"] or "null")
    return {"schema_version": 1, "item": {"id": row["id"], "language": row["language"]},
            "preparation": prepared, "speakers": speakers, "outline": outline,
            "outline_provenance": {"kind": "absent" if outline is None else "saved",
                "source_hash": prepared["source_hash"], "input_version": prepared["input_version"],
                "analysis_source_hash": prepared["analysis_source_hash"]},
            "selection": {"include_names": names, "speaker_attributes": attrs},
            "frames": {"status": "disabled", "reason": "not_requested", "media": None, "items": []}}


def preparation_export_snapshot(connection, row, segments):
    """Read the complete preparation export within the caller's snapshot."""
    value = preparation.view(connection, row, segments)
    value["original_segments"] = json_load(row["original_segments_json"], [])
    value["original_status"] = row["original_segments_status"]
    value["versions"] = [
        {"version": v["version"], "source_hash": v["source_hash"],
         "source": json.loads(v["source_json"]), "origin": v["origin"],
         "created_at": v["created_at"]}
        for v in connection.execute(
            "SELECT version, source_hash, source_json, origin, created_at "
            "FROM transcript_versions WHERE item_id=? ORDER BY version", (row["id"],))
    ]
    value["review_history"] = [
        {"revision": v["revision"], "created_at": v["created_at"],
         "state": json.loads(v["state_json"])}
        for v in connection.execute(
            "SELECT * FROM transcript_preparation_events WHERE item_id=? ORDER BY revision", (row["id"],))
    ]
    value["manifest"] = {
        "schema_version": 1, "encoding": "UTF-8", "row_count": len(value["rows"]),
        "rows_sha256": preparation.digest(value["rows"]), "columns": preparation.FIELDS,
        "missing_value": "JSON null / CSV empty",
        "order_basis": "saved transcript array; verification is separate",
        "ids": "application-managed IDs; split/merge lineage is researcher-confirmed",
        "csv_note": "CSV applies spreadsheet formula escaping; JSON preserves exact text.",
        "privacy": "Local export may contain personal data. Review before sharing. Media not included.",
    }
    return value
