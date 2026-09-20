"""HTTP adapters for the global speaker registry."""

from __future__ import annotations

import sqlite3
import subprocess
from typing import Any, Callable

from flask import Blueprint, Flask, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

from ..handlers.speaker_registry import (
    SpeakerIdentificationHandler,
    SpeakerIdentificationRequestError,
    SpeakerRegistryConflictError,
    SpeakerRegistryHandler,
    parse_registry_revision,
)


def register_speaker_routes(
    app: Flask,
    handler: Callable[[], SpeakerRegistryHandler],
    identification: Callable[[], SpeakerIdentificationHandler],
    ai_providers: frozenset[str] | set[str],
    import_csv: Callable[..., tuple[list[dict[str, Any]], int, int]],
    read_upload: Callable[[Any, int], bytes],
    max_csv_bytes: Callable[[], int],
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

    @blueprint.post("/api/library/<item_id>/speaker-identification")
    def rerun_library_speaker_identification(item_id: str):
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return jsonify({"error": "話者特定の指定が JSON ではありません。"}), 400
        provider = str(payload.get("provider") or "").strip().casefold()
        if provider not in ai_providers:
            return jsonify({
                "error": "OpenAI、Google Gemini、またはローカルLLMを選択してください。"
            }), 400
        expected_revision = payload.get("revision_count")
        if isinstance(expected_revision, bool) or not isinstance(expected_revision, int):
            return jsonify({
                "error": "最新の編集内容を保存してから実行してください。"
            }), 400
        try:
            return jsonify(identification().run(
                item_id,
                provider=provider,
                expected_revision=expected_revision,
            ))
        except SpeakerIdentificationRequestError as exc:
            body = {"error": str(exc)}
            if exc.current_revision is not None:
                body.update({
                    "conflict": True,
                    "current_revision": exc.current_revision,
                })
            return jsonify(body), exc.status
        except (LookupError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        except (OSError, sqlite3.Error, subprocess.SubprocessError) as exc:
            return jsonify({"error": f"話者名を保存できません: {exc}"}), 500

    def import_speaker_registry():
        upload = request.files.get("csv_file")
        if upload is None or not upload.filename:
            return jsonify({
                "error": "GoogleフォームまたはスプレッドシートのCSVを選択してください。"
            }), 400
        try:
            expected_revision = parse_registry_revision(
                request.form.get("registry_revision")
            )
            records, imported_count, revision = import_csv(
                read_upload(upload, max_csv_bytes()),
                expected_revision=expected_revision,
            )
            return jsonify({
                "speakers": records,
                "total": len(records),
                "imported_count": imported_count,
                "registry_revision": revision,
            })
        except SpeakerRegistryConflictError as exc:
            return jsonify({
                "error": str(exc),
                "conflict": True,
                "current_revision": exc.current_revision,
            }), 409
        except RequestEntityTooLarge:
            raise
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        except (OSError, sqlite3.Error) as exc:
            return jsonify({"error": f"CSVを取り込めません: {exc}"}), 500

    app.register_blueprint(blueprint)
    # Preserve the endpoint consumed by the global upload-size security hook.
    app.add_url_rule(
        "/api/speakers/import",
        "import_speaker_registry",
        import_speaker_registry,
        methods=["POST"],
    )
