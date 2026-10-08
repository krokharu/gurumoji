"""HTTP boundary for durable autonomous analysis; GET never calls a model."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Callable

from flask import Blueprint, Flask, Response, jsonify, request

from ..analysis_core import AnalysisContractError, TABLE_PILOT_MAX_BYTES
from ..analysis_store import (StoreConflict, AssetBindingError, HUMAN_RECORD_OPTIONS_MAX_BYTES,
                              human_record_options_offset)


def register_orchestration_routes(app: Flask, service: Callable[[], Any],
                                  prepare: Callable[[dict], dict],
                                  publication: Callable[[], Any] | None = None,
                                  history_viewer: Callable[[], Any] | None = None,
                                  table_reader: Callable[[], Any] | None = None) -> None:
    blueprint = Blueprint("analysis_orchestration", __name__)

    def payload(max_bytes=64 * 1024) -> dict:
        if ((request.content_length and request.content_length > max_bytes)
                or len(request.get_data(cache=True)) > max_bytes):
            raise AnalysisContractError("実行条件が大きすぎます。")
        value = request.get_json(silent=True)
        if not isinstance(value, dict):
            raise AnalysisContractError("実行条件をJSONオブジェクトで指定してください。")
        return value

    def public_run(item_id: str, value: dict) -> dict:
        if publication is None:
            return value
        return {**value, "publication": publication().status(item_id, value["run_id"])}

    @blueprint.errorhandler(AnalysisContractError)
    def contract_error(exc):
        conflict = exc.code in {"revision_conflict", "request_conflict", "active_run", "asset_plan_conflict", "asset_plan_revision",
                                "provider_unavailable", "resume_blocked", "uncertain_execution",
                                "nothing_to_resume", "recovery_required", "version_conflict", "history_integrity_mismatch", "initial_hash_mismatch",
                                "table_run_stopped", "table_run_unavailable", "table_task_limit"}
        return jsonify(error=str(exc), reason_code=exc.code, field=exc.field), 409 if conflict else 400

    @blueprint.errorhandler(StoreConflict)
    def publication_conflict(exc):
        return jsonify(error=str(exc), reason_code=exc.reason if isinstance(exc, AssetBindingError) else "publication_conflict"), 409

    @blueprint.errorhandler(LookupError)
    def not_found(_exc):
        return jsonify(error="対象の会話または分析履歴が見つかりません。"), 404

    @blueprint.errorhandler(sqlite3.Error)
    @blueprint.errorhandler(OSError)
    def storage_error(_exc):
        return jsonify(error="分析台帳を読み書きできません。元データは保持されています。"), 503

    def viewer():
        if history_viewer is not None:
            return history_viewer()
        # Never fall back to the execution factory: its lazy constructor can
        # initialize schema even when the caller only requests a GET.
        raise OSError("read-only history service is not configured")

    def viewer_response(value):
        response = jsonify(value)
        response.headers["Cache-Control"] = "no-store"
        return response

    @blueprint.get("/api/library/<item_id>/analysis/orchestration/viewer")
    def viewer_runs(item_id):
        return viewer_response(viewer().runs(item_id, limit=request.args.get("limit", "20"), offset=request.args.get("offset", "0")))

    @blueprint.get("/api/library/<item_id>/analysis/orchestration/<run_id>/viewer")
    def viewer_timeline(item_id, run_id):
        allowed = ("limit", "offset", "kind", "role", "operation", "status", "after", "before", "annotation_version")
        return viewer_response(viewer().timeline(item_id, run_id, **{key: request.args[key] for key in allowed if key in request.args}))

    @blueprint.get("/api/library/<item_id>/analysis/orchestration/<run_id>/viewer/entries/<entry_id>")
    def viewer_entry(item_id, run_id, entry_id):
        return viewer_response(viewer().entry(item_id, run_id, entry_id, annotation_version=request.args.get("annotation_version"),
                                              evidence_offset=request.args.get("evidence_offset", "0"), evidence_limit=request.args.get("evidence_limit", "30")))

    @blueprint.get("/api/library/<item_id>/analysis/orchestration/<run_id>/viewer/sources/<utterance_id>")
    def viewer_source(item_id, run_id, utterance_id):
        return viewer_response(viewer().source(item_id, run_id, utterance_id, annotation_version=request.args.get("annotation_version")))

    @blueprint.post("/api/library/<item_id>/analysis/orchestration")
    def start(item_id):
        value = service().start(item_id, prepare(payload()), app_url=request.url_root)
        return jsonify(run=public_run(item_id, value)), 202

    @blueprint.get("/api/library/<item_id>/analysis/orchestration")
    def history(item_id):
        return jsonify(runs=[public_run(item_id, value) for value in service().history(item_id)])

    @blueprint.get("/api/library/<item_id>/analysis/orchestration/<run_id>")
    def status(item_id, run_id):
        return jsonify(run=public_run(item_id, service().status(item_id, run_id)))

    @blueprint.post("/api/library/<item_id>/analysis/orchestration/<run_id>/cancel")
    def cancel(item_id, run_id):
        return jsonify(run=public_run(item_id, service().cancel(item_id, run_id)))

    @blueprint.get("/api/library/<item_id>/analysis/orchestration/<run_id>/table-pilot")
    def table_pilot_options(item_id, run_id):
        # Application wiring uses the viewer's readonly connection, never the
        # execution factory. The legacy injected Service constructor is inert.
        try:
            reader = table_reader() if table_reader is not None else service()
            response = viewer_response(reader.table_pilot_options(item_id, run_id, offset=request.args.get("offset", "0")))
        except LookupError as exc:
            return viewer_response({"error": str(exc), "reason_code": "table_selection_unavailable"}), 404
        if len(response.get_data()) > TABLE_PILOT_MAX_BYTES:
            raise AnalysisContractError("選択用の登録情報が上限を超えています。", code="table_selection_byte_limit")
        return response

    @blueprint.post("/api/library/<item_id>/analysis/orchestration/<run_id>/table-pilot/<method_id>")
    def table_pilot_register(item_id, run_id, method_id):
        task = service().register_table_pilot(item_id, run_id, method_id, payload(TABLE_PILOT_MAX_BYTES), server_bound=True)
        return jsonify(task=task), 200 if task["registration_duplicate"] else 202

    @blueprint.post("/api/library/<item_id>/analysis/orchestration/<run_id>/resume")
    def resume(item_id, run_id):
        return jsonify(run=public_run(item_id, service().resume(item_id, run_id, payload()))), 202

    @blueprint.post("/api/library/<item_id>/analysis/orchestration/<run_id>/asset-plans")
    def asset_plan_register(item_id,run_id):
        outcome=service().register_asset_plan(item_id,run_id,payload(TABLE_PILOT_MAX_BYTES))
        return jsonify(outcome),200 if outcome["duplicate"] else 202

    @blueprint.post("/api/library/<item_id>/analysis/orchestration/<run_id>/asset-plans/notifications/<producer_task_id>")
    def asset_plan_notification(item_id,run_id,producer_task_id):
        if payload():raise AnalysisContractError("通知は保存済producerだけを指定してください。",code="asset_notification_body")
        return jsonify(service().notify_asset_output(item_id,run_id,producer_task_id))

    @blueprint.get("/api/library/<item_id>/analysis/orchestration/<run_id>/human-records")
    def human_record_options(item_id, run_id):
        if set(request.args) - {"offset"} or len(request.args.getlist("offset")) > 1:
            raise AnalysisContractError("研究者記録の取得条件が不正です。", code="human_record_options_query")
        offset = human_record_options_offset(request.args.get("offset", "0"))
        # The existing app reader uses mode=ro/query_only. Never initialize an
        # execution service or writer store as a fallback for a missing reader.
        try:
            if table_reader is None: raise OSError("read-only record reader is not configured")
            reader = table_reader()
            item = reader.find_item(item_id)
            if item is None: raise LookupError("対象の会話がありません。")
            if reader.table_store is None: raise OSError("read-only record store is not configured")
            with reader.connect() as db:
                authority = db.execute("PRAGMA database_list").fetchone()[2]
            if not authority or Path(authority).resolve() != reader.table_store.database_file:
                raise OSError("record store authority mismatch")
            stamp = reader.source_fingerprint(item) if reader.source_fingerprint else None
            source = dict(item)
            response = viewer_response(reader.table_store.human_record_options(item_id=item_id,
                execution_run_id=run_id, offset=offset, current_input_hash=stamp,
                current_source_revisions={"source_revision": source.get("revision_count", 0),
                                          "analysis_revision": source.get("analysis_revision", 0)}))
        except LookupError:
            return viewer_response({"error": "対象の会話または固定分析が見つかりません。",
                                    "reason_code": "human_record_options_unavailable"}), 404
        except (sqlite3.Error, OSError):
            return viewer_response({"error": "研究者記録の保存済み台帳を読み取れません。",
                                    "reason_code": "human_record_options_storage_unavailable"}), 503
        if len(response.get_data()) > HUMAN_RECORD_OPTIONS_MAX_BYTES:
            raise AnalysisContractError("研究者記録の選択情報が上限を超えています。", code="human_record_options_byte_limit")
        return response

    @blueprint.post("/api/library/<item_id>/analysis/orchestration/<run_id>/human-records")
    def human_record(item_id, run_id):
        value = payload()
        outcome = service().submit_human_record(item_id, run_id, value, request_bytes=request.get_data(cache=True))
        response = jsonify(outcome)
        response.headers["Cache-Control"] = "no-store"
        return response, 200 if outcome["duplicate"] else 201

    @blueprint.post("/api/library/<item_id>/analysis/orchestration/<run_id>/publication/retry")
    def retry_publication(item_id, run_id):
        if publication is None:
            return jsonify(error="固定成果物の保存・公開を利用できません。"), 503
        value = payload()
        if value:
            raise AnalysisContractError("保存・公開の再試行で条件や公開先を変更できません。")
        publication().retry(item_id, run_id)
        backend = service()
        state = backend.status(item_id, run_id)
        memory = state.get("obsidian_management", {})
        if memory.get("enabled") and memory.get("status") != "unavailable":
            state = backend.sync_memory(item_id, run_id)
        return jsonify(run=public_run(item_id, state))

    @blueprint.post("/api/library/<item_id>/analysis/orchestration/<run_id>/memory/retry")
    def retry_memory(item_id, run_id):
        if payload():
            raise AnalysisContractError("管理ノートの更新で条件・保存先は変更できません。")
        return jsonify(run=public_run(item_id, service().sync_memory(item_id, run_id)))

    @blueprint.get("/api/library/<item_id>/analysis/orchestration/<run_id>/memory/note")
    def memory_note(item_id, run_id):
        return Response(service().memory_note(item_id, run_id), mimetype="text/markdown", headers={
            "Content-Disposition": 'attachment; filename="obsidian-management.md"', "Cache-Control": "no-store"})

    @blueprint.get("/api/library/<item_id>/analysis/orchestration/<run_id>/results")
    def results(item_id, run_id):
        return jsonify(service().result(item_id, run_id))

    @blueprint.get("/api/library/<item_id>/analysis/orchestration/<run_id>/results/<result_id>")
    def result(item_id, run_id, result_id):
        return jsonify(service().result(item_id, run_id, result_id))

    @blueprint.get("/api/library/<item_id>/analysis/orchestration/<run_id>/export.json")
    def export_json(item_id, run_id):
        value = service().result(item_id, run_id)
        return Response(json.dumps(value, ensure_ascii=False, indent=2),
                        mimetype="application/json", headers={
                            "Content-Disposition": 'attachment; filename="analysis-history.json"',
                            "Cache-Control": "no-store",
                        })

    @blueprint.get("/api/library/<item_id>/analysis/orchestration/<run_id>/export.md")
    def export_markdown(item_id, run_id):
        # A download only: never writes into a researcher-owned Vault. The full
        # ledger is included, rather than substituting a lossy LLM summary.
        backend = service()
        state = backend.status(item_id, run_id)
        value = backend.result(item_id, run_id)
        encoded = json.dumps(value, ensure_ascii=False, indent=2)
        text = (
            "---\nnote_type: gurumoji-analysis-history\nresearch_mode: exploratory\n---\n\n"
            "# 自律分析の保存履歴\n\n"
            f"- Run ID: {run_id}\n- 状態: {state.get('status', 'unknown')}\n"
            f"- 終了理由: {state.get('stop_reason') or '未確定'}\n\n"
            "このノートは保存済み台帳の書き出しです。探索的な分析・AIの解釈を含み、"
            "独立検証や批判レビューだけで科学的な確認結果にはなりません。\n\n"
            "初期全量、タスク結果、根拠ID、ラベル版、批判とCoreの応答は以下の履歴を参照してください。"
            "原文を含む場合があるため、保存先と共有範囲を確認してください。\n\n"
            "## 完全な保存履歴\n\n````json\n" + encoded + "\n````\n"
        )
        return Response(text, mimetype="text/markdown", headers={
            "Content-Disposition": 'attachment; filename="gurumoji-analysis-history.md"',
            "Cache-Control": "no-store",
        })

    app.register_blueprint(blueprint)
