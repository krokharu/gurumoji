"""Durable, evidence-linked exploratory Core/Handler orchestration.

The Handler is the only execution authority. Injected agents return data (intents,
results and decisions); they never receive executors or mutable application state.
SQLite is the source of truth. An interrupted external call is explicitly uncertain,
not retried: recovery may adopt an already-received raw response or abandon a call.
This module does not send data, publish notes, or change source annotations itself.
"""
from __future__ import annotations

import copy
import json
import math
import sqlite3
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable

from .analysis_core import (AnalysisContractError, canonical, fingerprint,
                            validate_publication_targets, EFFECTIVE_PUBLICATION_WRITERS)
from .orchestration_initial import (initialize_initial_checkpoints, create_initial_checkpoints,
    read_initial_checkpoints, stage_input_hash, write_stage, initial_progress, recover_initial_checkpoints)

SCHEMA_VERSION = 1
ROLES = {"core": "Core", "handler": "Handler", "interpretation": "会話解釈",
         "statistics": "数量・統計", "verification": "独立検証", "critic": "批判者"}
AI_ROLES = frozenset({"core", "interpretation", "verification", "critic"})
INITIAL_SECTIONS = frozenset({"segments", "annotations", "automatic", "manual", "research", "config", "cautions", "classification"})
LABEL_FIELDS = frozenset({"code", "codes", "theme", "sentiment", "dialogue_act", "importance", "review", "category"})
METHODS = frozenset({"participation", "conversation_dynamics", "label_frequency"})
TERMINAL = frozenset({"completed", "stopped", "cancelled", "failed"})
IMPORTANCE = {"low": 1, "medium": 2, "high": 3}


def _id(prefix: str) -> str:
    return prefix + "_" + uuid.uuid4().hex


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return canonical(value).decode("utf-8")


def _error(message: str, code: str = "invalid_request", field: str = "") -> AnalysisContractError:
    return AnalysisContractError(message, code=code, field=field)


def initialize_orchestration_store(connection: sqlite3.Connection) -> None:
    """Additive schema only; initialization never modifies an active execution."""
    schema = """
    CREATE TABLE IF NOT EXISTS orchestration_initials (
      initial_id TEXT PRIMARY KEY, identity TEXT NOT NULL UNIQUE, item_id TEXT NOT NULL,
      status TEXT NOT NULL, snapshot_json TEXT, snapshot_hash TEXT, error TEXT NOT NULL DEFAULT '',
      created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS orchestration_runs (
      run_id TEXT PRIMARY KEY, item_id TEXT NOT NULL, request_id TEXT NOT NULL UNIQUE,
      request_hash TEXT NOT NULL, initial_id TEXT NOT NULL, state_json TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS orchestration_runs_item ON orchestration_runs(item_id);
    CREATE TABLE IF NOT EXISTS orchestration_tasks (
      task_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, idempotency_key TEXT NOT NULL,
      state_json TEXT NOT NULL, UNIQUE(run_id,idempotency_key));
    CREATE TABLE IF NOT EXISTS orchestration_results (
      result_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, task_id TEXT NOT NULL UNIQUE,
      raw_json TEXT NOT NULL, state_json TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS orchestration_events (
      seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, payload_json TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS orchestration_decisions (
      decision_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, result_id TEXT NOT NULL UNIQUE,
      payload_json TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS orchestration_issues (
      issue_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, issue_key TEXT NOT NULL,
      target_id TEXT NOT NULL, target_version TEXT NOT NULL, evidence_version TEXT NOT NULL,
      payload_json TEXT NOT NULL, UNIQUE(run_id,issue_key,target_id,target_version,evidence_version));
    CREATE TABLE IF NOT EXISTS orchestration_responses (
      response_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, issue_id TEXT NOT NULL,
      decision_id TEXT NOT NULL, payload_json TEXT NOT NULL, UNIQUE(issue_id,decision_id));
    CREATE TABLE IF NOT EXISTS orchestration_label_versions (
      run_id TEXT NOT NULL, annotation_version INTEGER NOT NULL, payload_json TEXT NOT NULL,
      PRIMARY KEY(run_id,annotation_version));
    CREATE TABLE IF NOT EXISTS orchestration_label_proposals (
      proposal_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, result_id TEXT NOT NULL,
      payload_json TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS orchestration_label_audit (
      event_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, proposal_id TEXT NOT NULL,
      payload_json TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS orchestration_label_audit_run ON orchestration_label_audit(run_id,proposal_id);
    CREATE TABLE IF NOT EXISTS orchestration_usage (
      usage_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, task_id TEXT NOT NULL, payload_json TEXT NOT NULL);
    """
    initialize_initial_checkpoints(connection)
    for statement in schema.split(";"):
        if statement.strip():
            connection.execute(statement)
    # This ledger has no mutable status: each proposal and disposition is a new
    # row. Protect accidental rewrites even outside the orchestration service.
    for action in ("UPDATE", "DELETE"):
        connection.execute(f"""CREATE TRIGGER IF NOT EXISTS orchestration_label_audit_no_{action.lower()}
            BEFORE {action} ON orchestration_label_audit BEGIN
            SELECT RAISE(ABORT, 'label audit is append-only'); END""")


def recover_orchestration_runs(connection: sqlite3.Connection) -> None:
    """Startup-only recovery marker. Never invoke while this process runs jobs.

    Recovery preserves received results and makes uncertain calls explicit. It
    never launches workers and never promises exactly-once provider execution.
    """
    recover_initial_checkpoints(connection)
    rows = connection.execute("SELECT run_id,state_json FROM orchestration_runs").fetchall()
    for row in rows:
        run_id, encoded = row[0], row[1]
        run = json.loads(encoded)
        if run["status"] not in {"running", "queued"}:
            continue
        for task_row in connection.execute("SELECT task_id,state_json FROM orchestration_tasks WHERE run_id=?", (run_id,)).fetchall():
            task = json.loads(task_row[1])
            if task["status"] in {"running", "cancel_requested"}:
                received = connection.execute("SELECT 1 FROM orchestration_results WHERE task_id=?", (task_row[0],)).fetchone()
                task.update(status="received" if received else "uncertain", error="" if received else "execution_outcome_unknown")
                connection.execute("UPDATE orchestration_tasks SET state_json=? WHERE task_id=?", (_json(task), task_row[0]))
        run.update(status="recovery_required", error="実行環境が再起動しました。保存状態を確認して明示的に再開してください。", updated_at=_now())
        connection.execute("UPDATE orchestration_runs SET state_json=? WHERE run_id=?", (_json(run), run_id))


def validate_orchestration_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise _error("分析設定はオブジェクトで指定してください。")
    if payload.get("research_mode", payload.get("research_protocol", "exploratory")) != "exploratory":
        raise _error("この実装は探索分析専用です。隔離検証データを伴う確認分析には未対応です。", "confirmatory_unavailable")
    question = payload.get("question", payload.get("objective", "会話の特徴と代替説明を根拠付きで分析する"))
    if not isinstance(question, str) or not question.strip() or len(question) > 8000:
        raise _error("分析する問いを指定してください。", field="question")
    mode = payload.get("stop_mode", "auto")
    if mode not in {"time", "iterations", "importance", "auto"}:
        raise _error("終了モードが正しくありません。", field="stop_mode")
    config = {"question": question.strip(), "stop_mode": mode, "research_mode": "exploratory",
              "provider": payload.get("provider", "lmstudio"), "model": payload.get("model", ""),
              "provider_policy": payload.get("provider_policy", "local_only"),
              "cloud_consent": payload.get("cloud_consent") is True,
              "adapter_version": payload.get("adapter_version", "core-handler-prompts-1"),
              "template_version": payload.get("template_version", "existing-analysis-v1"),
              "template_config": payload.get("template_config", {}), "roles": payload.get("roles", {}),
              "importance_threshold": payload.get("importance_threshold", "medium"),
              "min_iterations": 3 if mode == "auto" else 0,
              "max_iterations": payload.get("max_iterations", None if mode == "auto" else 5),
              "time_limit_seconds": payload.get("time_limit_seconds", None if mode == "auto" else 300),
              "max_calls": payload.get("max_calls", 24), "max_tasks": payload.get("max_tasks", 40),
              "concurrency": payload.get("concurrency", 2),
              "call_timeout_seconds": payload.get("call_timeout_seconds", 120),
              "max_result_bytes": payload.get("max_result_bytes", 2_000_000),
              "max_cost": payload.get("max_cost"),
              "context_index_limit": payload.get("context_index_limit", 0),
              "context_evidence_limit": payload.get("context_evidence_limit", 120),
              "context_text_limit": payload.get("context_text_limit", 60000)}
    for key, low, high in (("max_calls", 1, 10000), ("max_tasks", 1, 20000), ("concurrency", 1, 4),
                           ("call_timeout_seconds", 1, 3600), ("max_result_bytes", 1000, 20_000_000),
                           ("context_evidence_limit", 1, 120), ("context_text_limit", 1, 60000)):
        if type(config[key]) is not int or not low <= config[key] <= high:
            raise _error(f"{key}は{low}〜{high}の整数です。", field=key)
    if type(config["context_index_limit"]) is not int or not 0 <= config["context_index_limit"] <= 120:
        raise _error("context_index_limitは0〜120の整数です。0は索引の省略なしです。", field="context_index_limit")
    for key in ("max_iterations", "time_limit_seconds"):
        value = config[key]
        if value is not None and (type(value) is not int or value < 1 or value > 864000):
            raise _error(f"{key}は正の整数またはnullです。", field=key)
    if mode == "time" and config["time_limit_seconds"] is None:
        raise _error("時間モードには時間上限が必要です。", field="time_limit_seconds")
    if mode == "iterations" and config["max_iterations"] is None:
        raise _error("回数モードには回数上限が必要です。", field="max_iterations")
    if mode == "auto" and config["max_iterations"] is not None and config["max_iterations"] < config["min_iterations"]:
        raise _error("AIお任せの回数上限は最低3回以上にしてください。", field="max_iterations")
    if config["importance_threshold"] not in IMPORTANCE:
        raise _error("重要度閾値が正しくありません。", field="importance_threshold")
    if not isinstance(config["template_version"], str) or not config["template_version"]:
        raise _error("テンプレート版を指定してください。", field="template_version")
    if not isinstance(config["template_config"], dict) or not isinstance(config["roles"], dict):
        raise _error("テンプレート設定と役割設定はオブジェクトで指定してください。")
    if config["max_cost"] is not None and (type(config["max_cost"]) not in {int, float}
            or not math.isfinite(config["max_cost"]) or config["max_cost"] <= 0):
        raise _error("費用上限は正の数です。", field="max_cost")
    if config["max_cost"] is not None:
        raise _error("実費用を確実に取得できないため金額上限には未対応です。呼出し数・タスク数上限を指定してください。", "cost_budget_unavailable")
    if config["provider_policy"] not in {"local_only", "cloud_allowed"}:
        raise _error("送信方針が正しくありません。", "provider_unavailable")
    for role in AI_ROLES:
        options = config["roles"].get(role, {})
        if not isinstance(options, dict):
            raise _error("役割設定が正しくありません。", field="roles")
        provider = options.get("provider", config["provider"])
        model = options.get("model", config["model"])
        if provider not in {"lmstudio", "openai", "google"}:
            raise _error("対応するLLMを選択してください。", "provider_unavailable")
        if provider != "lmstudio" and (config["provider_policy"] != "cloud_allowed" or not config["cloud_consent"]):
            raise _error("外部LLMの利用にはcloud_allowedが必要です。", "provider_unavailable")
        if not isinstance(model, str) or not model.strip() or len(model) > 200 or "\n" in model or "\r" in model:
            raise _error("実際に利用するモデル名を指定してください。", "provider_unavailable")
        config["roles"][role] = {"provider": provider, "model": model.strip()}
    config["publication_targets"] = validate_publication_targets(payload.get("publication_targets", []))
    config["effective_publication_writers"] = list(EFFECTIVE_PUBLICATION_WRITERS) if config["publication_targets"] else []
    canonical(config)
    return copy.deepcopy(config)


class ExecutionStopped(Exception):
    """A cooperative cancellation/deadline signal, never an agent result."""


class AnalysisOrchestrationService:
    def __init__(self, *, connect: Callable[[], sqlite3.Connection] | None = None,
                 database_connection: Callable[[], sqlite3.Connection] | None = None,
                 find_item: Callable[[str], Any], snapshot_builder: Callable[[Any], dict[str, Any]],
                 agent_runner: Callable[..., Any], method_runner: Callable[..., Any],
                 source_fingerprint: Callable[[Any], str] | None = None,
                 write_lock: Any = None, schedule: bool = True, adapter_version: str = "core-handler-prompts-1",
                 initial_builder: Any = None, on_complete: Callable[[str, str], Any] | None = None):
        self.connect = connect or database_connection
        if self.connect is None:
            raise TypeError("connect is required")
        self.find_item, self.snapshot_builder = find_item, snapshot_builder
        self.agent_runner, self.method_runner = agent_runner, method_runner
        self.source_fingerprint, self.schedule = source_fingerprint, schedule
        self.adapter_version = adapter_version
        self.initial_builder, self.on_complete = initial_builder, on_complete
        if initial_builder is not None and source_fingerprint is None:
            raise TypeError("staged initial analysis requires source_fingerprint")
        self._driving: set[str] = set()
        self.lock = write_lock or threading.RLock()
        self._workers: dict[str, threading.Thread] = {}
        self._worker_lock = threading.Lock()
        with self._db() as db:
            initialize_orchestration_store(db)

    @contextmanager
    def _db(self):
        with self.lock:
            connection = self.connect()
            try:
                with connection as db:
                    db.row_factory = sqlite3.Row
                    if not db.in_transaction:
                        db.execute("BEGIN IMMEDIATE")
                    yield db
            finally:
                # sqlite3.Connection's context manager commits but does not
                # close. Factories returning context managers close themselves.
                if isinstance(connection, sqlite3.Connection):
                    connection.close()

    def _check_version(self, run):
        if run.get("schema_version") != SCHEMA_VERSION:
            raise _error("保存されたrunの形式版が異なります。元の版で復旧してください。", "schema_version_conflict")
        if run["config"].get("adapter_version") != self.adapter_version:
            raise _error("モデル指示の版が変わりました。新しいrunを開始してください。", "adapter_version_conflict")

    def _read_run(self, db, run_id: str, item_id: str | None = None) -> dict:
        row = db.execute("SELECT * FROM orchestration_runs WHERE run_id=?", (run_id,)).fetchone()
        if row is None or (item_id is not None and row["item_id"] != item_id):
            raise LookupError("自律分析runが見つかりません。")
        return json.loads(row["state_json"])

    def _write_run(self, db, run: dict) -> None:
        run["updated_at"] = _now()
        db.execute("UPDATE orchestration_runs SET state_json=? WHERE run_id=?", (_json(run), run["run_id"]))

    def _event(self, db, run_id: str, event_type: str, message: str, *, source="handler", target="", task_id="", **extra):
        event = {"type": event_type, "from": source, "to": target, "task_id": task_id,
                 "message": message, "created_at": _now(), **extra}
        db.execute("INSERT INTO orchestration_events(run_id,payload_json) VALUES (?,?)", (run_id, _json(event)))

    def _tasks(self, db, run_id):
        return [json.loads(row[0]) for row in db.execute("SELECT state_json FROM orchestration_tasks WHERE run_id=? ORDER BY rowid", (run_id,))]

    def _write_task(self, db, task):
        db.execute("UPDATE orchestration_tasks SET state_json=? WHERE task_id=?", (_json(task), task["task_id"]))

    def _initial(self, db, initial_id):
        row = db.execute("SELECT * FROM orchestration_initials WHERE initial_id=?", (initial_id,)).fetchone()
        if row is None or row["status"] != "ready":
            raise _error("初期分析の固定版が利用できません。", "initial_unavailable")
        value = json.loads(row["snapshot_json"])
        if fingerprint(value) != row["snapshot_hash"]:
            raise _error("初期分析の保存hashが一致しません。AI実行を停止します。", "initial_hash_mismatch")
        return value

    def start(self, item_id: str, payload: dict, app_url: str = "") -> dict:
        config = validate_orchestration_payload(payload)
        request_id = payload.get("request_id") or _id("request")
        if not isinstance(request_id, str) or len(request_id) > 200:
            raise _error("request_idが正しくありません。")
        if self.find_item(item_id) is None:
            raise LookupError("会話が見つかりません。")
        request_hash = fingerprint({"item_id": item_id, "config": config,
                                    "source_revision": payload.get("source_revision"),
                                    "analysis_revision": payload.get("analysis_revision"),
                                    "input_hash": payload.get("input_hash")})
        with self._db() as db:
            existing = db.execute("SELECT * FROM orchestration_runs WHERE request_id=?", (request_id,)).fetchone()
            if existing:
                matches = existing["request_hash"] == request_hash
                saved_config = json.loads(existing["state_json"])["config"]
                if not matches and "publication_targets" not in saved_config and not config["publication_targets"]:
                    legacy_config = {key: value for key, value in config.items()
                                     if key not in {"publication_targets", "effective_publication_writers"}}
                    matches = existing["request_hash"] == fingerprint({"item_id": item_id, "config": legacy_config,
                        "source_revision": payload.get("source_revision"), "analysis_revision": payload.get("analysis_revision"),
                        "input_hash": payload.get("input_hash")})
                if existing["item_id"] != item_id or not matches:
                    raise _error("同じrequest_idに異なる設定は使えません。", "request_conflict")
                return self._public(db, json.loads(existing["state_json"]))
        item = self.find_item(item_id)
        if item is None:
            raise LookupError("会話が見つかりません。")
        current_item = dict(item)
        for supplied, actual in (("source_revision", "revision_count"), ("analysis_revision", "analysis_revision")):
            if supplied in payload and (type(payload[supplied]) is not int or payload[supplied] != int(current_item.get(actual, 0) or 0)):
                raise _error("確認した入力版が更新されています。", "revision_conflict", supplied)
        # A source fingerprint permits cache lookup before the expensive fixed analysis.
        before = self.source_fingerprint(item) if self.source_fingerprint else None
        if self.initial_builder is not None:
            return self._start_staged(item_id, payload, config, request_id, request_hash, app_url, item, before)
        snapshot = None
        if before is None:
            snapshot = self.snapshot_builder(item)
            before = snapshot.get("input_hash")
        if payload.get("input_hash") is not None and payload["input_hash"] != before:
            raise _error("確認した入力hashが更新されています。", "revision_conflict", "input_hash")
        identity = fingerprint({"item_id": item_id, "dataset_version": before,
                                "template_version": config["template_version"], "config": config["template_config"]})
        build = False
        with self._db() as db:
            initial = db.execute("SELECT * FROM orchestration_initials WHERE identity=?", (identity,)).fetchone()
            if initial is None:
                initial_id = _id("initial")
                db.execute("INSERT INTO orchestration_initials(initial_id,identity,item_id,status,created_at) VALUES (?,?,?,?,?)",
                           (initial_id, identity, item_id, "building", _now()))
                build = True
            elif initial["status"] != "ready":
                raise _error("同じ初期分析が作成中、または復旧確認待ちです。自動再実行しません。", "initial_recovery_required")
            else:
                initial_id = initial["initial_id"]
                snapshot = self._initial(db, initial_id)
        if build:
            try:
                snapshot = snapshot if snapshot is not None else self.snapshot_builder(item)
                if not isinstance(snapshot, dict) or not isinstance(snapshot.get("analysis"), dict) or not snapshot.get("input_hash"):
                    raise _error("初期分析スナップショットの形式が正しくありません。", "invalid_snapshot")
                latest = self.find_item(item_id)
                if snapshot["input_hash"] != before or (self.source_fingerprint and (latest is None or self.source_fingerprint(latest) != before)):
                    raise _error("入力固定中に会話が変更されました。", "revision_conflict")
                snapshot = copy.deepcopy(snapshot)
                snapshot["evidence"] = self._evidence(snapshot)
                if not any(not e["excluded"] and e["text"].strip() for e in snapshot["evidence"]):
                    raise _error("分析できる発話がありません。", "no_valid_input")
                with self._db() as db:
                    db.execute("UPDATE orchestration_initials SET status='ready',snapshot_json=?,snapshot_hash=? WHERE initial_id=? AND status='building'",
                               (_json(snapshot), fingerprint(snapshot), initial_id))
            except Exception as exc:
                with self._db() as db:
                    db.execute("UPDATE orchestration_initials SET status='failed',error=? WHERE initial_id=?", (type(exc).__name__, initial_id))
                raise
        run_id = _id("run")
        run = {"schema_version": SCHEMA_VERSION, "label_audit_version": 1, "run_id": run_id, "item_id": item_id, "request_id": request_id,
               "initial_id": initial_id, "input_hash": snapshot["input_hash"],
               "source_revision": snapshot.get("source_revision", 0), "analysis_revision": snapshot.get("analysis_revision", 0),
               "config": config, "app_url": app_url.rstrip("/"), "status": "queued", "phase": "core",
               "iteration": 0, "stop_reason": "", "created_at": _now(), "started_at": None,
               "updated_at": _now(), "ended_at": None, "deadline": None, "cancel_requested": False,
               "generation": 1, "calls_started": 0, "code_executions": 0, "annotation_version": 0,
               "codebook_version": int(snapshot["analysis"].get("manual", {}).get("codebook_version",
                       snapshot["analysis"].get("config", {}).get("codebook_version", 1))), "view_version": 0, "current_view": {}, "pending_stop": None,
               "reviewed_stop_versions": [], "last_decision_id": None, "error": "", "stale": False,
               "review_status": "not_requested", "publication_status": "not_requested"}
        labels = self._source_labels(snapshot)
        with self._db() as db:
            # Recheck a concurrent identical start after initial capture.
            existing = db.execute("SELECT * FROM orchestration_runs WHERE request_id=?", (request_id,)).fetchone()
            if existing:
                if existing["request_hash"] != request_hash:
                    raise _error("request_idが競合しました。", "request_conflict")
                return self._public(db, json.loads(existing["state_json"]))
            db.execute("INSERT INTO orchestration_runs VALUES (?,?,?,?,?,?)", (run_id, item_id, request_id, request_hash, initial_id, _json(run)))
            db.execute("INSERT INTO orchestration_label_versions VALUES (?,?,?)", (run_id, 0, _json(labels)))
            self._event(db, run_id, "initial_saved", "初期分析の全結果を不変の版として固定しました。", initial_id=initial_id)
        if self.schedule:
            self._schedule(run_id)
        return self.status(item_id, run_id)

    def _validate_initial_source(self, run):
        item = self.find_item(run["item_id"])
        if item is None or self.source_fingerprint(item) != run["input_hash"]:
            raise _error("初期分析の入力版が更新されています。新しいrunを開始してください。", "revision_conflict")
        row = dict(item)
        for key, column in (("source_revision", "revision_count"), ("analysis_revision", "analysis_revision")):
            if int(row.get(column, 0) or 0) != run[key]:
                raise _error("初期分析の入力版が更新されています。", "revision_conflict")

    def _start_staged(self, item_id, payload, config, request_id, request_hash, app_url, item, before):
        if payload.get("input_hash") is not None and payload["input_hash"] != before:
            raise _error("確認した入力hashが更新されています。", "revision_conflict", "input_hash")
        identity = fingerprint({"item_id": item_id, "dataset_version": before,
                                "template_version": config["template_version"], "config": config["template_config"]})
        run_id = _id("run")
        snapshot = None
        with self._db() as db:
            existing = db.execute("SELECT * FROM orchestration_runs WHERE request_id=?", (request_id,)).fetchone()
            if existing:
                if existing["item_id"] != item_id or existing["request_hash"] != request_hash:
                    raise _error("request_idが競合しました。", "request_conflict")
                return self._public(db, json.loads(existing["state_json"]))
            initial = db.execute("SELECT * FROM orchestration_initials WHERE identity=?", (identity,)).fetchone()
            if initial is None:
                initial_id = _id("initial")
                # Freeze row JSON before expensive work and before returning the run.
                frozen = self.initial_builder.freeze(item)
                db.execute("INSERT INTO orchestration_initials(initial_id,identity,item_id,status,created_at) VALUES (?,?,?,?,?)",
                           (initial_id, identity, item_id, "building", _now()))
                create_initial_checkpoints(db, initial_id, self.initial_builder, frozen, before, run_id)
            else:
                initial_id = initial["initial_id"]
                if initial["status"] == "ready":
                    snapshot = self._initial(db, initial_id)
                else:
                    build, _, states, _, _ = read_initial_checkpoints(db, initial_id, self.initial_builder)
                    owner = self._read_run(db, build["owner_run_id"])
                    if owner["status"] not in TERMINAL or any(s["status"] == "running" for s in states):
                        raise _error("同じ初期分析の保存済みrunを再開してください。", "initial_recovery_required")
                    # A new explicit start after cancellation can reuse committed
                    # deterministic outputs, but it cannot revive the old run.
                    db.execute("UPDATE orchestration_initial_builds SET owner_run_id=? WHERE initial_id=?", (run_id, initial_id))
            row = dict(item)
            run = {"schema_version": SCHEMA_VERSION, "label_audit_version": 1, "run_id": run_id, "item_id": item_id, "request_id": request_id,
                   "initial_id": initial_id, "input_hash": before,
                   "source_revision": int(row.get("revision_count", 0) or 0),
                   "analysis_revision": int(row.get("analysis_revision", 0) or 0),
                   "config": config, "app_url": app_url.rstrip("/"), "status": "queued",
                   "phase": "core" if snapshot is not None else "initial", "iteration": 0,
                   "stop_reason": "", "created_at": _now(), "started_at": None, "updated_at": _now(),
                   "ended_at": None, "deadline": None, "cancel_requested": False, "generation": 1,
                   "calls_started": 0, "code_executions": 0, "annotation_version": 0,
                   "codebook_version": 1, "view_version": 0, "current_view": {}, "pending_stop": None,
                   "reviewed_stop_versions": [], "last_decision_id": None, "error": "", "stale": False,
                   "review_status": "not_requested", "publication_status": "not_requested"}
            self._validate_initial_source(run)
            if snapshot is not None:
                run["source_revision"] = snapshot.get("source_revision", run["source_revision"])
                run["analysis_revision"] = snapshot.get("analysis_revision", run["analysis_revision"])
                run["codebook_version"] = int(snapshot["analysis"].get("manual", {}).get("codebook_version", snapshot["analysis"].get("config", {}).get("codebook_version", 1)))
            db.execute("INSERT INTO orchestration_runs VALUES (?,?,?,?,?,?)", (run_id, item_id, request_id, request_hash, initial_id, _json(run)))
            if snapshot is not None:
                db.execute("INSERT INTO orchestration_label_versions VALUES (?,?,?)", (run_id, 0, _json(self._source_labels(snapshot))))
            self._event(db, run_id, "initial_saved" if snapshot is not None else "initial_queued",
                        "初期分析の保存済み全結果を再利用します。" if snapshot is not None else "初期分析の入力を固定しました。段階ごとに保存して実行します。", initial_id=initial_id)
        if self.schedule:
            self._schedule(run_id)
        return self.status(item_id, run_id)

    def _build_initial(self, run_id):
        """Commit each deterministic output before advancing to the next stage."""
        stage_id = None
        attempt_id = None
        try:
            while True:
                with self._db() as db:
                    run = self._read_run(db, run_id)
                    if run["status"] in TERMINAL or run["status"] == "recovery_required":
                        return False
                    if run["phase"] != "initial":
                        return True
                    if run["started_at"] is None:
                        run["started_at"] = _now()
                        seconds = run["config"]["time_limit_seconds"]
                        run["deadline"] = time.time() + seconds if seconds is not None else None
                        self._write_run(db, run)
                    limit = self._limit(db, run)
                    if limit:
                        self._stop(db, run, limit)
                        return False
                    self._check_version(run)
                    self._validate_initial_source(run)
                    if self.initial_builder is None:
                        raise _error("初期分析の実装が利用できません。", "initial_version_conflict")
                    build, frozen, states, outputs, hashes = read_initial_checkpoints(db, run["initial_id"], self.initial_builder)
                    if build["source_hash"] != run["input_hash"] or build["owner_run_id"] != run_id:
                        raise _error("初期分析の入力または実行主体が一致しません。", "initial_hash_mismatch")
                    pending = next((s for s in states if s["status"] != "completed"), None)
                    if pending is None:
                        snapshot = copy.deepcopy(outputs[self.initial_builder.stages[-1].stage_id])
                        if not isinstance(snapshot, dict) or not isinstance(snapshot.get("analysis"), dict) or snapshot.get("input_hash") != run["input_hash"]:
                            raise _error("初期分析スナップショットの形式が正しくありません。", "invalid_snapshot")
                        if any(snapshot.get(key, 0) != run[key] for key in ("source_revision", "analysis_revision")):
                            raise _error("初期分析の入力版が一致しません。", "revision_conflict")
                        snapshot["evidence"] = self._evidence(snapshot)
                        if not any(not e["excluded"] and e["text"].strip() for e in snapshot["evidence"]):
                            raise _error("分析できる発話がありません。", "no_valid_input")
                        db.execute("UPDATE orchestration_initials SET status='ready',snapshot_json=?,snapshot_hash=?,error='' WHERE initial_id=?",
                                   (_json(snapshot), fingerprint(snapshot), run["initial_id"]))
                        db.execute("INSERT OR IGNORE INTO orchestration_label_versions VALUES (?,?,?)", (run_id, 0, _json(self._source_labels(snapshot))))
                        run.update(phase="core", error="", codebook_version=int(snapshot["analysis"].get("manual", {}).get("codebook_version", snapshot["analysis"].get("config", {}).get("codebook_version", 1))))
                        self._write_run(db, run)
                        self._event(db, run_id, "initial_saved", "初期分析の全段階を不変の版として固定しました。", initial_id=run["initial_id"])
                        return True
                    if pending["status"] == "running":
                        # Another live driver owns this stage. Startup recovery
                        # explicitly releases crashed deterministic attempts.
                        return False
                    stage_id, attempt_id = pending["stage_id"], _id("initial_attempt")
                    pending.update(status="running", attempt_count=pending["attempt_count"] + 1,
                                   attempt_id=attempt_id, started_at=_now(), completed_at=None, error="",
                                   input_hash=stage_input_hash(build, pending, hashes))
                    write_stage(db, run["initial_id"], pending)
                    db.execute("UPDATE orchestration_initials SET status='building',error='' WHERE initial_id=?", (run["initial_id"],))
                    run.update(status="running", error="")
                    self._write_run(db, run)
                    self._event(db, run_id, "initial_stage_started", pending["label"], stage_id=stage_id)
                # All expensive work is outside SQLite transactions and receives
                # frozen data, never current mutable row values.
                output = self.initial_builder.run_stage(stage_id, copy.deepcopy(frozen), copy.deepcopy(outputs))
                encoded = _json(output)
                with self._db() as db:
                    run = self._read_run(db, run_id)
                    self._validate_initial_source(run)
                    build, _, states, _, _ = read_initial_checkpoints(db, run["initial_id"], self.initial_builder)
                    state = next(s for s in states if s["stage_id"] == stage_id)
                    if state.get("attempt_id") != attempt_id or state["status"] != "running" or build["owner_run_id"] != run_id:
                        raise _error("初期分析段階の実行世代が変わりました。", "initial_attempt_conflict")
                    state.update(status="completed", output_hash=fingerprint(json.loads(encoded)), completed_at=_now(), error="")
                    write_stage(db, run["initial_id"], state, json.loads(encoded))
                    self._event(db, run_id, "initial_stage_completed", state["label"], stage_id=stage_id, output_hash=state["output_hash"])
                    # Cancellation permits retaining this deterministic output;
                    # the next loop fences adoption and all later stages/AI.
                stage_id, attempt_id = None, None
        except Exception as exc:
            with self._db() as db:
                run = self._read_run(db, run_id)
                error = getattr(exc, "code", type(exc).__name__)
                if stage_id:
                    row = db.execute("SELECT state_json FROM orchestration_initial_stages WHERE initial_id=? AND stage_id=?", (run["initial_id"], stage_id)).fetchone()
                    if row:
                        state = json.loads(row[0])
                        if state["status"] == "running" and state.get("attempt_id") == attempt_id:
                            state.update(status="failed", error=error)
                            write_stage(db, run["initial_id"], state)
                db.execute("UPDATE orchestration_initials SET status='failed',error=? WHERE initial_id=? AND status!='ready'", (error, run["initial_id"]))
                if run["status"] not in TERMINAL:
                    run.update(status="recovery_required", error=error, stale=run["stale"] or error == "revision_conflict")
                    self._write_run(db, run)
                    self._event(db, run_id, "initial_recovery_required", "初期分析は未完了です。完了済み段階を保持しています。", error=error)
            return False

    def _notify_completed(self, run_id):
        if self.on_complete is None:
            return
        with self._db() as db:
            run = self._read_run(db, run_id)
            if run["status"] != "completed" or run.get("completion_callback_status"):
                return
            run["completion_callback_status"] = "running"
            self._write_run(db, run)
            item_id = run["item_id"]
        try:
            self.on_complete(item_id, run_id)
        except Exception as exc:
            with self._db() as db:
                run = self._read_run(db, run_id)
                run.update(completion_callback_status="failed", publication_error=getattr(exc, "code", type(exc).__name__))
                self._write_run(db, run)
                self._event(db, run_id, "publication_failed", "分析は完了しています。結果保存・公開処理を確認してください。", error=run["publication_error"])
        else:
            with self._db() as db:
                run = self._read_run(db, run_id)
                run["completion_callback_status"] = "completed"
                self._write_run(db, run)

    @staticmethod
    def _evidence(snapshot: dict) -> list[dict]:
        evidence = []
        for index, segment in enumerate(snapshot["analysis"].get("segments", [])):
            utterance_id = str(segment.get("id", segment.get("segment_id", index)))
            text = str(segment.get("text", ""))
            evidence_id = "ev_" + fingerprint({"dataset": snapshot["input_hash"], "utterance": utterance_id, "text": text})[7:31]
            evidence.append({"id": evidence_id, "evidence_id": evidence_id, "utterance_id": utterance_id,
                             "dataset_version": snapshot["input_hash"], "source_hash": fingerprint(text),
                             "text": text, "speaker": segment.get("speaker"), "start": segment.get("start"),
                             "end": segment.get("end"), "excluded": bool(segment.get("excluded"))})
        if len({row["utterance_id"] for row in evidence}) != len(evidence):
            raise _error("発話IDが重複しています。", "invalid_snapshot")
        return evidence

    @staticmethod
    def _source_labels(snapshot):
        return {str(s.get("id", s.get("segment_id", i))): copy.deepcopy(s.get("annotation", s.get("labels", snapshot["analysis"].get("annotations", {}).get(str(s.get("id", s.get("segment_id", i))), {}))))
                for i, s in enumerate(snapshot["analysis"].get("segments", []))}

    def _schedule(self, run_id):
        with self._worker_lock:
            old = self._workers.get(run_id)
            if old and old.is_alive():
                return
            thread = threading.Thread(target=self.run, args=(run_id,), daemon=True, name="analysis-" + run_id[-8:])
            self._workers[run_id] = thread
            thread.start()

    def _usage(self, db, run):
        records = [json.loads(r[0]) for r in db.execute("SELECT payload_json FROM orchestration_usage WHERE run_id=?", (run["run_id"],))]
        def total(key):
            values = [r[key] for r in records if type(r.get(key)) in {int, float}]
            return sum(values) if values else None
        return {"calls": run["calls_started"], "code_executions": run["code_executions"],
                "input_tokens": total("input_tokens"), "output_tokens": total("output_tokens"),
                "total_tokens": total("total_tokens"), "cost": total("cost"),
                "currency": "USD" if any(r.get("currency") == "USD" for r in records) else None,
                "measured_calls": len({r.get("task_id") for r in records}),
                "measurement_status": "reported" if records else "unavailable"}

    def _public(self, db, run):
        result = copy.deepcopy(run)
        result["config"].setdefault("publication_targets", [])
        result["config"]["effective_publication_writers"] = list(EFFECTIVE_PUBLICATION_WRITERS) if result["config"]["publication_targets"] else []
        result["initial"] = initial_progress(db, run["initial_id"])
        result["initial_stages"] = result["initial"]["stages"]
        tasks = self._tasks(db, run["run_id"])
        result["tasks"] = tasks
        result["events"] = [{"seq": row[0], **json.loads(row[1])} for row in db.execute(
            "SELECT seq,payload_json FROM orchestration_events WHERE run_id=? ORDER BY seq", (run["run_id"],))]
        result["usage"] = self._usage(db, run)
        result["roles"] = []
        for role, label in ROLES.items():
            assigned = [task for task in tasks if task["role"] == role]
            running = [task for task in assigned if task["status"] in {"running", "cancel_requested"}]
            options = run["config"]["roles"].get(role, {})
            result["roles"].append({"id": role, "label": label, "kind": "ai" if role in AI_ROLES else "code",
                "provider": options.get("provider", "python"), "model": options.get("model", "deterministic"),
                "status": "running" if running else ("idle" if run["status"] not in TERMINAL else run["status"]),
                "assigned": len(assigned), "completed": sum(t["status"] == "succeeded" for t in assigned),
                "failed": sum(t["status"] in {"failed", "quarantined", "uncertain"} for t in assigned),
                "current_task": running[0]["title"] if running else ""})
        result["results"] = [json.loads(r[0]) for r in db.execute("SELECT state_json FROM orchestration_results WHERE run_id=? ORDER BY rowid", (run["run_id"],))]
        result["issues"] = [json.loads(r[0]) for r in db.execute("SELECT payload_json FROM orchestration_issues WHERE run_id=? ORDER BY rowid", (run["run_id"],))]
        result["critique_responses"] = [json.loads(r[0]) for r in db.execute("SELECT payload_json FROM orchestration_responses WHERE run_id=? ORDER BY rowid", (run["run_id"],))]
        result["label_proposals"] = [json.loads(r[0]) for r in db.execute("SELECT payload_json FROM orchestration_label_proposals WHERE run_id=? ORDER BY rowid", (run["run_id"],))]
        result["unresolved_issues"] = [issue for issue in result["issues"] if issue.get("status") != "resolved"]
        uncertain = [t["task_id"] for t in tasks if t["status"] in {"running", "uncertain", "cancel_requested"}]
        result["can_resume"] = run["status"] in {"queued", "recovery_required"} and not uncertain
        if run["phase"] == "initial":
            result["can_resume"] = result["can_resume"] and not run["stale"]
            try:
                if self.initial_builder is None:
                    raise _error("初期分析の実装が利用できません。", "initial_version_conflict")
                build, _, stages, _, _ = read_initial_checkpoints(db, run["initial_id"], self.initial_builder)
                if build["source_hash"] != run["input_hash"] or build["owner_run_id"] != run["run_id"]:
                    raise _error("初期分析の入力または実行主体が一致しません。", "initial_hash_mismatch")
                result["can_resume"] = result["can_resume"] and not any(s["status"] == "running" for s in stages)
            except (AnalysisContractError, ValueError, TypeError, KeyError) as exc:
                result["can_resume"] = False
                result["initial"]["recovery_error"] = getattr(exc, "code", "initial_checkpoint_invalid")
        result["allowed_actions"] = (["resume"] if result["can_resume"] else []) + (["cancel"] if run["status"] not in TERMINAL else [])
        result["uncertain_tasks"] = uncertain
        result["in_flight_count"] = sum(t["status"] in {"running", "cancel_requested", "uncertain"} for t in tasks)
        return result

    def status(self, item_id: str, run_id: str) -> dict:
        item = self.find_item(item_id)
        if item is None:
            raise LookupError("会話が見つかりません。")
        with self._db() as db:
            run = self._read_run(db, run_id, item_id)
            if self.source_fingerprint and (item is None or self.source_fingerprint(item) != run["input_hash"]):
                run["stale"] = True
                self._write_run(db, run)
            return self._public(db, run)

    def history(self, item_id: str) -> list[dict]:
        if self.find_item(item_id) is None:
            raise LookupError("会話が見つかりません。")
        with self._db() as db:
            return [self._public(db, json.loads(row[0])) for row in db.execute(
                "SELECT state_json FROM orchestration_runs WHERE item_id=? ORDER BY rowid DESC", (item_id,)).fetchall()]

    def result(self, item_id: str, run_id: str, result_id: str | None = None) -> dict:
        if self.find_item(item_id) is None:
            raise LookupError("会話が見つかりません。")
        with self._db() as db:
            return self.result_locked(db, item_id, run_id, result_id)

    def result_locked(self, db, item_id: str, run_id: str, result_id: str | None = None) -> dict:
        """Serialize an export inside the caller's transaction, without nesting."""
        run = self._read_run(db, run_id, item_id)
        if result_id:
            row = db.execute("SELECT * FROM orchestration_results WHERE result_id=? AND run_id=?", (result_id, run_id)).fetchone()
            if row is None:
                raise LookupError("結果が見つかりません。")
            return {**json.loads(row["state_json"]), "raw": json.loads(row["raw_json"])}
        initial = db.execute("SELECT * FROM orchestration_initials WHERE initial_id=?", (run["initial_id"],)).fetchone()
        return {"run": self._public(db, run), "initial": {"initial_id": initial["initial_id"],
            "hash": initial["snapshot_hash"], "snapshot": json.loads(initial["snapshot_json"]) if initial["snapshot_json"] else None},
            "raw_results": [{**json.loads(r[0]), "raw": json.loads(r[1])} for r in db.execute("SELECT state_json,raw_json FROM orchestration_results WHERE run_id=? ORDER BY rowid", (run_id,))],
            "decisions": [json.loads(r[0]) for r in db.execute("SELECT payload_json FROM orchestration_decisions WHERE run_id=? ORDER BY rowid", (run_id,))],
            "label_audit": [json.loads(r[0]) for r in db.execute("SELECT payload_json FROM orchestration_label_audit WHERE run_id=? ORDER BY rowid", (run_id,))],
            "label_versions": [{"annotation_version": r[0], "labels": json.loads(r[1])} for r in db.execute(
                "SELECT annotation_version,payload_json FROM orchestration_label_versions WHERE run_id=? ORDER BY annotation_version", (run_id,))],
            "usage_records": [{"usage_id": r[0], "task_id": r[1], "payload": json.loads(r[2])} for r in db.execute(
                "SELECT usage_id,task_id,payload_json FROM orchestration_usage WHERE run_id=? ORDER BY rowid", (run_id,))]}

    def _stop(self, db, run, reason, *, completed=False):
        if run["status"] in TERMINAL:
            return
        run.update(status="completed" if completed else ("cancelled" if reason == "user_stop" else "stopped"),
                   phase="stopped", stop_reason=reason, ended_at=_now(), generation=run["generation"] + 1)
        for task in self._tasks(db, run["run_id"]):
            if task["status"] == "queued":
                task.update(status="cancelled", error=reason)
                self._write_task(db, task)
            elif task["status"] == "running":
                task.update(status="cancel_requested", error=reason)
                self._write_task(db, task)
        if run["pending_stop"] and run["review_status"] not in {"reviewed", "unavailable"}:
            run["review_status"] = "incomplete"
        self._write_run(db, run)
        self._event(db, run["run_id"], "stopped", reason)

    def cancel(self, item_id: str, run_id: str) -> dict:
        if self.find_item(item_id) is None:
            raise LookupError("会話が見つかりません。")
        with self._db() as db:
            run = self._read_run(db, run_id, item_id)
            if run["status"] not in TERMINAL:
                run["cancel_requested"] = True
                self._stop(db, run, "user_stop")
            return self._public(db, run)

    def resume(self, item_id: str, run_id: str, payload: dict | None = None) -> dict:
        payload = payload or {}
        if self.find_item(item_id) is None:
            raise LookupError("会話が見つかりません。")
        with self._worker_lock:
            worker = self._workers.get(run_id)
            if worker and worker.is_alive():
                return self.status(item_id, run_id)
        with self._db() as db:
            run = self._read_run(db, run_id, item_id)
            self._check_version(run)
            if "publication_targets" in payload and validate_publication_targets(payload["publication_targets"]) != run["config"].get("publication_targets", []):
                raise _error("再開時に公開先を変更できません。新しいrunを開始してください。", "publication_scope_conflict")
            if run["phase"] == "initial":
                self._validate_initial_source(run)
                if self.initial_builder is None:
                    raise _error("初期分析の実装が利用できません。", "initial_version_conflict")
                read_initial_checkpoints(db, run["initial_id"], self.initial_builder)
            if run["status"] in TERMINAL:
                raise _error("終了済みrunは再実行しません。新しいrunを開始してください。", "run_terminal")
            uncertain = []
            for task in self._tasks(db, run_id):
                if task["status"] in {"running", "uncertain", "cancel_requested"}:
                    row = db.execute("SELECT state_json FROM orchestration_results WHERE task_id=?", (task["task_id"],)).fetchone()
                    if row:
                        task["status"] = "received"
                    elif payload.get("recovery", {}).get(task["task_id"]) == "abandon":
                        task.update(status="failed", error="explicitly_abandoned_uncertain_execution")
                        self._event(db, run_id, "recovery_abandoned", "実行結果不明の呼出しを明示的に放棄しました。再発注しません。", task_id=task["task_id"])
                    else:
                        task.update(status="uncertain", error="execution_outcome_unknown")
                        uncertain.append(task["task_id"])
                    self._write_task(db, task)
            if uncertain:
                run.update(status="recovery_required", error="実行済みか不明な呼出しがあります。結果を照合するか、明示的に放棄してください。")
                self._write_run(db, run)
                self._event(db, run_id, "recovery_required", run["error"], task_ids=uncertain)
                return self._public(db, run)
            run.update(status="queued", error="", generation=run["generation"] + 1)
            self._write_run(db, run)
        if self.schedule:
            self._schedule(run_id)
        return self.status(item_id, run_id)

    def _limit(self, db, run, *, new_round=False):
        if run["cancel_requested"]:
            return "user_stop"
        if run["deadline"] is not None and time.time() >= run["deadline"]:
            return "time_limit"
        if new_round and run["config"]["max_iterations"] is not None and run["iteration"] >= run["config"]["max_iterations"]:
            return "iteration_limit"
        usage = self._usage(db, run)
        if run["config"]["max_cost"] is not None and usage["cost"] is not None and usage["cost"] >= run["config"]["max_cost"]:
            return "budget_limit"
        return None

    def _completed_core_iterations(self, db, run):
        # Count adopted decisions, never queued attempts or quarantined results.
        return db.execute("SELECT COUNT(*) FROM orchestration_decisions WHERE run_id=?", (run["run_id"],)).fetchone()[0]

    def _continue_minimum_iterations(self, db, run, reason):
        minimum = run["config"].get("min_iterations", 0)
        completed = self._completed_core_iterations(db, run)
        if completed >= minimum:
            return False
        limit = self._limit(db, run, new_round=True)
        if limit:
            self._stop(db, run, limit)
        else:
            run["phase"] = "core"
            self._event(db, run["run_id"], "minimum_iterations_continued",
                        f"Core判断は{completed}/{minimum}回です。根拠・批判・未解決点を再検討して次の判断へ進みます。",
                        proposed_stop_reason=reason, completed_core_iterations=completed,
                        min_iterations=minimum)
            self._write_run(db, run)
        return True

    def _register(self, db, run, intent: dict, *, phase: str, automatic=False) -> dict | None:
        role = intent.get("role")
        if role not in AI_ROLES | {"statistics"}:
            raise _error("未対応の専門家です。", "invalid_intent")
        method = intent.get("method_id") or ("participation" if role == "statistics" else "agent-v1")
        if role == "statistics" and method != "label_frequency" and (intent.get("evidence_ids") or intent.get("scope") or intent.get("label_dependent")):
            raise _error("既存コード計算は初期版の全範囲専用です。部分範囲・ラベル再計算は未対応です。", "method_scope_unavailable")
        if method == "label_frequency" and (role != "statistics" or intent.get("label_field", "codes") not in LABEL_FIELDS):
            raise _error("対応するラベル集計列を指定してください。", "label_field_unavailable")
        if role == "statistics" and method not in METHODS:
            raise _error("未対応のコード計算です。", "method_unavailable")
        initial = self._initial(db, run["initial_id"])
        valid_evidence = {e["evidence_id"] for e in initial["evidence"] if not e["excluded"]}
        evidence_ids = intent.get("evidence_ids", [])
        if not isinstance(evidence_ids, list) or any(e not in valid_evidence for e in evidence_ids):
            raise _error("タスクが存在しない根拠を参照しています。", "evidence_missing")
        question = intent.get("question", run["config"]["question"])
        if not isinstance(question, str) or not question.strip():
            raise _error("タスクの問いがありません。", "invalid_intent")
        if not automatic and (not intent.get("why_now") or not intent.get("success_criteria")):
            raise _error("追加タスクには理由と採用基準が必要です。", "invalid_intent")
        if intent.get("kind", "analysis") not in {"analysis", "clarification", ""}:
            raise _error("未対応のタスク種別です。", "invalid_intent")
        if intent.get("kind") == "clarification":
            target = db.execute("SELECT state_json FROM orchestration_results WHERE result_id=? AND run_id=?",
                                (intent.get("result_id"), run["run_id"])).fetchone()
            is_initial = intent.get("result_id") == run["initial_id"]
            if role not in {"interpretation", "critic", "verification"} or (not is_initial and (target is None or json.loads(target[0])["validation_status"] != "valid")):
                raise _error("説明対象の保存済み結果を指定してください。", "clarification_target_missing")
            if role == "verification" and (is_initial or target is None or json.loads(target[0]).get("role") != "verification"):
                raise _error("独立検証への説明依頼は、その独立検証の保存済み結果だけを対象にしてください。", "clarification_target_mismatch")
            if is_initial:
                sections = intent.get("initial_sections", [])
                if not isinstance(sections, list) or not sections or len(sections) > 6 or any(section not in initial["analysis"] or section not in INITIAL_SECTIONS for section in sections):
                    raise _error("初期版の存在する節を1〜6件指定してください。", "initial_section_missing")
        dependencies = intent.get("dependencies", [])
        tasks = self._tasks(db, run["run_id"])
        known = {task["task_id"]: task for task in tasks}
        if not isinstance(dependencies, list) or any(d not in known for d in dependencies):
            raise _error("タスク依存関係が存在しません。", "dependency_missing")
        label_dependent = bool(intent.get("label_dependent", False)) if role != "statistics" else method == "label_frequency"
        identity = {"input": run["input_hash"], "annotation_version": run["annotation_version"] if label_dependent else None,
                    "role": role, "method": method, "question": question.strip(), "evidence_ids": sorted(evidence_ids),
                    "scope": intent.get("scope"), "label_field": intent.get("label_field", "codes") if method == "label_frequency" else None, "target_id": intent.get("target_id"), "target_version": intent.get("target_version"),
                    "evidence_version": fingerprint([run["input_hash"], run["annotation_version"]]) if role == "critic" else intent.get("evidence_version", run["input_hash"]), "replicate_id": intent.get("replicate_id") or None,
                    "round": run["iteration"] if role == "core" else None, "options": run["config"]["roles"].get(role), "kind": intent.get("kind", "analysis"), "result_id": intent.get("result_id"), "initial_sections": intent.get("initial_sections", []),
                    "dependencies": sorted(dependencies)}
        key = fingerprint(identity)
        existing = db.execute("SELECT state_json FROM orchestration_tasks WHERE run_id=? AND idempotency_key=?", (run["run_id"], key)).fetchone()
        if existing:
            task = json.loads(existing[0])
            self._event(db, run["run_id"], "duplicate_suppressed", "同じ入力・目的・対象版のタスクを再発注しません。", task_id=task["task_id"])
            return None
        if len(tasks) >= run["config"]["max_tasks"]:
            self._stop(db, run, "task_budget_limit")
            return None
        queued_calls = sum(t["kind"] == "ai" and t["status"] == "queued" for t in tasks)
        if role in AI_ROLES and run["calls_started"] + queued_calls >= run["config"]["max_calls"]:
            self._stop(db, run, "call_budget_limit")
            return None
        options = run["config"]["roles"].get(role, {"provider": "python", "model": method})
        task = {"task_id": _id("task"), "run_id": run["run_id"], "intent_id": intent.get("intent_id") or _id("intent"),
                "parent_task_id": intent.get("parent_task_id"), "attempt_id": _id("attempt"),
                "idempotency_key": key, "role": role, "kind": "ai" if role in AI_ROLES else "code",
                "provider": options["provider"], "model": options["model"], "method_id": method,
                "title": question.strip(), "intent": copy.deepcopy(intent), "phase": phase, "iteration": run["iteration"],
                "dataset_version": run["input_hash"], "annotation_version": run["annotation_version"],
                "codebook_version": run["codebook_version"], "label_dependent": label_dependent,
                "dependencies": dependencies, "status": "queued", "validation_status": "pending", "stale": False,
                "created_at": _now(), "started_at": None, "ended_at": None, "error": ""}
        db.execute("INSERT INTO orchestration_tasks VALUES (?,?,?,?)", (task["task_id"], run["run_id"], key, _json(task)))
        self._event(db, run["run_id"], "task_registered", task["title"], target=role, task_id=task["task_id"])
        return task

    @staticmethod
    def _safe_section(value, evidence):
        """Filter excluded IDs, referenced rows/maps and verbatim excluded text.

        Complete original sections remain available through the owner-only result
        export. This bounded AI view is deliberately allowed to omit more data.
        """
        excluded = {e["utterance_id"] for e in evidence if e["excluded"]}
        texts = [e["text"] for e in evidence if e["excluded"] and e["text"]]
        omitted = object()
        def clean(node):
            if isinstance(node, str):
                return omitted if node in excluded or any(text in node for text in texts) else node
            if isinstance(node, list):
                children = [clean(child) for child in node]
                return [child for child in children if child is not omitted]
            if isinstance(node, dict):
                if node.get("excluded") is True:
                    return omitted
                for key, child in node.items():
                    if (key in {"id", "segment_id", "utterance_id"} or key.endswith(("_segment_id", "_utterance_id"))) and str(child) in excluded:
                        return omitted
                    if key.endswith(("segment_ids", "utterance_ids")) and isinstance(child, list) and any(str(v) in excluded for v in child):
                        return omitted
                result = {}
                for key, child in node.items():
                    if str(key) in excluded:
                        continue
                    fixed = clean(child)
                    if fixed is not omitted:
                        result[key] = fixed
                return result
            return copy.deepcopy(node)
        result = clean(value)
        return None if result is omitted else result

    def _context(self, db, run, task):
        initial = self._initial(db, run["initial_id"])
        raw = [e for e in initial["evidence"] if not e["excluded"]]
        selected = task["intent"].get("evidence_ids", [])
        if selected:
            raw = [e for e in raw if e["evidence_id"] in selected]
        available_count = len(raw)
        bounded, size = [], 0
        for evidence in raw:
            if len(bounded) >= run["config"]["context_evidence_limit"] or size + len(evidence["text"]) > run["config"]["context_text_limit"]:
                break
            bounded.append(evidence); size += len(evidence["text"])
        raw = bounded
        evidence_index = [{"evidence_id": e["evidence_id"], "utterance_id": e["utterance_id"]}
                          for e in initial["evidence"] if not e["excluded"]]
        index_count = len(evidence_index)
        index_limit = run["config"].get("context_index_limit", 0)
        if index_limit:
            evidence_index = evidence_index[:index_limit]
        coverage = {"available_count": available_count, "provided_count": len(raw), "omitted_count": available_count - len(raw),
                    "complete": len(raw) == available_count, "scope": "selected" if selected else "dataset",
                    "evidence_index": evidence_index, "index_available_count": index_count,
                    "index_provided_count": len(evidence_index), "index_omitted_count": index_count - len(evidence_index)}
        # Deliberately construct the blind packet from an allowlist. Even the
        # Core-written question/success criteria may disclose its expected answer.
        if task["role"] == "verification" and task["intent"].get("kind") == "clarification":
            target = db.execute("SELECT raw_json,state_json FROM orchestration_results WHERE result_id=? AND run_id=?",
                                (task["intent"].get("result_id"), run["run_id"])).fetchone()
            if target is None:
                raise _error("説明対象が見つかりません。", "clarification_target_missing")
            content, metadata = json.loads(target[0]), json.loads(target[1])
            if metadata.get("role") != "verification" or metadata.get("validation_status") != "valid":
                raise _error("独立検証以外の結果はこの対話に渡せません。", "clarification_target_mismatch")
            if fingerprint(content) != metadata["raw_hash"]:
                raise _error("保存済み結果のhashが一致しません。", "result_integrity_mismatch")
            references = {ref for claim in content.get("claims", []) for ref in claim.get("evidence_ids", [])}
            relevant = [e for e in initial["evidence"] if not e["excluded"] and e["evidence_id"] in references]
            provided, size = [], 0
            for evidence in relevant:
                if len(provided) >= run["config"]["context_evidence_limit"] or size + len(evidence["text"]) > run["config"]["context_text_limit"]:
                    break
                provided.append(evidence); size += len(evidence["text"])
            return {"schema_version": SCHEMA_VERSION, "task": {"task_id": task["task_id"], "role": "verification"},
                    "question": task["title"], "data_version": metadata["dataset_version"],
                    "annotation_version": metadata["annotation_version"], "raw_evidence": copy.deepcopy(provided),
                    "coverage": {"available_count": len(relevant), "provided_count": len(provided),
                                 "omitted_count": len(relevant) - len(provided), "complete": len(relevant) == len(provided),
                                 "scope": "saved_verification_result"},
                    "clarification_target": {"metadata": metadata,
                        "content": content if len(target[0]) <= 16000 else {"content_excerpt": target[0][:16000], "truncated": True}},
                    "blind_first": False, "execution_allowed": False, "research_mode": "exploratory"}
        if task["role"] == "verification":
            return {"schema_version": SCHEMA_VERSION, "task": {"task_id": task["task_id"], "role": "verification"},
                    "question": "原文から観察事実、矛盾、判断できない点を独立に確認してください。",
                    "data_version": run["input_hash"], "annotation_version": task["annotation_version"],
                    "raw_evidence": copy.deepcopy(raw), "coverage": coverage, "blind_first": True,
                    "research_mode": "exploratory"}
        public = self._public(db, run)
        accepted = []
        for result in public["results"]:
            if result["validation_status"] == "valid":
                row = db.execute("SELECT raw_json FROM orchestration_results WHERE result_id=?", (result["result_id"],)).fetchone()
                content = json.loads(row[0])
                if fingerprint(content) != result["raw_hash"]:
                    raise _error("保存済み結果のhashが一致しません。", "result_integrity_mismatch")
                if len(row[0]) > 16000:
                    content = {"summary": content.get("summary", ""), "claims": content.get("claims", [])[:24], "omitted_full_result": True}
                accepted.append({**result, "content": content})
        accepted = accepted[-20:]
        context = {"schema_version": SCHEMA_VERSION, "task": copy.deepcopy(task), "question": run["config"]["question"],
                   "data_version": run["input_hash"], "annotation_version": task["annotation_version"],
                   "raw_evidence": copy.deepcopy(raw), "coverage": coverage, "research_mode": "exploratory",
                   "current_view": run["current_view"], "view_version": run["view_version"],
                   "initial": {"initial_id": run["initial_id"], "available_sections": [section for section in initial["analysis"] if section in INITIAL_SECTIONS],
                               "full_results_preserved": True, "read_scope": "index_only"},
                   "results": accepted, "issues": public["issues"], "critique_responses": public["critique_responses"],
                   "label_proposals": public["label_proposals"], "usage": public["usage"],
                   "budget": {"remaining_calls": run["config"]["max_calls"] - run["calls_started"],
                              "remaining_tasks": run["config"]["max_tasks"] - len(public["tasks"]),
                              "max_iterations": run["config"]["max_iterations"], "iteration": run["iteration"],
                              "min_iterations": run["config"].get("min_iterations", 0),
                              "completed_core_iterations": self._completed_core_iterations(db, run),
                              "deadline": run["deadline"]}, "stop_proposal": run["pending_stop"]}
        context["labels"] = json.loads(db.execute("SELECT payload_json FROM orchestration_label_versions WHERE run_id=? AND annotation_version=?",
                                                    (run["run_id"], task["annotation_version"])).fetchone()[0])
        included_ids = {e["utterance_id"] for e in raw}
        context["labels"] = {key: value for key, value in context["labels"].items() if key in included_ids}
        if task["intent"].get("kind") == "clarification":
            target = db.execute("SELECT raw_json,state_json FROM orchestration_results WHERE result_id=? AND run_id=?",
                                (task["intent"].get("result_id"), run["run_id"])).fetchone()
            if task["intent"].get("result_id") == run["initial_id"]:
                sections = {}
                remaining = 16000
                eligible = {e["utterance_id"] for e in initial["evidence"] if not e["excluded"]}
                for section in task["intent"].get("initial_sections", []):
                    value = self._safe_section(initial["analysis"][section], initial["evidence"])
                    if section == "segments":
                        value = [s for s in (value or []) if str(s.get("id", s.get("segment_id"))) in eligible]
                    elif section == "annotations":
                        value = {k: v for k, v in (value or {}).items() if k in eligible}
                    encoded = _json(value)
                    sections[section] = value if len(encoded) <= remaining else {"content_excerpt": encoded[:remaining], "truncated": True}
                    remaining = max(0, remaining - len(encoded))
                context["clarification_target"] = {"initial_id": run["initial_id"], "sections": sections, "read_only": True}
            else:
                encoded = target[0]
                content = json.loads(encoded) if len(encoded) <= 16000 else {"content_excerpt": encoded[:16000], "truncated": True}
                context["clarification_target"] = {"metadata": json.loads(target[1]), "content": content}
            context["execution_allowed"] = False
        if task["role"] == "critic":
            context["review_target"] = {"target_id": task["intent"]["target_id"], "target_version": task["intent"]["target_version"],
                                        "evidence_version": fingerprint([run["input_hash"], run["annotation_version"]]), "view": run["current_view"], "stop": run["pending_stop"]}
        return copy.deepcopy(context)

    def _check(self, run_id, generation, task_id=None):
        with self._db() as db:
            run = self._read_run(db, run_id)
            limit = "source_deleted" if self.find_item(run["item_id"]) is None else self._limit(db, run)
            if limit and run["status"] not in TERMINAL:
                self._stop(db, run, limit)
            if limit or run["status"] in TERMINAL or run["generation"] != generation:
                raise ExecutionStopped(run["stop_reason"] or "stopped")
            if task_id:
                row = db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (task_id,)).fetchone()
                task = json.loads(row[0])
                if task.get("started_epoch") and time.time() - task["started_epoch"] > run["config"]["call_timeout_seconds"]:
                    self._stop(db, run, "call_timeout")
                    raise ExecutionStopped("call_timeout")

    def _record_usage(self, run_id, task_id, usage=None, **values):
        data = dict(usage or {}, **values)
        if data.get("reported") is False:
            return
        record = {"task_id": task_id, "reported_at": _now()}
        for key in ("input_tokens", "output_tokens", "total_tokens", "cost"):
            value = data.get(key)
            if type(value) in {int, float} and math.isfinite(value) and value >= 0:
                record[key] = value
        if not any(k in record for k in ("input_tokens", "output_tokens", "total_tokens", "cost")):
            return
        if data.get("currency") == "USD":
            record["currency"] = "USD"
        usage_id = str(data.get("usage_id") or task_id + ":response")
        with self._db() as db:
            db.execute("INSERT OR IGNORE INTO orchestration_usage VALUES (?,?,?,?)", (run_id + ":" + usage_id, run_id, task_id, _json(record)))

    def _execute(self, run_id: str, task_id: str):
        with self._db() as db:
            run = self._read_run(db, run_id)
            row = db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (task_id,)).fetchone()
            task = json.loads(row[0])
            if task["status"] != "queued" or run["status"] in TERMINAL:
                return
            self._check_version(run)
            limit = self._limit(db, run)
            if limit:
                self._stop(db, run, limit)
                return
            task.update(status="running", started_at=_now(), started_epoch=time.time(), generation=run["generation"])
            run["calls_started" if task["kind"] == "ai" else "code_executions"] += 1
            self._write_task(db, task)
            self._write_run(db, run)
            self._event(db, run_id, "task_started", task["title"], target=task["role"], task_id=task_id)
            context = self._context(db, run, task)
            snapshot = self._initial(db, run["initial_id"]) if task["kind"] == "code" else None
            if snapshot is not None:
                snapshot["orchestration_task"] = copy.deepcopy(task)
                snapshot["orchestration_labels"] = json.loads(db.execute("SELECT payload_json FROM orchestration_label_versions WHERE run_id=? AND annotation_version=?",
                    (run_id, task["annotation_version"])).fetchone()[0])
        check = lambda: self._check(run_id, task["generation"], task_id)
        try:
            check()
            if task["kind"] == "code":
                raw = self.method_runner(task["method_id"], snapshot)
            else:
                options = {**copy.deepcopy(run["config"]), **run["config"]["roles"][task["role"]], "timeout_seconds": run["config"]["call_timeout_seconds"],
                           "deadline": run["deadline"], "research_mode": "exploratory", "provider_policy": run["config"]["provider_policy"]}
                raw = self.agent_runner(task["role"], context, options, check,
                                        lambda usage=None, **kw: self._record_usage(run_id, task_id, usage, **kw))
            # Raw response commits before semantic validation, including a late response.
            raw_json = _json(raw)
            with self._db() as db:
                latest = self._read_run(db, run_id)
                if self.find_item(latest["item_id"]) is None and latest["status"] not in TERMINAL:
                    self._stop(db, latest, "source_deleted")
                limit = self._limit(db, latest)
                if not limit and time.time() - task["started_epoch"] > latest["config"]["call_timeout_seconds"]:
                    limit = "call_timeout"
                if limit and latest["status"] not in TERMINAL:
                    self._stop(db, latest, limit)
                late = latest["status"] in TERMINAL or latest["generation"] != task["generation"]
                metadata = {"result_id": _id("result"), "run_id": run_id, "task_id": task_id, "role": task["role"],
                            "attempt_id": task["attempt_id"], "received_at": _now(), "raw_hash": fingerprint(raw),
                            "dataset_version": task["dataset_version"], "annotation_version": task["annotation_version"],
                            "validation_status": "quarantined" if late else "received", "content_status": "unreviewed",
                            "error": "late_response_after_stop" if late else "", "stale": False}
                db.execute("INSERT OR IGNORE INTO orchestration_results VALUES (?,?,?,?,?)", (metadata["result_id"], run_id, task_id, raw_json, _json(metadata)))
                current_task = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (task_id,)).fetchone()[0])
                current_task.update(status="quarantined" if late else "received", ended_at=_now(), result_id=metadata["result_id"],
                                    validation_status=metadata["validation_status"], error=metadata["error"])
                self._write_task(db, current_task)
                self._event(db, run_id, "raw_received", "原結果を保存しました。", source=task["role"], target="handler", task_id=task_id)
            if not late:
                self._validate_received(run_id, task_id)
        except ExecutionStopped:
            with self._db() as db:
                current = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (task_id,)).fetchone()[0])
                if current["status"] in {"running", "cancel_requested"}:
                    current.update(status="cancelled", ended_at=_now(), error="cooperative_stop")
                    self._write_task(db, current)
        except Exception as exc:
            with self._db() as db:
                current = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (task_id,)).fetchone()[0])
                # Transport errors may have consumed external work. Never retry blind.
                current.update(status="uncertain" if task["kind"] == "ai" else "failed", ended_at=_now(), error=type(exc).__name__)
                self._write_task(db, current)
                latest = self._read_run(db, run_id)
                if latest["status"] not in TERMINAL and task["kind"] == "ai":
                    latest.update(status="recovery_required", error="外部呼出しの実行結果が不明です。自動再試行しません。")
                    self._write_run(db, latest)
                self._event(db, run_id, "execution_uncertain" if task["kind"] == "ai" else "task_failed", type(exc).__name__, task_id=task_id)

    def _validate_received(self, run_id, task_id):
        with self._db() as db:
            run = self._read_run(db, run_id)
            task = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (task_id,)).fetchone()[0])
            row = db.execute("SELECT * FROM orchestration_results WHERE task_id=?", (task_id,)).fetchone()
            meta, raw = json.loads(row["state_json"]), json.loads(row["raw_json"])
            if (fingerprint(raw) != meta["raw_hash"] or meta.get("task_id") != task_id
                    or meta.get("run_id") != run_id or meta.get("result_id") != row["result_id"]
                    or meta.get("attempt_id") != task["attempt_id"]):
                meta.update(validation_status="quarantined", error="result_integrity_mismatch")
                task.update(status="quarantined", validation_status="quarantined", error="result_integrity_mismatch")
                db.execute("UPDATE orchestration_results SET state_json=? WHERE result_id=?", (_json(meta), row["result_id"]))
                self._write_task(db, task)
                self._event(db, run_id, "result_quarantined", "result_integrity_mismatch", task_id=task_id)
                return
            if meta["validation_status"] != "received":
                if task["status"] == "received":
                    task.update(status="succeeded" if meta["validation_status"] == "valid" else "quarantined",
                                validation_status=meta["validation_status"], result_id=meta["result_id"])
                    self._write_task(db, task)
                return
            try:
                if len(row["raw_json"].encode("utf-8")) > run["config"]["max_result_bytes"]:
                    raise _error("結果が保存上限を超えています。", "result_size_limit")
                if run["status"] in TERMINAL:
                    raise _error("停止後の結果は採用しません。", "late_response_after_stop")
                self._validate_result(db, run, task, raw)
                meta.update(validation_status="valid", error="")
                task.update(status="succeeded", validation_status="valid", error="")
                if task["role"] == "critic":
                    self._save_issues(db, run, task, raw, meta)
                for patch in raw.get("label_patches", []):
                    self._save_patch(db, run, task, patch, meta)
                self._event(db, run_id, "result_validated", "保存済み・内容未検証としてCoreへ渡します。", source="handler", target="core", task_id=task_id)
            except (AnalysisContractError, ValueError, TypeError, KeyError) as exc:
                code = getattr(exc, "code", "invalid_result")
                meta.update(validation_status="quarantined", error=code)
                task.update(status="quarantined", validation_status="quarantined", error=code)
                self._event(db, run_id, "result_quarantined", code, task_id=task_id)
            db.execute("UPDATE orchestration_results SET state_json=? WHERE result_id=?", (_json(meta), meta["result_id"]))
            self._write_task(db, task)

    def _validate_result(self, db, run, task, raw):
        if not isinstance(raw, dict):
            raise _error("結果はJSONオブジェクトで返してください。", "invalid_result")
        if raw.get("research_mode", "exploratory") != "exploratory":
            raise _error("確認的主張には未対応です。", "confirmatory_unavailable")
        if raw.get("dataset_version", run["input_hash"]) != run["input_hash"]:
            raise _error("結果の入力版が一致しません。", "revision_conflict")
        evidence = {e["evidence_id"]: e for e in self._initial(db, run["initial_id"])["evidence"] if not e["excluded"]}
        for key in ("claims", "issues", "label_patches", "intents", "critique_responses", "label_decisions"):
            if key in raw and (not isinstance(raw[key], list) or any(not isinstance(v, dict) for v in raw[key])):
                raise _error("結果配列の形式が正しくありません。", "invalid_result")
        for claim in raw.get("claims", []):
            if not claim.get("text") or not claim.get("claim_id") or claim.get("kind") not in {"observation", "interpretation", "hypothesis"}:
                raise _error("主張のID・本文・区分が必要です。", "invalid_claim")
            if not claim.get("evidence_ids"):
                raise _error("主張には根拠参照が必要です。", "evidence_missing")
        for value in [*raw.get("claims", []), *raw.get("issues", []), *raw.get("label_patches", [])]:
            refs = value.get("evidence_ids", [])
            if not isinstance(refs, list) or any(ref not in evidence for ref in refs):
                raise _error("根拠発話が存在しません。", "evidence_missing")
        if task["role"] == "core":
            if not isinstance(raw.get("summary"), str) or not raw["summary"].strip():
                raise _error("空でない統合要約が必要です。", "invalid_result")
            if raw.get("stop") is not None and (not isinstance(raw["stop"], dict) or not raw["stop"].get("reason")):
                raise _error("停止案には理由が必要です。", "invalid_stop")
            for intent in raw.get("intents", []):
                role = intent.get("role")
                if (role not in {"interpretation", "statistics", "verification", "critic"}
                        or not isinstance(intent.get("question"), str) or not intent["question"].strip()
                        or not intent.get("why_now") or not intent.get("success_criteria")):
                    raise _error("追加タスクの役割・問い・理由・採用基準が不足しています。", "invalid_intent")
                if role == "statistics":
                    method = intent.get("method_id")
                    if method not in METHODS or (method != "label_frequency" and (intent.get("evidence_ids") or intent.get("scope") or intent.get("label_dependent"))):
                        raise _error("既存コード計算は初期版の全範囲専用です。", "method_scope_unavailable")
                    if method == "label_frequency" and intent.get("label_field", "codes") not in LABEL_FIELDS:
                        raise _error("対応するラベル集計列を指定してください。", "label_field_unavailable")
                elif intent.get("method_id") == "label_frequency":
                    raise _error("ラベル集計はstatisticsへ指定してください。", "label_field_unavailable")
                if not isinstance(intent.get("evidence_ids", []), list) or any(ref not in evidence for ref in intent.get("evidence_ids", [])):
                    raise _error("タスクの根拠が存在しません。", "evidence_missing")
            for response in raw.get("critique_responses", []):
                if response.get("disposition") not in {"adopt", "reject", "defer"} or not response.get("reason") or not response.get("impact"):
                    raise _error("批判への応答には採否・理由・結論への影響が必要です。", "invalid_critique_response")
                if not db.execute("SELECT 1 FROM orchestration_issues WHERE issue_id=? AND run_id=?", (response.get("issue_id"), run["run_id"])).fetchone():
                    raise _error("応答先の批判が存在しません。", "issue_missing")
        if task["role"] == "critic":
            if raw.get("review_status") not in {"issues", "no_issues", "undetermined"} or not raw.get("reviewed_scope"):
                raise _error("批判レビューの範囲と状態が必要です。", "invalid_critique")
            if raw["review_status"] == "issues" and not raw.get("issues"):
                raise _error("指摘ありのレビューには指摘が必要です。", "invalid_critique")
            if raw["review_status"] == "no_issues" and raw.get("issues"):
                raise _error("指摘なしと指摘一覧が矛盾しています。", "invalid_critique")
            for issue in raw.get("issues", []):
                if (not issue.get("issue_key") or issue.get("severity") not in IMPORTANCE or not issue.get("reason")
                        or issue.get("target_id") != task["intent"].get("target_id")
                        or str(issue.get("target_version")) != str(task["intent"].get("target_version"))):
                    raise _error("指摘の対象版・問題ID・重大度・理由が正しくありません。", "invalid_critique")
                if not issue.get("evidence_ids") and not issue.get("missing_evidence"):
                    raise _error("批判には根拠または不足している証拠の特定が必要です。", "evidence_missing")
        for patch in raw.get("label_patches", []):
            if (str(patch.get("utterance_id")) not in {e["utterance_id"] for e in evidence.values()}
                    or patch.get("field") not in LABEL_FIELDS or not patch.get("reason") or not patch.get("evidence_ids")
                    or "old_value" not in patch or "new_value" not in patch
                    or type(patch.get("base_annotation_version")) is not int
                    or patch.get("codebook_version") != task["codebook_version"]
                    or patch.get("operation", "update") not in {"add", "update", "delete"}
                    or (patch.get("operation") == "delete" and patch["new_value"] is not None)
                    or not isinstance(patch.get("reason"), str)):
                raise _error("ラベル変更案の根拠・旧値・版が不足しています。", "invalid_label_patch")
            for key in ("old_value", "new_value"):
                value = patch[key]
                if not (value is None or type(value) in {str, bool, int, float}
                        or (isinstance(value, list) and all(isinstance(v, str) for v in value))):
                    raise _error("ラベル値は文字列・数値・真偽値・文字列配列で指定してください。", "invalid_label_patch")

    def _save_issues(self, db, run, task, raw, meta):
        for issue in raw.get("issues", []):
            value = {**copy.deepcopy(issue), "issue_id": _id("issue"), "critique_id": meta["result_id"],
                     "result_id": meta["result_id"], "dataset_version": run["input_hash"],
                     "evidence_version": fingerprint([run["input_hash"], task["annotation_version"]]), "status": "open", "stale": False}
            db.execute("INSERT OR IGNORE INTO orchestration_issues VALUES (?,?,?,?,?,?,?)",
                (value["issue_id"], run["run_id"], issue["issue_key"], issue["target_id"], str(issue["target_version"]), value["evidence_version"], _json(value)))

    def _label_audit(self, db, run, patch, *, disposition, task=None,
                     result_id=None, decision_id=None, before=None, after=None,
                     before_present=None, after_present=None, before_version=None,
                     reason=None):
        """Append the recorded justification, never arbitrary model output."""
        task = task or {}
        def value(v):
            if v is None or type(v) in {bool, int, float}:
                return v
            if isinstance(v, str):
                return v
            if isinstance(v, list):
                return copy.deepcopy(v)
            return None
        operation = patch.get("operation") or ("add" if before_present is False else "update")
        event = {"event_id": _id("label_event"), "item_id": run["item_id"],
                 "run_id": run["run_id"], "proposal_id": patch["proposal_id"],
                 "task_id": task.get("task_id"), "result_id": result_id,
                 "proposal_task_id": patch.get("task_id"), "proposal_result_id": patch.get("result_id"),
                 "decision_id": decision_id, "created_at": _now(),
                 "role": task.get("role"), "model": task.get("model"), "provider": task.get("provider"),
                 "utterance_id": str(patch["utterance_id"]), "field": patch["field"],
                 "operation": operation, "disposition": disposition, "status": patch["status"],
                 "before_value": value(before), "after_value": value(after),
                 "before_present": before_present, "after_present": after_present,
                 "proposed_value": value(patch.get("new_value")),
                 "stated_old_value": value(patch.get("old_value")),
                 "tombstone": disposition == "adopt" and operation == "delete",
                 "base_annotation_version": patch.get("base_annotation_version"),
                 "before_annotation_version": before_version,
                 "after_annotation_version": before_version if disposition == "proposal" else run["annotation_version"],
                 "annotation_version": run["annotation_version"],
                 "codebook_version": run.get("codebook_version"),
                 "reason": str(reason if reason is not None else patch.get("reason", ""))[:2000],
                 "evidence_ids": [e for e in patch.get("evidence_ids", []) if isinstance(e, str)],
                 "audit_status": "recorded"}
        recorded_reason = reason if reason is not None else patch.get("reason", "")
        event["truncated_fields"] = ["reason"] if len(str(recorded_reason)) > 2000 else []
        event["reason_hash"] = fingerprint(recorded_reason)
        event["before_value_hash"] = fingerprint(before)
        event["after_value_hash"] = fingerprint(after)
        db.execute("INSERT INTO orchestration_label_audit VALUES (?,?,?,?)",
                   (event["event_id"], run["run_id"], patch["proposal_id"], _json(event)))

    def _save_patch(self, db, run, task, patch, meta):
        value = {**copy.deepcopy(patch), "proposal_id": _id("label"), "result_id": meta["result_id"],
                 "task_id": task["task_id"], "status": "proposed", "created_at": _now()}
        db.execute("INSERT INTO orchestration_label_proposals VALUES (?,?,?,?)", (value["proposal_id"], run["run_id"], meta["result_id"], _json(value)))
        row = db.execute("SELECT payload_json FROM orchestration_label_versions WHERE run_id=? AND annotation_version=?",
                         (run["run_id"], patch["base_annotation_version"])).fetchone()
        labels = json.loads(row[0]).get(str(patch["utterance_id"]), {}) if row else None
        present = patch["field"] in labels if isinstance(labels, dict) else None
        # A proposal has not changed the saved labels. Keep the actual base
        # value on both sides; the agent's claims live in stated/proposed fields.
        before = copy.deepcopy(labels.get(patch["field"])) if isinstance(labels, dict) else None
        self._label_audit(db, run, value, disposition="proposal", task=task, result_id=meta["result_id"],
                         before=before, after=before, before_present=present, after_present=present,
                         before_version=patch["base_annotation_version"] if row else None)

    def _commit_labels(self, db, run, decisions, *, task=None, result_id=None, decision_id=None):
        # Validate the complete batch before applying any disposition.
        patches = []
        for decision in decisions:
            row = db.execute("SELECT payload_json FROM orchestration_label_proposals WHERE proposal_id=? AND run_id=?",
                             (decision.get("proposal_id"), run["run_id"])).fetchone()
            if row is None or decision.get("disposition") not in {"adopt", "reject", "defer"} or not decision.get("reason"):
                raise _error("ラベル採否の対象・理由が不足しています。", "invalid_label_decision")
            patches.append((decision, json.loads(row[0])))
        processed = set()
        for decision, patch in patches:
            if patch["status"] != "proposed" or patch["proposal_id"] in processed:
                continue
            processed.add(patch["proposal_id"])
            labels = json.loads(db.execute("SELECT payload_json FROM orchestration_label_versions WHERE run_id=? AND annotation_version=?",
                                           (run["run_id"], run["annotation_version"])).fetchone()[0])
            utterance_labels = labels.get(str(patch["utterance_id"]), {})
            before = copy.deepcopy(utterance_labels.get(patch["field"]))
            present = patch["field"] in utterance_labels
            version = run["annotation_version"]
            patch["decision"] = copy.deepcopy(decision)
            disposition = decision["disposition"]
            if disposition != "adopt":
                patch["status"] = "rejected" if disposition == "reject" else "deferred"
            elif (patch["base_annotation_version"] != version or before != patch["old_value"]
                    or patch["codebook_version"] != run["codebook_version"]
                    or (patch.get("operation") == "add" and present)
                    or (patch.get("operation") in {"update", "delete"} and not present)):
                patch["status"], disposition = "conflict", "conflict"
            else:
                target = labels.setdefault(str(patch["utterance_id"]), {})
                if patch.get("operation") == "delete":
                    target.pop(patch["field"], None)
                else:
                    target[patch["field"]] = patch["new_value"]
                run["annotation_version"] += 1
                run["view_version"] += 1
                run["reviewed_stop_versions"] = []
                db.execute("INSERT INTO orchestration_label_versions VALUES (?,?,?)", (run["run_id"], run["annotation_version"], _json(labels)))
                patch.update(status="committed", committed_annotation_version=run["annotation_version"])
                for dependent in self._tasks(db, run["run_id"]):
                    if dependent["label_dependent"] and dependent["annotation_version"] < run["annotation_version"]:
                        dependent["stale"] = True
                        self._write_task(db, dependent)
                        result = db.execute("SELECT result_id,state_json FROM orchestration_results WHERE task_id=?", (dependent["task_id"],)).fetchone()
                        if result:
                            meta = json.loads(result[1]); meta["stale"] = True
                            db.execute("UPDATE orchestration_results SET state_json=? WHERE result_id=?", (_json(meta), result[0]))
                self._event(db, run["run_id"], "labels_committed", "新しいラベル版を保存し、依存結果を旧版として表示します。", annotation_version=run["annotation_version"])
            after_labels = labels.get(str(patch["utterance_id"]), {})
            self._label_audit(db, run, patch, disposition=disposition, task=task,
                             result_id=result_id, decision_id=decision_id, before=before,
                             after=after_labels.get(patch["field"]), before_present=present,
                             after_present=patch["field"] in after_labels, before_version=version,
                             reason=decision["reason"])
            db.execute("UPDATE orchestration_label_proposals SET payload_json=? WHERE proposal_id=?", (_json(patch), patch["proposal_id"]))

    def _apply_core(self, db, run, task, result):
        meta, raw = json.loads(result["state_json"]), json.loads(result["raw_json"])
        # The validation commit and the decision commit are separate durable
        # boundaries. Recheck the stored bytes at adoption, including restart.
        if (fingerprint(raw) != meta["raw_hash"] or meta.get("task_id") != task["task_id"]
                or meta.get("run_id") != run["run_id"] or meta.get("result_id") != result["result_id"]
                or meta.get("attempt_id") != task["attempt_id"]):
            meta.update(validation_status="quarantined", error="result_integrity_mismatch")
            task.update(status="quarantined", validation_status="quarantined", error="result_integrity_mismatch")
            db.execute("UPDATE orchestration_results SET state_json=? WHERE result_id=?", (_json(meta), result["result_id"]))
            self._write_task(db, task)
            self._event(db, run["run_id"], "result_quarantined", "result_integrity_mismatch", task_id=task["task_id"])
            run["error"] = "result_integrity_mismatch"
            self._stop(db, run, "execution_failure")
            return
        if db.execute("SELECT 1 FROM orchestration_decisions WHERE result_id=?", (meta["result_id"],)).fetchone():
            return
        decision = {**copy.deepcopy(raw), "decision_id": _id("decision"), "result_id": meta["result_id"],
                    "iteration": run["iteration"], "created_at": _now(),
                    "task_id": task["task_id"], "annotation_version": task["annotation_version"],
                    "before_annotation_version": run["annotation_version"],
                    "role": task["role"], "model": task.get("model"), "provider": task.get("provider")}
        self._commit_labels(db, run, raw.get("label_decisions", []), task=task,
                            result_id=meta["result_id"], decision_id=decision["decision_id"])
        decision["after_annotation_version"] = run["annotation_version"]
        for response in raw.get("critique_responses", []):
            value = {**response, "response_id": _id("response"), "decision_id": decision["decision_id"], "created_at": _now()}
            db.execute("INSERT OR IGNORE INTO orchestration_responses VALUES (?,?,?,?,?)", (value["response_id"], run["run_id"], response["issue_id"], decision["decision_id"], _json(value)))
            issue = json.loads(db.execute("SELECT payload_json FROM orchestration_issues WHERE issue_id=?", (response["issue_id"],)).fetchone()[0])
            # Adoption is not proof of resolution. A reasoned defer/reject stays visible.
            issue.update(status="adopted_unresolved" if response["disposition"] == "adopt" else response["disposition"], latest_response=value)
            db.execute("UPDATE orchestration_issues SET payload_json=? WHERE issue_id=?", (_json(issue), issue["issue_id"]))
        claims_changed = bool(raw.get("claims")) and fingerprint(raw.get("claims", [])) != fingerprint(run["current_view"].get("claims", []))
        next_view = {"summary": raw.get("summary", ""), "claims": raw.get("claims", []),
                     "alternatives": raw.get("alternatives", []), "unresolved": raw.get("unresolved", [])}
        if next_view != run["current_view"]:
            run["view_version"] += 1
            run["current_view"] = next_view
            for row in db.execute("SELECT issue_id,payload_json FROM orchestration_issues WHERE run_id=?", (run["run_id"],)).fetchall():
                issue = json.loads(row[1])
                if str(issue["target_version"]) != str(run["view_version"]):
                    issue["stale"] = True
                    db.execute("UPDATE orchestration_issues SET payload_json=? WHERE issue_id=?", (_json(issue), row[0]))
        decision["view_version"] = run["view_version"]
        db.execute("INSERT INTO orchestration_decisions VALUES (?,?,?,?)", (decision["decision_id"], run["run_id"], meta["result_id"], _json(decision)))
        run["last_decision_id"] = decision["decision_id"]
        self._event(db, run["run_id"], "core_decision", raw.get("summary", "Core判断を保存しました。"), source="core", target="handler", task_id=task["task_id"])
        intents = raw.get("intents", [])
        if raw.get("stop"):
            proposal = {**raw["stop"], "target_id": "view:" + run["run_id"], "target_version": run["view_version"],
                        "decision_id": decision["decision_id"], "unexecuted_intents": intents}
            # A reviewer cannot veto indefinitely. A reviewed unchanged view needs
            # only Core's explicit reasoned responses; no repeated critic call.
            reviewed = run["view_version"] in run["reviewed_stop_versions"]
            unanswered = db.execute("SELECT issue_id FROM orchestration_issues WHERE run_id=? AND issue_id NOT IN (SELECT issue_id FROM orchestration_responses WHERE run_id=?)",
                                    (run["run_id"], run["run_id"])).fetchall()
            if reviewed:
                run["pending_stop"] = proposal
                if self._continue_minimum_iterations(db, run, raw["stop"]["reason"]):
                    return
                if unanswered:
                    self._stop(db, run, "human_review_required")
                else:
                    self._stop(db, run, raw["stop"]["reason"], completed=raw["stop"]["reason"] in {"question_satisfied", "no_more_evidence"})
                return
            run["pending_stop"] = proposal
            limit = self._limit(db, run, new_round=True)
            if limit:
                self._stop(db, run, limit)
                return
            run["phase"], run["review_status"] = "stop_review", "pending"
            self._register(db, run, {"role": "critic", "question": "終了案の結論・代替説明・未解決点をレビューする",
                "target_id": proposal["target_id"], "target_version": proposal["target_version"],
                "scope": "pre_stop", "evidence_version": run["input_hash"]}, phase="stop_review", automatic=True)
            if raw.get("claims") and run["status"] not in TERMINAL and not any(t["role"] == "verification" and t["status"] == "succeeded" and t["annotation_version"] == run["annotation_version"] for t in self._tasks(db, run["run_id"])):
                self._register(db, run, {"role": "verification", "question": "原文から独立に観察事実・矛盾を確認する",
                    "target_version": run["view_version"] if claims_changed else None}, phase="stop_review", automatic=True)
        else:
            run["pending_stop"] = None
            run["phase"] = "specialists"
            registered = 0
            for intent in intents:
                if run["status"] in TERMINAL:
                    break
                if intent.get("role") == "core":
                    raise _error("Coreは専門家として再帰発注できません。", "invalid_intent")
                if run["config"]["stop_mode"] == "importance":
                    importance = intent.get("importance")
                    if importance not in IMPORTANCE or not intent.get("importance_reason"):
                        raise _error("重要度モードには重要度と理由が必要です。", "invalid_intent")
                    if IMPORTANCE[importance] < IMPORTANCE[run["config"]["importance_threshold"]]:
                        self._event(db, run["run_id"], "intent_deferred", "重要度の閾値未満の案を保存し、実行しません。", intent=intent)
                        continue
                if intent.get("role") == "critic":
                    intent = {**intent, "target_id": "view:" + run["run_id"], "target_version": run["view_version"]}
                if self._register(db, run, intent, phase="specialists"):
                    registered += 1
            if claims_changed and run["status"] not in TERMINAL:
                requested_roles = {intent["role"] for intent in intents}
                if "verification" not in requested_roles:
                    registered += bool(self._register(db, run, {"role": "verification", "question": "原文から独立に観察事実・矛盾を確認する",
                        "target_version": run["view_version"]}, phase="specialists", automatic=True))
                if "critic" not in requested_roles and run["status"] not in TERMINAL:
                    registered += bool(self._register(db, run, {"role": "critic", "question": "主要な主張と代替説明をレビューする",
                        "target_id": "view:" + run["run_id"], "target_version": run["view_version"], "scope": "major_claim"},
                        phase="specialists", automatic=True))
            if not registered and run["status"] not in TERMINAL:
                # No useful new work is a bounded pause, not a fabricated success.
                reason = "importance_threshold" if run["config"]["stop_mode"] == "importance" else "no_new_tasks"
                if not self._continue_minimum_iterations(db, run, reason):
                    self._stop(db, run, reason)
        self._write_run(db, run)

    def _drain_tasks(self, run_id):
        with self._db() as db:
            run = self._read_run(db, run_id)
            concurrency = run["config"]["concurrency"]
        pool = ThreadPoolExecutor(max_workers=concurrency, thread_name_prefix="analysis-task")
        futures = {}
        try:
            while True:
                with self._db() as db:
                    received = [t["task_id"] for t in self._tasks(db, run_id) if t["status"] == "received"]
                for task_id in received:
                    self._validate_received(run_id, task_id)
                with self._db() as db:
                    run = self._read_run(db, run_id)
                    limit = self._limit(db, run)
                    if limit:
                        self._stop(db, run, limit)
                    if run["status"] in TERMINAL or run["status"] == "recovery_required":
                        return
                    tasks = self._tasks(db, run_id)
                    if any(t["status"] == "running" and t.get("started_epoch") is not None and time.time() - t["started_epoch"] > run["config"]["call_timeout_seconds"] for t in tasks):
                        self._stop(db, run, "call_timeout")
                        return
                    by_id = {t["task_id"]: t for t in tasks}
                    for task in tasks:
                        if task["status"] != "queued" or task["task_id"] in futures.values():
                            continue
                        dependencies = [by_id[i] for i in task["dependencies"]]
                        if any(t["status"] in {"failed", "quarantined", "cancelled", "blocked"} for t in dependencies):
                            task.update(status="blocked", error="dependency_failed")
                            self._write_task(db, task)
                        elif all(t["status"] == "succeeded" for t in dependencies) and len(futures) < concurrency:
                            futures[pool.submit(self._execute, run_id, task["task_id"])] = task["task_id"]
                    active = [t for t in tasks if t["status"] in {"running", "queued", "received"}]
                    if not futures and not active:
                        return
                if futures:
                    done, _ = wait(futures, timeout=.05, return_when=FIRST_COMPLETED)
                    for future in done:
                        future.result()
                        futures.pop(future, None)
                else:
                    # Unresolvable dependency is explicit, never a busy loop.
                    with self._db() as db:
                        for task in self._tasks(db, run_id):
                            if task["status"] == "queued":
                                task.update(status="blocked", error="dependency_unavailable")
                                self._write_task(db, task)
                    return
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    def run(self, run_id: str) -> None:
        """Drive the initial stages and Core phases without duplicate local drivers."""
        with self._worker_lock:
            if run_id in self._driving:
                return
            self._driving.add(run_id)
        try:
            if self._build_initial(run_id):
                self._run_analysis(run_id)
            self._notify_completed(run_id)
        finally:
            with self._worker_lock:
                self._driving.discard(run_id)

    def _run_analysis(self, run_id: str) -> None:
        """Drive persisted phases; safe to call synchronously with mock adapters."""
        try:
            with self._db() as db:
                run = self._read_run(db, run_id)
                if run["status"] in TERMINAL or run["status"] == "recovery_required":
                    return
                self._check_version(run)
                if any(t["status"] in {"running", "uncertain"} for t in self._tasks(db, run_id)):
                    run.update(status="recovery_required", error="進行中だった呼出しを照合してから再開してください。")
                    self._write_run(db, run)
                    return
                if run["started_at"] is None:
                    run["started_at"] = _now()
                    seconds = run["config"]["time_limit_seconds"]
                    run["deadline"] = time.time() + seconds if seconds is not None else None
                run["status"] = "running"
                self._write_run(db, run)
            while True:
                with self._db() as db:
                    run = self._read_run(db, run_id)
                    if run["status"] in TERMINAL or run["status"] == "recovery_required":
                        return
                    limit = self._limit(db, run)
                    if limit:
                        self._stop(db, run, limit); return
                    phase = run["phase"]
                    tasks = self._tasks(db, run_id)
                    if phase == "core":
                        pending_core = [t for t in tasks if t["role"] == "core" and t["iteration"] == run["iteration"]]
                        if not pending_core or pending_core[-1]["status"] == "succeeded" and db.execute(
                            "SELECT 1 FROM orchestration_decisions WHERE result_id=(SELECT result_id FROM orchestration_results WHERE task_id=?)", (pending_core[-1]["task_id"],)).fetchone():
                            limit = self._limit(db, run, new_round=True)
                            if limit:
                                self._stop(db, run, limit); return
                            run["iteration"] += 1
                            self._register(db, run, {"role": "core", "question": run["config"]["question"]}, phase="core", automatic=True)
                            self._write_run(db, run)
                self._drain_tasks(run_id)
                with self._db() as db:
                    run = self._read_run(db, run_id)
                    if run["status"] in TERMINAL or run["status"] == "recovery_required":
                        return
                    tasks = self._tasks(db, run_id)
                    if run["phase"] == "core":
                        task = next((t for t in reversed(tasks) if t["role"] == "core" and t["iteration"] == run["iteration"]), None)
                        if task is None or task["status"] != "succeeded":
                            self._stop(db, run, "execution_failure"); return
                        result = db.execute("SELECT * FROM orchestration_results WHERE task_id=?", (task["task_id"],)).fetchone()
                        self._apply_core(db, run, task, result)
                    elif run["phase"] == "stop_review":
                        reviews = [t for t in tasks if t["role"] == "critic" and t["phase"] == "stop_review" and t["intent"].get("target_version") == run["pending_stop"]["target_version"]]
                        blind_reviews = [t for t in tasks if t["role"] == "verification" and t["phase"] == "stop_review" and t["iteration"] == run["iteration"]]
                        if not reviews or reviews[-1]["status"] != "succeeded" or any(t["status"] != "succeeded" for t in blind_reviews):
                            run["review_status"] = "unavailable"
                            self._stop(db, run, "review_incomplete"); return
                        run["reviewed_stop_versions"].append(run["pending_stop"]["target_version"])
                        run["review_status"] = "reviewed"
                        run["phase"] = "core"
                        self._write_run(db, run)
                    else:
                        run["phase"] = "core"
                        self._write_run(db, run)
        except Exception as exc:
            with self._db() as db:
                run = self._read_run(db, run_id)
                if run["status"] not in TERMINAL:
                    run["error"] = getattr(exc, "code", type(exc).__name__)
                    self._stop(db, run, "execution_failure")
