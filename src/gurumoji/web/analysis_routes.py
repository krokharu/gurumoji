"""HTTP adapters for analysis queries and fixed-result commands."""

from __future__ import annotations

import io
import re
import sqlite3
from typing import Callable

from flask import Blueprint, Flask, jsonify, request, send_file

from ..analysis_store import StoreConflict
from ..handlers.analysis_commands import AnalysisCommands, AnalysisCommandNotFound
from ..handlers.analysis_queries import AnalysisQueries, AnalysisQueryNotFound


def register_analysis_routes(
    app: Flask,
    queries: Callable[[], AnalysisQueries],
    commands: Callable[[], AnalysisCommands],
) -> None:
    blueprint = Blueprint("analysis_queries", __name__)

    @blueprint.get("/api/analysis/methods")
    def get_analysis_methods():
        return jsonify(queries().methods())

    @blueprint.get("/api/library/<item_id>/analysis/runs")
    def get_analysis_runs(item_id: str):
        try:
            return jsonify(queries().runs(item_id))
        except AnalysisQueryNotFound as exc:
            return jsonify({"error": str(exc)}), 404

    @blueprint.get("/api/analysis/artifacts/<artifact_id>")
    def get_analysis_artifact(artifact_id: str):
        try:
            artifact = queries().artifact(artifact_id)
            return send_file(
                io.BytesIO(artifact.data),
                mimetype=artifact.media_type,
                as_attachment=True,
                download_name=artifact.download_name,
            )
        except AnalysisQueryNotFound as exc:
            return jsonify({"error": str(exc)}), 404
        except (OSError, ValueError):
            return jsonify({"error": "保存ファイルが移動または変更されています。"}), 409

    @blueprint.post("/api/library/<item_id>/analysis/runs")
    def save_analysis_run(item_id: str):
        payload = request.get_json(silent=True)
        if (
            not isinstance(payload, dict)
            or not isinstance(payload.get("request_id"), str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{16,100}", payload["request_id"])
            or any(
                type(payload.get(key)) is not int
                for key in ("source_revision", "analysis_revision")
            )
        ):
            return jsonify({
                "error": "リクエストIDと保存済みデータのrevisionを指定してください。"
            }), 400
        kwic_request = payload.get("kwic")
        if kwic_request is not None and not isinstance(kwic_request, dict):
            return jsonify({"error": "検索条件が正しくありません。"}), 400
        try:
            run = commands().save(
                item_id,
                request_id=payload["request_id"],
                source_revision=payload["source_revision"],
                analysis_revision=payload["analysis_revision"],
                kwic_request=kwic_request,
                app_url=request.url_root,
            )
            return jsonify({"run": run})
        except AnalysisCommandNotFound as exc:
            return jsonify({"error": str(exc)}), 404
        except StoreConflict as exc:
            return jsonify({"error": str(exc), "conflict": True}), 409
        except (ValueError, TypeError) as exc:
            return jsonify({"error": str(exc)}), 400
        except (OSError, sqlite3.Error):
            return jsonify({
                "error": "分析結果を保存できませんでした。元データは保持されています。"
            }), 500

    @blueprint.post("/api/analysis/runs/<run_id>/vault")
    def retry_analysis_vault(run_id: str):
        try:
            return jsonify({"run": commands().retry_vault(run_id)})
        except AnalysisCommandNotFound as exc:
            return jsonify({"error": str(exc)}), 404
        except (OSError, ValueError, LookupError, sqlite3.Error):
            return jsonify({"error": "Vaultへの再保存に失敗しました。"}), 409

    app.register_blueprint(blueprint)
