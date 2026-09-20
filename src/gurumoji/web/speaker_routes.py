"""HTTP adapters for the global speaker registry."""

from __future__ import annotations

import sqlite3
from typing import Callable

from flask import Blueprint, Flask, jsonify, request

from ..handlers.speaker_registry import (
    SpeakerRegistryConflictError,
    SpeakerRegistryHandler,
    parse_registry_revision,
)


def register_speaker_routes(
    app: Flask, handler: Callable[[], SpeakerRegistryHandler]
) -> None:
    blueprint = Blueprint("speaker_registry", __name__)

    @blueprint.get("/api/speakers")
    def get_speaker_registry():
        include_inactive = request.args.get("include_inactive", "1") != "0"
        return jsonify(handler().list(include_inactive=include_inactive))

    @blueprint.put("/api/speakers")
    def update_speaker_registry():
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "話者管理の編集内容がJSONではありません。"}), 400
        try:
            records, revision = handler().save(
                payload.get("speakers"),
                delete_ids=payload.get("delete_ids"),
                expected_revision=parse_registry_revision(
                    payload.get("registry_revision")
                ),
            )
            return jsonify({
                "speakers": records,
                "total": len(records),
                "registry_revision": revision,
            })
        except SpeakerRegistryConflictError as exc:
            return jsonify({
                "error": str(exc),
                "conflict": True,
                "current_revision": exc.current_revision,
            }), 409
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except sqlite3.Error as exc:
            return jsonify({"error": f"話者管理データを保存できません: {exc}"}), 500

    app.register_blueprint(blueprint)
