from __future__ import annotations

import copy
import json

from .orchestration_initial import validate_ready_initial
from .analysis_core import (
    EFFECTIVE_PUBLICATION_WRITERS,
    AnalysisContractError,
    fingerprint,
)
from .orchestration_initial import initial_progress, read_initial_checkpoints
from .orchestration_shared import (
    AI_ROLES,
    ROLES,
    TERMINAL,
    _error,
    _json,
    _now,
    _read_events,
)
from .services.orchestration_required_methods import required_progress
from .services.orchestration_task_completion import analysis_processing_tasks_complete


class LedgerProjectionMixin:
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

    def _public(self, db, run, events_after=None):
        result = copy.deepcopy(run)
        result["config"].setdefault("publication_targets", [])
        result["config"]["effective_publication_writers"] = list(EFFECTIVE_PUBLICATION_WRITERS) if result["config"]["publication_targets"] else []
        result["initial"] = initial_progress(db, run["initial_id"])
        initial_reusable = True
        if self.initial_builder is not None and result["initial"]["status"] == "ready":
            try:
                validate_ready_initial(db, run["initial_id"], self.initial_builder)
            except AnalysisContractError as exc:
                initial_reusable = False
                result["initial"].update(status="revalidation_required", stored_status="ready", recovery_error=exc.code)
        result["initial_stages"] = result["initial"]["stages"]
        tasks = self._tasks(db, run["run_id"])
        result["tasks"] = tasks
        decision = db.execute("SELECT result_id FROM orchestration_decisions WHERE run_id=? AND decision_id=?",
                              (run["run_id"], run.get("last_decision_id"))).fetchone()
        result["analysis_result_id"] = decision[0] if decision else None
        result["required_methods_progress"] = self._required_methods_progress(db, run, tasks=tasks)
        if run.get("analysis_partition"):
            from .services.analysis_intervals import progress
            result["interval_progress"] = progress(run["analysis_partition"], tasks)
        result["completed_core_iterations"] = self._completed_core_iterations(db, run)
        if run["config"].get("initial_label_definitions_version"):
            try:
                result["initial_label_catalog"] = self._initial_label_catalog(db, run)
            except AnalysisContractError as exc:
                result["initial_label_catalog"] = None
                result["initial_label_error"] = exc.code
        if run.get("initial_analysis_report"):
            result["initial_analysis_report"] = copy.deepcopy(run["initial_analysis_report"])
        events, reset = _read_events(db, run["run_id"], events_after)
        result["events"] = events
        if events_after is not None:
            result["events_reset"] = reset
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
        result["can_resume"] = run["status"] in {"queued", "recovery_required"} and not uncertain and initial_reusable
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

    def _analysis_processing_tasks_complete(self, db, run):
        tasks = self._tasks(db, run["run_id"])
        results = [json.loads(row[0]) for row in db.execute(
            "SELECT state_json FROM orchestration_results WHERE run_id=? ORDER BY rowid", (run["run_id"],))]
        decisions = [json.loads(row[0]) for row in db.execute(
            "SELECT payload_json FROM orchestration_decisions WHERE run_id=? ORDER BY rowid", (run["run_id"],))]
        return analysis_processing_tasks_complete(run, tasks, results, decisions)

    def _required_methods_progress(self, db, run, *, tasks=None):
        methods = run["config"].get("required_methods", [])
        if not methods:
            return []
        results = [json.loads(row[0]) for row in db.execute(
            "SELECT state_json FROM orchestration_results WHERE run_id=? ORDER BY rowid", (run["run_id"],))]
        decisions = [json.loads(row[0]) for row in db.execute(
            "SELECT payload_json FROM orchestration_decisions WHERE run_id=? ORDER BY rowid", (run["run_id"],))]
        return required_progress(methods, self._tasks(db, run["run_id"]) if tasks is None else tasks,
            results, decisions, dataset_version=run["input_hash"], annotation_version=run["annotation_version"],
            codebook_version=run["codebook_version"], run_stale=run.get("stale", False))

    def status(self, item_id: str, run_id: str, events_after: int | None = None) -> dict:
        item = self.find_item(item_id)
        if item is None:
            raise LookupError("会話が見つかりません。")
        with self._db() as db:
            run = self._read_run(db, run_id, item_id)
            if self.source_fingerprint and (item is None or self.source_fingerprint(item) != run["input_hash"]):
                run["stale"] = True
                self._write_run(db, run)
            return self._public(db, run, events_after=events_after)

    def history(self, item_id: str) -> list[dict]:
        if self.find_item(item_id) is None:
            raise LookupError("会話が見つかりません。")
        with self._db() as db:
            return [self._public(db, json.loads(row[0])) for row in db.execute(
                "SELECT state_json FROM orchestration_runs WHERE item_id=? AND coalesce(json_extract(state_json, '$.config.adapter_version'), '') != 'core-pipeline-1' ORDER BY rowid DESC", (item_id,)).fetchall()]

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

