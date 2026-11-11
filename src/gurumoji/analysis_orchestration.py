"""Durable, evidence-linked exploratory Core/Handler orchestration.

The Handler is the only execution authority. Injected agents return data (intents,
results and decisions); they never receive executors or mutable application state.
SQLite is the source of truth. An interrupted external call is explicitly uncertain,
not retried: recovery may adopt an already-received raw response or abandon a call.
This module does not send data, publish notes, or change source annotations itself.
"""
from __future__ import annotations

import copy as copy
from difflib import SequenceMatcher as SequenceMatcher
import json as json
import hashlib as hashlib
import math as math
import sqlite3 as sqlite3
import threading as threading
import time as time
import uuid as uuid
import unicodedata as unicodedata
from concurrent.futures import ThreadPoolExecutor as ThreadPoolExecutor, wait as wait, FIRST_COMPLETED as FIRST_COMPLETED
from contextlib import contextmanager as contextmanager
from datetime import datetime as datetime, timezone as timezone
from typing import Any as Any, Callable as Callable

from .orchestration_shared import SCHEMA_VERSION as SCHEMA_VERSION, ROLES as ROLES, AI_ROLES as AI_ROLES, INITIAL_SECTIONS as INITIAL_SECTIONS, LABEL_FIELDS as LABEL_FIELDS, INITIAL_METHODS as INITIAL_METHODS, METHODS as METHODS, TERMINAL as TERMINAL, IMPORTANCE as IMPORTANCE, _id as _id, _now as _now, _json as _json, _error as _error, _scope as _scope, _read_events as _read_events, ExecutionStopped as ExecutionStopped
from .orchestration_payload import validate_orchestration_payload as validate_orchestration_payload

from .orchestration_ledger_projection import LedgerProjectionMixin as LedgerProjectionMixin
from .orchestration_lifecycle import LifecycleMixin as LifecycleMixin
from .orchestration_review_context import ReviewContextMixin as ReviewContextMixin
from .orchestration_execution import ExecutionMixin as ExecutionMixin
from .orchestration_result_validation import ResultValidationMixin as ResultValidationMixin
from .orchestration_run_control import RunControlMixin as RunControlMixin

from .analysis_core import AnalysisContractError as AnalysisContractError, canonical as canonical, fingerprint as fingerprint, validate_publication_targets as validate_publication_targets, validate_label_definitions as validate_label_definitions, EFFECTIVE_PUBLICATION_WRITERS as EFFECTIVE_PUBLICATION_WRITERS
from .analysis_templates import selection_valid as selection_valid
from .services import artifact_review as artifact_review
from .services.orchestration_required_methods import validate_required_methods as validate_required_methods, required_method_intent as required_method_intent, required_progress as required_progress, LABEL_METHODS as LABEL_METHODS
from .services.orchestration_task_completion import analysis_processing_tasks_complete as analysis_processing_tasks_complete
from .orchestration_initial import initialize_initial_checkpoints as initialize_initial_checkpoints, create_initial_checkpoints as create_initial_checkpoints, read_initial_checkpoints as read_initial_checkpoints, stage_input_hash as stage_input_hash, write_stage as write_stage, initial_progress as initial_progress, recover_initial_checkpoints as recover_initial_checkpoints


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
    CREATE INDEX IF NOT EXISTS orchestration_events_run_seq ON orchestration_events(run_id,seq);
    CREATE INDEX IF NOT EXISTS orchestration_results_run ON orchestration_results(run_id);
    CREATE INDEX IF NOT EXISTS orchestration_decisions_run ON orchestration_decisions(run_id);
    CREATE INDEX IF NOT EXISTS orchestration_usage_run ON orchestration_usage(run_id);
    CREATE INDEX IF NOT EXISTS orchestration_responses_run ON orchestration_responses(run_id);
    CREATE INDEX IF NOT EXISTS orchestration_label_proposals_run ON orchestration_label_proposals(run_id);
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





class AnalysisOrchestrationService(
    RunControlMixin,
    ResultValidationMixin,
    ExecutionMixin,
    ReviewContextMixin,
    LifecycleMixin,
    LedgerProjectionMixin,
):
    def __init__(self, *, connect: Callable[[], sqlite3.Connection] | None = None,
                 database_connection: Callable[[], sqlite3.Connection] | None = None,
                 find_item: Callable[[str], Any], snapshot_builder: Callable[[Any], dict[str, Any]],
                 agent_runner: Callable[..., Any], method_runner: Callable[..., Any],
                 source_fingerprint: Callable[[Any], str] | None = None,
                 write_lock: Any = None, schedule: bool = True, adapter_version: str = "core-handler-prompts-1",
                 initial_builder: Any = None, on_complete: Callable[[str, str], Any] | None = None,
                 outline_builder: Callable[..., Any] | None = None,
                 execution_driver: Callable[..., Any] | None = None):
        self.connect = connect or database_connection
        if self.connect is None:
            raise TypeError("connect is required")
        self.find_item, self.snapshot_builder = find_item, snapshot_builder
        self.agent_runner, self.method_runner = agent_runner, method_runner
        self.source_fingerprint, self.schedule = source_fingerprint, schedule
        self.adapter_version = adapter_version
        self.initial_builder, self.on_complete = initial_builder, on_complete
        self.outline_builder = outline_builder
        self.execution_driver = execution_driver
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
        if run.get("analysis_partition"):
            from .services.analysis_intervals import check_partition
            check_partition(run["analysis_partition"], run["config"], run["input_hash"])
        if run.get("schema_version") != SCHEMA_VERSION:
            raise _error("保存されたrunの形式版が異なります。元の版で復旧してください。", "schema_version_conflict")
        if run["config"].get("adapter_version") != self.adapter_version:
            raise _error("モデル指示の版が変わりました。新しいrunを開始してください。", "adapter_version_conflict")
        if run["config"].get("artifact_review_version"):
            from .method_experts import counterexample_review_procedure
            procedure = counterexample_review_procedure()
            if run["config"].get("artifact_procedure") != {k: procedure[k] for k in ("procedure_id", "version", "sha256")}:
                raise _error("反例点検の手順版が変わりました。", "artifact_input_invalid")

