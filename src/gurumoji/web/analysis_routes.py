"""HTTP adapters for read-only analysis queries."""

from __future__ import annotations

import io
from typing import Callable

from flask import Blueprint, Flask, jsonify, send_file

from ..handlers.analysis_queries import AnalysisQueries, AnalysisQueryNotFound


def register_analysis_routes(
    app: Flask, queries: Callable[[], AnalysisQueries]
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

    app.register_blueprint(blueprint)
