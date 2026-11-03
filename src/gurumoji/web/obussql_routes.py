"""Local preview port for the optional ObusSQL integration."""
from __future__ import annotations

from flask import Flask, jsonify, request

from ..services.obussql import ObusSQLError, status


def register_obussql_routes(app: Flask, *, local_access_allowed, service_factory) -> None:
    def integration_status():
        if not local_access_allowed():
            return jsonify({"error": "ObusSQLの接続確認は保存PCから操作してください。"}), 403
        return jsonify(status())

    def notes():
        if not local_access_allowed():
            return jsonify({"error": "管理ノートの一覧は保存PCから操作してください。"}), 403
        try:
            offset = request.args.get("offset", "0")
            if not offset.isascii() or not offset.isdecimal() or len(offset) > 7:
                raise ObusSQLError("invalid_request", "一覧の位置が不正です。", 400)
            return jsonify(service_factory().list_notes(int(offset)))
        except ObusSQLError as exc:
            return jsonify({"error": str(exc), "code": exc.code}), exc.http_status

    def preview():
        if not local_access_allowed():
            return jsonify({"error": "ObusSQLの読取プレビューは保存PCから操作してください。"}), 403
        try:
            return jsonify(service_factory().preview(request.get_json(silent=True)))
        except ObusSQLError as exc:
            return jsonify({"error": str(exc), "code": exc.code}), exc.http_status

    app.add_url_rule("/api/obsidian/obussql", "obussql_status", integration_status, methods=["GET"])
    app.add_url_rule("/api/obsidian/obussql/notes", "obussql_notes", notes, methods=["GET"])
    app.add_url_rule("/api/obsidian/obussql/preview", "obussql_preview", preview, methods=["POST"])
