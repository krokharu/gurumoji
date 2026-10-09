"""HTTP adapters for downloadable exports (analysis, meeting minutes, speakers)."""

from __future__ import annotations

import csv
import io
import json
import sqlite3
from typing import Any

from flask import Flask, jsonify, request, send_file

from .. import transcript_preparation as preparation
from ..research_analysis import build_analysis_workbook
from ..services.ai_data_export import (
    ExportError, ai_export_payload, preparation_export_snapshot, validate_export_request,
)
from ..services.ai_data_export_frames import extract_frames, media_identity, permitted_media
from ..services.group_analysis import (
    ANALYSIS_CSV_FIELDS,
    analysis_csv_content,
    analysis_csv_rows,
    analysis_csv_safe,
    focus_group_analysis_report_markdown,
)
from ..services.meeting_minutes import (
    format_meeting_minutes_markdown,
    meeting_external_payload,
    meeting_tasks_csv_text,
)
from ..services.outputs import safe_output_stem
from ..services.speaker_registry import speaker_registry_csv_bytes
from ..services.transcription.segments import segment_bounds
from ..text_utils import json_load


def register_export_routes(
    app: Flask,
    *,
    database_connection: Any,
    group_analysis_for_row: Any,
    library_row: Any,
    list_speaker_registry: Any,
    meeting_minutes_export_row: Any,
    row_segments: Any,
    row_session_profile: Any,
    row_speaker_profiles: Any,
    media_directory: Any = None,
    path_is_within: Any = None,
) -> None:
    def export_speaker_registry():
        content = speaker_registry_csv_bytes(list_speaker_registry())
        return send_file(
            io.BytesIO(content),
            mimetype="text/csv; charset=utf-8",
            as_attachment=True,
            download_name="gurumoji_speaker_registry.csv",
        )

    def export_transcript_preparation(item_id: str):
        with database_connection() as connection:
            connection.execute("BEGIN")
            row = connection.execute("SELECT * FROM library_items WHERE id=?", (item_id,)).fetchone()
            if row is None:
                return jsonify({"error": "データが見つかりません。"}), 404
            value = preparation_export_snapshot(connection, row, row_segments(row))
        return send_file(io.BytesIO(preparation.encode(value).encode("utf-8")),
                         mimetype="application/json", as_attachment=True, download_name=f"{item_id}_preparation.json")

    def export_ai_data_bundle(item_id: str):
        try:
            options = validate_export_request(request.get_json(silent=True))
            with database_connection() as connection:
                connection.execute("PRAGMA query_only=ON")
                connection.execute("BEGIN")
                row = connection.execute("SELECT * FROM library_items WHERE id=?", (item_id,)).fetchone()
                if row is None:
                    raise ExportError("unknown_item", 404)
                segments = row_segments(row)
                prepared = preparation_export_snapshot(connection, row, segments)
                if options["expected_source_hash"] is not None and options["expected_source_hash"] != prepared["source_hash"] or \
                        options["expected_revision"] is not None and options["expected_revision"] != prepared["revision"]:
                    raise ExportError("source_changed", 409)
                # Capture all saved fields before selective metadata projection.
                row_token = dict(row)
                revision = prepared["revision"]
                payload = ai_export_payload(row, segments, prepared, options)
            if options["frames"]["enabled"]:
                payload["frames"] = extract_frames(row, prepared["rows"], options["frames"],
                    media_directory=media_directory, path_is_within=path_is_within)
            # Dot owns this pure serializer; import only when the feature runs.
            from ..services.ai_data_export_bundle import build_ai_bundle
            content = build_ai_bundle(payload)
            with database_connection() as connection:
                connection.execute("PRAGMA query_only=ON")
                connection.execute("BEGIN")
                fresh = connection.execute("SELECT * FROM library_items WHERE id=?", (item_id,)).fetchone()
                if fresh is None or dict(fresh) != row_token or preparation.load_state(connection, item_id)[0] != revision:
                    raise ExportError("source_changed", 409)
                if options["frames"]["enabled"]:
                    try:
                        current_path = permitted_media(fresh, media_directory, path_is_within)
                        current_identity = media_identity(current_path)
                    except (OSError, ExportError) as exc:
                        raise ExportError("media_changed", 409, frame_status="failed") from exc
                    if current_identity != payload["frames"]["media"]["identity"]:
                        raise ExportError("media_changed", 409, frame_status="failed")
        except ExportError as exc:
            body = {"error": exc.reason}
            if exc.frame_status:
                body["frames"] = {"status": exc.frame_status, "reason": exc.reason}
            return jsonify(body), exc.status
        except (ValueError, TypeError, KeyError, OverflowError, sqlite3.Error):
            return jsonify({"error": "invalid_saved_export_data"}), 422
        except (ImportError, OSError):
            return jsonify({"error": "export_unavailable"}), 503
        response = send_file(io.BytesIO(content), mimetype="application/zip", as_attachment=True,
                             download_name=f"{safe_output_stem(str(row['source_name']))[:72]}_ai-export.zip")
        response.headers["Cache-Control"] = "no-store"
        return response

    def export_library_analysis_json(item_id: str):
        row = library_row(item_id)
        if row is None:
            return jsonify({"error": "処理済みデータが見つかりません。"}), 404
        try:
            analysis = group_analysis_for_row(row, include_research_rows=True)
            content = json.dumps(
                analysis,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            ).encode("utf-8")
        except (ValueError, TypeError, OverflowError, sqlite3.Error):
            return jsonify({"error": "分析データを出力できません。元データを確認してください。"}), 500
        return send_file(
            io.BytesIO(content),
            mimetype="application/json; charset=utf-8",
            as_attachment=True,
            download_name=f"{safe_output_stem(str(row['source_name']))[:72]}_analysis.json",
        )

    def export_library_analysis_report(item_id: str):
        row = library_row(item_id)
        if row is None:
            return jsonify({"error": "処理済みデータが見つかりません。"}), 404
        try:
            analysis = group_analysis_for_row(row, include_research_rows=True)
            content = focus_group_analysis_report_markdown(analysis).encode("utf-8")
        except (ValueError, TypeError, OverflowError, sqlite3.Error):
            return jsonify({"error": "分析レポートを出力できません。元データを確認してください。"}), 500
        return send_file(
            io.BytesIO(content),
            mimetype="text/markdown; charset=utf-8",
            as_attachment=True,
            download_name=f"{safe_output_stem(str(row['source_name']))[:64]}_分析レポート.md",
        )

    def export_library_analysis_xlsx(item_id: str):
        row = library_row(item_id)
        if row is None:
            return jsonify({"error": "処理済みデータが見つかりません。"}), 404
        try:
            analysis = group_analysis_for_row(row, include_research_rows=True)
            datasets = {
                dataset: analysis_csv_rows(analysis, dataset)
                for dataset in ANALYSIS_CSV_FIELDS
            }
            content = build_analysis_workbook(analysis, datasets)
        except RuntimeError as exc:
            return jsonify({"error": str(exc)}), 503
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except (TypeError, OverflowError, sqlite3.Error):
            return jsonify({"error": "Excel分析データを出力できません。元データを確認してください。"}), 500
        return send_file(
            io.BytesIO(content),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=(
                f"{safe_output_stem(str(row['source_name']))[:64]}_研究分析.xlsx"
            ),
        )

    def export_library_analysis_csv(item_id: str):
        row = library_row(item_id)
        if row is None:
            return jsonify({"error": "処理済みデータが見つかりません。"}), 404
        dataset = request.args.get("dataset", "speakers").strip().lower()
        try:
            analysis = group_analysis_for_row(row, include_research_rows=True)
            content = analysis_csv_content(analysis, dataset)
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except (TypeError, OverflowError, sqlite3.Error):
            return jsonify({"error": "分析データを出力できません。元データを確認してください。"}), 500
        return send_file(
            io.BytesIO(content),
            mimetype="text/csv; charset=utf-8",
            as_attachment=True,
            download_name=(
                f"{safe_output_stem(str(row['source_name']))[:64]}_analysis_{dataset}.csv"
            ),
        )

    def export_meeting_json(item_id: str):
        try:
            row, minutes = meeting_minutes_export_row(item_id)
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        content = json.dumps(
            meeting_external_payload(str(row["source_name"]), minutes, item_id),
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")
        return send_file(
            io.BytesIO(content), mimetype="application/json; charset=utf-8",
            as_attachment=True,
            download_name=f"{safe_output_stem(str(row['source_name']))[:72]}_meeting.json",
        )

    def export_meeting_tasks_csv(item_id: str):
        try:
            row, minutes = meeting_minutes_export_row(item_id)
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        content = ("\ufeff" + meeting_tasks_csv_text(minutes)).encode("utf-8")
        return send_file(
            io.BytesIO(content), mimetype="text/csv; charset=utf-8",
            as_attachment=True,
            download_name=f"{safe_output_stem(str(row['source_name']))[:72]}_tasks.csv",
        )

    def export_meeting_minutes_markdown(item_id: str):
        try:
            row, minutes = meeting_minutes_export_row(item_id)
        except LookupError as exc:
            return jsonify({"error": str(exc)}), 404
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        content = format_meeting_minutes_markdown(str(row["source_name"]), minutes).encode("utf-8")
        return send_file(
            io.BytesIO(content), mimetype="text/markdown; charset=utf-8",
            as_attachment=True,
            download_name=f"{safe_output_stem(str(row['source_name']))[:72]}_meeting_minutes.md",
        )

    def export_conversation_speakers(item_id: str):
        row = library_row(item_id)
        if row is None:
            return jsonify({"error": "データが見つかりません。"}), 404
        segments = row_segments(row)
        raw_names = json_load(row["speaker_names_json"], {})
        speaker_names = raw_names if isinstance(raw_names, dict) else {}
        profiles = row_speaker_profiles(row, segments, speaker_names)
        session = row_session_profile(row)
        registry = {item["id"]: item for item in list_speaker_registry()}
        metrics: dict[str, dict[str, float | int]] = {}
        for segment in segments:
            label = str(segment.get("speaker") or "UNKNOWN")
            start, end = segment_bounds(segment)
            data = metrics.setdefault(label, {"count": 0, "seconds": 0.0, "characters": 0})
            data["count"] = int(data["count"]) + 1
            data["seconds"] = float(data["seconds"]) + max(0.0, end - start)
            data["characters"] = int(data["characters"]) + len(str(segment.get("text") or ""))
        custom_headers = sorted({
            key
            for profile in profiles.values()
            for key in (
                registry.get(profile.get("global_speaker_id"), {}).get("attributes", {}) or {}
            )
        })
        fixed_headers = [
            "会話ID", "データ名", "会話種別", "実施日", "場所", "目的",
            "話者ラベル", "表示名", "グローバル話者ID", "参加者コード",
            "話者登録状態", "テーマカラー", "会話役割", "組織", "部署", "役職", "参加状態",
            "会話固有条件", "メモ", "発話数", "発話秒数", "文字数",
        ]
        stream = io.StringIO(newline="")
        writer = csv.DictWriter(stream, fieldnames=fixed_headers + custom_headers)
        writer.writerow({header: analysis_csv_safe(header) for header in fixed_headers + custom_headers})
        for label, profile in profiles.items():
            global_record = registry.get(profile.get("global_speaker_id"), {})
            metric = metrics.get(label, {"count": 0, "seconds": 0.0, "characters": 0})
            export_row = {
                "会話ID": row["id"],
                "データ名": row["source_name"],
                "会話種別": session["session_type"],
                "実施日": session["session_date"],
                "場所": session["location"],
                "目的": session["objective"],
                "話者ラベル": label,
                "表示名": profile["display_name"] or speaker_names.get(label, ""),
                "グローバル話者ID": profile["global_speaker_id"],
                "参加者コード": global_record.get("participant_code", ""),
                "話者登録状態": {
                    "registered": "登録済み",
                    "temporary_single_group": "一時話者（この会話のみ）",
                    "unidentified": "未特定",
                }.get(profile.get("registration_status"), "未特定"),
                "テーマカラー": profile["theme_color"],
                "会話役割": profile["session_role"],
                "組織": profile["organization"],
                "部署": profile["department"],
                "役職": profile["job_title"],
                "参加状態": profile["attendance_status"],
                "会話固有条件": profile["conditions"],
                "メモ": profile["notes"],
                "発話数": metric["count"],
                "発話秒数": round(float(metric["seconds"]), 3),
                "文字数": metric["characters"],
                **(global_record.get("attributes", {}) or {}),
            }
            writer.writerow({key: analysis_csv_safe(value) for key, value in export_row.items()})
        content = ("\ufeff" + stream.getvalue()).encode("utf-8")
        return send_file(
            io.BytesIO(content),
            mimetype="text/csv; charset=utf-8",
            as_attachment=True,
            download_name=f"{safe_output_stem(str(row['source_name']))[:72]}_speakers.csv",
        )

    # Keep established endpoint names: the security hook and the
    # route-map snapshot depend on them.
    endpoints = (
        ('/api/speakers/export.csv', 'export_speaker_registry', export_speaker_registry, 'GET'),
        ('/api/library/<item_id>/preparation/export.json', 'export_transcript_preparation', export_transcript_preparation, 'GET'),
        ('/api/library/<item_id>/ai-export.zip', 'export_ai_data_bundle', export_ai_data_bundle, 'POST'),
        ('/api/library/<item_id>/analysis/export.json', 'export_library_analysis_json', export_library_analysis_json, 'GET'),
        ('/api/library/<item_id>/analysis/export.md', 'export_library_analysis_report', export_library_analysis_report, 'GET'),
        ('/api/library/<item_id>/analysis/export.xlsx', 'export_library_analysis_xlsx', export_library_analysis_xlsx, 'GET'),
        ('/api/library/<item_id>/analysis/export.csv', 'export_library_analysis_csv', export_library_analysis_csv, 'GET'),
        ('/api/library/<item_id>/meeting.json', 'export_meeting_json', export_meeting_json, 'GET'),
        ('/api/library/<item_id>/meeting-tasks.csv', 'export_meeting_tasks_csv', export_meeting_tasks_csv, 'GET'),
        ('/api/library/<item_id>/meeting-minutes.md', 'export_meeting_minutes_markdown', export_meeting_minutes_markdown, 'GET'),
        ('/api/library/<item_id>/speakers.csv', 'export_conversation_speakers', export_conversation_speakers, 'GET'),
    )
    for rule, endpoint, view, method in endpoints:
        app.add_url_rule(rule, endpoint, view, methods=[method])
