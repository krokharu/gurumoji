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
from .services.analysis_orchestration_methods import STATISTICAL_TOOLS
from .analysis_method_registry import TABLE_PILOT_METHODS as LEGACY_TABLE_METHODS, CONNECTED_METHODS
TABLE_PILOT_METHODS = {**LEGACY_TABLE_METHODS, **CONNECTED_METHODS}

SCHEMA_VERSION = 1
ROLES = {"core": "Core", "handler": "Handler", "interpretation": "会話解釈",
         "statistics": "数量・統計", "verification": "独立検証", "critic": "批判者",
         "obsidian_manager": "Obsidian管理"}
AI_ROLES = frozenset({"core", "interpretation", "verification", "critic"})
INITIAL_SECTIONS = frozenset({"segments", "annotations", "automatic", "manual", "research", "config", "cautions", "classification"})
LABEL_FIELDS = frozenset({"code", "codes", "theme", "sentiment", "dialogue_act", "importance", "review", "category"})
METHODS = frozenset({"participation", "conversation_dynamics", "label_frequency", *STATISTICAL_TOOLS})
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
              "context_text_limit": payload.get("context_text_limit", 60000),
              "obsidian_management": payload.get("obsidian_management", True),
              "expert_hooks": payload.get("expert_hooks", True)}
    for key in ("expert_ids", "expert_inputs"):
        if key in payload:
            config[key] = copy.deepcopy(payload[key])
    if "expert_ids" in config and (not isinstance(config["expert_ids"], list)
            or not 1 <= len(config["expert_ids"]) <= 9
            or any(not isinstance(eid, str) or not eid.startswith("exp-") or len(eid) > 100 for eid in config["expert_ids"])
            or len(set(config["expert_ids"])) != len(config["expert_ids"])):
        raise _error("専門家IDは重複なく1〜6件指定してください。", "expert_selection_invalid")
    if "expert_inputs" in config and (not isinstance(config["expert_inputs"], dict)
            or len(_json(config["expert_inputs"]).encode("utf-8")) > 16000):
        raise _error("専門家の入力形式・サイズが正しくありません。", "expert_format_mismatch")
    if type(config["obsidian_management"]) is not bool:
        raise _error("Obsidian管理はtrueまたはfalseです。", field="obsidian_management")
    if type(config["expert_hooks"]) is not bool:
        raise _error("専門家のデータhookはtrueまたはfalseです。", field="expert_hooks")
    if config["expert_hooks"]:
        from .services.expert_data_hooks import VERSION
        config["expert_hook_version"] = payload.get("expert_hook_version", VERSION)
        if config["expert_hook_version"] != VERSION:
            raise _error("専門家のデータhookの版が異なります。", "expert_hook_version_conflict")
    for key, low, high in (("max_calls", 1, 10000), ("max_tasks", 1, 20000), ("concurrency", 1, 4),
                           ("call_timeout_seconds", 1, 3600), ("max_result_bytes", 1000, 20_000_000),
                           ("context_evidence_limit", 1, 120), ("context_text_limit", 1, 60000)):
        if type(config[key]) is not int or not low <= config[key] <= high:
            raise _error(f"{key}は{low}〜{high}の整数です。", field=key)
    if "context_evidence_limits_by_role" in payload:
        limits = payload["context_evidence_limits_by_role"]
        if (not isinstance(limits, dict) or any(role not in ROLES or type(limit) is not int
                or not 1 <= limit <= config["context_evidence_limit"] for role, limit in limits.items())):
            raise _error("役割別の根拠行数は既知の役割と1〜共有上限の整数で指定してください。",
                         field="context_evidence_limits_by_role")
        # Omission must retain legacy config/hash bytes and shared-cap behavior.
        config["context_evidence_limits_by_role"] = copy.deepcopy(limits)
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


class OrchestrationBudget:
    """Private lifecycle state around the existing transport guard (not a serializer).

    The caller owns proof, reservation limits and any shared batch quota. A run
    never recreates this controller from persisted clock numbers on restart.
    """
    def __init__(self, request_budget, *, run_id, run_started_at, clock):
        from .services.ai.request_budget import TASK_SECONDS, payload_hash, profile_limits
        ledger = request_budget.ledger()
        if (request_budget._clock is not clock or ledger["run_started_at"] != run_started_at
                or ledger["run_id"] != payload_hash(run_id)
                or ledger["run_deadline"] != run_started_at + profile_limits(ledger["profile"])["run_seconds"]):
            raise _error("budgetの時計と起点が一致しません。", "budget_origin_mismatch")
        self.request_budget, self.clock = request_budget, clock
        self.origin, self.deadline = run_started_at, ledger["run_deadline"]
        self.task_seconds, self.tasks = TASK_SECONDS, {}
        self.clock_id = uuid.uuid4().hex
        self.last_clock = run_started_at
        self.lock = threading.RLock()
        self.cleanup_hold = None
        self.clock_hold = None

    def register(self, task_id, origin):
        with self.lock:
            self.request_budget.register_task(task_id, origin)
            self.tasks[task_id] = origin

    def reason(self, task_id=None):
        with self.lock:
            if self.clock_hold:
                return self.clock_hold
            try:
                now = self.clock()
            except Exception:
                self.clock_hold = "budget_clock_mismatch"
                return self.clock_hold
            if type(now) not in (int, float) or not math.isfinite(now) or now < self.last_clock:
                self.clock_hold = "budget_clock_mismatch"
                return self.clock_hold
            self.last_clock = now
            if now >= self.deadline:
                return "time_limit"
            if task_id is not None:
                if task_id not in self.tasks:
                    return "budget_origin_unavailable"
                if now >= min(self.deadline, self.tasks[task_id] + self.task_seconds):
                    return "call_timeout"
            if self.request_budget.ledger()["batch"]["hold_reason"]:
                return "budget_hold"
            return None

    def snapshot(self):
        return {"guarded": True, "run_started_at": self.origin, "clock_id": self.clock_id,
                "cleanup_hold": self.cleanup_hold, "clock_hold": self.clock_hold, "ledger": self.request_budget.ledger()}


class AnalysisOrchestrationService:
    def __init__(self, *, connect: Callable[[], sqlite3.Connection] | None = None,
                 database_connection: Callable[[], sqlite3.Connection] | None = None,
                 find_item: Callable[[str], Any], snapshot_builder: Callable[[Any], dict[str, Any]],
                 agent_runner: Callable[..., Any], method_runner: Callable[..., Any],
                 source_fingerprint: Callable[[Any], str] | None = None,
                 write_lock: Any = None, schedule: bool = True, adapter_version: str = "core-handler-prompts-1",
                 initial_builder: Any = None, on_complete: Callable[[str, str], Any] | None = None,
                 memory_manager: Any = None, expert_provider: Callable[[dict], dict] | None = None,
                 budget_factory: Callable[..., Any] | None = None, budget_clock: Callable[[], float] = time.monotonic,
                 table_store: Any = None):
        self.connect = connect or database_connection
        if self.connect is None:
            raise TypeError("connect is required")
        self.find_item, self.snapshot_builder = find_item, snapshot_builder
        self.agent_runner, self.method_runner = agent_runner, method_runner
        self.source_fingerprint, self.schedule = source_fingerprint, schedule
        self.adapter_version = adapter_version
        self.initial_builder, self.on_complete = initial_builder, on_complete
        self.memory_manager = memory_manager
        self.expert_provider = expert_provider
        self.table_store = table_store
        if table_store is not None:
            def current_source(item_id):
                item = self.find_item(item_id)
                if item is None or self.source_fingerprint is None: return None
                value = dict(item)
                return {"input_hash": self.source_fingerprint(item),
                    "source_revision": int(value.get("revision_count", 0) or 0),
                    "analysis_revision": int(value.get("analysis_revision", 0) or 0)}
            table_store.current_source_lookup = current_source
        self._table_validation_lock = threading.Lock()
        self._budget_factory, self._budget_clock = budget_factory, budget_clock
        self._run_budgets: dict[str, OrchestrationBudget] = {}
        if initial_builder is not None and source_fingerprint is None:
            raise TypeError("staged initial analysis requires source_fingerprint")
        self._driving: set[str] = set()
        self.lock = write_lock or threading.RLock()
        self._workers: dict[str, threading.Thread] = {}
        self._worker_lock = threading.Lock()
        # Construction is inert, including legacy factories used by GET.
        # Schema initialization belongs to the first execution transaction.
        self._store_initialized = False

    @contextmanager
    def _db(self):
        with self.lock:
            connection = self.connect()
            try:
                with connection as db:
                    db.row_factory = sqlite3.Row
                    if not db.in_transaction:
                        db.execute("BEGIN IMMEDIATE")
                    if not self._store_initialized:
                        initialize_orchestration_store(db)
                    yield db
                self._store_initialized = True
            finally:
                # sqlite3.Connection's context manager commits but does not
                # close. Factories returning context managers close themselves.
                if isinstance(connection, sqlite3.Connection):
                    connection.close()

    @contextmanager
    def _table_read(self, item_id):
        from pathlib import Path
        from .services.analysis_history import AnalysisHistoryService
        # Reuse the viewer's query-only deferred read transaction. Production
        # also supplies its mode=ro connection to both this reader and Store.
        if self.table_store is None:
            raise _error("表pilotのStore接続がありません。", "table_pilot_disabled")
        if not Path(self.table_store.database_file).is_file():
            raise LookupError("固定表の選択に必要な保存済み台帳がありません。")
        connection = None
        def connect():
            nonlocal connection
            connection = self.connect()
            return connection
        viewer = AnalysisHistoryService(connect=connect, find_item=self.find_item)
        try:
            with viewer._read(item_id) as db:
                if any(not viewer._table(db, name) for name in
                       ("orchestration_runs", "orchestration_initials", "orchestration_tasks", "orchestration_results", "orchestration_usage")):
                    raise LookupError("固定表の選択に必要な保存済み台帳がありません。")
                yield db
        except sqlite3.OperationalError as exc:
            if str(exc).startswith(("no such table:", "no such column:")):
                raise LookupError("固定表の選択に必要な保存済み台帳がありません。") from exc
            raise
        finally:
            if isinstance(connection, sqlite3.Connection):
                connection.close()

    def _check_version(self, run):
        if run["config"].get("expert_hooks", False):
            from .services.expert_data_hooks import VERSION
            if run["config"].get("expert_hook_version") != VERSION:
                raise _error("専門家のデータhookの版が変わりました。新しいrunを開始してください。", "expert_hook_version_conflict")
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
        db.execute("UPDATE orchestration_runs SET state_json=? WHERE run_id=?", (self._run_json(run), run["run_id"]))

    def _run_json(self, run: dict) -> str:
        """Prepare safety metadata and serialization before a promotion fence."""
        run["updated_at"] = _now()
        guard = self._run_budgets.get(run["run_id"])
        if guard is not None:
            run["request_budget"] = guard.snapshot()
        return _json(run)

    def _budget_reason(self, run, task_id=None):
        saved = run.get("request_budget")
        guard = self._run_budgets.get(run["run_id"])
        if saved is None and guard is None:
            return None
        if guard is None or guard.clock is not self._budget_clock or guard.request_budget._clock is not guard.clock or (saved is not None and
                (saved.get("clock_id") != guard.clock_id or saved.get("run_started_at") != guard.origin)):
            return "budget_origin_unavailable"
        return guard.reason(task_id)

    def _require_budget(self, run, task_id=None):
        reason = self._budget_reason(run, task_id)
        if reason:
            raise _error("guarded実行の期限・時計・usage証明を確認できません。", reason)

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

    def _thematic_source(self, db, run, profile, snapshot):
        """Opt-in only: actual Store authority and immutable Handler snapshot."""
        if profile.get("typed_contract") not in {"thematic_candidates_v1", "focus_group_interaction_candidates_v1"}: return None
        if profile.get("typed_contract") == "focus_group_interaction_candidates_v1":
            initial = db.execute("SELECT item_id,snapshot_hash FROM orchestration_initials WHERE initial_id=?",
                                 (run["initial_id"],)).fetchone()
            if (initial is None or initial["item_id"] != run["item_id"]
                    or initial["snapshot_hash"] != fingerprint(snapshot)
                    or snapshot.get("conversation_id", run["item_id"]) != run["item_id"]
                    or snapshot.get("input_hash") != run["input_hash"]):
                raise _error("固定入力の会話・版が一致しません。", "fgi_source_or_delivery_mismatch")
        if self.table_store is None:
            raise _error("型付き候補の固定保存先が利用できません。", "typed_source_missing")
        from pathlib import Path
        authority = next((row[2] for row in db.execute("PRAGMA database_list") if row[1] == "main"), None)
        if not authority or Path(authority).resolve() != self.table_store.database_file:
            raise _error("HandlerとStoreのlibraryが異なります。", "typed_store_mismatch")
        from .services.expert_agents import thematic_source_packet
        return thematic_source_packet({"initial_id": run["initial_id"], "snapshot": snapshot},
            library_id=self.table_store.library_id(), conversation_id=run["item_id"])

    def start(self, item_id: str, payload: dict, app_url: str = "", *, budget_factory=None) -> dict:
        origin = self._budget_clock()
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
                comparison_config = copy.deepcopy(config)
                if "obsidian_management" not in saved_config and "obsidian_management" not in payload:
                    comparison_config.pop("obsidian_management", None)
                    matches = existing["request_hash"] == fingerprint({"item_id": item_id, "config": comparison_config,
                        "source_revision": payload.get("source_revision"), "analysis_revision": payload.get("analysis_revision"),
                        "input_hash": payload.get("input_hash")})
                if not matches and "publication_targets" not in saved_config and not config["publication_targets"]:
                    legacy_config = {key: value for key, value in comparison_config.items()
                                     if key not in {"publication_targets", "effective_publication_writers"}}
                    matches = existing["request_hash"] == fingerprint({"item_id": item_id, "config": legacy_config,
                        "source_revision": payload.get("source_revision"), "analysis_revision": payload.get("analysis_revision"),
                        "input_hash": payload.get("input_hash")})
                if existing["item_id"] != item_id or not matches:
                    raise _error("同じrequest_idに異なる設定は使えません。", "request_conflict")
                return self._public(db, json.loads(existing["state_json"]))
        run_id = _id("run")
        factory = budget_factory if budget_factory is not None else self._budget_factory
        if factory is not None:
            budget = factory(run_id=run_id, run_started_at=origin, clock=self._budget_clock)
            self._run_budgets[run_id] = OrchestrationBudget(budget, run_id=run_id, run_started_at=origin, clock=self._budget_clock)
            self._require_budget({"run_id": run_id})
        item = self.find_item(item_id)
        if item is None:
            raise LookupError("会話が見つかりません。")
        current_item = dict(item)
        for supplied, actual in (("source_revision", "revision_count"), ("analysis_revision", "analysis_revision")):
            if supplied in payload and (type(payload[supplied]) is not int or payload[supplied] != int(current_item.get(actual, 0) or 0)):
                raise _error("確認した入力版が更新されています。", "revision_conflict", supplied)
        # A source fingerprint permits cache lookup before the expensive fixed analysis.
        before = self.source_fingerprint(item) if self.source_fingerprint else None
        self._require_budget({"run_id": run_id})
        if self.expert_provider is None and any(key in config for key in ("expert_ids", "expert_inputs")):
            raise _error("専門家の知識取得が接続されていません。", "expert_provider_unavailable")
        expert_bundle = self.expert_provider(config) if self.expert_provider is not None else None
        self._require_budget({"run_id": run_id})
        if self.initial_builder is not None:
            return self._start_staged(item_id, payload, config, request_id, request_hash, app_url, item, before, expert_bundle, run_id)
        snapshot = None
        if before is None:
            snapshot = self.snapshot_builder(item)
            self._require_budget({"run_id": run_id})
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
                if run_id not in self._run_budgets:
                    # Preserve the ordinary unguarded capture/cache behavior.
                    with self._db() as db:
                        db.execute("UPDATE orchestration_initials SET status='ready',snapshot_json=?,snapshot_hash=? WHERE initial_id=? AND status='building'",
                                   (_json(snapshot), fingerprint(snapshot), initial_id))
            except Exception as exc:
                with self._db() as db:
                    db.execute("UPDATE orchestration_initials SET status='failed',error=? WHERE initial_id=?", (type(exc).__name__, initial_id))
                raise
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
        if expert_bundle is not None:
            run["expert_agents"] = expert_bundle
        guarded_build = build and run_id in self._run_budgets
        try:
            # No guarded ready state is visible until every preparation has
            # completed and this transaction, including its final fence, commits.
            labels_json = _json(self._source_labels(snapshot))
            snapshot_json = _json(snapshot) if guarded_build else None
            snapshot_hash = fingerprint(snapshot) if guarded_build else None
            run_json = self._run_json(run)
            with self._db() as db:
                # Recheck a concurrent identical start after initial capture.
                existing = db.execute("SELECT * FROM orchestration_runs WHERE request_id=?", (request_id,)).fetchone()
                if existing:
                    if existing["request_hash"] != request_hash:
                        raise _error("request_idが競合しました。", "request_conflict")
                    return self._public(db, json.loads(existing["state_json"]))
                self._require_budget(run)
                if guarded_build:
                    db.execute("UPDATE orchestration_initials SET status='ready',snapshot_json=?,snapshot_hash=? WHERE initial_id=? AND status='building'",
                               (snapshot_json, snapshot_hash, initial_id))
                db.execute("INSERT INTO orchestration_runs VALUES (?,?,?,?,?,?)", (run_id, item_id, request_id, request_hash, initial_id, run_json))
                db.execute("INSERT INTO orchestration_label_versions VALUES (?,?,?)", (run_id, 0, labels_json))
                self._event(db, run_id, "initial_saved", "初期分析の全結果を不変の版として固定しました。", initial_id=initial_id)
                self._require_budget(run)
        except Exception as exc:
            if guarded_build:
                with self._db() as db:
                    # Never invalidate a cached initial owned by an earlier run.
                    db.execute("UPDATE orchestration_initials SET status='failed',error=? WHERE initial_id=? AND status='building'",
                               (getattr(exc, "code", type(exc).__name__), initial_id))
            raise
        self._notify_management(run_id)
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

    def _start_staged(self, item_id, payload, config, request_id, request_hash, app_url, item, before, expert_bundle=None, run_id=None):
        if payload.get("input_hash") is not None and payload["input_hash"] != before:
            raise _error("確認した入力hashが更新されています。", "revision_conflict", "input_hash")
        identity = fingerprint({"item_id": item_id, "dataset_version": before,
                                "template_version": config["template_version"], "config": config["template_config"]})
        run_id = run_id or _id("run")
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
                self._require_budget({"run_id": run_id})
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
            if expert_bundle is not None:
                run["expert_agents"] = expert_bundle
            self._validate_initial_source(run)
            if snapshot is not None:
                run["source_revision"] = snapshot.get("source_revision", run["source_revision"])
                run["analysis_revision"] = snapshot.get("analysis_revision", run["analysis_revision"])
                run["codebook_version"] = int(snapshot["analysis"].get("manual", {}).get("codebook_version", snapshot["analysis"].get("config", {}).get("codebook_version", 1)))
            labels_json = _json(self._source_labels(snapshot)) if snapshot is not None else None
            run_json = self._run_json(run)
            self._require_budget(run)
            db.execute("INSERT INTO orchestration_runs VALUES (?,?,?,?,?,?)", (run_id, item_id, request_id, request_hash, initial_id, run_json))
            if snapshot is not None:
                db.execute("INSERT INTO orchestration_label_versions VALUES (?,?,?)", (run_id, 0, labels_json))
            self._event(db, run_id, "initial_saved" if snapshot is not None else "initial_queued",
                         "初期分析の保存済み全結果を再利用します。" if snapshot is not None else "初期分析の入力を固定しました。段階ごとに保存して実行します。", initial_id=initial_id)
            self._require_budget(run)
        self._notify_management(run_id)
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
                        encoded_snapshot, snapshot_hash = _json(snapshot), fingerprint(snapshot)
                        labels_json = _json(self._source_labels(snapshot))
                        run.update(phase="core", error="", codebook_version=int(snapshot["analysis"].get("manual", {}).get("codebook_version", snapshot["analysis"].get("config", {}).get("codebook_version", 1))))
                        run_json = self._run_json(run)
                        self._require_budget(run)
                        db.execute("UPDATE orchestration_initials SET status='ready',snapshot_json=?,snapshot_hash=?,error='' WHERE initial_id=?",
                                   (encoded_snapshot, snapshot_hash, run["initial_id"]))
                        db.execute("INSERT OR IGNORE INTO orchestration_label_versions VALUES (?,?,?)", (run_id, 0, labels_json))
                        db.execute("UPDATE orchestration_runs SET state_json=? WHERE run_id=?", (run_json, run_id))
                        self._event(db, run_id, "initial_saved", "初期分析の全段階を不変の版として固定しました。", initial_id=run["initial_id"])
                        self._require_budget(run)
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
                self._notify_management(run_id)
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
                    limit = self._budget_reason(run)
                    if limit:
                        run["error"] = error
                        self._stop(db, run, limit)
                    else:
                        run.update(status="recovery_required", error=error, stale=run["stale"] or error == "revision_conflict")
                        self._write_run(db, run)
                        self._event(db, run_id, "initial_recovery_required", "初期分析は未完了です。完了済み段階を保持しています。", error=error)
            return False

    def _notify_management(self, run_id):
        """Forward committed Core/Handler data without a DB transaction during writes.

        Keep the library -> Vault lock order and serialize receipts, so a delayed
        worker cannot publish an older view over a newer committed snapshot.
        """
        if self.memory_manager is None:
            return
        from .services.obsidian_management import management_packet
        with self.lock:
            with self._db() as db:
                run = self._read_run(db, run_id)
                if not run["config"].get("obsidian_management", False):
                    return
                state = self._public(db, run)
                decisions = [json.loads(row[0]) for row in db.execute(
                    "SELECT payload_json FROM orchestration_decisions WHERE run_id=? ORDER BY rowid", (run_id,))]
            try:
                item = self.find_item(run["item_id"])
                if item is None:
                    raise LookupError("source_deleted")
                state["stale"] = bool(state["stale"] or self.source_fingerprint and self.source_fingerprint(item) != run["input_hash"])
                receipt = self.memory_manager.receive(management_packet(state, decisions))
            except Exception as exc:
                # Exceptions can contain paths/secrets. Store only a reason code.
                receipt = {"status": "failed", "error_code": type(exc).__name__}
            with self._db() as db:
                latest = self._read_run(db, run_id)
                latest["obsidian_management"] = receipt
                self._write_run(db, latest)

    def sync_memory(self, item_id, run_id):
        with self._db() as db:
            run = self._read_run(db, run_id, item_id)
            if not run["config"].get("obsidian_management", False) or self.memory_manager is None:
                raise _error("この実行ではObsidian管理が有効ではありません。", "memory_not_enabled")
        self._notify_management(run_id)
        return self.status(item_id, run_id)

    def memory_note(self, item_id, run_id):
        with self._db() as db:
            run = self._read_run(db, run_id, item_id)
            if not run["config"].get("obsidian_management", False) or self.memory_manager is None:
                raise LookupError("管理ノートがありません。")
            state = self._public(db, run)
        return self.memory_manager.read_note(state, state["obsidian_management"])

    def _notify_completed(self, run_id):
        if self.on_complete is None:
            return
        with self._db() as db:
            run = self._read_run(db, run_id)
            if run["status"] != "completed" or run.get("completion_callback_status"):
                return
            limit = self._budget_reason(run)
            if limit:
                run.update(completion_callback_status="failed", publication_error=limit)
                self._write_run(db, run)
                return
            run["completion_callback_status"] = "running"
            self._write_run(db, run)
            item_id = run["item_id"]
        try:
            self.on_complete(item_id, run_id)
            with self._db() as db:
                self._require_budget(self._read_run(db, run_id))
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
            row = {"id": evidence_id, "evidence_id": evidence_id, "utterance_id": utterance_id,
                   "dataset_version": snapshot["input_hash"], "source_hash": fingerprint(text),
                   "text": text, "speaker": segment.get("speaker"), "start": segment.get("start"),
                   "end": segment.get("end"), "excluded": bool(segment.get("excluded"))}
            if "valid_time" in segment:
                row["valid_time"] = segment["valid_time"]
                if "duration" in segment:
                    row["duration"] = segment["duration"]
                # Timeline zeroes can be placeholders; only the explicit flag
                # marks unknown time. Observed zero and legacy rows stay intact.
                if segment["valid_time"] is False:
                    row["start"] = row["end"] = None
                    if "duration" in row:
                        row["duration"] = None
            evidence.append(row)
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
                "measured_calls": len(records),
                "measurement_status": "reported" if records else "unavailable"}

    def _public(self, db, run):
        result = copy.deepcopy(run)
        if "expert_agents" in run:
            from .services.expert_agents import catalog_packet
            result["expert_agents"] = catalog_packet(run["expert_agents"])
        result["config"].setdefault("publication_targets", [])
        result["config"]["effective_publication_writers"] = list(EFFECTIVE_PUBLICATION_WRITERS) if result["config"]["publication_targets"] else []
        result["initial"] = initial_progress(db, run["initial_id"])
        result["initial_stages"] = result["initial"]["stages"]
        tasks = self._tasks(db, run["run_id"])
        for task in tasks:
            if task["method_id"] in TABLE_PILOT_METHODS and task.get("table_pilot_prepared"):
                task["current_permission"] = self._table_current_permission(task)
                if run["cancel_requested"] or run["status"] == "cancelled":
                    task["current_permission"] = {"decision": "blocked", "reason": "table_run_cancelled",
                                                  "execution_enabled": False, "adoption_performed": False}
                if task["status"] == "succeeded" and task["current_permission"]["decision"] != "eligible":
                    task["status"] = "blocked"
        result["tasks"] = tasks
        result["events"] = [{"seq": row[0], **json.loads(row[1])} for row in db.execute(
            "SELECT seq,payload_json FROM orchestration_events WHERE run_id=? ORDER BY seq", (run["run_id"],))]
        enabled = run["config"].get("obsidian_management", False)
        memory = copy.deepcopy(run.get("obsidian_management") or {"status": "pending" if self.memory_manager else "unavailable"})
        if not enabled:
            memory = {"status": "disabled"}
        elif self.memory_manager is not None:
            try:
                memory = self.memory_manager.inspect(result, memory)
            except (OSError, ValueError, TypeError, KeyError):
                memory = {**memory, "status": "conflict"}
        result["obsidian_management"] = {**memory, "enabled": enabled}
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
            if role == "obsidian_manager":
                result["roles"][-1].update(status=memory["status"], assigned=None, completed=None, failed=None,
                    current_task="Core判断・Handler台帳とデータ参照を管理")
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

    def submit_human_record(self, item_id, run_id, payload, *, request_bytes):
        """Explicit local researcher submission; no model dispatch or inference."""
        if self.table_store is None: raise _error("固定保存が接続されていません。", "human_store_unavailable")
        with self.lock:
            with self._db() as db:
                run = self._read_run(db, run_id, item_id)
                self._check_version(run)
                from pathlib import Path
                authority = db.execute("PRAGMA database_list").fetchone()[2]
                if not authority or Path(authority).resolve() != self.table_store.database_file.resolve():
                    raise _error("保存台帳が一致しません。", "human_store_mismatch")
                generation = run["generation"]
            def guard(db):
                current = self._read_run(db, run_id, item_id)
                self._check_version(current)
                item = self.find_item(item_id)
                if item is None:
                    raise _error("元データが変更されています。", "revision_conflict")
                if self.source_fingerprint: self._validate_initial_source(current)
                if current["generation"] != generation:
                    raise _error("記録中に分析版が変わりました。", "revision_conflict")
            outcome = self.table_store.submit_human_record(item_id=item_id, execution_run_id=run_id,
                payload=payload, request_bytes=request_bytes, commit_guard=guard)
            if outcome["stale_assets"]:
                assets, _originals, _states, links = self.table_store._connection_index()
                keys = outcome["stale_assets"]
                producers = {(a.get("execution_run_id"), a.get("producer_task_id")) for a in assets.values() if a["asset_key"] in keys}
                producers.update((link["execution_run_id"], link["producer_task_id"]) for link in links if link["asset_key"] in keys)
                with self._db() as db:
                    for producer_run, task_id in producers:
                        if not producer_run or not task_id: continue
                        row = db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=? AND run_id=?", (task_id, producer_run)).fetchone()
                        if row:
                            task = json.loads(row[0])
                            if task.get("human_record_ref") == outcome["record_ref"]: continue
                            task.update(stale=True, stale_reason="human_record_corrected", human_record_ref=outcome["record_ref"])
                            self._write_task(db, task)
                        for row in db.execute("SELECT result_id,state_json FROM orchestration_results WHERE task_id=? AND run_id=?", (task_id, producer_run)).fetchall():
                            meta = json.loads(row["state_json"]); meta.update(stale=True, stale_reason="human_record_corrected")
                            db.execute("UPDATE orchestration_results SET state_json=? WHERE result_id=?", (_json(meta), row["result_id"]))
                        dependent_run = self._read_run(db, producer_run)
                        # A record correction affects these retained outputs,
                        # not every independent output sharing the execution run.
                        marked = set(dependent_run.get("human_record_stale_tasks", [])); marked.add(task_id)
                        dependent_run["human_record_stale_tasks"] = sorted(marked)
                        self._write_run(db, dependent_run)
                        self._event(db, producer_run, "human_record_corrected", "参照した研究者記録が訂正されました。", task_id=task_id,
                                    record_ref=outcome["record_ref"])
            return outcome

    def result_locked(self, db, item_id: str, run_id: str, result_id: str | None = None) -> dict:
        """Serialize an export inside the caller's transaction, without nesting."""
        run = self._read_run(db, run_id, item_id)
        if result_id:
            row = db.execute("SELECT * FROM orchestration_results WHERE result_id=? AND run_id=?", (result_id, run_id)).fetchone()
            if row is None:
                raise LookupError("結果が見つかりません。")
            result = {**json.loads(row["state_json"]), "raw": json.loads(row["raw_json"])}
            task = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (row["task_id"],)).fetchone()[0])
            if task["method_id"] in TABLE_PILOT_METHODS:
                result["current_permission"] = self._table_current_permission(task)
                if run["cancel_requested"] or run["status"] == "cancelled":
                    result["current_permission"] = {"decision": "blocked", "reason": "table_run_cancelled",
                                                    "execution_enabled": False, "adoption_performed": False}
            return result
        initial = db.execute("SELECT * FROM orchestration_initials WHERE initial_id=?", (run["initial_id"],)).fetchone()
        public = self._public(db, run)
        table_permissions = {t["task_id"]: t["current_permission"] for t in public["tasks"] if "current_permission" in t}
        if "obsidian_management" in run:
            # Seal committed receipts, not a filesystem observation made at export
            # time. Live integrity/missing states remain on the status API.
            public["obsidian_management"] = copy.deepcopy(run["obsidian_management"])
        return {"run": public, **({"expert_knowledge_snapshot": copy.deepcopy(run["expert_agents"])} if "expert_agents" in run else {}),
            "initial": {"initial_id": initial["initial_id"],
            "hash": initial["snapshot_hash"], "snapshot": json.loads(initial["snapshot_json"]) if initial["snapshot_json"] else None},
            "raw_results": [{**json.loads(r[0]), "raw": json.loads(r[1]),
                             **({"current_permission": table_permissions[json.loads(r[0])["task_id"]]}
                                if json.loads(r[0])["task_id"] in table_permissions else {})} for r in db.execute("SELECT state_json,raw_json FROM orchestration_results WHERE run_id=? ORDER BY rowid", (run_id,))],
            "decisions": [json.loads(r[0]) for r in db.execute("SELECT payload_json FROM orchestration_decisions WHERE run_id=? ORDER BY rowid", (run_id,))],
            "label_audit": [json.loads(r[0]) for r in db.execute("SELECT payload_json FROM orchestration_label_audit WHERE run_id=? ORDER BY rowid", (run_id,))],
            "label_versions": [{"annotation_version": r[0], "labels": json.loads(r[1])} for r in db.execute(
                "SELECT annotation_version,payload_json FROM orchestration_label_versions WHERE run_id=? ORDER BY annotation_version", (run_id,))],
            "usage_records": [{"usage_id": r[0], "task_id": r[1], "payload": json.loads(r[2])} for r in db.execute(
                "SELECT usage_id,task_id,payload_json FROM orchestration_usage WHERE run_id=? ORDER BY rowid", (run_id,))]}

    def _stop(self, db, run, reason, *, completed=False):
        if run["status"] in TERMINAL:
            return
        if completed and self._statistical_review_gate(db, run):
            completed, reason = False, "human_review_required"
        run.update(status="completed" if completed else ("cancelled" if reason == "user_stop" else "stopped"),
                   phase="stopped", stop_reason=reason, ended_at=_now(), generation=run["generation"] + (0 if completed else 1))
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
        self._notify_management(run_id)
        return self.status(item_id, run_id)

    def resume(self, item_id: str, run_id: str, payload: dict | None = None) -> dict:
        payload = payload or {}
        if "obsidian_management" in payload and type(payload["obsidian_management"]) is not bool:
            raise _error("Obsidian管理はtrueまたはfalseです。", field="obsidian_management")
        if self.find_item(item_id) is None:
            raise LookupError("会話が見つかりません。")
        with self._worker_lock:
            worker = self._workers.get(run_id)
            if worker and worker.is_alive():
                return self.status(item_id, run_id)
        with self._db() as db:
            run = self._read_run(db, run_id, item_id)
            self._check_version(run)
            self._require_budget(run)
            if "publication_targets" in payload and validate_publication_targets(payload["publication_targets"]) != run["config"].get("publication_targets", []):
                raise _error("再開時に公開先を変更できません。新しいrunを開始してください。", "publication_scope_conflict")
            if "obsidian_management" in payload and payload["obsidian_management"] != run["config"].get("obsidian_management", False):
                raise _error("再開時にObsidian管理の保存範囲を変更できません。", "memory_scope_conflict")
            if run["phase"] == "initial":
                self._validate_initial_source(run)
                if self.initial_builder is None:
                    raise _error("初期分析の実装が利用できません。", "initial_version_conflict")
                read_initial_checkpoints(db, run["initial_id"], self.initial_builder)
            if run["status"] in TERMINAL:
                raise _error("終了済みrunは再実行しません。新しいrunを開始してください。", "run_terminal")
            saved_tasks=self._tasks(db,run_id)
            safe_plan_restart=bool(run.get("asset_plan_identity")) and all(t["kind"]=="code" and t["status"] not in {"running","uncertain","cancel_requested"} for t in saved_tasks)
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
            # A code-only plan with no in-flight call keeps its frozen generation;
            # queued children and receipts remain the same persisted tasks.
            run.update(status="queued", error="", generation=run["generation"] if safe_plan_restart else run["generation"] + 1)
            self._write_run(db, run)
        self._notify_management(run_id)
        if self.schedule:
            self._schedule(run_id)
        return self.status(item_id, run_id)

    def _limit(self, db, run, *, new_round=False):
        if run["cancel_requested"]:
            return "user_stop"
        guarded_limit = self._budget_reason(run)
        if guarded_limit:
            return guarded_limit
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

    def _table_run(self, db, item_id, run_id):
        if self.table_store is None:
            raise _error("表pilotのStore接続がありません。", "table_pilot_disabled")
        item = self.find_item(item_id)
        if item is None:
            raise LookupError("会話が見つかりません。")
        run = self._read_run(db, run_id, item_id)
        if run["status"] in TERMINAL or run["cancel_requested"]:
            raise _error("停止したrunへ発注できません。", "table_run_stopped")
        if run["status"] not in {"queued", "running"} or run["phase"] == "initial":
            raise _error("固定入力と実行状態を確認してください。", "table_run_unavailable")
        if run["stale"] or (self.source_fingerprint and self.source_fingerprint(item) != run["input_hash"]):
            raise _error("固定入力の版が更新されています。", "revision_conflict")
        self._check_version(run)
        self._require_budget(run)
        if self._limit(db, run):
            raise _error("実行上限に達しています。", "table_run_unavailable")
        authority_path = db.execute("PRAGMA database_list").fetchone()[2]
        from pathlib import Path
        if Path(authority_path).resolve() != Path(self.table_store.database_file).resolve():
            raise _error("HandlerとStoreのlibraryが異なります。", "table_store_mismatch")
        return run

    def table_pilot_options(self, item_id, run_id, *, offset=0):
        """Read fixed context and existing permitted inputs; never adopt or execute."""
        from .analysis_core import TABLE_PILOT_VERSION, TABLE_PILOT_MAX_BYTES
        from .analysis_method_registry import table_pilot_slot
        from .analysis_store import AssetBindingError
        if type(offset) not in (str, int) or (type(offset) is int and not 0 <= offset <= 10000):
            raise _error("表候補の開始位置が不正です。", "table_selection_offset")
        text = str(offset)
        if (len(text) > 5 or not text
                or any(c not in "0123456789" for c in text)
                or (len(text) > 1 and text[0] == "0") or int(text) > 10000):
            raise _error("表候補の開始位置が不正です。", "table_selection_offset")
        offset = int(text)
        with self._table_read(item_id) as db:
            run = self._table_run(db, item_id, run_id)
            initial = self._initial(db, run["initial_id"])
        context = {"plan_id": run_id, "plan_version": 1,
                   "plan_hash": fingerprint({"run_id": run_id, "input_hash": run["input_hash"]}),
                   "generation": run["generation"], "consumer_task_id": "table-selection:" + run_id,
                   "purpose": "exploratory", "destination": "local", "cancelled": False}
        selector = {"row_ids": [], "column_ids": [], "range_ref": None}
        selector["selection_hash"] = fingerprint(selector)
        result = {"version": TABLE_PILOT_VERSION, "actor": "code", "context": context,
                  "input": {k: run[k] for k in ("initial_id", "input_hash", "source_revision", "analysis_revision")},
                  "library_id": self.table_store.library_id(), "max_bytes": TABLE_PILOT_MAX_BYTES,
                  "methods": [{"method_id": method, "parameter_fields": list(parameters), "slot": table_pilot_slot(method),
                               "parameter_defaults": ({"key": "utterance_id"} if method == "table_join" else
                                    {} if method == "table_projection" else {"status_column": "value_status",
                                    **({"operation": "count", "group_by": "utterance_id", "unit": "utterance"}
                                       if method == "table_aggregate" else {})})}
                              for method, parameters in LEGACY_TABLE_METHODS.items()],
                  "scope_requirements": ["scope_id", "scope_manifest_hash"],
                  "purposes": ["exploratory", "descriptive"], "selector": selector,
                  "inputs": [], "offset": offset, "next_offset": None, "truncated": False}
        # Existing Store metadata is authoritative; no inferred descriptors/policies.
        try:
            assets = self.table_store._connection_index()[0]
            eligible_index = 0
            for key in sorted(assets):
                asset = assets[key]
                if (asset["asset_key"]["library_id"] != result["library_id"]
                        or asset["scope"]["conversation_ids"] != [item_id]):
                    continue
                binding_context = {**context, "scope_id": asset["scope"]["scope_id"],
                                   "scope_manifest_hash": asset["scope"]["manifest_hash"]}
                source = {"type": "frozen", **{k: asset[k] for k in ("asset_key", "content_hash", "content_domain")}}
                ref = {k: binding_context[k] for k in ("plan_id", "plan_version", "plan_hash", "generation", "consumer_task_id")}
                ref.update(slot_id="table", input_ref_id="table-input", role="data_input", selection="selected",
                           omission_reason=None, source=source, selector=selector)
                receipt = self.table_store.bind_asset_inputs(method_id="table_projection", slot=table_pilot_slot("table_projection"),
                                                            inputs=[ref], context=binding_context)
                if receipt["decision"] != "eligible":
                    continue
                table = receipt["payloads"][0]["value"]
                template = {"version": TABLE_PILOT_VERSION, "actor": "code",
                            "parameters": {"columns": table["fields"], "row_ids": [r["row_id"] for r in table["rows"]]},
                            "bindings": {"slot": table_pilot_slot("table_projection"), "inputs": [ref], "context": binding_context}}
                try:
                    self.table_store.prepare_table_pilot("table_projection", template, expected_snapshot=initial)
                except (AnalysisContractError, AssetBindingError):
                    continue
                eligible_index += 1
                if eligible_index <= offset:
                    continue
                candidate = {"source": source, "scope": asset["scope"], "variables": asset["variables"],
                             "fields": table["fields"], "row_ids": template["parameters"]["row_ids"],
                             "projection_request": template}
                if len(result["inputs"]) >= 20 or len(canonical({**result, "inputs": result["inputs"] + [candidate]})) > TABLE_PILOT_MAX_BYTES:
                    if not result["inputs"]:
                        raise _error("選択用の登録情報が上限を超えています。", "table_selection_byte_limit")
                    result["truncated"] = True
                    result["next_offset"] = offset + len(result["inputs"])
                    break
                result["inputs"].append(candidate)
        except AssetBindingError as exc:
            raise _error("固定表の登録情報を確認してください。", "table_input_" + exc.reason) from exc
        return result

    def register_table_pilot(self, item_id, run_id, method_id, request, *, server_bound=False):
        """Explicit local code opt-in; normal Core/Pack readers remain unchanged."""
        if not isinstance(method_id, str) or method_id not in TABLE_PILOT_METHODS:
            raise _error("未登録の表計算です。", "table_method_unsupported")
        with self._db() as db:
            run = self._table_run(db, item_id, run_id)
            from .analysis_core import validate_table_pilot_request
            request = validate_table_pilot_request(method_id, request)
            if server_bound and (request["bindings"]["context"]["consumer_task_id"] != "table-selection:" + run_id
                    or any(ref["consumer_task_id"] != "table-selection:" + run_id for ref in request["bindings"]["inputs"])):
                raise AnalysisContractError("サーバーが発行した表選択の接続先と一致しません。",
                                            code="table_plan_mismatch", field="bindings.context.consumer_task_id")
            self.table_store.prepare_table_pilot(method_id, request, expected_snapshot=self._initial(db, run["initial_id"]))
            prior_ids = {t["task_id"] for t in self._tasks(db, run_id)}
            task = self._register(db, run, {"role": "statistics", "method_id": method_id,
                "question": "固定表の局所記述", "why_now": "明示的な表pilot要求",
                "success_criteria": "固定入力・構造・保存・現在権限を確認", "table_pilot": request},
                phase="table_pilot", reuse_existing=True)
            if task is None:
                raise _error("表タスクの登録上限に達しています。", "table_task_limit")
            duplicate = task["task_id"] in prior_ids
        if self.schedule and not duplicate:
            self._schedule(run_id)
        return {**copy.deepcopy(task), "registration_duplicate": duplicate}

    def asset_plan_options(self, item_id, run_id, *, offset=0):
        from .analysis_store import asset_plan_options_offset
        offset = asset_plan_options_offset(offset)
        if self.source_fingerprint is None:
            raise _error("現在の元入力を確認できません。", "asset_plan_source_unavailable")
        with self._table_read(item_id) as db:
            run = self._table_run(db, item_id, run_id)
            item = dict(self.find_item(item_id))
            if any(int(item.get(k, 0) or 0) != run.get(v) for k, v in
                   (("revision_count", "source_revision"), ("analysis_revision", "analysis_revision"))):
                raise _error("固定元入力の版が更新されています。", "revision_conflict")
            initial = self._initial(db, run["initial_id"])
        value = self.table_store.asset_plan_options(run=run, initial=initial, offset=offset)
        with self._table_read(item_id) as db:
            current = self._table_run(db, item_id, run_id)
            if current["generation"] != run["generation"] or current.get("asset_plans", []) != run.get("asset_plans", []):
                raise _error("取得中に接続計画が更新されました。", "asset_plan_changed")
        return value

    def _check_web_plan_inputs(self, db, run, plan, *, existing_tasks=None):
        """Normal UI declarations must come from current verified choices."""
        from .analysis_core import connected_web_methods
        initial = self._initial(db, run["initial_id"])
        options = []; offset = 0
        while True:
            page = self.table_store.asset_plan_options(run=run, initial=initial, offset=offset)
            options.extend(page["inputs"])
            options.extend({**o,"compatible_methods":["unit_pool"]} for o in page["unit_pool"]["sources"]
                if not any(c["source"]==o["source"] for c in options))
            for choice in options:
                if choice["source"].get("type")=="frozen" and any(o["source"]==choice["source"] for o in page["unit_pool"]["sources"]):
                    choice["compatible_methods"]=list(dict.fromkeys(choice["compatible_methods"]+["unit_pool"]))
            if page["next_offset"] is None: break
            offset = page["next_offset"]
        methods = {m["method_id"]: m for m in connected_web_methods()}
        steps = {s["step_id"]: s for s in plan["steps"]}
        for step in plan["steps"]:
            method = step["method_id"]; params = step["parameters"]; choices = []
            for ref in step["inputs"]:
                if ref["selection"] == "omitted": continue
                source = ref["source"]
                if source["type"] == "from_step":
                    parent = steps[source["step_id"]]; declaration = methods[parent["method_id"]]
                    if method not in declaration["compatible_methods"]:
                        raise _error("宣言された出力能力と一致しません。", "asset_plan_capability")
                    saved_choice = None
                    if existing_tasks:
                        task_id = existing_tasks[source["step_id"]]
                        row = db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=? AND run_id=?", (task_id, run["run_id"])).fetchone()
                        task = json.loads(row[0]) if row else {}
                        if task.get("table_store_run_id"):
                            saved_choice = next((o for o in options if o["source"].get("asset_key", {}).get("store_run_id") == task["table_store_run_id"]), None)
                            if saved_choice is None or method not in saved_choice["compatible_methods"]:
                                raise _error("保存済みproducerの現在権限を確認できません。", "asset_plan_input_unavailable")
                    choices.append(saved_choice or {"fields": declaration["output_fields"], "unit_ids": [], "theme_ids": [], "relation_ids": [],
                        "semantic_targets": [], "variables": [], "scope": parent["scope"], "future": True,
                        "unit": parent["parameters"].get("unit") if parent["method_id"] == "unit_aggregate" else
                                declaration["output_units"][0] if len(declaration["output_units"]) == 1 else None})
                else:
                    choice = next((o for o in options if o["source"] == source), None)
                    if choice is None or method not in choice["compatible_methods"]:
                        raise _error("現在利用できる保存済み入力ではありません。", "asset_plan_input_unavailable")
                    choices.append(choice)
            if not choices: raise _error("固定入力を選択してください。", "asset_plan_input_unavailable")
            scope = step["scope"]
            if method != "unit_pool" and not any(all(c["scope"].get(k) == scope[k] for k in scope) for c in choices):
                raise _error("保存済み範囲と一致しません。", "asset_plan_scope")
            first = choices[0]
            def require(value, reason="asset_plan_parameter_choice"):
                if not value: raise _error("保存済み選択肢または宣言された能力と一致しません。", reason)
            if method == "unit_pool":
                require(all(set(params["columns"])<=set(c["fields"]) for c in choices))
            elif method == "theme_evidence_table": require(params["theme_id"] in first["theme_ids"])
            elif method == "unit_projection":
                require(not first.get("future"), "require_saved_output")
                require({"unit_id", "conversation_id", "value_status"} <= set(params["columns"]) <= set(first["fields"])
                    and set(params["unit_ids"]) <= set(first["unit_ids"]))
            elif method == "unit_aggregate":
                require(first["unit"] == "utterance")
                require(params["value_column"] in first["fields"] and params["value_column"] not in {"unit_id", "conversation_id", "speaker_id", "value_status"})
                variable = next((v for v in first["variables"] if v["variable_id"] == params["value_column"]), None)
                if params["operation"] != "count":
                    require((variable is not None and variable["value_type"] in {"number", "integer"} and variable["scale"] in {"interval", "ratio"})
                        or (first.get("future") and params["value_column"] in {"support_count", "counter_count"}))
                if params["unit"] == "participant": require(params["participant_mapping"] == first.get("confirmed_participant_mapping")
                    and params["participant_mapping"] is not None, "connected_participant_record")
            elif method == "unit_join": require(all(set(params["keys"]) <= set(c["fields"]) for c in choices))
            elif method == "unit_correlation":
                require(not first.get("future"), "require_saved_output")
                variables = {v["variable_id"]: v for v in first["variables"]}
                require(all(params[k] in variables and variables[params[k]]["value_type"] in {"number", "integer"}
                    and variables[params[k]]["scale"] in ({"interval", "ratio"} if params["statistic"] == "pearson" else {"ordinal", "interval", "ratio"})
                    for k in ("x_column", "y_column")))
            elif method == "qualitative_reuse":
                basis = [c for c, ref in zip(choices, [r for r in step["inputs"] if r["selection"] == "selected"]) if ref["role"] == "selection_basis"]
                require(bool(basis) and not any(c.get("future") for c in basis), "require_saved_output")
                require(set(params["relation_ids"]) <= {r for c in basis for r in c["relation_ids"]})
            elif method == "qualitative_compare":
                allowed = []
                for choice, ref in zip(choices, [r for r in step["inputs"] if r["selection"] == "selected"]):
                    allowed.extend({**t, "input_ref_id": ref["input_ref_id"]} for t in choice["semantic_targets"])
                for proposal in params["proposals"]:
                    require(isinstance(proposal, dict) and set(proposal) == {"relation_id", "left", "right", "relation", "reason", "actor"})
                    require(fingerprint(proposal["left"]) in {fingerprint(t) for t in allowed}
                        and fingerprint(proposal["right"]) in {fingerprint(t) for t in allowed}, "require_saved_output")
                    actor = proposal["actor"]
                    require(isinstance(actor, dict) and set(actor) == {"kind", "actor_id", "step_ids"}
                        and actor["kind"] in {"code", "ai", "researcher", "system"} and isinstance(actor["actor_id"], str) and actor["actor_id"].strip()
                        and isinstance(actor["step_ids"], list) and all(isinstance(s, str) and s.strip() for s in actor["step_ids"]))

    def register_asset_plan(self,item_id,run_id,value):
        from .analysis_core import validate_asset_plan,validate_connected_request,web_asset_plan_template
        from .analysis_method_registry import connected_slot
        group_scope=None
        if isinstance(value,dict) and value.get("version")=="unit-pool-request-1":
            with self._table_read(item_id) as db:
                run=self._table_run(db,item_id,run_id)
                initial=self._initial(db,run["initial_id"])
            value,group_scope=self.table_store.pool_plan(value,run,initial)
        plan,ordered=validate_asset_plan(value); plan_hash=fingerprint(plan)
        with self._db() as db:
            run=self._read_run(db,run_id,item_id)
            web_bound = plan["plan_id"].startswith("web-assets:")
            if web_bound:
                if self.source_fingerprint is None:
                    raise _error("現在の元入力を確認できません。", "asset_plan_source_unavailable")
                self._check_version(run)
                item_row = self.find_item(item_id)
                if item_row is None: raise LookupError("会話が見つかりません。")
                from pathlib import Path
                authority = db.execute("PRAGMA database_list").fetchone()[2]
                if self.table_store is None or not authority or Path(authority).resolve() != self.table_store.database_file:
                    raise _error("HandlerとStoreのlibraryが異なります。", "table_store_mismatch")
                if run.get("cancel_requested") or run["status"] not in {"queued", "running", "completed"}:
                    raise _error("停止したrunへ発注できません。", "table_run_stopped")
                if run.get("stale") or self.source_fingerprint(item_row) != run["input_hash"]:
                    raise _error("固定入力の版が更新されています。", "revision_conflict")
                if plan["plan_id"] != web_asset_plan_template(run)["plan_id"]:
                    raise _error("接続計画の世代が変わりました。", "asset_plan_changed")
                item = dict(item_row)
                if any(int(item.get(k, 0) or 0) != run.get(v) for k, v in
                       (("revision_count", "source_revision"), ("analysis_revision", "analysis_revision"))):
                    raise _error("固定元入力の版が更新されています。", "revision_conflict")
            previous=next((p for p in run.get("asset_plans",[]) if p["plan_id"]==plan["plan_id"] and p["plan_version"]==plan["plan_version"]),None)
            if previous:
                if previous["plan_hash"] != plan_hash:raise _error("同じ計画版を変更できません。","asset_plan_conflict")
                if web_bound:
                    self._check_web_plan_inputs(db, run, plan, existing_tasks=previous["tasks"])
                return {"identity":previous["identity"],"tasks":previous["tasks"],"duplicate":True,
                    **({"scope":group_scope} if group_scope is not None else {})}
            run=self._table_run(db,item_id,run_id)
            if web_bound: self._check_web_plan_inputs(db, run, plan)
            versions=[p["plan_version"] for p in run.get("asset_plans",[]) if p["plan_id"]==plan["plan_id"]]
            if plan["plan_version"] != (max(versions)+1 if versions else 1):raise _error("計画版は連続です。","asset_plan_revision")
            if len(self._tasks(db,run_id))+len(ordered)>run["config"]["max_tasks"]:raise _error("計画全体がtask予算を超えます。","asset_plan_budget")
            identity={"plan_id":plan["plan_id"],"plan_version":plan["plan_version"],"plan_hash":plan_hash,"generation":run["generation"]}
            run["asset_plan_identity"]=identity
            tasks={};steps={s["step_id"]:s for s in plan["steps"]}
            for sid in ordered:
                step=steps[sid];method=step["method_id"]
                context={**identity,"consumer_task_id":"asset-plan-registration:"+run_id, "purpose":"exploratory","destination":"local",
                    "scope_id":step["scope"]["scope_id"],"scope_manifest_hash":step["scope"]["manifest_hash"],"cancelled":False}
                selector={"row_ids":[],"column_ids":[],"range_ref":None};selector["selection_hash"]=fingerprint(selector)
                inputs=[];deps=[]
                for ref in step["inputs"]:
                    if ref["selection"]=="omitted":
                        inputs.append({**{k:context[k] for k in identity},"consumer_task_id":context["consumer_task_id"],"slot_id":"table",**copy.deepcopy(ref)})
                        continue
                    source=copy.deepcopy(ref["source"])
                    if source["type"]=="from_step":
                        parent=tasks[source.pop("step_id")];source["producer_task_id"]=parent;deps.append(parent)
                    inputs.append({**{k:context[k] for k in identity},"consumer_task_id":context["consumer_task_id"],"slot_id":"table",
                        **copy.deepcopy(ref),"source":source,"selector":copy.deepcopy(selector)})
                request={"version":"connected-assets-2","actor":"code","parameters":step["parameters"],
                    "bindings":{"slot":connected_slot(method),"inputs":inputs,"context":context}}
                validate_connected_request(method,request)
                if not deps:self.table_store.prepare_connected(method,request,expected_snapshot=self._initial(db,run["initial_id"]))
                task=self._register(db,run,{"role":"statistics","method_id":method,"question":"固定資産step "+sid,
                    "why_now":"明示的な固定資産計画","success_criteria":"全選択入力の確定・保存・現在権限を検証",
                    "table_pilot":request,"dependencies":sorted(set(deps))},phase="table_pilot",reuse_existing=True)
                if task is None:raise _error("計画を全て登録できません。","asset_plan_budget")
                task.update(asset_plan_identity=identity,asset_step_id=sid,generation=run["generation"])
                self._write_task(db,task);tasks[sid]=task["task_id"]
            run.setdefault("asset_plans",[]).append({**plan,"identity":identity,"plan_hash":plan_hash,"tasks":tasks})
            self._write_run(db,run)
            self._event(db,run_id,"asset_plan_registered","選択した依存とslotを固定しました。",plan_identity=identity,tasks=tasks)
        if self.schedule:self._schedule(run_id)
        return {"identity":identity,"tasks":tasks,"duplicate":False,
            **({"scope":group_scope} if group_scope is not None else {})}

    def _register(self, db, run, intent: dict, *, phase: str, automatic=False, reuse_existing=False) -> dict | None:
        task_origin = self._budget_clock()
        role = intent.get("role")
        if role not in AI_ROLES | {"statistics"}:
            raise _error("未対応の専門家です。", "invalid_intent")
        method = intent.get("method_id") or ("participation" if role == "statistics" else "agent-v1")
        if role == "statistics" and method != "label_frequency" and (intent.get("evidence_ids") or intent.get("scope") or intent.get("label_dependent")):
            raise _error("既存コード計算は初期版の全範囲専用です。部分範囲・ラベル再計算は未対応です。", "method_scope_unavailable")
        if method == "label_frequency" and (role != "statistics" or intent.get("label_field", "codes") not in LABEL_FIELDS):
            raise _error("対応するラベル集計列を指定してください。", "label_field_unavailable")
        if role == "statistics" and method not in METHODS and method not in TABLE_PILOT_METHODS:
            raise _error("未対応のコード計算です。", "method_unavailable")
        initial = self._initial(db, run["initial_id"])
        pilot = method in TABLE_PILOT_METHODS
        if pilot:
            from .analysis_core import validate_table_pilot_request
            if self.table_store is None or role != "statistics" or intent.get("expert_id") or phase != "table_pilot" or automatic:
                raise _error("表pilotは明示的なcode接続専用です。", "table_pilot_disabled")
            request = validate_table_pilot_request(method, intent.get("table_pilot"))
            context = request["bindings"]["context"]
            expected_identity = run.get("asset_plan_identity") if method in CONNECTED_METHODS and context["plan_id"] == run.get("asset_plan_identity",{}).get("plan_id") else {
                "plan_id":run["run_id"],"plan_version":1,"plan_hash":fingerprint({"run_id":run["run_id"],"input_hash":run["input_hash"]}),"generation":run["generation"]}
            if (expected_identity is None or any(context[k] != expected_identity[k] for k in ("plan_id","plan_version","plan_hash","generation"))
                    or context["cancelled"] or any(ref["consumer_task_id"] != context["consumer_task_id"]
                                                   for ref in request["bindings"]["inputs"])):
                raise _error("run・plan・consumer版が一致しません。", "table_plan_mismatch")
            intent = {**intent, "table_pilot": request}
        elif "table_pilot" in intent:
            raise _error("未登録の表計算です。", "table_method_unsupported")
        expert = self._intent_expert(run, intent)
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
        if pilot:
            normalized = copy.deepcopy(request)
            normalized["bindings"]["context"]["consumer_task_id"] = "table-selection:" + run["run_id"]
            for index, ref in enumerate(normalized["bindings"]["inputs"]):
                ref["consumer_task_id"] = normalized["bindings"]["context"]["consumer_task_id"]
                ref["input_ref_id"] = "table-input-" + str(index)
            identity["table_pilot_hash"] = fingerprint(normalized)
        if expert is not None:
            identity["expert_id"], identity["expert_profile_hash"] = expert["expert_id"], expert["profile_hash"]
        key = fingerprint(identity)
        existing = db.execute("SELECT state_json FROM orchestration_tasks WHERE run_id=? AND idempotency_key=?", (run["run_id"], key)).fetchone()
        if existing:
            task = json.loads(existing[0])
            self._event(db, run["run_id"], "duplicate_suppressed", "同じ入力・目的・対象版のタスクを再発注しません。", task_id=task["task_id"])
            return task if reuse_existing else None
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
        if pilot:
            trusted = task["intent"]["table_pilot"]["bindings"]
            trusted["context"]["consumer_task_id"] = task["task_id"]
            for ref in trusted["inputs"]: ref["consumer_task_id"] = task["task_id"]
        if expert is not None:
            task["expert_agent"] = {key: expert[key] for key in ("expert_id", "profile_hash", "knowledge_hash", "contract_version")}
        self._require_budget(run)
        guard = self._run_budgets.get(run["run_id"])
        if guard is not None:
            guard.register(task["task_id"], task_origin)
            task["budget_started_at"] = task_origin
        db.execute("INSERT INTO orchestration_tasks VALUES (?,?,?,?)", (task["task_id"], run["run_id"], key, _json(task)))
        self._event(db, run["run_id"], "task_registered", task["title"], target=role, task_id=task["task_id"])
        return task

    @staticmethod
    def _intent_expert(run, intent):
        expert_id = intent.get("expert_id", "")
        bundle = run.get("expert_agents")
        if expert_id and (bundle is None or intent.get("role") != "interpretation"):
            raise _error("専門家IDは知識を接続した会話解釈タスクへ指定してください。", "expert_selection_invalid")
        if bundle is not None and intent.get("role") == "interpretation":
            from .services.expert_agents import expert_profile
            return expert_profile(bundle, expert_id)
        return None

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
        evidence_limit = run["config"].get("context_evidence_limits_by_role", {}).get(
            task["role"], run["config"]["context_evidence_limit"])
        bounded, size = [], 0
        for evidence in raw:
            if len(bounded) >= evidence_limit or size + len(evidence["text"]) > run["config"]["context_text_limit"]:
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
                if len(provided) >= evidence_limit or size + len(evidence["text"]) > run["config"]["context_text_limit"]:
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
        history_scoped = task["role"] in {"core", "critic"} and task["intent"].get("kind") != "clarification"
        dependency_scoped = task["role"] == "interpretation" and task["intent"].get("kind") != "clarification"
        if dependency_scoped and task.get("expert_agent") and "expert_agents" in run:
            from .services.expert_agents import expert_profile
            profile = expert_profile(run["expert_agents"], task["expert_agent"]["expert_id"])
            # Statistical plans/explanations retain the existing Handler delivery.
            dependency_scoped = "statistical_tools" not in profile
        if dependency_scoped or history_scoped:
            dependencies = task.get("dependencies")
            if (not isinstance(dependencies, list)
                    or any(not isinstance(value, str) or not value.strip() for value in dependencies)):
                raise _error("タスク依存関係の形式が不正です。", "dependency_missing")
            dependencies = set(dependencies)
            source_tasks = {source["task_id"]: source for source in public["tasks"]}
        accepted = []
        unrelated_results = 0
        core_references = False
        # Keep physical identities available when discovering Core authority;
        # mutable result/task role labels cannot demote a committed decision.
        result_rows = ((result, None) for result in public["results"])
        if history_scoped:
            # Discover committed references from the decision's run, not the
            # result's mutable physical membership. Do not read foreign bodies.
            references = db.execute(
                "SELECT r.result_id,r.run_id,r.task_id,t.task_id AS source_task_id,t.run_id AS source_run_id "
                "FROM orchestration_decisions d LEFT JOIN orchestration_results r ON r.result_id=d.result_id "
                "LEFT JOIN orchestration_tasks t ON t.task_id=r.task_id WHERE d.run_id=?",
                (run["run_id"],)).fetchall()
            for reference in references:
                if (reference["result_id"] is None or reference["run_id"] != run["run_id"]
                        or reference["source_task_id"] != reference["task_id"]
                        or reference["source_run_id"] != run["run_id"]):
                    raise _error("採択済みCore判断の保存元が一致しません。", "result_integrity_mismatch")
            result_rows = ((json.loads(row["state_json"]), row) for row in db.execute(
                "SELECT result_id,run_id,task_id,state_json FROM orchestration_results WHERE run_id=? ORDER BY rowid",
                (run["run_id"],)).fetchall())
        for result, saved_row in result_rows:
            if dependency_scoped:
                # Neither metadata nor bodies of unrelated results belong to an
                # independent expert's input. The complete ledger stays saved.
                if result["task_id"] not in dependencies:
                    unrelated_results += 1
                    continue
                source = source_tasks.get(result["task_id"], {})
                if (result["validation_status"] != "valid"
                        or result.get("run_id") != run["run_id"] or result.get("stale")
                        or result.get("dataset_version") != run["input_hash"]
                        or source.get("run_id") != run["run_id"] or source.get("stale")
                        or source.get("dataset_version") != run["input_hash"]
                        or source.get("status") != "succeeded" or source.get("validation_status") != "valid"
                        or source.get("result_id") != result["result_id"]
                        or not isinstance(source.get("attempt_id"), str) or not source["attempt_id"].strip()
                        or source.get("attempt_id") != result.get("attempt_id")):
                    accepted.append({**result, "body_not_delivered": True})
                    continue
            source, decision_row = {}, None
            if history_scoped:
                if any(result.get(key) != saved_row[key] for key in ("result_id", "run_id", "task_id")):
                    raise _error("保存済み結果の参照が一致しません。", "result_integrity_mismatch")
                source_row = db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=? AND run_id=?",
                                        (saved_row["task_id"], run["run_id"])).fetchone()
                source = json.loads(source_row[0]) if source_row else {}
                decision_row = db.execute("SELECT * FROM orchestration_decisions WHERE result_id=?",
                                          (saved_row["result_id"],)).fetchone()
            core_history = history_scoped and (result.get("role") == "core" or source.get("role") == "core"
                                               or decision_row is not None)
            if core_history:
                if (result.get("role") != "core" or result["validation_status"] != "valid" or result.get("stale")
                        or result.get("run_id") != run["run_id"] or result.get("dataset_version") != run["input_hash"]
                        or source.get("task_id") != result["task_id"] or source.get("run_id") != run["run_id"]
                        or source.get("role") != "core" or source.get("dataset_version") != run["input_hash"]
                        or source.get("stale") or source.get("status") != "succeeded"
                        or source.get("validation_status") != "valid" or source.get("result_id") != result["result_id"]
                        or canonical(source.get("annotation_version")) != canonical(result.get("annotation_version"))
                        or not isinstance(source.get("attempt_id"), str) or not source["attempt_id"].strip()
                        or source["attempt_id"] != result.get("attempt_id")):
                    raise _error("Core履歴の入力版・実行来歴が一致しません。", "result_integrity_mismatch")
            if result["validation_status"] == "valid":
                if dependency_scoped or core_history:
                    row = db.execute("SELECT raw_json FROM orchestration_results WHERE result_id=? AND run_id=? AND task_id=?",
                                     (result["result_id"], run["run_id"], result["task_id"])).fetchone()
                    if row is None:
                        raise _error("保存済み結果の参照が一致しません。", "result_integrity_mismatch")
                else:
                    row = db.execute("SELECT raw_json FROM orchestration_results WHERE result_id=?", (result["result_id"],)).fetchone()
                content = json.loads(row[0])
                if fingerprint(content) != result["raw_hash"]:
                    raise _error("保存済み結果のhashが一致しません。", "result_integrity_mismatch")
                if core_history:
                    if decision_row is not None:
                        decision = json.loads(decision_row["payload_json"])
                        # _apply_core saves the raw response plus these Handler
                        # fields. Verify both before replacing even a large body.
                        if not isinstance(decision, dict):
                            raise _error("採択済みCore判断が不正です。", "result_integrity_mismatch")
                        generated = ("created_at", "after_annotation_version", "view_version")
                        expected = {**content, **{key: decision.get(key) for key in generated},
                            "decision_id": decision_row["decision_id"], "result_id": result["result_id"],
                            "iteration": source["iteration"], "task_id": source["task_id"],
                            "annotation_version": source["annotation_version"], "role": "core",
                            "before_annotation_version": source["annotation_version"],
                            "model": source.get("model"), "provider": source.get("provider")}
                        if (decision_row["run_id"] != run["run_id"]
                                or not isinstance(decision.get("decision_id"), str) or not decision["decision_id"].strip()
                                or not isinstance(decision.get("created_at"), str) or not decision["created_at"].strip()
                                or decision.get("before_annotation_version") != source["annotation_version"]
                                or type(decision.get("after_annotation_version")) is not int
                                or not source["annotation_version"] <= decision["after_annotation_version"] <= run["annotation_version"]
                                or type(decision.get("view_version")) is not int
                                or not 0 <= decision["view_version"] <= run["view_version"]
                                or canonical(decision) != canonical(expected)):
                            raise _error("採択済みCore判断と保存原結果が一致しません。", "result_integrity_mismatch")
                        if result["task_id"] not in dependencies:
                            accepted.append({"result_id": result["result_id"], "raw_hash": result["raw_hash"],
                                             "body_not_delivered": True})
                            core_references = True
                            continue
                if len(row[0]) > 16000:
                    content = {"summary": content.get("summary", ""), "claims": content.get("claims", [])[:24], "omitted_full_result": True}
                accepted.append({**result, "content": content})
        if history_scoped:
            accepted = [result for index, result in enumerate(accepted)
                        if index >= len(accepted) - 20 or result.get("task_id") in dependencies]
        elif not dependency_scoped:
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
        if core_references:
            context["result_delivery"] = {"core_history": "verified_committed_decision_references",
                "reference_fields": ["result_id", "raw_hash", "body_not_delivered"],
                "full_results_preserved": True, "reference_is_body_read": False}
        elif dependency_scoped:
            context["result_delivery"] = {"scope": "explicit_dependencies_only",
                "unrelated_results_not_delivered": unrelated_results,
                "unrelated_result_metadata": "not_delivered", "full_results_preserved": True,
                "omission_is_body_read": False}
        if history_scoped and sum("content" in row and row.get("role") != "core"
                                  and row.get("task_id") not in dependencies for row in accepted) >= 2:
            # Bind the adapter's reversible metadata projection to this exact
            # validated delivery and order. Never rewrite the saved/full rows.
            context["_result_metadata_hash"] = fingerprint(accepted)
        gate = self._statistical_review_gate(db, run)
        if gate:
            context["statistical_review_gate"] = gate
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
        if run["config"].get("obsidian_management", False):
            context["management"] = {"role": "obsidian_manager", "kind": "code", "enabled": True,
                "status": run.get("obsidian_management", {}).get("status", "not_started"),
                "note_id": run.get("obsidian_management", {}).get("note_id", ""),
                "authority": "Handler forwards committed records; manager links data without executing analysis"}
        if "expert_agents" in run:
            from .services.expert_agents import catalog_packet, expert_profile, request_packet
            if task["role"] == "core":
                context["expert_catalog"] = catalog_packet(run["expert_agents"])
            elif task.get("expert_agent"):
                profile = expert_profile(run["expert_agents"], task["expert_agent"]["expert_id"])
                self._validate_expert_receipt(task, profile)
                if "statistical_tools" in profile:
                    from .services.analysis_orchestration_methods import calculation_packet
                    calculations = {}
                    for metadata in public["results"]:
                        if (metadata["role"] != "statistics" or metadata["validation_status"] != "valid"
                                or metadata.get("stale") or metadata["dataset_version"] != run["input_hash"]):
                            continue
                        source_task = next(value for value in public["tasks"] if value["task_id"] == metadata["task_id"])
                        if (source_task["method_id"] not in profile["statistical_tools"]
                                or source_task["status"] != "succeeded"
                                or (task["dependencies"] and source_task["task_id"] not in task["dependencies"])):
                            continue
                        row = db.execute("SELECT raw_json FROM orchestration_results WHERE result_id=? AND run_id=?",
                                         (metadata["result_id"], run["run_id"])).fetchone()
                        content = self._statistical_source(db, run, source_task, metadata, json.loads(row[0]), initial)
                        calculations[source_task["method_id"]] = (content, metadata)
                    allowance = 10000 // max(1, len(calculations))
                    context["statistical_calculations"] = [calculation_packet(content, metadata, max_chars=allowance)
                                                          for content, metadata in calculations.values()]
                typed_source = self._thematic_source(db, run, profile, initial)
                context["expert_request"] = request_packet(profile, context, initial["analysis"],
                    **({"thematic_source": typed_source} if typed_source is not None else {}))
                if run["config"].get("expert_hooks", False):
                    from .services.expert_data_hooks import prepare_context
                    context = prepare_context(context, evidence_limit=run["config"]["context_evidence_limit"],
                                              text_limit=run["config"]["context_text_limit"])
                if profile.get("typed_contract") == "focus_group_interaction_candidates_v1":
                    from .services.expert_agents import focus_group_interaction_delivery
                    context["expert_request"]["delivery_coverage"] = focus_group_interaction_delivery(typed_source, context)
        return copy.deepcopy(context)

    def _check(self, run_id, generation, task_id=None):
        stopped = None
        with self._db() as db:
            run = self._read_run(db, run_id)
            limit = "source_deleted" if self.find_item(run["item_id"]) is None else self._limit(db, run)
            if not limit and task_id:
                limit = self._budget_reason(run, task_id)
                row = db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (task_id,)).fetchone()
                task = json.loads(row[0])
                if task.get("asset_plan_identity") and (canonical(task["asset_plan_identity"]) != canonical(run.get("asset_plan_identity"))
                        or task["asset_plan_identity"]["generation"]!=run["generation"] or task.get("generation")!=run["generation"]):
                    raise ExecutionStopped("asset_plan_changed")
                if task.get("stale"):raise ExecutionStopped("asset_lineage_stale")
                if not limit and task.get("started_epoch") and time.time() - task["started_epoch"] > run["config"]["call_timeout_seconds"]:
                    limit = "call_timeout"
            if limit and run["status"] not in TERMINAL:
                self._stop(db, run, limit)
            if limit or run["status"] in TERMINAL or run["generation"] != generation:
                stopped = run["stop_reason"] or "stopped"
                if "request_budget" not in run and run_id not in self._run_budgets:
                    raise ExecutionStopped(stopped)  # Preserve the legacy path.
        # Raising inside _db would roll back the stop just recorded above.
        if stopped:
            raise ExecutionStopped(stopped)

    def _expert_data_hook(self, run_id, original_task, action, payload):
        """Serve reads for an active expert; never create another analysis task."""
        from .services.expert_data_hooks import read_data, MAX_ROUNDS, VERSION, fail
        task_id = original_task["task_id"]
        self._check(run_id, original_task["generation"], task_id)
        with self._db() as db:
            run = self._read_run(db, run_id)
            row = db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=? AND run_id=?", (task_id, run_id)).fetchone()
            task = json.loads(row[0]) if row else {}
            if (not task.get("expert_agent") or task.get("status") != "running"
                    or task.get("attempt_id") != original_task["attempt_id"]
                    or task.get("generation") != original_task["generation"]
                    or not run["config"].get("expert_hooks", False)
                    or run["config"].get("expert_hook_version") != VERSION):
                fail("expert_hook_inactive")
            self._validate_initial_source(run)
            if action == "response":
                history = task.setdefault("expert_hook_responses", [])
                if len(history) >= MAX_ROUNDS + 1 or len(_json(payload).encode("utf-8")) > 32000:
                    fail("expert_hook_round_limit")
                history.append({"response": copy.deepcopy(payload), "response_hash": fingerprint(payload)})
                self._write_task(db, task)
                return None
            if action == "continue":
                if task.get("model_calls", 1) >= MAX_ROUNDS + 1:
                    fail("expert_hook_round_limit")
                retrieved = set(task["expert_evidence_ids"])
                for read in task.get("expert_hook_reads", []):
                    retrieved.update(read.get("provided_evidence_ids", []))
                packets = []
                if isinstance(payload, dict):
                    if set(payload) != {"evidence_ids", "calculation_packets"} or not isinstance(payload["calculation_packets"], list):
                        fail("expert_hook_delivery_mismatch")
                    packets, payload = payload["calculation_packets"], payload["evidence_ids"]
                if not isinstance(payload, list) or any(not isinstance(eid, str) or eid not in retrieved for eid in payload):
                    fail("expert_hook_scope_mismatch")
                deliveries = []
                for packet in packets:
                    packet_hash = fingerprint(packet)
                    read = next((read for read in task.get("expert_hook_reads", [])
                                 if read["packet_hash"] == packet_hash and "provided_rows" in read), None)
                    if (read is None or any(read.get(key) != task[key] for key in ("run_id", "task_id", "attempt_id", "generation"))
                            or read.get("version") != VERSION or read.get("data_version") != run["input_hash"]
                            or packet.get("version") != VERSION or packet.get("data_version") != run["input_hash"]):
                        fail("expert_hook_delivery_mismatch")
                    ref = next((ref for ref in task.get("expert_calculation_refs", []) if ref["result_id"] == packet.get("result_id")), None)
                    if (ref is None or ref.get("delivery_version") != VERSION
                            or ref["raw_hash"] != packet.get("source_hash")):
                        fail("expert_hook_delivery_mismatch")
                    deliveries.append({"packet_hash": packet_hash, "result_id": packet["result_id"],
                                       "table_id": packet["table_id"], "provided_rows": copy.deepcopy(read["provided_rows"])})
                queued_calls = sum(t["kind"] == "ai" and t["status"] == "queued" for t in self._tasks(db, run_id))
                if run["calls_started"] + queued_calls >= run["config"]["max_calls"]:
                    self._stop(db, run, "call_budget_limit")
                    return {"stopped": True}
                run["calls_started"] += 1
                task["expert_evidence_ids"] = sorted(set(task["expert_evidence_ids"]) | set(payload))
                task["model_calls"] = task.get("model_calls", 1) + 1
                if deliveries:
                    task.setdefault("expert_hook_deliveries", []).append({"version": VERSION,
                        **{key: task[key] for key in ("run_id", "task_id", "attempt_id", "generation")},
                        "model_call": task["model_calls"], "packets": deliveries})
                    for delivery in deliveries:
                        ref = next(ref for ref in task["expert_calculation_refs"] if ref["result_id"] == delivery["result_id"])
                        for name, ids in delivery["provided_rows"].items():
                            ref["provided_rows"][name] = sorted(set(ref["provided_rows"][name]) | set(ids))
                self._write_run(db, run)
                self._write_task(db, task)
                self._event(db, run_id, "expert_hook_continue", "追加取得したデータで専門家の応答を継続します。", target=task["role"], task_id=task_id)
                return None
            if action != "read":
                fail()
            initial = self._initial(db, run["initial_id"])
            selected = task["intent"].get("evidence_ids", [])
            allowed = selected or [e["evidence_id"] for e in initial["evidence"] if not e["excluded"]]
            calculations = {}
            for ref in task.get("expert_calculation_refs", []):
                saved = db.execute("SELECT raw_json,state_json FROM orchestration_results WHERE result_id=? AND run_id=?", (ref["result_id"], run_id)).fetchone()
                metadata = json.loads(saved["state_json"]) if saved else {}
                if (metadata.get("task_id") != ref["task_id"] or metadata.get("raw_hash") != ref["raw_hash"]
                        or metadata.get("dataset_version") != run["input_hash"] or metadata.get("stale")
                        or metadata.get("validation_status") != "valid"
                        or fingerprint(json.loads(saved["raw_json"])) != ref["raw_hash"]):
                    fail("statistics_result_mismatch")
                source = db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=? AND run_id=?", (ref["task_id"], run_id)).fetchone()
                if source is None:
                    fail("statistics_result_mismatch")
                content = self._statistical_source(db, run, json.loads(source[0]), metadata, json.loads(saved["raw_json"]), initial)
                calculations[ref["result_id"]] = (content, metadata)
            packet = read_data(payload, evidence=initial["evidence"], calculations=calculations,
                               allowed_evidence_ids=allowed, data_version=run["input_hash"],
                               max_chars=run["config"]["context_text_limit"], evidence_limit=min(8, run["config"]["context_evidence_limit"]))
            receipt = {"version": VERSION, "request": copy.deepcopy(payload), "request_hash": fingerprint(payload),
                       "packet_hash": fingerprint(packet), "source_hash": packet["source_hash"],
                       "data_version": run["input_hash"], "created_at": _now(),
                       **{key: task[key] for key in ("run_id", "task_id", "attempt_id", "generation")}}
            if packet["hook"] == "read_evidence":
                receipt["provided_evidence_ids"] = [row["evidence_id"] for row in packet["evidence"]]
            else:
                receipt.update(result_id=packet["result_id"], table_id=packet["table_id"],
                               provided_rows={packet["table_id"]: [row["row_id"] for row in packet["rows"]]})
            task.setdefault("expert_hook_reads", []).append(receipt)
            self._write_task(db, task)
            self._event(db, run_id, "expert_hook_data", "専門家へ指示範囲内の保存済みデータを渡しました。", source="handler", target=task["role"], task_id=task_id,
                        hook=packet["hook"], request_hash=receipt["request_hash"], packet_hash=receipt["packet_hash"],
                        source_hash=receipt["source_hash"])
            return packet

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
            if task.get("asset_plan_identity"):
                if (task["asset_plan_identity"]!=run.get("asset_plan_identity") or task["asset_plan_identity"]["generation"]!=run["generation"]
                        or task.get("generation")!=run["generation"] or task.get("stale")):
                    task.update(status="blocked",error="asset_plan_changed");self._write_task(db,task);return
                parents={t["task_id"]:t for t in self._tasks(db,run_id)}
                if any(parents[d].get("stale") or parents[d]["status"] in {"failed","quarantined","cancelled","blocked"} for d in task["dependencies"]):
                    task.update(status="blocked",error="dependency_failed");self._write_task(db,task);return
                if any(parents[d]["status"]!="succeeded" for d in task["dependencies"]):return
                if not self._asset_dependencies_delivered(task):return
            self._check_version(run)
            limit = self._limit(db, run) or self._budget_reason(run, task_id)
            if limit:
                self._stop(db, run, limit)
                return
            try:
                context = self._context(db, run, task)
                self._require_budget(run, task_id)
            except AnalysisContractError as exc:
                task.update(status="failed", ended_at=_now(), error=exc.code)
                self._write_task(db, task)
                self._event(db, run_id, "task_input_rejected", exc.code, task_id=task_id)
                self._stop(db, run, self._budget_reason(run, task_id) or "human_review_required")
                return
            task.update(status="running", started_at=_now(), started_epoch=time.time(), generation=run["generation"])
            if task.get("expert_agent"):
                task["expert_evidence_ids"] = [row["evidence_id"] for row in context["raw_evidence"]]
                if "delivery_coverage" in context["expert_request"]:
                    task["expert_fgi_delivery"] = copy.deepcopy(context["expert_request"]["delivery_coverage"])
                if "calculations" in context["expert_request"]:
                    task["expert_calculation_refs"] = [{key: row[key] for key in ("result_id", "task_id", "raw_hash")}
                                                       for row in context["expert_request"]["calculations"]]
                    task["expert_response_phase"] = context["expert_request"]["response_phase"]
                    for ref, calc in zip(task["expert_calculation_refs"], context["expert_request"]["calculations"]):
                        ref["provided_rows"] = {name: [row["row_id"] for row in table["rows"]]
                                                for name, table in calc["datasets"].items()}
                        if run["config"].get("expert_hooks", False):
                            from .services.expert_data_hooks import VERSION
                            ref["delivery_version"] = VERSION
                            ref["initial_provided_rows"] = copy.deepcopy(ref["provided_rows"])
                self._event(db, run_id, "expert_knowledge_loaded", "専門知識と入出力契約を固定版から渡しました。",
                            target=task["role"], task_id=task_id, **task["expert_agent"])
            run["calls_started" if task["kind"] == "ai" else "code_executions"] += 1
            self._write_task(db, task)
            self._write_run(db, run)
            self._event(db, run_id, "task_started", task["title"], target=task["role"], task_id=task_id)
            snapshot = self._initial(db, run["initial_id"]) if task["kind"] == "code" else None
            if snapshot is not None:
                snapshot["orchestration_task"] = copy.deepcopy(task)
                snapshot["orchestration_labels"] = json.loads(db.execute("SELECT payload_json FROM orchestration_label_versions WHERE run_id=? AND annotation_version=?",
                    (run_id, task["annotation_version"])).fetchone()[0])
        check = lambda: self._check(run_id, task["generation"], task_id)
        self._notify_management(run_id)
        try:
            check()
            if task["kind"] == "code":
                if task["method_id"] in TABLE_PILOT_METHODS:
                    from .services.analysis_orchestration_adapters import resolve_table_pilot
                    snapshot["table_pilot"] = resolve_table_pilot(self.table_store, task["method_id"],
                                                               task["intent"]["table_pilot"], snapshot)
                    check()
                    with self._db() as db:
                        current = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?",
                                                        (task_id,)).fetchone()[0])
                        current["table_pilot_prepared"] = copy.deepcopy(snapshot["table_pilot"])
                        self._require_budget(self._read_run(db, run_id), task_id)
                        self._write_task(db, current)
                raw = self.method_runner(task["method_id"], snapshot)
            else:
                options = {**copy.deepcopy(run["config"]), **run["config"]["roles"][task["role"]], "timeout_seconds": run["config"]["call_timeout_seconds"],
                           "deadline": run["deadline"], "research_mode": "exploratory", "provider_policy": run["config"]["provider_policy"]}
                guard = self._run_budgets.get(run_id)
                if guard is not None:
                    options.update(_request_budget=guard.request_budget, _budget_attempt_id=task["attempt_id"])
                if task.get("expert_agent") and run["config"].get("expert_hooks", False):
                    options["_expert_data_hook"] = lambda action, payload: self._expert_data_hook(run_id, task, action, payload)
                raw = self.agent_runner(task["role"], context, options, check,
                                        lambda usage=None, **kw: self._record_usage(run_id, task_id, usage, **kw))
            # Raw response commits before semantic validation, including a late response.
            raw_json = _json(raw)
            with self._db() as db:
                latest = self._read_run(db, run_id)
                if self.find_item(latest["item_id"]) is None and latest["status"] not in TERMINAL:
                    self._stop(db, latest, "source_deleted")
                limit = self._limit(db, latest) or self._budget_reason(latest, task_id)
                if not limit and time.time() - task["started_epoch"] > latest["config"]["call_timeout_seconds"]:
                    limit = "call_timeout"
                if limit and latest["status"] not in TERMINAL:
                    self._stop(db, latest, limit)
                if run_id in self._run_budgets:
                    self._write_run(db, latest)
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
                if run_id in self._run_budgets:
                    self._write_run(db, self._read_run(db, run_id))
        except Exception as exc:
            with self._db() as db:
                current = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (task_id,)).fetchone()[0])
                # Transport errors may have consumed external work. Never retry blind.
                current.update(status="uncertain" if task["kind"] == "ai" else "failed", ended_at=_now(), error=getattr(exc, "code", type(exc).__name__))
                self._write_task(db, current)
                latest = self._read_run(db, run_id)
                if latest["status"] not in TERMINAL and task["kind"] == "ai":
                    latest.update(status="recovery_required", error="外部呼出しの実行結果が不明です。自動再試行しません。")
                    self._write_run(db, latest)
                elif run_id in self._run_budgets:
                    self._write_run(db, latest)
                self._event(db, run_id, "execution_uncertain" if task["kind"] == "ai" else "task_failed", type(exc).__name__, task_id=task_id)

    def _validate_received(self, run_id, task_id):
        with self._db() as db:
            probe = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (task_id,)).fetchone()[0])
        if probe["method_id"] in TABLE_PILOT_METHODS:
            # Execution workers and the drain loop can observe the same received
            # table concurrently; only one may save/promote it outside the DB tx.
            with self._table_validation_lock:
                return self._validate_table_received(run_id, task_id)
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
                    valid_state = "blocked" if meta.get("statistical_review", {}).get("ai_complete") is False else "succeeded"
                    task.update(status=valid_state if meta["validation_status"] == "valid" else "quarantined",
                                validation_status=meta["validation_status"], result_id=meta["result_id"])
                    self._write_task(db, task)
                return
            guarded = "request_budget" in run or run_id in self._run_budgets
            try:
                if guarded:
                    db.execute("SAVEPOINT guarded_validation")
                self._require_budget(run, task_id)
                if len(row["raw_json"].encode("utf-8")) > run["config"]["max_result_bytes"]:
                    raise _error("結果が保存上限を超えています。", "result_size_limit")
                if run["status"] in TERMINAL:
                    raise _error("停止後の結果は採用しません。", "late_response_after_stop")
                statistical_review = self._validate_result(db, run, task, raw)
                self._require_budget(run, task_id)
                meta.update(validation_status="valid", error="")
                task.update(status="succeeded", validation_status="valid", error="")
                if task["role"] == "statistics" and task["method_id"] in STATISTICAL_TOOLS:
                    meta["calculation_status"] = raw["status"]
                if statistical_review is not None:
                    meta["statistical_review"] = statistical_review
                    task["statistical_review_status"] = statistical_review["status"]
                    if not statistical_review["ai_complete"]:
                        task.update(status="blocked", error=statistical_review["ai_status"])
                if task["role"] == "critic":
                    self._save_issues(db, run, task, raw, meta)
                for patch in raw.get("label_patches", []):
                    self._save_patch(db, run, task, patch, meta)
                self._require_budget(run, task_id)
                self._event(db, run_id, "result_validated", "保存済み・内容未検証としてCoreへ渡します。", source="handler", target="core", task_id=task_id)
            except (AnalysisContractError, ValueError, TypeError, KeyError) as exc:
                if guarded:
                    db.execute("ROLLBACK TO guarded_validation")
                code = getattr(exc, "code", "invalid_result")
                meta.update(validation_status="quarantined", error=code)
                task.update(status="quarantined", validation_status="quarantined", error=code)
                self._event(db, run_id, "result_quarantined", code, task_id=task_id)
            finally:
                if guarded:
                    db.execute("RELEASE guarded_validation")
            db.execute("UPDATE orchestration_results SET state_json=? WHERE result_id=?", (_json(meta), meta["result_id"]))
            self._write_task(db, task)

    def _table_current_permission(self, task, snapshot=None):
        try:
            if self.table_store is None: raise ValueError("table_pilot_disabled")
            self.table_store.revalidate_table_pilot(task["table_pilot_prepared"], expected_snapshot=snapshot)
            if task.get("table_store_run_id"):
                self.table_store.read_table(task["table_store_run_id"], "table")
            return {"decision": "eligible", "execution_enabled": False, "adoption_performed": False}
        except (AnalysisContractError, ValueError, TypeError, KeyError, OSError) as exc:
            return {"decision": "blocked", "reason": getattr(exc, "code", "table_revalidation_failed"),
                    "execution_enabled": False, "adoption_performed": False}

    def _validate_table_received(self, run_id, task_id):
        """Store outside Handler's write transaction, then fence final promotion."""
        from .services.analysis_orchestration_methods import validate_table_pilot_result
        try:
            with self._db() as db:
                run = self._read_run(db, run_id)
                task = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (task_id,)).fetchone()[0])
                row = db.execute("SELECT * FROM orchestration_results WHERE task_id=?", (task_id,)).fetchone()
                meta, raw = json.loads(row["state_json"]), json.loads(row["raw_json"])
                if meta["validation_status"] != "received": return
                if (fingerprint(raw) != meta["raw_hash"] or meta["task_id"] != task_id or meta["run_id"] != run_id
                        or meta["attempt_id"] != task["attempt_id"] or meta["result_id"] != row["result_id"]):
                    raise _error("原結果hashが異なります。", "result_integrity_mismatch")
                self._require_budget(run, task_id)
                self._check_version(run)
                if run["status"] in TERMINAL or run["cancel_requested"] or task["generation"] != run["generation"]:
                    raise _error("停止後の結果です。", "late_response_after_stop")
                if len(row["raw_json"].encode("utf8")) > run["config"]["max_result_bytes"]:
                    raise _error("結果上限を超えました。", "result_size_limit")
                initial = self._initial(db, run["initial_id"])
                prepared = task["table_pilot_prepared"]
                validate_table_pilot_result(raw, task, prepared)
                self.table_store.revalidate_table_pilot(prepared, expected_snapshot=initial)
            def fence(connection):
                # Store and Handler must share this SQLite authority. No nested writer.
                current = self._read_run(connection, run_id)
                if (current["status"] in TERMINAL or current["cancel_requested"]
                        or current["generation"] != task["generation"]
                        or (task.get("asset_plan_identity") and (task["asset_plan_identity"]!=current.get("asset_plan_identity")
                            or task["asset_plan_identity"]["generation"]!=current["generation"]))):
                    raise _error("保存前に停止されました。", "table_cancelled")
                self._require_budget(current, task_id)
                self._check_version(current)
                self.table_store.revalidate_table_pilot(prepared, expected_snapshot=initial)
            check = lambda: self._check(run_id, task["generation"], task_id)
            check()
            carrier, provenance = self.table_store.table_pilot_carrier(raw, prepared)
            from .analysis_core import TABLE_PILOT_MAX_BYTES
            if len(canonical({"carrier": carrier, "provenance": provenance})) > TABLE_PILOT_MAX_BYTES:
                raise _error("保存payloadのUTF8上限を超えました。", "table_carrier_byte_limit")
            # Use the Handler's existing writer lock throughout Store's commit
            # fence. Fresh permission reads may outlast SQLite's busy timeout;
            # the scheduler must wait outside BEGIN IMMEDIATE in that case.
            with self.lock:
                saved = self.table_store.save(item_id=run["item_id"], kind="ai_insights", snapshot=initial,
                    result={**raw, "parameters": {"table_pilot": prepared["request"], "task_id": task_id, "execution_run_id": run_id,
                                                "adoption_state": "unanswered", "input_content_hash": prepared["content_hash"],
                                                "table_pilot_provenance": provenance}},
                    datasets={"table": (carrier["fields"], carrier["rows"])},
                    request_id="table-pilot:" + task_id, input_fingerprint=prepared["content_hash"],
                    source_revision=run["source_revision"], analysis_revision=run["analysis_revision"],
                    publish=False, check_cancelled=check, commit_guard=fence)
            check()
            reloaded = self.table_store.read_table(saved["id"], "table")
            if fingerprint([r["values"] for r in reloaded["rows"]]) != fingerprint(carrier["rows"]):
                raise _error("再読込結果が異なります。", "table_reload_mismatch")
            self.table_store.revalidate_table_pilot(prepared, expected_snapshot=initial)
            with self._db() as db:
                fence(db)
                current = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (task_id,)).fetchone()[0])
                if current["status"] != "received": raise _error("採用状態が変わりました。", "table_task_changed")
                meta.update(validation_status="valid", error="", table_store_run_id=saved["id"],
                            permission_at_validation={"decision": "eligible"}, adoption_performed=False,
                            content_status="unreviewed")
                current.update(status="succeeded", validation_status="valid", error="", table_store_run_id=saved["id"],
                               adoption_performed=False)
                self._require_budget(self._read_run(db, run_id), task_id)
                db.execute("UPDATE orchestration_results SET state_json=? WHERE result_id=?", (_json(meta), meta["result_id"]))
                self._write_task(db, current)
                self._event(db, run_id, "table_pilot_validated", "固定表を保存・再読込しました。研究者採否は未回答。", task_id=task_id)
                self._require_budget(self._read_run(db, run_id), task_id)
        except (AnalysisContractError, ValueError, TypeError, KeyError, OSError, ExecutionStopped) as exc:
            code = getattr(exc, "code", "table_validation_failed")
            with self._db() as db:
                current = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (task_id,)).fetchone()[0])
                current.update(status="quarantined", validation_status="quarantined", error=code)
                self._write_task(db, current)
                row = db.execute("SELECT state_json FROM orchestration_results WHERE task_id=?", (task_id,)).fetchone()
                if row:
                    metadata = json.loads(row[0])
                    metadata.update(validation_status="quarantined", error=code, adoption_performed=False)
                    db.execute("UPDATE orchestration_results SET state_json=? WHERE task_id=?", (_json(metadata), task_id))
                self._event(db, run_id, "table_pilot_quarantined", code, task_id=task_id)
        self.reconcile_asset_plan(run_id)

    def _register_asset_output(self,run_id,task_id):
        """Technical code reuse authorized by the fixed plan, never human adoption."""
        with self._db() as db:
            run=self._read_run(db,run_id);task=json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=? AND run_id=?",(task_id,run_id)).fetchone()[0])
            if not task.get("asset_plan_identity") or task["status"]!="succeeded" or not task.get("table_store_run_id"):return None
            if (task.get("stale") or run["cancel_requested"] or run["status"]=="cancelled" or task["generation"]!=run["generation"]
                    or task["asset_plan_identity"]["generation"]!=run["generation"] or task["asset_plan_identity"]!=run.get("asset_plan_identity")):return None
            initial=self._initial(db,run["initial_id"])
        self.table_store.revalidate_table_pilot(task["table_pilot_prepared"],expected_snapshot=initial)
        asset=self.table_store.connected_output_descriptor(task["table_store_run_id"])
        assets,_originals,states,links=self.table_store._connection_index()
        key=fingerprint(asset["asset_key"]).removeprefix("sha256:"); history=states.get(key,{})
        if history:
            state=history[max(history)]
            if state["revoked"] or state["status"]!="adopted":return None
        else:
            state={"asset_key":asset["asset_key"],"target_content_hash":asset["content_hash"],"target_domain":asset["content_domain"],
                "state_revision":1,"policy_revision":1,"status":"adopted","allowed_purposes":["exploratory"],"send_policy":"local_only",
                "destinations":[],"revoked":False,"review_refs":[],"reason":"Explicit fixed plan authorizes structural deterministic reuse; human meaning remains pending",
                "updated_at":(task.get("ended_at") or task["created_at"]).replace("+00:00","Z")}
        link={**task["asset_plan_identity"],"execution_run_id":run_id,"producer_task_id":task_id,"output_name":"tables/table.json","asset_key":asset["asset_key"]}
        def fence(connection):
            current=self._read_run(connection,run_id)
            latest=json.loads(connection.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?",(task_id,)).fetchone()[0])
            if (current["cancel_requested"] or current["status"]=="cancelled" or latest.get("stale") or latest["generation"]!=current["generation"]
                    or task["asset_plan_identity"]["generation"]!=current["generation"] or current.get("asset_plan_identity")!=task["asset_plan_identity"]):
                raise _error("現在の計画・停止状態が変わりました。","asset_output_fence")
            self._check_version(current);self._require_budget(current,task_id)
            self.table_store.revalidate_table_pilot(task["table_pilot_prepared"],expected_snapshot=initial)
        if link not in links:
            with self.lock:
                self.table_store.save_connection_metadata(item_id=run["item_id"],snapshot={"asset_plan_identity":task["asset_plan_identity"],"producer_task_id":task_id},
                    request_id="asset-output:"+task_id,metadata={"version":1,"assets":[asset],"originals":[],"states":[] if history else [state],"producer_links":[link]},commit_guard=fence)
        return asset

    def notify_asset_output(self,item_id,run_id,producer_task_id):
        """Re-delivery has a closed deterministic receipt per selected consumer ref."""
        with self._db() as db:self._read_run(db,run_id,item_id)
        asset=self._register_asset_output(run_id,producer_task_id)
        if asset is None:return {"receipts":[],"duplicate":True}
        created=[];duplicates=[]
        with self._db() as db:
            run=self._read_run(db,run_id,item_id)
            if run["cancel_requested"] or run["status"]=="cancelled":return {"receipts":[],"duplicate":True}
            for child in self._tasks(db,run_id):
                if child.get("asset_plan_identity")!=run.get("asset_plan_identity"):continue
                for ref in child.get("intent",{}).get("table_pilot",{}).get("bindings",{}).get("inputs",[]):
                    source=ref.get("source",{})
                    if source.get("type")!="from_step" or source.get("producer_task_id")!=producer_task_id:continue
                    identity={"version":"asset-notification-1","event":"producer_fixed","hook_version":"1",**child["asset_plan_identity"],
                        "producer_task_id":producer_task_id,"producer_content_hash":asset["content_hash"],"consumer_task_id":child["task_id"],
                        "slot_id":ref["slot_id"],"input_ref_id":ref["input_ref_id"]}
                    rid=fingerprint(identity);receipts=child.setdefault("asset_receipts",{})
                    if rid in receipts:duplicates.append(rid);continue
                    receipts[rid]={"identity":identity,"status":"recorded"};self._write_task(db,child);created.append(rid)
                    self._event(db,run_id,"asset_notification_received","保存済producerの通知を受領しました。",task_id=child["task_id"],receipt_id=rid,identity=identity)
        return {"receipts":created,"duplicates":duplicates,"duplicate":not created}

    @staticmethod
    def _asset_dependencies_delivered(task):
        """Success alone precedes the fixed Store mapping; receipts close that race."""
        if not task.get("asset_plan_identity"):return True
        identity=task["asset_plan_identity"]
        receipts=task.get("asset_receipts",{})
        for ref in task["intent"]["table_pilot"]["bindings"]["inputs"]:
            source=ref.get("source",{})
            if ref["selection"]!="selected" or source.get("type")!="from_step":continue
            if not any(r.get("status")=="recorded" and isinstance(r.get("identity"),dict)
                and set(r["identity"])=={"version","event","hook_version",*identity,"producer_task_id","producer_content_hash","consumer_task_id","slot_id","input_ref_id"}
                and fingerprint(r["identity"])==rid and r["identity"].get("version")=="asset-notification-1"
                and r["identity"].get("event")=="producer_fixed" and r["identity"].get("hook_version")=="1"
                and all(r["identity"].get(k)==v for k,v in identity.items())
                and r["identity"].get("consumer_task_id")==task["task_id"]
                and r["identity"].get("producer_task_id")==source["producer_task_id"]
                and r["identity"].get("slot_id")==ref["slot_id"] and r["identity"].get("input_ref_id")==ref["input_ref_id"]
                for rid,r in receipts.items()):return False
        return True

    def reconcile_asset_plan(self,run_id):
        """Rebuild lost delivery from durable tasks/packages using the same scheduler."""
        assets,_originals,states,_links=self.table_store._connection_index() if self.table_store else ({},{},{},[])
        with self._db() as db:
            run=self._read_run(db,run_id)
            if not run.get("asset_plan_identity") or run["cancel_requested"] or run["status"]=="cancelled":return
            for key,asset in assets.items():
                history=states.get(key,{})
                if not history or asset.get("execution_run_id")!=run_id:continue
                state=history[max(history)]
                if not state["revoked"] and state["status"] not in {"stale","rejected","retired","unavailable"}:continue
                row=db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=? AND run_id=?",(asset["producer_task_id"],run_id)).fetchone()
                task=json.loads(row[0]) if row else {}
                if task and not task.get("stale"):
                    task.update(stale=True,asset_stale_reason=state["reason"]);self._write_task(db,task)
                    result=db.execute("SELECT state_json FROM orchestration_results WHERE task_id=?",(task["task_id"],)).fetchone()
                    if result:
                        meta=json.loads(result[0]);meta["stale"]=True
                        db.execute("UPDATE orchestration_results SET state_json=? WHERE task_id=?",(_json(meta),task["task_id"]))
                    self._event(db,run_id,"asset_descendant_stale",state["reason"],task_id=task["task_id"])
            producers=[t["task_id"] for t in self._tasks(db,run_id) if t.get("asset_plan_identity")==run["asset_plan_identity"] and t["status"]=="succeeded" and not t.get("stale")]
        for tid in producers:
            try:self.notify_asset_output(run["item_id"],run_id,tid)
            except (AnalysisContractError,ValueError,TypeError,KeyError,OSError) as exc:
                with self._db() as db:
                    current=json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?",(tid,)).fetchone()[0])
                    code=getattr(exc,"code",getattr(exc,"reason","asset_reconciliation_failed"))
                    if current.get("asset_delivery_error")!=code:
                        current["asset_delivery_error"]=code;self._write_task(db,current)
                        self._event(db,run_id,"asset_delivery_pending",code,task_id=tid)

    def _validate_result(self, db, run, task, raw):
        statistical_review = None
        if not isinstance(raw, dict):
            raise _error("結果はJSONオブジェクトで返してください。", "invalid_result")
        if raw.get("research_mode", "exploratory") != "exploratory":
            raise _error("確認的主張には未対応です。", "confirmatory_unavailable")
        if raw.get("dataset_version", run["input_hash"]) != run["input_hash"]:
            raise _error("結果の入力版が一致しません。", "revision_conflict")
        evidence = {e["evidence_id"]: e for e in self._initial(db, run["initial_id"])["evidence"] if not e["excluded"]}
        if task["role"] == "statistics" and task["method_id"] in STATISTICAL_TOOLS:
            initial = self._initial(db, run["initial_id"])
            self._validate_statistical_table(raw, task, initial)
        if task.get("expert_agent"):
            from .services.expert_agents import expert_profile, report_schema, validate_shape, validate_report, bind_evidence_ids, bind_statistical_requests
            from .services.analysis_orchestration_adapters import SPECIALIST_SCHEMA
            profile = expert_profile(run["expert_agents"], task["expert_agent"]["expert_id"])
            self._validate_expert_receipt(task, profile)
            schema = copy.deepcopy(SPECIALIST_SCHEMA)
            calculation_ids = [ref["result_id"] for ref in task.get("expert_calculation_refs", [])]
            calculations = []
            initial = self._initial(db, run["initial_id"])
            for ref in task.get("expert_calculation_refs", []):
                saved = db.execute("SELECT raw_json,state_json FROM orchestration_results WHERE result_id=? AND run_id=?",
                                   (ref["result_id"], run["run_id"])).fetchone()
                metadata = json.loads(saved["state_json"]) if saved else {}
                if (metadata.get("raw_hash") != ref["raw_hash"] or metadata.get("task_id") != ref["task_id"]
                        or metadata.get("validation_status") != "valid" or metadata.get("stale")
                        or metadata.get("dataset_version") != run["input_hash"]
                        or fingerprint(json.loads(saved["raw_json"])) != ref["raw_hash"]):
                    raise _error("参照計算結果のhash・入力版が一致しません。", "statistics_result_mismatch")
                source_row = db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=? AND run_id=?",
                                        (ref["task_id"], run["run_id"])).fetchone()
                if source_row is None:
                    raise _error("参照計算タスクが見つかりません。", "statistics_result_mismatch")
                source_task = json.loads(source_row[0])
                content = self._statistical_source(db, run, source_task, metadata, json.loads(saved["raw_json"]), initial)
                if source_task["method_id"] not in profile.get("statistical_tools", []):
                    raise _error("担当外の計算参照です。", "statistics_result_mismatch")
                # Validate original full tables above, then enforce the exact
                # delivery receipt. Never rehash a bounded row excerpt.
                view = {"result_id": ref["result_id"], "manifest": content["manifest"], "status": content["status"],
                        "datasets": {}, "_original_datasets": content["datasets"]}
                delivered = self._statistical_delivery_rows(run, task, ref, content, metadata)
                for name, table in content["datasets"].items():
                    provided = delivered.get(name, [])
                    view["datasets"][name] = {"rows": [row for row in table["rows"] if row["row_id"] in provided]}
                calculations.append(view)
            schema["properties"]["expert_report"] = report_schema(profile, task["expert_evidence_ids"], calculation_ids, calculations=calculations)
            schema["required"].append("expert_report")
            bind_evidence_ids(schema, task["expert_evidence_ids"])
            bind_statistical_requests(schema, profile)
            validate_shape(schema, raw)
            cells = validate_report(profile, raw, task["expert_evidence_ids"], calculation_ids, calculations=calculations,
                                    response_phase=task.get("expert_response_phase"),
                                    thematic_source=self._thematic_source(db, run, profile, initial),
                                    source_analysis=initial["analysis"], expected_delivery=task.get("expert_fgi_delivery"),
                                    expected_producer={"kind": "ai", "actor_id": task["task_id"], "model_id": task["model"],
                                        "provider": task["provider"], "revision": "unverified"} if profile.get("typed_contract") else None)
            if profile.get("contract_schema_version") == 2:
                phase = task["expert_response_phase"]
                requirements = profile["phase_requirements"][phase]
                statistical_review = {"status": "human_pending", "phase": phase,
                    "contract_version": profile["contract_version"], "profile_hash": profile["profile_hash"],
                    "knowledge_hash": profile["knowledge_hash"], "ai_status": raw["expert_report"]["status"],
                    "ai_complete": raw["expert_report"]["status"] in {"draft", "needs_calculation"},
                    "researcher_record_status": "unsupported", "researcher_steps_pending": requirements["researcher"],
                    "code_steps": [{"step_id": sid, "status": "verified_attempt", "result_ids": calculation_ids,
                                    "calculation_statuses": [calc["status"] for calc in calculations]} for sid in requirements["code"]],
                    "semantic_review": "undetermined", "free_text_status": "unverified_ai_draft",
                    "eligible_as_confirmed_evidence": False, "rendered_cells": cells}
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
            if raw.get("claims") and self._statistical_review_gate(db, run):
                raise _error("統計専門家の未判定候補を確定根拠へ昇格できません。", "statistical_human_review_required")
            if not isinstance(raw.get("summary"), str) or not raw["summary"].strip():
                raise _error("空でない統合要約が必要です。", "invalid_result")
            if raw.get("stop") is not None and (not isinstance(raw["stop"], dict) or not raw["stop"].get("reason")):
                raise _error("停止案には理由が必要です。", "invalid_stop")
            for intent in raw.get("intents", []):
                self._intent_expert(run, intent)
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

        return statistical_review

    @staticmethod
    def _statistical_delivery_rows(run, task, ref, content, metadata):
        """Recheck saved delivery proof without running AI or computations."""
        from .services.expert_data_hooks import read_data, VERSION, REQUEST_SCHEMA, fail
        from .services.expert_agents import validate_shape
        def record(value, fields):
            if not isinstance(value, dict) or any(type(value.get(key)) is not kind for key, kind in fields.items()):
                fail("expert_hook_delivery_mismatch")
        def row_map(value):
            if (not isinstance(value, dict) or any(not isinstance(name, str) or not isinstance(ids, list)
                    or any(not isinstance(rid, str) for rid in ids) or len(set(ids)) != len(ids)
                    for name, ids in value.items())):
                fail("expert_hook_delivery_mismatch")
        row_map(ref.get("provided_rows", {}))
        if "delivery_version" not in ref:
            if run["config"].get("expert_hooks") and run["config"].get("expert_hook_version") == VERSION:
                fail("expert_hook_delivery_mismatch")
            # Frozen legacy receipts retain their original initial-row scope.
            return ref.get("provided_rows", {})
        if ref["delivery_version"] != VERSION:
            fail("expert_hook_delivery_mismatch")
        provided = copy.deepcopy(ref.get("initial_provided_rows", {}))
        row_map(provided)
        if set(provided) != set(content["datasets"]):
            fail("expert_hook_delivery_mismatch")
        for name, ids in provided.items():
            if (not isinstance(ids, list) or len(set(ids)) != len(ids)
                    or not set(ids) <= {row["row_id"] for row in content["datasets"][name]["rows"]}):
                fail("expert_hook_delivery_mismatch")
        deliveries, reads = task.get("expert_hook_deliveries", []), task.get("expert_hook_reads", [])
        model_calls = task.get("model_calls", 1)
        if not isinstance(deliveries, list) or not isinstance(reads, list) or type(model_calls) is not int:
            fail("expert_hook_delivery_mismatch")
        identity = {"run_id": str, "task_id": str, "attempt_id": str, "generation": int}
        for read in reads:
            record(read, {**identity, "version": str, "request": dict, "request_hash": str,
                          "packet_hash": str, "source_hash": str, "data_version": str})
            try:
                validate_shape(REQUEST_SCHEMA, read["request"])
            except AnalysisContractError:
                fail("expert_hook_delivery_mismatch")
            if read["request"]["name"] == "read_calculation_table":
                record(read, {"result_id": str, "table_id": str, "provided_rows": dict})
                row_map(read["provided_rows"])
            elif (not isinstance(read.get("provided_evidence_ids"), list)
                  or any(not isinstance(eid, str) for eid in read["provided_evidence_ids"])):
                fail("expert_hook_delivery_mismatch")
        known_results = {r["result_id"] for r in task["expert_calculation_refs"]}
        for delivery in deliveries:
            record(delivery, {**identity, "version": str, "model_call": int, "packets": list})
            if (delivery.get("version") != VERSION
                    or any(delivery.get(key) != task[key] for key in ("run_id", "task_id", "attempt_id", "generation"))
                    or not 2 <= delivery.get("model_call", 0) <= model_calls):
                fail("expert_hook_delivery_mismatch")
            for packet in delivery["packets"]:
                record(packet, {"packet_hash": str, "result_id": str, "table_id": str, "provided_rows": dict})
                row_map(packet["provided_rows"])
                if packet["result_id"] not in known_results:
                    fail("expert_hook_delivery_mismatch")
                if packet["result_id"] != ref["result_id"]:
                    continue
                read = next((r for r in task.get("expert_hook_reads", []) if r["packet_hash"] == packet["packet_hash"]), None)
                if (read is None or read.get("version") != VERSION or read.get("source_hash") != ref["raw_hash"]
                        or read.get("data_version") != run["input_hash"]
                        or any(read.get(key) != task[key] for key in ("run_id", "task_id", "attempt_id", "generation"))
                        or fingerprint(read["request"]) != read["request_hash"]):
                    fail("expert_hook_delivery_mismatch")
                replay = read_data(read["request"], evidence=[], calculations={ref["result_id"]: (content, metadata)},
                    allowed_evidence_ids=[], data_version=run["input_hash"], max_chars=run["config"]["context_text_limit"])
                expected = {replay["table_id"]: [row["row_id"] for row in replay["rows"]]}
                if (fingerprint(replay) != packet["packet_hash"] or replay["table_id"] != packet["table_id"]
                        or read.get("provided_rows") != expected or packet["provided_rows"] != expected
                        or read.get("result_id") != replay["result_id"] or read.get("table_id") != replay["table_id"]):
                    fail("expert_hook_delivery_mismatch")
                for name, ids in expected.items():
                    provided[name] = sorted(set(provided[name]) | set(ids))
        if ({name: sorted(ids) for name, ids in provided.items()}
                != {name: sorted(ids) for name, ids in ref.get("provided_rows", {}).items()}):
            fail("expert_hook_delivery_mismatch")
        return provided

    def _statistical_source(self, db, run, task, metadata, raw, initial):
        if fingerprint(raw) != metadata.get("raw_hash"):
            raise _error("保存済み結果のhashが一致しません。", "result_integrity_mismatch")
        if (task.get("run_id") != run["run_id"] or metadata.get("run_id") != run["run_id"]
                or task.get("task_id") != metadata.get("task_id") or task.get("result_id") != metadata.get("result_id")
                or task.get("attempt_id") != metadata.get("attempt_id") or task.get("role") != "statistics"
                or metadata.get("role") != "statistics" or task.get("kind") != "code"
                or task.get("method_id") not in STATISTICAL_TOOLS
                or task.get("status") != "succeeded" or metadata.get("validation_status") != "valid"
                or task.get("stale") or metadata.get("stale")
                or task.get("dataset_version") != run["input_hash"] or metadata.get("dataset_version") != run["input_hash"]):
            raise _error("原計算のタスク・結果・固定入力が一致しません。", "statistics_result_mismatch")
        self._validate_statistical_table(raw, task, initial)
        return raw

    @staticmethod
    def _validate_expert_receipt(task, profile):
        if any(task["expert_agent"].get(key) != profile[key] for key in
               ("expert_id", "profile_hash", "knowledge_hash", "contract_version")):
            raise _error("専門家タスクと固定契約の版・hashが一致しません。", "expert_knowledge_hash_mismatch")

    @staticmethod
    def _validate_statistical_table(raw, task, initial):
        from .services.analysis_orchestration_methods import validate_statistical_result
        linguistics = initial["analysis"].get("research", {}).get("linguistics", {})
        if (set(raw.get("datasets", {})) != {STATISTICAL_TOOLS[task["method_id"]][0]}
                or raw.get("manifest", {}).get("computation_input_hash") != fingerprint({"analysis": initial["analysis"], "linguistics": linguistics})):
            raise _error("原計算の表・固定入力hashが一致しません。", "statistics_result_mismatch")
        validate_statistical_result(raw, task, initial["evidence"])
        statuses = {row.get("status") for table in raw["datasets"].values() for row in table["rows"] if "status" in row}
        rows = [row for table in raw["datasets"].values() for row in table["rows"]]
        expected_status = ("not_computed" if not rows or statuses and "computed" not in statuses
                           else "partial" if statuses - {"computed"} else "computed")
        if raw.get("status") != expected_status:
            raise _error("計算の部分・未計算状態が一致しません。", "statistics_result_mismatch")

    def _statistical_review_gate(self, db, run):
        pending = []
        for row in db.execute("SELECT state_json FROM orchestration_results WHERE run_id=?", (run["run_id"],)):
            meta = json.loads(row[0])
            if meta.get("statistical_review", {}).get("status") == "human_pending":
                pending.append(meta["result_id"])
        return {"status": "human_pending", "result_ids": pending, "eligible_as_confirmed_evidence": False} if pending else None

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
        promotion_blocked = bool(raw.get("claims") and self._statistical_review_gate(db, run))
        if (promotion_blocked or fingerprint(raw) != meta["raw_hash"] or meta.get("task_id") != task["task_id"]
                or meta.get("run_id") != run["run_id"] or meta.get("result_id") != result["result_id"]
                or meta.get("attempt_id") != task["attempt_id"]):
            error = "statistical_human_review_required" if promotion_blocked else "result_integrity_mismatch"
            meta.update(validation_status="quarantined", error=error)
            task.update(status="quarantined", validation_status="quarantined", error=error)
            db.execute("UPDATE orchestration_results SET state_json=? WHERE result_id=?", (_json(meta), result["result_id"]))
            self._write_task(db, task)
            self._event(db, run["run_id"], "result_quarantined", error, task_id=task["task_id"])
            run["error"] = error
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
        gate = self._statistical_review_gate(db, run)
        if gate:
            next_view.update(content_status="unreviewed", statistical_review=gate)
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
        self.reconcile_asset_plan(run_id)
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
                self.reconcile_asset_plan(run_id)
                if received:
                    self._notify_management(run_id)
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
                        if any(t.get("stale") or t["status"] in {"failed", "quarantined", "cancelled", "blocked"} for t in dependencies):
                            task.update(status="blocked", error="dependency_failed")
                            self._write_task(db, task)
                        elif (all(t["status"] == "succeeded" for t in dependencies)
                              and self._asset_dependencies_delivered(task) and len(futures) < concurrency):
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
            try:
                self._notify_management(run_id)
            finally:
                try:
                    guard = self._run_budgets.get(run_id)
                    if guard is not None:
                        guard.cleanup_hold = guard.reason()
                        with self._db() as db:
                            self._write_run(db, self._read_run(db, run_id))
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
                self._notify_management(run_id)
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
                        guarded = "request_budget" in run or run_id in self._run_budgets
                        before_adoption = copy.deepcopy(run) if guarded else None
                        if guarded:
                            db.execute("SAVEPOINT guarded_adoption")
                        try:
                            self._require_budget(run, task["task_id"])
                            self._apply_core(db, run, task, result)
                            self._require_budget(run, task["task_id"])
                        except AnalysisContractError:
                            if not guarded:
                                raise
                            db.execute("ROLLBACK TO guarded_adoption")
                            run = before_adoption
                            self._stop(db, run, self._budget_reason(run, task["task_id"]) or "execution_failure")
                            return
                        finally:
                            if guarded:
                                db.execute("RELEASE guarded_adoption")
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
