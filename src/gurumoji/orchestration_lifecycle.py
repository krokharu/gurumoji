from __future__ import annotations

import copy
import json
import threading
import time

from .analysis_core import fingerprint, validate_publication_targets
from .orchestration_initial import (
    create_initial_checkpoints,
    read_initial_checkpoints,
    stage_input_hash,
    write_stage,
)
from .orchestration_payload import validate_orchestration_payload
from .orchestration_shared import SCHEMA_VERSION, TERMINAL, _error, _id, _json, _now


class LifecycleMixin:
    def start(self, item_id: str, payload: dict, app_url: str = "") -> dict:
        config = validate_orchestration_payload(payload)
        request_id = payload.get("request_id") or _id("request")
        if not isinstance(request_id, str) or len(request_id) > 200:
            raise _error("request_idが正しくありません。")
        if self.find_item(item_id) is None:
            raise LookupError("会話が見つかりません。")
        if config.get("source_analysis_id"):
            from .services.analysis_history import AnalysisHistoryService
            from .services.analysis_reanalysis import freeze_reanalysis
            viewer = AnalysisHistoryService(connect=self.connect, find_item=self.find_item)
            with self._db() as db:
                config["reanalysis"] = freeze_reanalysis(viewer, item_id, config["source_analysis_id"],
                    config["human_prompt"], connection=db)
                for key, actual in (("expected_source_result_id", "source_result_id"), ("expected_source_raw_hash", "raw_hash")):
                    if key in config and config[key] != config["reanalysis"][actual]:
                        raise _error("確認後に参照結果が変わりました。参照結果を確認し直してください。",
                                     "revision_conflict", "source_analysis_id")
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
        if config.get("reanalysis") and before is not None and config["reanalysis"]["input_hash"] != before:
            raise _error("参照結果の入力版が現在の会話と異なります。現在の入力で分析してから結果IDを指定してください。",
                         "revision_conflict", "source_analysis_id")
        if self.initial_builder is not None:
            return self._start_staged(item_id, payload, config, request_id, request_hash, app_url, item, before)
        snapshot = None
        if before is None:
            snapshot = self.snapshot_builder(item)
            before = snapshot.get("input_hash")
        if payload.get("input_hash") is not None and payload["input_hash"] != before:
            raise _error("確認した入力hashが更新されています。", "revision_conflict", "input_hash")
        if config.get("reanalysis") and config["reanalysis"]["input_hash"] != before:
            raise _error("参照結果の入力版が現在の会話と異なります。", "revision_conflict", "source_analysis_id")
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
        run = {"schema_version": SCHEMA_VERSION, "label_audit_version": 1, "completion_protocol_version": 1 if config.get("core_progress_version") else 0, "run_id": run_id, "item_id": item_id, "request_id": request_id,
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
            run = {"schema_version": SCHEMA_VERSION, "label_audit_version": 1, "completion_protocol_version": 1 if config.get("core_progress_version") else 0, "run_id": run_id, "item_id": item_id, "request_id": request_id,
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
            if not (run["status"] == "completed" or (run["status"] == "stopped" and run.get("stop_reason") == "human_review_required" and run.get("analysis_processing_complete") is True)) or run.get("completion_callback_status"):
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
                if task.get("input_artifacts"):
                    self._recheck_review_binding(db, run, task)
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

