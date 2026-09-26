"""Durable M0-M7 execution for the selected first analysis slice."""

from __future__ import annotations

import copy
import json
import math
import sqlite3
import statistics
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Callable

from .analysis_plan_advisor import sign_proposal, verify_proposal
from .analysis_core import (
    AnalysisContractError,
    build_execution_binding,
    build_plan_envelope,
    canonical,
    capability_catalog,
    fingerprint,
    validate_definition,
    validate_planning_proposal,
)
from .env_settings import local_app_url


ACTIVE_STEP_STATES = (
    "checking", "ready", "running", "validating", "persisting", "waiting_resource",
    "retry_wait", "cancelling",
)
TERMINAL_SUCCESS = {"committed", "reused", "not_applicable"}
MILESTONES = tuple(f"M{index}" for index in range(8))
RUNTIME_LOCK = threading.RLock()
RUNTIMES: dict[str, threading.Thread] = {}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def initialize_pipeline_store(connection: sqlite3.Connection) -> None:
    connection.execute("""CREATE TABLE IF NOT EXISTS analysis_definitions (
        item_id TEXT NOT NULL, definition_id TEXT NOT NULL, revision INTEGER NOT NULL,
        status TEXT NOT NULL, payload_json TEXT NOT NULL, last_trial_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        PRIMARY KEY(item_id, definition_id))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS analysis_pipeline_requests (
        pipeline_id TEXT PRIMARY KEY, request_id TEXT NOT NULL UNIQUE, item_id TEXT NOT NULL,
        source_revision INTEGER NOT NULL, analysis_revision INTEGER NOT NULL,
        input_hash TEXT NOT NULL, plan_hash TEXT NOT NULL, plan_json TEXT NOT NULL,
        binding_json TEXT NOT NULL DEFAULT '{}', snapshot_json TEXT NOT NULL,
        status TEXT NOT NULL, current_milestone TEXT NOT NULL DEFAULT 'M0',
        wait_reason TEXT NOT NULL DEFAULT '', result_run_id TEXT NOT NULL DEFAULT '',
        cancel_requested INTEGER NOT NULL DEFAULT 0, generation INTEGER NOT NULL DEFAULT 1,
        error TEXT NOT NULL DEFAULT '', created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
    connection.execute("CREATE INDEX IF NOT EXISTS analysis_pipeline_item ON analysis_pipeline_requests(item_id,created_at)")
    connection.execute("""CREATE TABLE IF NOT EXISTS analysis_step_attempts (
        attempt_id TEXT PRIMARY KEY, pipeline_id TEXT NOT NULL, step_id TEXT NOT NULL,
        milestone TEXT NOT NULL, generation INTEGER NOT NULL, attempt INTEGER NOT NULL,
        status TEXT NOT NULL, directive_json TEXT NOT NULL DEFAULT '{}',
        report_json TEXT NOT NULL DEFAULT '{}', artifact_json TEXT NOT NULL DEFAULT '{}',
        error_code TEXT NOT NULL DEFAULT '', error TEXT NOT NULL DEFAULT '',
        started_at TEXT, updated_at TEXT NOT NULL, ended_at TEXT,
        UNIQUE(pipeline_id,step_id,attempt))""")
    connection.execute("CREATE INDEX IF NOT EXISTS analysis_steps_pipeline ON analysis_step_attempts(pipeline_id,milestone,step_id,attempt)")
    connection.execute("""CREATE TABLE IF NOT EXISTS analysis_pipeline_publications (
        pipeline_id TEXT NOT NULL, target_role TEXT NOT NULL, result_run_id TEXT NOT NULL DEFAULT '',
        package_hash TEXT NOT NULL DEFAULT '', status TEXT NOT NULL, attempt_id TEXT NOT NULL DEFAULT '',
        error TEXT NOT NULL DEFAULT '', updated_at TEXT NOT NULL,
        PRIMARY KEY(pipeline_id,target_role))""")
    connection.execute("""CREATE TABLE IF NOT EXISTS analysis_pipeline_events (
        pipeline_id TEXT NOT NULL, sequence INTEGER NOT NULL, event_type TEXT NOT NULL,
        payload_json TEXT NOT NULL, created_at TEXT NOT NULL,
        PRIMARY KEY(pipeline_id,sequence))""")
    placeholders = ",".join("?" for _ in ACTIVE_STEP_STATES)
    connection.execute(
        f"UPDATE analysis_step_attempts SET status='interrupted',error_code='process_restart',"
        f"error='アプリの再起動により中断しました。固定入力から再開します。',updated_at=? "
        f"WHERE status IN ({placeholders})",
        (utc_now(), *ACTIVE_STEP_STATES),
    )
    connection.execute(
        "UPDATE analysis_pipeline_requests SET status='waiting',wait_reason='retry',"
        "error='アプリの再起動後に再開を待っています。',updated_at=? "
        "WHERE status IN ('accepted','running','cancelling')",
        (utc_now(),),
    )


def _latest_steps(connection: sqlite3.Connection, pipeline_id: str) -> list[dict[str, Any]]:
    rows = connection.execute("""SELECT attempt.* FROM analysis_step_attempts attempt
        JOIN (SELECT step_id,MAX(attempt) AS number FROM analysis_step_attempts
              WHERE pipeline_id=? GROUP BY step_id) latest
          ON latest.step_id=attempt.step_id AND latest.number=attempt.attempt
        WHERE attempt.pipeline_id=? ORDER BY attempt.milestone,attempt.step_id""",
        (pipeline_id, pipeline_id)).fetchall()
    return [dict(row) for row in rows]


def _measurement_value(segment: dict[str, Any], definition: dict[str, Any]) -> Any:
    rule = definition["measurement_rule"]
    column = definition["source_columns"][0]
    value = segment.get(column)
    if rule == "identity":
        return value
    if rule == "text_length":
        return len(str(segment.get("text") or ""))
    if rule == "nonempty":
        return bool(str(value or "").strip())
    if rule == "duration":
        return float(segment.get("duration") or 0)
    if rule == "boolean_true":
        return bool(value)
    raise AnalysisContractError("測定規則を実行できません。", code="measurement_unavailable")


def measure_segments(analysis: dict[str, Any], definitions: list[dict[str, Any]], *, limit: int | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    segments = [segment for segment in analysis.get("segments", []) if not segment.get("excluded")]
    if limit is not None:
        segments = segments[:limit]
    for segment in segments:
        row = {
            "segment_id": segment.get("id"), "speaker": segment.get("speaker"),
            "speaker_name": segment.get("speaker_name"),
        }
        for definition in definitions:
            try:
                row[definition["output_column"]] = _measurement_value(segment, definition)
                row[definition["output_column"] + "__missing_reason"] = ""
            except (TypeError, ValueError):
                row[definition["output_column"]] = None
                row[definition["output_column"] + "__missing_reason"] = "invalid_source_value"
        rows.append(row)
    return rows


def _manual_method(definitions: list[dict[str, Any]], rows: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, tuple[list[str], list[dict[str, Any]]]]]:
    fields = ["segment_id", "speaker", "speaker_name"]
    summaries = []
    for definition in definitions:
        column = definition["output_column"]
        fields.extend((column, column + "__missing_reason"))
        values = [row[column] for row in rows if row.get(column) is not None]
        if definition["method"] == "descriptive":
            numeric = [float(value) for value in values if isinstance(value, (int, float)) and not isinstance(value, bool)]
            text = f"有効N={len(numeric)}"
            if numeric:
                text += f"、平均={statistics.fmean(numeric):.3f}、最小={min(numeric):.3f}、最大={max(numeric):.3f}"
        else:
            counts: dict[str, int] = {}
            for value in values:
                key = str(value)
                counts[key] = counts.get(key, 0) + 1
            text = f"有効N={len(values)}、度数=" + json.dumps(counts, ensure_ascii=False, sort_keys=True)
        summaries.append({"title": definition["name"], "text": text})
    method = {
        "method_id": "descriptive_statistics", "method_version": "analysis-pipeline-1",
        "title": "手入力定義の記述集計", "status": "completed",
        "datasets": ["measurements"], "findings": [], "summaries": summaries,
        "details": {"definitions": definitions},
        "previews": [{"dataset": "measurements", "fields": fields, "rows": rows[:10], "total": len(rows)}],
        "analysis_unit": "発話", "engine": {"name": "manual-measurement", "version": 1},
        "limitations": ["研究者が入力した定義に基づく記述集計です。推測統計は実行していません。"],
    }
    return method, {"measurements": (fields, rows)}


class AnalysisPipelineService:
    """Coordinate one durable pipeline using injected application boundaries."""

    def __init__(
        self, *, connect: Callable[[], sqlite3.Connection], find_item: Callable[[str], Any],
        source_fingerprint: Callable[[Any], str], snapshot_builder: Callable[[Any], dict[str, Any]],
        method_runner: Callable[[str, dict[str, Any]], dict[str, Any]],
        save_result: Callable[..., dict[str, Any]], publish_result: Callable[[str], dict[str, Any]],
        publication_outcomes: Callable[[str], dict[str, dict[str, str]]],
        public_run: Callable[[dict[str, Any]], dict[str, Any]],
        runtime_key: str,
        plan_advisor: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] | None = None,
    ) -> None:
        self.connect = connect
        self.find_item = find_item
        self.source_fingerprint = source_fingerprint
        self.snapshot_builder = snapshot_builder
        self.method_runner = method_runner
        self.save_result = save_result
        self.publish_result = publish_result
        self.publication_outcomes = publication_outcomes
        self.public_run = public_run
        self.runtime_key = runtime_key
        self.plan_advisor = plan_advisor

    def capabilities(self) -> dict[str, Any]:
        return capability_catalog()

    def _definitions(self, item_id: str, ids: list[str], *, adopted_only: bool = True) -> list[dict[str, Any]]:
        if not ids:
            return []
        with self.connect() as connection:
            rows = connection.execute(
                f"SELECT * FROM analysis_definitions WHERE item_id=? AND definition_id IN ({','.join('?' for _ in ids)})",
                (item_id, *ids),
            ).fetchall()
        by_id = {row["definition_id"]: row for row in rows}
        missing = [value for value in ids if value not in by_id]
        if missing:
            raise AnalysisContractError("定義が見つかりません: " + ", ".join(missing), code="definition_missing")
        if adopted_only:
            drafts = [value for value in ids if by_id[value]["status"] != "adopted"]
            if drafts:
                raise AnalysisContractError("試行後に定義を採用してください: " + ", ".join(drafts), code="definition_not_adopted")
        return [json.loads(by_id[value]["payload_json"]) for value in ids]

    def save_definition(self, item_id: str, definition_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if definition_id != payload.get("definition_id"):
            raise AnalysisContractError("URLと本文のdefinition_idが一致しません。", field="definition_id")
        value = validate_definition(payload)
        status = payload.get("status", "draft")
        if status not in {"draft", "adopted", "retired"}:
            raise AnalysisContractError("定義のstatusが正しくありません。", field="status")
        expected_revision = payload.get("expected_revision")
        now = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM analysis_definitions WHERE item_id=? AND definition_id=?",
                (item_id, definition_id),
            ).fetchone()
            if existing is not None and expected_revision != existing["revision"]:
                raise AnalysisContractError("定義が更新されています。再読み込みしてください。", code="revision_conflict")
            if existing is None and expected_revision not in (None, 0):
                raise AnalysisContractError("新規定義のexpected_revisionは0です。", code="revision_conflict")
            revision = (int(existing["revision"]) + 1) if existing else 1
            value["version"] = revision
            connection.execute("""INSERT INTO analysis_definitions
                (item_id,definition_id,revision,status,payload_json,last_trial_json,created_at,updated_at)
                VALUES (?,?,?,?,?,'{}',?,?) ON CONFLICT(item_id,definition_id) DO UPDATE SET
                revision=excluded.revision,status=excluded.status,payload_json=excluded.payload_json,
                updated_at=excluded.updated_at""",
                (item_id, definition_id, revision, status, canonical(value).decode("utf-8"),
                 existing["created_at"] if existing else now, now),
            )
        return {**value, "revision": revision, "status": status, "updated_at": now}

    def trial_definition(self, item_id: str, definition_id: str, *, limit: int = 20) -> dict[str, Any]:
        if not 1 <= int(limit) <= 100:
            raise AnalysisContractError("試行件数は1〜100です。", field="limit")
        definitions = self._definitions(item_id, [definition_id], adopted_only=False)
        item = self.find_item(item_id)
        if item is None:
            raise LookupError("分析対象が見つかりません。")
        snapshot = self.snapshot_builder(item)
        rows = measure_segments(snapshot["analysis"], definitions, limit=int(limit))
        column = definitions[0]["output_column"]
        values = [row[column] for row in rows if row.get(column) is not None]
        trial = {
            "definition_id": definition_id, "input_hash": snapshot["input_hash"],
            "sample_size": len(rows), "valid_count": len(values),
            "missing_count": len(rows) - len(values), "values": values[:20],
            "external_calls": 0, "created_at": utc_now(),
        }
        with self.connect() as connection:
            connection.execute(
                "UPDATE analysis_definitions SET last_trial_json=?,updated_at=? WHERE item_id=? AND definition_id=?",
                (canonical(trial).decode("utf-8"), utc_now(), item_id, definition_id),
            )
        return trial

    def preview(self, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        item = self.find_item(item_id)
        if item is None:
            raise LookupError("分析対象が見つかりません。")
        source_revision = int(item["revision_count"] or 0)
        analysis_revision = int(item["analysis_revision"] or 0)
        if payload.get("source_revision") != source_revision or payload.get("analysis_revision") != analysis_revision:
            raise AnalysisContractError("入力版が更新されています。", code="revision_conflict")
        ids = payload.get("definition_ids", [])
        if not isinstance(ids, list) or any(not isinstance(value, str) for value in ids):
            raise AnalysisContractError("definition_idsはIDの配列です。", field="definition_ids")
        definitions = self._definitions(item_id, ids)
        snapshot = self.snapshot_builder(item)
        if payload.get("planning_proposal") is not None:
            verify_proposal(payload["planning_proposal"])
        envelope = build_plan_envelope(
            item_id=item_id, source_revision=source_revision, analysis_revision=analysis_revision,
            input_fingerprint=snapshot["input_hash"], payload=payload, definitions=definitions,
            segment_count=len(snapshot["analysis"].get("segments", [])),
        )
        binding = build_execution_binding(envelope, definitions)
        return {"plan": envelope, "binding": binding, "definitions": definitions,
                "capabilities": capability_catalog()["capabilities"]}

    def propose(self, item_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        if self.plan_advisor is None:
            raise AnalysisContractError("計画候補の生成を利用できません。", code="method_unavailable")
        item = self.find_item(item_id)
        if item is None:
            raise LookupError("分析対象が見つかりません。")
        source_revision = int(item["revision_count"] or 0)
        analysis_revision = int(item["analysis_revision"] or 0)
        if (payload.get("source_revision") != source_revision
                or payload.get("analysis_revision") != analysis_revision):
            raise AnalysisContractError("入力版が更新されています。", code="revision_conflict")
        snapshot = self.snapshot_builder(item)
        proposal = self.plan_advisor(snapshot, payload)
        latest = self.find_item(item_id)
        if (latest is None
                or int(latest["revision_count"] or 0) != source_revision
                or int(latest["analysis_revision"] or 0) != analysis_revision
                or self.source_fingerprint(latest) != snapshot["input_hash"]):
            raise AnalysisContractError("候補生成中に入力が更新されました。", code="revision_conflict")
        normalized = validate_planning_proposal(
            proposal, input_hash=snapshot["input_hash"],
            source_revision=source_revision, analysis_revision=analysis_revision,
            provider_policy=payload.get("provider_policy", "local_only"),
        )
        return {"proposal": sign_proposal(normalized)}

    def start(self, item_id: str, payload: dict[str, Any], *, app_url: str) -> tuple[dict[str, Any], int]:
        request_id = payload.get("request_id")
        if not isinstance(request_id, str) or not 16 <= len(request_id) <= 100 or not request_id.replace("-", "").replace("_", "").isalnum():
            raise AnalysisContractError("request_idが正しくありません。", field="request_id")
        preview = self.preview(item_id, payload)
        if preview["plan"]["eligibility"]["execution"] != "allowed":
            raise AnalysisContractError("必須の適用性検査に合格していません。", code="ineligible")
        item = self.find_item(item_id)
        snapshot = self.snapshot_builder(item)
        if snapshot["input_hash"] != preview["plan"]["input_hash"]:
            raise AnalysisContractError("計画確認中に入力が更新されました。", code="revision_conflict")
        library_key = self.runtime_key
        pipeline_id = uuid.uuid5(uuid.NAMESPACE_URL, library_key + request_id).hex
        now = utc_now()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM analysis_pipeline_requests WHERE request_id=?", (request_id,)
            ).fetchone()
            if existing:
                if existing["item_id"] != item_id or existing["plan_hash"] != preview["plan"]["plan_hash"]:
                    raise AnalysisContractError("request_idが別の計画に使われています。", code="request_conflict")
                result = self.status(item_id, existing["pipeline_id"], ensure_running=False)
                if result["status"] in {"accepted", "running", "waiting"}:
                    self._schedule(existing["pipeline_id"], app_url)
                return result, 200
            connection.execute("""INSERT INTO analysis_pipeline_requests
                (pipeline_id,request_id,item_id,source_revision,analysis_revision,input_hash,plan_hash,
                 plan_json,binding_json,snapshot_json,status,current_milestone,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,'accepted','M0',?,?)""",
                (pipeline_id, request_id, item_id, item["revision_count"], item["analysis_revision"],
                 snapshot["input_hash"], preview["plan"]["plan_hash"],
                 canonical(preview["plan"]).decode("utf-8"), canonical(preview["binding"]).decode("utf-8"),
                 canonical(snapshot).decode("utf-8"), now, now),
            )
            for step in preview["plan"]["steps"]:
                attempt_id = uuid.uuid5(uuid.NAMESPACE_URL, pipeline_id + step["step_id"] + ":1").hex
                directive = {
                    "contract": "HandlerDirective", "pipeline_id": pipeline_id,
                    "step_id": step["step_id"], "attempt_id": attempt_id,
                    "generation": 1, "milestone": step["milestone"], "operation": "execute",
                    "input_hash": snapshot["input_hash"], "plan_hash": preview["plan"]["plan_hash"],
                }
                connection.execute("""INSERT INTO analysis_step_attempts
                    (attempt_id,pipeline_id,step_id,milestone,generation,attempt,status,directive_json,updated_at)
                    VALUES (?,?,?,?,?,1,'planned',?,?)""",
                    (attempt_id, pipeline_id, step["step_id"], step["milestone"], 1,
                     canonical(directive).decode("utf-8"), now),
                )
            for target in ("input", "orchestrator", "visualization"):
                status = "pending" if target in preview["plan"]["publication_targets"] else "not_selected"
                connection.execute("""INSERT INTO analysis_pipeline_publications
                    (pipeline_id,target_role,status,updated_at) VALUES (?,?,?,?)""",
                    (pipeline_id, target, status, now),
                )
            self._event(connection, pipeline_id, "pipeline_accepted", {
                "plan_hash": preview["plan"]["plan_hash"], "input_hash": snapshot["input_hash"]})
        self._schedule(pipeline_id, app_url)
        return self.status(item_id, pipeline_id, ensure_running=False), 202

    def _event(self, connection: sqlite3.Connection, pipeline_id: str, kind: str, payload: dict[str, Any]) -> None:
        sequence = connection.execute(
            "SELECT COALESCE(MAX(sequence),0)+1 FROM analysis_pipeline_events WHERE pipeline_id=?",
            (pipeline_id,),
        ).fetchone()[0]
        connection.execute(
            "INSERT INTO analysis_pipeline_events(pipeline_id,sequence,event_type,payload_json,created_at) VALUES (?,?,?,?,?)",
            (pipeline_id, sequence, kind, canonical(payload).decode("utf-8"), utc_now()),
        )

    def _schedule(self, pipeline_id: str, app_url: str) -> None:
        key = self.runtime_key + ":" + pipeline_id
        with RUNTIME_LOCK:
            current = RUNTIMES.get(key)
            if current and current.is_alive():
                return
            thread = threading.Thread(
                target=self._run_guarded, args=(pipeline_id, app_url, key),
                name=f"analysis-pipeline-{pipeline_id[:8]}", daemon=True,
            )
            RUNTIMES[key] = thread
            thread.start()

    def _run_guarded(self, pipeline_id: str, app_url: str, runtime_key: str) -> None:
        try:
            self._run(pipeline_id, app_url)
        except Exception as exc:  # last-resort boundary: persist, never lose the reason
            with self.connect() as connection:
                connection.execute(
                    "UPDATE analysis_pipeline_requests SET status='failed',error=?,updated_at=? WHERE pipeline_id=? AND status NOT IN ('completed','cancelled')",
                    (str(exc)[:1000], utc_now(), pipeline_id),
                )
                self._event(connection, pipeline_id, "pipeline_failed", {"error": str(exc)[:1000]})
        finally:
            with RUNTIME_LOCK:
                RUNTIMES.pop(runtime_key, None)

    def _pipeline_row(self, pipeline_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM analysis_pipeline_requests WHERE pipeline_id=?", (pipeline_id,)
            ).fetchone()
        if row is None:
            raise LookupError("分析pipelineが見つかりません。")
        return dict(row)

    def _cancelled(self, pipeline_id: str, generation: int) -> bool:
        row = self._pipeline_row(pipeline_id)
        return bool(row["cancel_requested"]) or int(row["generation"]) != int(generation)

    def _set_step(self, attempt_id: str, status: str, *, artifact: Any = None,
                  report: Any = None, error_code: str = "", error: str = "") -> None:
        now = utc_now()
        fields = ["status=?", "updated_at=?", "error_code=?", "error=?"]
        values: list[Any] = [status, now, error_code, error]
        if status == "running":
            fields.append("started_at=COALESCE(started_at,?)")
            values.append(now)
        if status in TERMINAL_SUCCESS | {"failed", "cancelled", "interrupted"}:
            fields.append("ended_at=?")
            values.append(now)
        if artifact is not None:
            fields.append("artifact_json=?")
            values.append(canonical(artifact).decode("utf-8"))
        if report is not None:
            fields.append("report_json=?")
            values.append(canonical(report).decode("utf-8"))
        values.append(attempt_id)
        with self.connect() as connection:
            connection.execute(
                "UPDATE analysis_step_attempts SET " + ",".join(fields) + " WHERE attempt_id=?",
                tuple(values),
            )

    def _execute_step(self, pipeline: dict[str, Any], step: dict[str, Any], snapshot: dict[str, Any],
                      definitions: list[dict[str, Any]], app_url: str) -> dict[str, Any]:
        attempt_id = step["attempt_id"]
        generation = int(step["generation"])
        if self._cancelled(pipeline["pipeline_id"], generation):
            self._set_step(attempt_id, "cancelled", error_code="cancelled", error="開始前に取り消されました。")
            return {"status": "cancelled"}
        self._set_step(attempt_id, "checking")
        plan_steps = {value["step_id"]: value for value in json.loads(pipeline["plan_json"])["steps"]}
        spec = plan_steps[step["step_id"]]
        if spec.get("allow_not_applicable") and (
            step["step_id"] in {"outline_scope", "comparison_scope"}
            or (step["step_id"] == "manual_measurement" and not definitions)
            or (step["step_id"] == "publish_result" and not json.loads(pipeline["plan_json"])["publication_targets"])
        ):
            artifact = {"reason_code": "not_selected", "rule_version": "analysis-core-1", "verified_by": "analysis_core"}
            self._set_step(attempt_id, "not_applicable", artifact=artifact, report={"status": "not_applicable"})
            return {"status": "not_applicable", "artifact": artifact}
        self._set_step(attempt_id, "ready")
        self._set_step(attempt_id, "running")
        step_id = step["step_id"]
        if step_id == "freeze_input":
            artifact = {"input_hash": snapshot["input_hash"], "source_revision": pipeline["source_revision"],
                        "analysis_revision": pipeline["analysis_revision"]}
        elif step_id in {"participation", "conversation_dynamics"}:
            artifact = self.method_runner(step_id, copy.deepcopy(snapshot))
        elif step_id == "chart_specs":
            artifact = {"chart_specs": self._chart_specs(pipeline["pipeline_id"])}
        elif step_id == "execution_binding":
            artifact = json.loads(pipeline["binding_json"])
        elif step_id == "manual_measurement":
            rows = measure_segments(snapshot["analysis"], definitions)
            method, datasets = _manual_method(definitions, rows)
            artifact = {"method": method, "datasets": {name: {"fields": value[0], "rows": value[1]} for name, value in datasets.items()}}
        elif step_id == "save_result":
            if self._cancelled(pipeline["pipeline_id"], generation):
                raise AnalysisContractError("保存確定前に取り消されました。", code="cancelled")
            artifact = self._save_package(pipeline, snapshot, definitions, app_url)
        elif step_id == "publish_result":
            artifact = self._publish_package(pipeline)
            if any(value["status"] != "published" for value in artifact["outcomes"].values()
                   if value["status"] != "not_selected"):
                raise AnalysisContractError("選択したVaultへの公開を完了できませんでした。", code="publication_failed")
        else:
            raise AnalysisContractError("未対応のstepです。", code="step_unavailable")
        if self._cancelled(pipeline["pipeline_id"], generation) and step_id != "save_result":
            self._set_step(attempt_id, "cancelled", artifact=artifact, error_code="cancelled", error="結果到着後に取り消されました。")
            return {"status": "cancelled", "artifact": artifact}
        self._set_step(attempt_id, "validating")
        canonical(artifact)  # JSON/NaN validation before persistence
        self._set_step(attempt_id, "persisting")
        report = {
            "contract": "HandlerReport", "pipeline_id": pipeline["pipeline_id"],
            "step_id": step_id, "attempt_id": attempt_id, "generation": generation,
            "status": "completed", "input_hash": pipeline["input_hash"],
        }
        self._set_step(attempt_id, "committed", artifact=artifact, report=report)
        return {"status": "committed", "artifact": artifact}

    def _chart_specs(self, pipeline_id: str) -> list[dict[str, Any]]:
        artifacts = self._artifacts(pipeline_id)
        specs = []
        for method_id in ("participation", "conversation_dynamics"):
            artifact = artifacts.get(method_id, {})
            for dataset, table in artifact.get("datasets", {}).items():
                fields = table.get("fields", [])
                specs.append({
                    "chart_id": f"{pipeline_id}:{dataset}", "visual_id": f"V-{dataset}",
                    "dataset_ref": dataset, "source_hash": fingerprint(table.get("rows", [])),
                    "grain": "speaker" if dataset == "speakers" else "conversation_event",
                    "filters": [], "encodings": {"fields": fields}, "category_order": [],
                    "palette": "gurumoji-default", "value_format": "auto",
                    "denominator": "fixed_dataset", "missing_policy": "show",
                    "evidence_ref": "input_snapshot", "layout_ref": "table-or-deterministic-svg",
                    "title": dataset, "captions": {"unit": "dataset rows", "n": len(table.get("rows", []))},
                    "size": {"width": 960, "height": 540}, "font": "system-ui",
                })
        return specs

    def _artifacts(self, pipeline_id: str) -> dict[str, Any]:
        with self.connect() as connection:
            steps = _latest_steps(connection, pipeline_id)
        values = {}
        for step in steps:
            if step["artifact_json"]:
                try:
                    values[step["step_id"]] = json.loads(step["artifact_json"])
                except json.JSONDecodeError:
                    continue
        return values

    def _save_package(self, pipeline: dict[str, Any], snapshot: dict[str, Any],
                      definitions: list[dict[str, Any]], app_url: str) -> dict[str, Any]:
        artifacts = self._artifacts(pipeline["pipeline_id"])
        methods = []
        datasets: dict[str, tuple[list[str], list[dict[str, Any]]]] = {}
        for step_id in ("participation", "conversation_dynamics", "manual_measurement"):
            value = artifacts.get(step_id, {})
            if value.get("method"):
                methods.append(value["method"])
            for name, table in value.get("datasets", {}).items():
                datasets[name] = (table["fields"], table["rows"])
        plan = json.loads(pipeline["plan_json"])
        parameters = {
            "pipeline_id": pipeline["pipeline_id"], "plan_hash": pipeline["plan_hash"],
            "binding": json.loads(pipeline["binding_json"]), "definitions": definitions,
            "research_protocol": plan["research_protocol"],
        }
        if "planning_proposal" in plan:
            parameters["planning_proposal"] = plan["planning_proposal"]
        result = {
            "schema_version": 1,
            "parameters": parameters,
            "algorithms": {"analysis_pipeline": "analysis-pipeline-1"},
            "methods": methods, "chart_specs": artifacts.get("chart_specs", {}).get("chart_specs", []),
        }
        request_id = "pipeline-result-" + pipeline["pipeline_id"]
        run = self.save_result(
            item_id=pipeline["item_id"], kind="milestone_analysis",
            snapshot=snapshot["archive_snapshot"], result=result, datasets=datasets,
            request_id=request_id, input_fingerprint=pipeline["input_hash"],
            source_revision=pipeline["source_revision"], analysis_revision=pipeline["analysis_revision"],
            app_url=app_url, publish=False,
        )
        current_item = self.find_item(pipeline["item_id"])
        if current_item is None or self.source_fingerprint(current_item) != pipeline["input_hash"]:
            with self.connect() as connection:
                connection.execute("UPDATE analysis_runs SET stale=1 WHERE id=?", (run["id"],))
            run = {**run, "stale": 1}
        package_hash = str(run.get("fingerprint") or fingerprint({"run_id": run["id"], "methods": methods}))
        with self.connect() as connection:
            connection.execute(
                "UPDATE analysis_pipeline_requests SET result_run_id=?,updated_at=? WHERE pipeline_id=?",
                (run["id"], utc_now(), pipeline["pipeline_id"]),
            )
            connection.execute(
                "UPDATE analysis_pipeline_publications SET result_run_id=?,package_hash=?,updated_at=? WHERE pipeline_id=?",
                (run["id"], package_hash, utc_now(), pipeline["pipeline_id"]),
            )
        return {"result_run_id": run["id"], "package_hash": package_hash, "status": run["status"]}

    def _publish_package(self, pipeline: dict[str, Any]) -> dict[str, Any]:
        current = self._pipeline_row(pipeline["pipeline_id"])
        run_id = current["result_run_id"]
        if not run_id:
            raise AnalysisContractError("保存済みresult_runがありません。", code="result_missing")
        plan = json.loads(current["plan_json"])
        selected = set(plan["publication_targets"])
        with self.connect() as connection:
            connection.execute(
                "UPDATE analysis_pipeline_publications SET status='publishing',error='',updated_at=? "
                "WHERE pipeline_id=? AND target_role IN ({})".format(",".join("?" for _ in selected)),
                (utc_now(), current["pipeline_id"], *selected) if selected else (utc_now(), current["pipeline_id"]),
            ) if selected else None
        self.publish_result(run_id)
        outcomes = self.publication_outcomes(run_id)
        with self.connect() as connection:
            for target in ("input", "orchestrator", "visualization"):
                value = outcomes.get(target, {"status": "unknown", "error": "公開結果を確認できません。"})
                status = value["status"] if target in selected else "not_selected"
                connection.execute("""UPDATE analysis_pipeline_publications
                    SET status=?,error=?,updated_at=? WHERE pipeline_id=? AND target_role=?""",
                    (status, str(value.get("error") or ""), utc_now(), current["pipeline_id"], target),
                )
        return {"result_run_id": run_id, "outcomes": {
            target: outcomes.get(target, {"status": "unknown"}) if target in selected else {"status": "not_selected"}
            for target in ("input", "orchestrator", "visualization")
        }}

    def _run(self, pipeline_id: str, app_url: str) -> None:
        pipeline = self._pipeline_row(pipeline_id)
        if pipeline["status"] in {"completed", "cancelled", "failed"}:
            return
        generation = int(pipeline["generation"])
        definitions = self._definitions(
            pipeline["item_id"],
            [slot["definition_id"] for slot in json.loads(pipeline["binding_json"])["resolved"]],
        )
        snapshot = json.loads(pipeline["snapshot_json"])
        with self.connect() as connection:
            connection.execute(
                "UPDATE analysis_pipeline_requests SET status='running',wait_reason='',error='',updated_at=? WHERE pipeline_id=?",
                (utc_now(), pipeline_id),
            )
            self._event(connection, pipeline_id, "pipeline_running", {"generation": generation})
        for milestone in MILESTONES:
            pipeline = self._pipeline_row(pipeline_id)
            if self._cancelled(pipeline_id, generation):
                with self.connect() as connection:
                    connection.execute(
                        "UPDATE analysis_pipeline_requests SET status='cancelled',current_milestone=?,updated_at=? WHERE pipeline_id=?",
                        (milestone, utc_now(), pipeline_id),
                    )
                    self._event(connection, pipeline_id, "pipeline_cancelled", {"milestone": milestone})
                return
            plan_steps = {
                value["step_id"]: value
                for value in json.loads(pipeline["plan_json"])["steps"]
            }
            with self.connect() as connection:
                connection.execute(
                    "UPDATE analysis_pipeline_requests SET current_milestone=?,updated_at=? WHERE pipeline_id=?",
                    (milestone, utc_now(), pipeline_id),
                )
                self._event(connection, pipeline_id, "milestone_started", {"milestone": milestone})
            while True:
                with self.connect() as connection:
                    all_steps = _latest_steps(connection, pipeline_id)
                by_id = {step["step_id"]: step for step in all_steps}
                pending = [
                    step for step in all_steps
                    if step["milestone"] == milestone and step["status"] not in TERMINAL_SUCCESS
                ]
                if not pending:
                    break
                ready = [
                    step for step in pending
                    if step["status"] not in {"failed", "cancelled"}
                    and all(by_id.get(parent, {}).get("status") in TERMINAL_SUCCESS
                            for parent in plan_steps[step["step_id"]].get("parents", []))
                ]
                if not ready:
                    raise AnalysisContractError(
                        "親stepが未確定のため段階を進められません。", code="parent_incomplete"
                    )
                # M2 has two independent adapters and is observably concurrent.
                # Parent-dependent M7 publication is selected only after save_result.
                with ThreadPoolExecutor(max_workers=max(1, min(2, len(ready))),
                                        thread_name_prefix=f"{milestone}-analysis") as executor:
                    futures = {
                        executor.submit(self._execute_step, pipeline, step, snapshot, definitions, app_url): step
                        for step in ready
                    }
                    failed: list[tuple[dict[str, Any], Exception]] = []
                    for future in as_completed(futures):
                        step = futures[future]
                        try:
                            future.result()
                        except Exception as exc:
                            code = exc.code if isinstance(exc, AnalysisContractError) else "execution_failed"
                            self._set_step(step["attempt_id"], "failed", error_code=code, error=str(exc)[:1000])
                            failed.append((step, exc))
                    if self._cancelled(pipeline_id, generation):
                        with self.connect() as connection:
                            connection.execute(
                                "UPDATE analysis_pipeline_requests SET status='cancelled',current_milestone=?,updated_at=? WHERE pipeline_id=?",
                                (milestone, utc_now(), pipeline_id),
                            )
                            self._event(connection, pipeline_id, "pipeline_cancelled", {"milestone": milestone})
                        return
                    if failed:
                        reason = "publication" if any(
                            isinstance(exc, AnalysisContractError) and exc.code == "publication_failed"
                            for _, exc in failed
                        ) else "retry"
                        with self.connect() as connection:
                            connection.execute(
                                "UPDATE analysis_pipeline_requests SET status='waiting',wait_reason=?,error=?,updated_at=? WHERE pipeline_id=?",
                                (reason, str(failed[0][1])[:1000], utc_now(), pipeline_id),
                            )
                            self._event(connection, pipeline_id, "milestone_waiting", {
                                "milestone": milestone, "reason": reason,
                                "failed_steps": [value[0]["step_id"] for value in failed]})
                        return
            with self.connect() as connection:
                final_steps = [step for step in _latest_steps(connection, pipeline_id) if step["milestone"] == milestone]
                if any(step["status"] not in TERMINAL_SUCCESS for step in final_steps):
                    raise AnalysisContractError("段階の必須stepが未確定です。", code="gate_incomplete")
                self._event(connection, pipeline_id, "milestone_committed", {"milestone": milestone})
        current = self._pipeline_row(pipeline_id)
        with self.connect() as connection:
            publications = connection.execute(
                "SELECT * FROM analysis_pipeline_publications WHERE pipeline_id=?", (pipeline_id,)
            ).fetchall()
            if any(row["status"] not in {"published", "not_selected"} for row in publications):
                connection.execute(
                    "UPDATE analysis_pipeline_requests SET status='waiting',wait_reason='publication',updated_at=? WHERE pipeline_id=?",
                    (utc_now(), pipeline_id),
                )
                return
            connection.execute(
                "UPDATE analysis_pipeline_requests SET status='completed',wait_reason='',error='',current_milestone='M7',updated_at=? WHERE pipeline_id=?",
                (utc_now(), pipeline_id),
            )
            self._event(connection, pipeline_id, "pipeline_completed", {"result_run_id": current["result_run_id"]})

    def status(self, item_id: str, pipeline_id: str, *, ensure_running: bool = True) -> dict[str, Any]:
        row = self._pipeline_row(pipeline_id)
        if row["item_id"] != item_id:
            raise LookupError("分析pipelineが見つかりません。")
        with self.connect() as connection:
            steps = _latest_steps(connection, pipeline_id)
            publications = [dict(value) for value in connection.execute(
                "SELECT * FROM analysis_pipeline_publications WHERE pipeline_id=? ORDER BY target_role",
                (pipeline_id,),
            ).fetchall()]
            events = [dict(value) for value in connection.execute(
                "SELECT * FROM analysis_pipeline_events WHERE pipeline_id=? ORDER BY sequence DESC LIMIT 80",
                (pipeline_id,),
            ).fetchall()][::-1]
        if (ensure_running and row["status"] == "waiting" and row["wait_reason"] == "retry"
                and any(step["status"] == "interrupted" and step["error_code"] == "process_restart"
                        for step in steps)):
            self.retry(item_id, pipeline_id, {}, app_url=local_app_url())
            return self.status(item_id, pipeline_id, ensure_running=False)
        milestones = []
        for milestone in MILESTONES:
            values = [step for step in steps if step["milestone"] == milestone]
            statuses = [value["status"] for value in values]
            if statuses and all(value in TERMINAL_SUCCESS for value in statuses):
                status = "committed"
            elif any(value == "failed" for value in statuses):
                status = "failed"
            elif any(value in ACTIVE_STEP_STATES for value in statuses):
                status = "active"
            elif any(value == "cancelled" for value in statuses):
                status = "cancelled"
            else:
                status = "pending"
            milestones.append({"id": milestone, "status": status, "steps": [self._public_step(value) for value in values]})
        result_run = None
        if row["result_run_id"]:
            try:
                result_run = self.public_run({"id": row["result_run_id"]})
            except (LookupError, KeyError, TypeError):
                result_run = {"id": row["result_run_id"]}
        completed = sum(step["status"] in TERMINAL_SUCCESS for step in steps)
        proposal = json.loads(row["plan_json"]).get("planning_proposal")
        planning = ({key: proposal[key] for key in
                     ("objective", "provider", "model", "primary_method")}
                    if isinstance(proposal, dict) else None)
        return {
            "contract": "AnalysisResponse", "pipeline_id": pipeline_id,
            "request_id": row["request_id"], "item_id": item_id, "status": row["status"],
            "current_milestone": row["current_milestone"], "wait_reason": row["wait_reason"],
            "error": row["error"], "plan_hash": row["plan_hash"], "input_hash": row["input_hash"],
            "progress": round(100 * completed / len(steps)) if steps else 0,
            "planning": planning,
            "milestones": milestones,
            "publications": [{key: value[key] for key in ("target_role", "status", "error", "result_run_id", "package_hash")} for value in publications],
            "events": [{"sequence": value["sequence"], "type": value["event_type"],
                        "payload": json.loads(value["payload_json"]), "created_at": value["created_at"]} for value in events],
            "result_run": result_run,
            "allowed_actions": self._allowed_actions(row, steps),
            "summary": {"completed": completed, "total": len(steps),
                        "failed": sum(step["status"] == "failed" for step in steps),
                        "not_applicable": sum(step["status"] == "not_applicable" for step in steps)},
        }

    @staticmethod
    def _public_step(value: dict[str, Any]) -> dict[str, Any]:
        return {key: value[key] for key in (
            "step_id", "attempt_id", "attempt", "status", "error_code", "error",
            "started_at", "updated_at", "ended_at",
        )}

    @staticmethod
    def _allowed_actions(row: dict[str, Any], steps: list[dict[str, Any]]) -> list[str]:
        if row["status"] in {"accepted", "running", "waiting"}:
            actions = ["cancel"]
            if any(step["status"] in {"failed", "interrupted"} for step in steps):
                actions.append("retry_failed")
            if row["wait_reason"] == "publication":
                actions.append("retry_publication")
            return actions
        return ["view_results"] if row["status"] == "completed" else []

    def cancel(self, item_id: str, pipeline_id: str) -> dict[str, Any]:
        row = self._pipeline_row(pipeline_id)
        if row["item_id"] != item_id:
            raise LookupError("分析pipelineが見つかりません。")
        if row["status"] in {"completed", "failed", "cancelled"}:
            return self.status(item_id, pipeline_id, ensure_running=False)
        with self.connect() as connection:
            connection.execute(
                "UPDATE analysis_pipeline_requests SET cancel_requested=1,status='cancelling',updated_at=? WHERE pipeline_id=?",
                (utc_now(), pipeline_id),
            )
            self._event(connection, pipeline_id, "cancel_requested", {})
        return self.status(item_id, pipeline_id, ensure_running=False)

    def retry(self, item_id: str, pipeline_id: str, payload: dict[str, Any], *, app_url: str) -> dict[str, Any]:
        row = self._pipeline_row(pipeline_id)
        if row["item_id"] != item_id:
            raise LookupError("分析pipelineが見つかりません。")
        if row["status"] == "completed":
            return self.status(item_id, pipeline_id, ensure_running=False)
        target = payload.get("step_id")
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            steps = _latest_steps(connection, pipeline_id)
            candidates = [step for step in steps if step["status"] in {"failed", "interrupted", "cancelled"}]
            if target:
                candidates = [step for step in candidates if step["step_id"] == target]
            if row["wait_reason"] == "publication" and not candidates:
                candidates = [step for step in steps if step["step_id"] == "publish_result"]
            if not candidates:
                raise AnalysisContractError("再試行できるstepがありません。", code="nothing_to_retry")
            if any(int(step["attempt"]) >= 3 for step in candidates):
                raise AnalysisContractError(
                    "再試行上限に達しました。完了済み成果を保持して停止します。",
                    code="retry_limit_reached",
                )
            generation = int(row["generation"]) + 1
            candidate_ids = {value["step_id"] for value in candidates}
            for old in candidates:
                attempt = int(old["attempt"]) + 1
                attempt_id = uuid.uuid5(uuid.NAMESPACE_URL, pipeline_id + old["step_id"] + f":{attempt}").hex
                directive = json.loads(old["directive_json"])
                directive.update(attempt_id=attempt_id, generation=generation)
                connection.execute("""INSERT INTO analysis_step_attempts
                    (attempt_id,pipeline_id,step_id,milestone,generation,attempt,status,directive_json,updated_at)
                    VALUES (?,?,?,?,?,?, 'planned',?,?)""",
                    (attempt_id, pipeline_id, old["step_id"], old["milestone"], generation, attempt,
                     canonical(directive).decode("utf-8"), utc_now()),
                )
            for future in steps:
                if future["status"] != "planned" or future["step_id"] in candidate_ids:
                    continue
                directive = json.loads(future["directive_json"] or "{}")
                directive["generation"] = generation
                connection.execute(
                    "UPDATE analysis_step_attempts SET generation=?,directive_json=?,updated_at=? WHERE attempt_id=?",
                    (generation, canonical(directive).decode("utf-8"), utc_now(), future["attempt_id"]),
                )
            connection.execute(
                "UPDATE analysis_pipeline_requests SET status='accepted',wait_reason='',error='',cancel_requested=0,generation=?,updated_at=? WHERE pipeline_id=?",
                (generation, utc_now(), pipeline_id),
            )
            self._event(connection, pipeline_id, "retry_accepted", {"steps": [value["step_id"] for value in candidates], "generation": generation})
        self._schedule(pipeline_id, app_url)
        return self.status(item_id, pipeline_id, ensure_running=False)
