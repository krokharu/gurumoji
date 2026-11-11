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
    read_initial_checkpoints, stage_input_hash, write_stage, initial_progress, recover_initial_checkpoints, validate_ready_initial)
from .services.core_pipeline_methods import STATISTICAL_TOOLS
from .services.pipeline_context import VERSION as ADAPTER_VERSION
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


def _call_started_epoch(task: dict[str, Any]) -> float | None:
    """現在のモデル呼出しの開始時刻を返す。"""
    return task.get("call_started_epoch") or task.get("started_epoch")


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
    from .services.analysis_state import initialize_state_store
    initialize_state_store(connection)


def recover_orchestration_runs(connection: sqlite3.Connection) -> None:
    """Startup-only recovery marker. Never invoke while this process runs jobs.

    Recovery preserves received results and makes uncertain calls explicit. It
    never launches workers and never promises exactly-once provider execution.
    """
    recover_initial_checkpoints(connection, adapter_version=ADAPTER_VERSION)
    rows = connection.execute("SELECT run_id,state_json FROM orchestration_runs "
                              "WHERE json_extract(state_json, '$.config.adapter_version')=?", (ADAPTER_VERSION,)).fetchall()
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


# 開始APIはUI送信項目と明示的な専門家・研究質問だけを受け取る。
PAYLOAD_FIELDS = frozenset({
    "request_id", "source_revision", "analysis_revision", "question", "provider", "model",
    "provider_policy", "cloud_consent", "stop_mode", "time_limit_seconds", "max_iterations",
    "importance_threshold", "max_calls", "max_tasks", "concurrency", "research_mode", "roles",
    "publication_targets", "obsidian_management", "expert_ids", "research_question",
})


def validate_orchestration_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise _error("分析設定はオブジェクトで指定してください。")
    unknown = set(payload) - PAYLOAD_FIELDS
    if unknown:
        raise _error("未対応の分析設定です。", field=sorted(unknown)[0])
    if payload.get("research_mode", "exploratory") != "exploratory":
        raise _error("この実装は探索分析専用です。隔離検証データを伴う確認分析には未対応です。", "confirmatory_unavailable")
    question = payload.get("question", "会話の特徴と代替説明を根拠付きで分析する")
    if not isinstance(question, str) or not question.strip() or len(question) > 8000:
        raise _error("分析する問いを指定してください。", field="question")
    mode = payload.get("stop_mode", "auto")
    if mode not in {"time", "iterations", "importance", "auto"}:
        raise _error("終了モードが正しくありません。", field="stop_mode")
    config = {"question": question.strip(), "stop_mode": mode, "research_mode": "exploratory",
              "provider": payload.get("provider", "lmstudio"), "model": payload.get("model", ""),
              "provider_policy": payload.get("provider_policy", "local_only"),
              "cloud_consent": payload.get("cloud_consent") is True,
              "adapter_version": ADAPTER_VERSION,
              "template_version": ADAPTER_VERSION,
              "template_config": {}, "roles": payload.get("roles", {}),
              "importance_threshold": payload.get("importance_threshold", "medium"),
              "min_iterations": 3 if mode == "auto" else 0,
              "max_iterations": payload.get("max_iterations", None if mode == "auto" else 5),
              "time_limit_seconds": payload.get("time_limit_seconds", None if mode == "auto" else 300),
              "max_calls": payload.get("max_calls"), "max_tasks": payload.get("max_tasks"),
              "concurrency": payload.get("concurrency", 2),
              "call_timeout_seconds": 120,
              "max_result_bytes": 2_000_000,
              "obsidian_management": payload.get("obsidian_management", True)}
    if "research_question" in payload:
        research_question = payload["research_question"]
        if (not isinstance(research_question, str) or not research_question.strip()
                or len(research_question) > 8000):
            raise _error("研究質問は空でない文字列で指定してください。", field="research_question")
        config["research_question"] = research_question.strip()
    for key in ("expert_ids",):
        if key in payload:
            config[key] = copy.deepcopy(payload[key])
    if "expert_ids" in config and (not isinstance(config["expert_ids"], list)
            or not 1 <= len(config["expert_ids"]) <= 9
            or any(not isinstance(eid, str) or not eid.startswith("exp-") or len(eid) > 100 for eid in config["expert_ids"])
            or len(set(config["expert_ids"])) != len(config["expert_ids"])):
        raise _error("専門家IDは重複なく1〜6件指定してください。", "expert_selection_invalid")
    if type(config["obsidian_management"]) is not bool:
        raise _error("Obsidian管理はtrueまたはfalseです。", field="obsidian_management")
    for key, low, high in (("concurrency", 1, 4),
                           ("call_timeout_seconds", 1, 3600), ("max_result_bytes", 1000, 20_000_000)):
        if type(config[key]) is not int or not low <= config[key] <= high:
            raise _error(f"{key}は{low}〜{high}の整数です。", field=key)
    for key, high in (("max_calls", 10000), ("max_tasks", 20000)):
        if config[key] is None:
            continue
        if type(config[key]) is not int or not 1 <= config[key] <= high:
            raise _error(f"{key}は1〜{high}の整数です。", field=key)
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
        self.slot_released_at = None  # when this run's last task left its worker slot

    def register(self, task_id, origin):
        with self.lock:
            self.request_budget.register_task(task_id, origin)
            self.tasks[task_id] = origin

    def advance_waiting_origin(self, task_id):
        """At dispatch: the time spent behind this run's own running task is not ageing."""
        with self.lock:
            origin, released = self.tasks.get(task_id), self.slot_released_at
            if origin is None or released is None:
                return
            moved = min(max(origin, released), self.clock())
            if moved > origin:
                self.request_budget.advance_unstarted_task_origin(task_id, moved)
                self.tasks[task_id] = moved

    def restart_task(self, task_id):
        """The task's next model call (a hook continuation) gets its own task window."""
        with self.lock:
            now = self.clock()
            self.request_budget.restart_task_clock(task_id, now)
            self.tasks[task_id] = now

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
                 write_lock: Any = None, schedule: bool = True, adapter_version: str = ADAPTER_VERSION,
                 initial_builder: Any = None, on_complete: Callable[[str, str], Any] | None = None,
                 memory_manager: Any = None, expert_provider: Callable[[dict], dict] | None = None,
                 budget_factory: Callable[..., Any] | None = None, budget_clock: Callable[[], float] = time.monotonic,
                 table_store: Any = None):
        self.connect = connect or database_connection
        self._outline_tag_cache = {}  # frozen snapshot hash -> outline tags
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
        viewer = AnalysisHistoryService(connect=self.connect, find_item=self.find_item)
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

    def _check_version(self, run):
        if run.get("schema_version") != SCHEMA_VERSION:
            raise _error("保存されたrunの形式版が異なります。元の版で復旧してください。", "schema_version_conflict")
        if run["config"].get("adapter_version") != self.adapter_version:
            raise _error("モデル指示の版が変わりました。新しいrunを開始してください。", "adapter_version_conflict")

    def _read_run(self, db, run_id: str, item_id: str | None = None) -> dict:
        row = db.execute("SELECT * FROM orchestration_runs WHERE run_id=? AND json_extract(state_json, '$.config.adapter_version')=?", (run_id, ADAPTER_VERSION)).fetchone()
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

    def _guarded(self, run) -> bool:
        return "request_budget" in run or run["run_id"] in self._run_budgets

    def _call_elapsed(self, run, task):
        """Seconds the task's current model call has run, on the clock that governs this run.

        A guarded run is judged on its monotonic budget clock only: a wall-clock step
        (NTP, suspend, manual change) says nothing about elapsed time. An unguarded run
        keeps the legacy epoch comparison. None means the call has no recorded start.
        """
        if self._guarded(run):
            started = task.get("call_started_monotonic")
            if started is None:
                started = task.get("started_monotonic")
            return None if started is None else self._budget_clock() - started
        started = _call_started_epoch(task)
        return None if not started else time.time() - started

    def _deadline_reached(self, run) -> bool:
        """The run's own time limit (config.time_limit_seconds), on the clock of its kind."""
        if run["deadline"] is None:
            return False
        if self._guarded(run):
            limit = run.get("deadline_monotonic")
            return limit is not None and self._budget_clock() >= limit
        return time.time() >= run["deadline"]

    def _start_deadline(self, run):
        seconds = run["config"]["time_limit_seconds"]
        run["deadline"] = time.time() + seconds if seconds is not None else None
        if run["run_id"] in self._run_budgets and seconds is not None:
            run["deadline_monotonic"] = self._budget_clock() + seconds

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

    def _record_agent_diagnostic(self, run_id, original_task, payload):
        """Append safe metadata to the existing run journal; never a dispatch authority."""
        from .services.analysis_diagnostics import sanitize, VERSION
        diagnostic = sanitize(payload)
        with self._db() as db:
            row = db.execute("SELECT state_json FROM orchestration_tasks WHERE run_id=? AND task_id=?",
                             (run_id, original_task["task_id"])).fetchone()
            if row is None:
                return
            task = json.loads(row[0])
            if (task["attempt_id"] != original_task["attempt_id"]
                    or task["generation"] != original_task["generation"]):
                return  # A late observer must not mutate a newer attempt's diagnostic state.
            count = task.get("diagnostic_event_count", 0) + 1
            task.update(diagnostic_version=VERSION, diagnostic_event_count=count, diagnostic_last=diagnostic)
            phase = diagnostic.get("phase")
            if phase == "input_assembled":
                task.pop("diagnostic_last_response", None)
                task.pop("diagnostic_failure", None)
            if phase == "request_final":
                task["diagnostic_last_request"] = diagnostic
                task.pop("diagnostic_last_response", None)
            elif phase in {"response_returned", "response_decoded"}:
                task["diagnostic_last_response"] = diagnostic
            if phase in {"failed", "transport_failed"} or diagnostic.get("event") == "error":
                previous = task.get("diagnostic_failure", {})
                # The hook's agent_call contains provider and adapter validation;
                # retain the more specific boundary already recorded by the adapter.
                same_call = previous.get("call", previous.get("round")) == diagnostic.get("call", diagnostic.get("round"))
                if not (same_call and ((diagnostic.get("stage") == "agent_call" and previous.get("stage") not in {None, "agent_call"})
                        or (diagnostic.get("stage") == "provider_call" and previous.get("stage") == "transport"))):
                    task["diagnostic_failure"] = diagnostic
            self._write_task(db, task)
            if count <= 256:
                self._event(db, run_id, "agent_diagnostic", "実行診断を記録しました。", source=task["role"], target="handler",
                    task_id=task["task_id"], run_id_ref=run_id, attempt_id=task["attempt_id"], generation=task["generation"],
                    dataset_version=task["dataset_version"], annotation_version=task["annotation_version"], diagnostic=diagnostic)
            elif count == 257:
                task["diagnostic_events_truncated"] = True
                self._write_task(db, task)
                self._event(db, run_id, "agent_diagnostic_limit", "診断件数の上限に達しました。最新状態と失敗情報を保持します。",
                    task_id=task["task_id"], attempt_id=task["attempt_id"])

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
                                    "input_hash": None})
        with self._db() as db:
            existing = db.execute("SELECT * FROM orchestration_runs WHERE request_id=? AND json_extract(state_json, '$.config.adapter_version')=?", (request_id, ADAPTER_VERSION)).fetchone()
            if existing is None and db.execute("SELECT 1 FROM orchestration_runs WHERE request_id=?", (request_id,)).fetchone():
                raise _error("旧版の依頼IDは再利用できません。", "adapter_version_conflict")
            if existing:
                matches = existing["request_hash"] == request_hash
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
        if self.expert_provider is None and "expert_ids" in config:
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
        identity = fingerprint({"item_id": item_id, "dataset_version": before, "adapter_version": ADAPTER_VERSION,
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
                self._validate_reusable_initial(db, initial_id)
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
                existing = db.execute("SELECT * FROM orchestration_runs WHERE request_id=? AND json_extract(state_json, '$.config.adapter_version')=?", (request_id, ADAPTER_VERSION)).fetchone()
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

    def _validate_reusable_initial(self, db, initial_id):
        stored = db.execute("SELECT 1 FROM orchestration_initial_builds WHERE initial_id=?", (initial_id,)).fetchone()
        if self.initial_builder is not None or stored:
            validate_ready_initial(db, initial_id, self.initial_builder)

    def _start_staged(self, item_id, payload, config, request_id, request_hash, app_url, item, before, expert_bundle=None, run_id=None):
        if payload.get("input_hash") is not None and payload["input_hash"] != before:
            raise _error("確認した入力hashが更新されています。", "revision_conflict", "input_hash")
        identity = fingerprint({"item_id": item_id, "dataset_version": before, "adapter_version": ADAPTER_VERSION,
                                "template_version": config["template_version"], "config": config["template_config"]})
        run_id = run_id or _id("run")
        snapshot = None
        with self._db() as db:
            existing = db.execute("SELECT * FROM orchestration_runs WHERE request_id=? AND json_extract(state_json, '$.config.adapter_version')=?", (request_id, ADAPTER_VERSION)).fetchone()
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
                    self._validate_reusable_initial(db, initial_id)
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
                        self._start_deadline(run)
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
        measured_calls = len({r.get("task_id") for r in records})
        tokens_complete = bool(records) and measured_calls == run["calls_started"] and all(
            type(r.get(key)) in {int, float} for r in records
            for key in ("input_tokens", "output_tokens", "total_tokens"))
        return {"calls": run["calls_started"], "code_executions": run["code_executions"],
                "input_tokens": total("input_tokens"), "output_tokens": total("output_tokens"),
                "total_tokens": total("total_tokens"), "cost": total("cost"),
                "currency": "USD" if any(r.get("currency") == "USD" for r in records) else None,
                "measured_calls": measured_calls, "tokens_complete": tokens_complete,
                "measurement_status": ("reported" if tokens_complete else "partial") if records else "unavailable"}

    def _outline_tags(self, db, initial_id, initial=None):
        """Outline tags of the frozen snapshot, cached by its stored hash; None without an outline."""
        row = db.execute("SELECT status,snapshot_hash FROM orchestration_initials WHERE initial_id=?", (initial_id,)).fetchone()
        if row is None or row["status"] != "ready":
            return None
        cache = self._outline_tag_cache
        if row["snapshot_hash"] not in cache:
            from .services.outline_tags import outline_tags
            try:
                snapshot = initial if initial is not None else self._initial(db, initial_id)
            except AnalysisContractError:
                return None  # a tampered snapshot is reported by the integrity checks, not here
            cache[row["snapshot_hash"]] = outline_tags(snapshot)
        return copy.deepcopy(cache[row["snapshot_hash"]])

    def _public(self, db, run):
        result = copy.deepcopy(run)
        if "expert_agents" in run:
            from .services.expert_agents import catalog_packet
            result["expert_agents"] = catalog_packet(run["expert_agents"])
        result["config"].setdefault("publication_targets", [])
        result["config"]["effective_publication_writers"] = list(EFFECTIVE_PUBLICATION_WRITERS) if result["config"]["publication_targets"] else []
        result["initial"] = initial_progress(db, run["initial_id"])
        initial_reusable = True
        if result["initial"]["status"] == "ready":
            try:
                self._validate_reusable_initial(db, run["initial_id"])
            except AnalysisContractError as exc:
                initial_reusable = False
                result["initial"].update(status="revalidation_required", stored_status="ready", recovery_error=exc.code)
        result["initial_stages"] = result["initial"]["stages"]
        # Derived from the frozen snapshot: the ledger and saved package keep the per-utterance map.
        outline = self._outline_tags(db, run["initial_id"])
        if outline:
            result["outline_tags"] = outline
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
        result["can_resume"] = initial_reusable and run["status"] in {"queued", "recovery_required"} and not uncertain
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
                "SELECT state_json FROM orchestration_runs WHERE item_id=? AND json_extract(state_json, '$.config.adapter_version')=? ORDER BY rowid DESC", (item_id, ADAPTER_VERSION)).fetchall()]

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
            if run["phase"] != "initial":
                self._validate_reusable_initial(db, run["initial_id"])
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
        if self._deadline_reached(run):
            return "time_limit"
        if new_round and run["config"]["max_iterations"] is not None and run["iteration"] >= run["config"]["max_iterations"]:
            return "iteration_limit"
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
            if run["config"]["max_tasks"] is not None and len(self._tasks(db,run_id))+len(ordered)>run["config"]["max_tasks"]:
                raise _error("計画全体がtask予算を超えます。","asset_plan_budget")
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
            if not is_initial:
                # initial_sections names the result's fields here (result_fields manifest); the hash is fixed now.
                intent = self._pin_result_fields(db, run, intent, target)
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
        if "pipeline" in intent:
            identity["pipeline"] = copy.deepcopy(intent["pipeline"])
        key = fingerprint(identity)
        existing = db.execute("SELECT state_json FROM orchestration_tasks WHERE run_id=? AND idempotency_key=?", (run["run_id"], key)).fetchone()
        if existing:
            task = json.loads(existing[0])
            self._event(db, run["run_id"], "duplicate_suppressed", "同じ入力・目的・対象版のタスクを再発注しません。", task_id=task["task_id"])
            return task if reuse_existing else None
        if run["config"]["max_tasks"] is not None and len(tasks) >= run["config"]["max_tasks"]:
            self._stop(db, run, "task_budget_limit")
            return None
        queued_calls = sum(t["kind"] == "ai" and t["status"] == "queued" for t in tasks)
        if role in AI_ROLES and run["config"]["max_calls"] is not None and run["calls_started"] + queued_calls >= run["config"]["max_calls"]:
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
    def _pin_result_fields(db, run, intent, target):
        """Fix the target hash and check the requested field names against the stored result."""
        from .services import result_fields
        requested = intent.get("initial_sections", [])
        if (not isinstance(requested, list) or len(requested) > result_fields.MAX_REQUESTED
                or any(not isinstance(name, str) or not name or len(name) > 300 for name in requested)):
            raise _error("結果のfield指定は12件以内の文字列で指定してください。", "result_field_missing")
        row = db.execute("SELECT raw_json,state_json FROM orchestration_results WHERE result_id=? AND run_id=?",
                         (intent.get("result_id"), run["run_id"])).fetchone()
        metadata, stored = json.loads(row["state_json"]), json.loads(row["raw_json"])
        if fingerprint(stored) != metadata.get("raw_hash"):
            raise _error("保存済み結果のhashが一致しません。", "result_integrity_mismatch")
        values = dict(result_fields.leaves(stored))
        for name in requested:
            path, offset = result_fields.split_request(name)
            if path not in values or offset < 0:
                raise _error("保存済み結果にないfieldです。", "result_field_missing")
            size = len(json.dumps(values[path], ensure_ascii=False, separators=(",", ":")))
            if offset > 0 and offset >= size:
                raise _error("fieldの範囲外のoffsetです。", "result_field_missing")
        return {**intent, "target_raw_hash": metadata["raw_hash"]}

    @staticmethod
    def _intent_expert(run, intent):
        if "pipeline" in intent:
            return None
        expert_id = intent.get("expert_id", "")
        bundle = run.get("expert_agents")
        if expert_id and (bundle is None or intent.get("role") != "interpretation"):
            raise _error("専門家IDは知識を接続した会話解釈タスクへ指定してください。", "expert_selection_invalid")
        if bundle is not None and intent.get("role") == "interpretation":
            from .services.expert_agents import expert_profile
            return expert_profile(bundle, expert_id)
        return None


    def _context(self, db, run, task):
        if task["kind"] == "code":
            return {}
        if not task.get("expert_agent"):
            from .services import pipeline_run
            return pipeline_run.context(self, db, run, task)
        from .services.expert_agents import (expert_profile, request_packet, report_schema,
            focus_group_interaction_delivery, EXPERT_PROMPT, obj)
        from .services.core_pipeline_methods import calculation_packet
        initial = self._initial(db, run["initial_id"])
        profile = expert_profile(run["expert_agents"], task["expert_agent"]["expert_id"])
        self._validate_expert_receipt(task, profile)
        scope = set(task["intent"].get("evidence_ids", []))
        available = [row for row in initial["evidence"] if not row["excluded"] and (not scope or row["evidence_id"] in scope)]
        raw, remaining = [], 60000
        for row in available[:120]:
            if remaining <= 0:
                break
            delivered = copy.deepcopy(row)
            delivered["text"] = row["text"][:remaining]
            remaining -= len(delivered["text"])
            raw.append(delivered)
        packet = {"schema_version": SCHEMA_VERSION, "task": copy.deepcopy(task),
            "question": run["config"]["question"], "research_question": run["config"].get("research_question", run["config"]["question"]),
            "data_version": run["input_hash"], "annotation_version": task["annotation_version"], "raw_evidence": raw,
            "coverage": {"scope": "selected" if scope else "dataset", "available_count": len(available),
                "provided_count": len(raw), "omitted_count": len(available)-len(raw), "complete": len(raw)==len(available)},
            "statistical_calculations": []}
        if "statistical_tools" in profile:
            calculations = {}
            tasks = {t["task_id"]: t for t in self._tasks(db, run["run_id"])}
            for row in db.execute("SELECT raw_json,state_json FROM orchestration_results WHERE run_id=?", (run["run_id"],)):
                metadata = json.loads(row[1]); source = tasks[metadata["task_id"]]
                if (metadata["role"] != "statistics" or metadata["validation_status"] != "valid" or metadata.get("stale")
                        or source["method_id"] not in profile["statistical_tools"]
                        or task["dependencies"] and source["task_id"] not in task["dependencies"]):
                    continue
                content = self._statistical_source(db, run, source, metadata, json.loads(row[0]), initial)
                calculations[source["method_id"]] = (content, metadata)
            packet["statistical_calculations"] = [calculation_packet(content, metadata, max_chars=10000//max(1,len(calculations)))
                                                 for content, metadata in calculations.values()]
        source = self._thematic_source(db, run, profile, initial)
        packet["expert_request"] = request_packet(profile, packet, initial["analysis"], thematic_source=source)
        if profile.get("typed_contract") == "focus_group_interaction_candidates_v1":
            packet["expert_request"]["delivery_coverage"] = focus_group_interaction_delivery(source, packet)
        calculations = packet["expert_request"].get("calculations", [])
        task["expert_evidence_ids"] = [row["evidence_id"] for row in raw]
        task["expert_calculation_refs"] = [{**{key: row[key] for key in ("result_id", "task_id", "raw_hash")},
            "provided_rows": {name: [r["row_id"] for r in table["rows"]] for name, table in row["datasets"].items()}}
            for row in calculations]
        task["expert_response_phase"] = packet["expert_request"].get("response_phase")
        task["expert_fgi_delivery"] = packet["expert_request"].get("delivery_coverage")
        text = {"type": "string"}
        ids = {"type": "array", "items": text, "maxItems": 80}
        claim = obj({"claim_id": text, "text": text,
            "kind": {"type": "string", "enum": ["observation", "interpretation", "hypothesis"]}, "evidence_ids": ids})
        intent = obj({"role": {"type": "string", "enum": ["statistics"]},
            "kind": {"type": "string", "enum": ["analysis"]}, "result_id": text,
            "initial_sections": ids, "question": text, "why_now": text, "success_criteria": text,
            "expert_id": text, "method_id": text, "label_field": text, "evidence_ids": ids,
            "importance": {"type": "string", "enum": ["high", "medium", "low"]}, "importance_reason": text,
            "dependencies": ids, "label_dependent": {"type": "boolean"}, "replicate_id": text})
        schema = obj({"summary": {"type": "string", "minLength": 1},
            "claims": {"type": "array", "items": claim},
            "analysis_requests": {"type": "array", "items": intent},
            "label_patches": {"type": "array", "items": text, "maxItems": 0},
            "expert_report": report_schema(profile, task["expert_evidence_ids"], [r["result_id"] for r in calculations], calculations=calculations)})
        if "statistical_tools" in profile:
            schema["properties"]["claims"]["maxItems"] = 0
        from .services.expert_agents import bind_evidence_ids, bind_task_dependencies, bind_statistical_requests, render_expert_context
        bind_evidence_ids(schema, task["expert_evidence_ids"])
        bind_task_dependencies(schema, [t["task_id"] for t in self._tasks(db, run["run_id"])])
        bind_statistical_requests(schema, profile)
        task["pipeline_schema"] = copy.deepcopy(schema)
        packet = render_expert_context(packet)
        return {"version": ADAPTER_VERSION, "role": "expert", "schema_name": "analysis_orchestration_expert",
            "schema": schema, "system": EXPERT_PROMPT, "packet": packet, "task_id": task["task_id"]}


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
                elapsed = self._call_elapsed(run, task)
                if not limit and elapsed is not None and elapsed > run["config"]["call_timeout_seconds"]:
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


    def _record_usage(self, run_id, task_id, usage=None, **values):
        data = dict(usage or {}, **values)
        record = {"task_id": task_id, "reported_at": _now()}
        for key in ("input_tokens", "output_tokens", "total_tokens", "cost"):
            value = data.get(key)
            if value is None and key in data:
                record[key] = None
            elif type(value) in {int, float} and math.isfinite(value) and value >= 0:
                record[key] = value
        if data.get("currency") == "USD":
            record["currency"] = "USD"
        usage_id = str(data.get("usage_id") or task_id + ":response")
        # Timestamps are observations of delivery, not part of a call's payload.
        payload_hash = fingerprint({"task_id": task_id, "usage": {
            key: value for key, value in data.items() if key not in {"usage_id", "reported_at"}}})
        with self._db() as db:
            identifier = run_id + ":" + usage_id
            existing = db.execute("SELECT task_id,payload_json FROM orchestration_usage WHERE usage_id=?", (identifier,)).fetchone()
            if existing:
                saved = json.loads(existing["payload_json"])
                if existing["task_id"] == task_id and saved.get("usage_payload_hash") == payload_hash:
                    return
                raise _error("同じ利用量IDに異なる記録があります。保存済み記録を保持し、照合が必要です。", "usage_conflict")
            if data.get("reported") is False or not any(
                    type(record.get(k)) in {int, float} for k in ("input_tokens", "output_tokens", "total_tokens", "cost")):
                return
            record["usage_payload_hash"] = payload_hash
            db.execute("INSERT INTO orchestration_usage VALUES (?,?,?,?)", (identifier, run_id, task_id, _json(record)))

    def _execute(self, run_id: str, task_id: str):
        try:
            self._execute_task(run_id, task_id)
        finally:
            guard = self._run_budgets.get(run_id)
            if guard is not None:
                try:
                    guard.slot_released_at = self._budget_clock()
                except Exception:
                    pass

    def _execute_task(self, run_id: str, task_id: str):
        with self._db() as db:
            run = self._read_run(db, run_id)
            row = db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (task_id,)).fetchone()
            task = json.loads(row[0])
            if task["status"] != "queued" or run["status"] in TERMINAL:
                return
            guard = self._run_budgets.get(run_id)
            if guard is not None and task_id in guard.tasks:
                try:
                    guard.advance_waiting_origin(task_id)  # waiting for the slot is not ageing
                except Exception:
                    pass  # a refused move keeps the registered origin: the stricter, existing window
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
                from .services.analysis_diagnostics import error_metadata
                task["failure_diagnostic"] = {"stage": "task_input", "response_observed": False, **error_metadata(exc)}
                self._write_task(db, task)
                self._event(db, run_id, "task_input_rejected", exc.code, task_id=task_id, diagnostic=task["failure_diagnostic"])
                self._stop(db, run, self._budget_reason(run, task_id) or "human_review_required")
                return
            task.update(status="running", started_at=_now(), started_epoch=time.time(), call_started_epoch=None, generation=run["generation"])
            for key in ("diagnostic_last_request", "diagnostic_last_response", "diagnostic_failure", "failure_diagnostic", "diagnostics_unavailable"):
                task.pop(key, None)
            if run_id in self._run_budgets:
                task.update(started_monotonic=self._budget_clock(), call_started_monotonic=None)
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
        diagnostic_unavailable = False
        def record_diagnostic(payload):
            nonlocal diagnostic_unavailable
            try:
                self._record_agent_diagnostic(run_id, task, payload)
            except Exception:
                diagnostic_unavailable = True
                import logging
                logging.getLogger(__name__).error("orchestration diagnostic persistence failed; task_id=%s", task_id)
        self._notify_management(run_id)
        try:
            check()
            if task["kind"] == "code":
                if task["method_id"] in TABLE_PILOT_METHODS:
                    from .services.core_pipeline_adapters import resolve_table_pilot
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
                options["_agent_diagnostic"] = record_diagnostic
                guard = self._run_budgets.get(run_id)
                if guard is not None:
                    options.update(_request_budget=guard.request_budget, _budget_attempt_id=task["attempt_id"])
                raw = self.agent_runner(task["role"], context, options, check,
                                        lambda usage=None, **kw: self._record_usage(run_id, task_id, usage, **kw))
            # Raw response commits before semantic validation, including a late response.
            raw_json = _json(raw)
            with self._db() as db:
                latest = self._read_run(db, run_id)
                if self.find_item(latest["item_id"]) is None and latest["status"] not in TERMINAL:
                    self._stop(db, latest, "source_deleted")
                limit = self._limit(db, latest) or self._budget_reason(latest, task_id)
                saved_task = db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (task_id,)).fetchone()
                elapsed = self._call_elapsed(latest, json.loads(saved_task[0]) if saved_task else task)
                if not limit and elapsed is not None and elapsed > latest["config"]["call_timeout_seconds"]:
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
                if diagnostic_unavailable:
                    current_task["diagnostics_unavailable"] = True
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
                from .services.analysis_diagnostics import error_metadata
                specific = current.get("diagnostic_failure", {})
                failure = {**error_metadata(exc), "stage": specific.get("stage", "agent_execution"),
                           "response_observed": bool(current.get("diagnostic_last_response"))}
                current["failure_diagnostic"] = failure
                if diagnostic_unavailable:
                    current["diagnostics_unavailable"] = True
                # Transport errors may have consumed external work. Never retry blind.
                from .services.ai.request_budget import BudgetHold
                proven_not_sent = isinstance(exc, BudgetHold) and exc.strict_preworker_not_sent
                current.update(status="uncertain" if task["kind"] == "ai" and not proven_not_sent else "failed",
                               ended_at=_now(), error=getattr(exc, "code", type(exc).__name__))
                self._write_task(db, current)
                latest = self._read_run(db, run_id)
                if latest["status"] not in TERMINAL and task["kind"] == "ai":
                    known_rejection = (failure["response_observed"] and isinstance(exc, AnalysisContractError)
                        and failure["stage"] in {"generation_schema_validation", "wire_adoption", "response_validation", "section_expansion", "request_repeat_check",
                            "expert_output_projection", "read_progress_plan", "read_progress_before_execution",
                            "read_progress_after_execution", "read_progress_delivery"})
                    latest.update(status="recovery_required", error=("AI応答後の検査・取得要求で失敗しました。診断ログを確認してください。自動再試行しません。"
                        if known_rejection else "外部呼出しの実行結果が不明です。自動再試行しません。"))
                    self._write_run(db, latest)
                elif run_id in self._run_budgets:
                    self._write_run(db, latest)
                self._event(db, run_id, "execution_uncertain" if task["kind"] == "ai" else "task_failed", type(exc).__name__, task_id=task_id,
                            attempt_id=task["attempt_id"], diagnostic=failure)

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
                from .services.analysis_diagnostics import error_metadata
                task["failure_diagnostic"] = {"stage": "handler_validation", "response_observed": True, **error_metadata(exc)}
                if code == "expert_input_incomplete":
                    task["failure_diagnostic"]["input_delivery"] = copy.deepcopy(task.get("expert_input_delivery", {}))
                self._event(db, run_id, "result_quarantined", code, task_id=task_id, attempt_id=task["attempt_id"],
                            result_id=meta["result_id"], raw_hash=meta["raw_hash"], diagnostic=task["failure_diagnostic"])
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
        from .services.core_pipeline_methods import validate_table_pilot_result
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
        assets,_originals,states,links=self.table_store._connection_index() if self.table_store else ({},{},{},[])
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
            tasks = self._tasks(db, run_id)
            producers = []
            for task in tasks:
                if (task.get("asset_plan_identity") != run["asset_plan_identity"]
                        or task["status"] != "succeeded" or task.get("stale")):
                    continue
                linked = any(link.get("execution_run_id") == run_id
                    and link.get("producer_task_id") == task["task_id"]
                    and link.get("asset_key", {}).get("store_run_id") == task.get("table_store_run_id")
                    and all(link.get(key) == value for key, value in run["asset_plan_identity"].items())
                    for link in links)
                missing = not linked
                for child in tasks:
                    if child.get("asset_plan_identity") != run["asset_plan_identity"]:
                        continue
                    refs = child.get("intent", {}).get("table_pilot", {}).get("bindings", {}).get("inputs", [])
                    for ref in refs:
                        if ref.get("source", {}).get("producer_task_id") != task["task_id"]:
                            continue
                        probe = {**child, "intent": {"table_pilot": {"bindings": {"inputs": [ref]}}}}
                        missing = missing or not self._asset_dependencies_delivered(probe)
                # 復旧が必要な通知だけを再配送する。実行・保存直前の原票と権限の再検証は維持する。
                if missing:
                    producers.append(task["task_id"])
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
        if task.get("expert_agent"):
            from .services.expert_agents import expert_profile, validate_shape, validate_report
            profile = expert_profile(run["expert_agents"], task["expert_agent"]["expert_id"])
            self._validate_expert_receipt(task, profile)
            schema = copy.deepcopy(task["pipeline_schema"])
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
                delivered = ref["provided_rows"]
                for name, table in content["datasets"].items():
                    provided = delivered.get(name, [])
                    view["datasets"][name] = {"rows": [row for row in table["rows"] if row["row_id"] in provided]}
                calculations.append(view)
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
            return statistical_review
        if task["kind"] == "ai":
            from .services import pipeline_run
            return pipeline_run.validate_result(self, db, run, task, raw)
        if task["method_id"] in STATISTICAL_TOOLS:
            self._validate_statistical_table(raw, task, self._initial(db, run["initial_id"]))
        return None


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
        from .services.core_pipeline_methods import validate_statistical_result
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
                    running = [t for t in tasks if t["status"] == "running"]
                    # A guarded run is watched on the guard's own task windows (opened at registration),
                    # so a worker that never cooperates still stops the driver on the monotonic deadline.
                    guard_reason = next((reason for reason in (self._budget_reason(run, t["task_id"]) for t in running)
                                         if reason), None) if self._guarded(run) else None
                    if guard_reason:
                        self._stop(db, run, guard_reason)
                        return
                    if any((self._call_elapsed(run, t) or 0) > run["config"]["call_timeout_seconds"] for t in running):
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
        from .services import pipeline_run
        with self._db() as db:
            run = self._read_run(db, run_id)
            try:
                self._validate_reusable_initial(db, run["initial_id"])
            except AnalysisContractError as exc:
                run.update(status="recovery_required", error=exc.code)
                self._write_run(db, run)
                return
        pipeline_run.drive(self, run_id)
