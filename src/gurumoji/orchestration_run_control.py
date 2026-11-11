from __future__ import annotations

import copy
import hashlib
import json
import time
import unicodedata
from difflib import SequenceMatcher

from .orchestration_initial import validate_ready_initial
from .analysis_core import AnalysisContractError, fingerprint
from .orchestration_shared import (
    IMPORTANCE,
    INITIAL_METHODS,
    TERMINAL,
    ExecutionStopped,
    _error,
    _id,
    _json,
    _now,
)
from .services.orchestration_required_methods import (
    LABEL_METHODS,
    required_method_intent,
)


class RunControlMixin:
    def _schedule_required_methods(self, db, run):
        registered = False
        for progress in self._required_methods_progress(db, run):
            if progress["status"] not in {"not_run", "stale"}:
                continue
            intent = required_method_intent(progress["id"], run["config"]["question"])
            if progress["id"] in LABEL_METHODS:
                intent["replicate_id"] = f"required-a{run['annotation_version']}-c{run['codebook_version']}"
            if self._register(db, run, intent, phase="required_methods", automatic=True):
                registered = True
            if run["status"] in TERMINAL:
                break
        return registered

    def _record_critique_responses(self, db, run, raw, decision_id):
        for response in raw.get("critique_responses", []):
            value = {**response, "response_id": _id("response"), "decision_id": decision_id, "created_at": _now()}
            db.execute("INSERT OR IGNORE INTO orchestration_responses VALUES (?,?,?,?,?)", (value["response_id"], run["run_id"], response["issue_id"], decision_id, _json(value)))
            issue = json.loads(db.execute("SELECT payload_json FROM orchestration_issues WHERE issue_id=?", (response["issue_id"],)).fetchone()[0])
            issue.update(status="adopted_unresolved" if response["disposition"] == "adopt" else response["disposition"], latest_response=value)
            db.execute("UPDATE orchestration_issues SET payload_json=? WHERE issue_id=?", (_json(issue), issue["issue_id"]))

    def _apply_specialist_review(self, db, run, task, raw, meta):
        metric_validation = self._validate_result(db, run, task, raw)
        decision = {**copy.deepcopy(raw), "decision_id": _id("decision"), "role": "orchestrator",
            "phase": "specialist_review", "domain": task["intent"]["scope"]["domain"],
            "result_id": meta["result_id"], "task_id": task["task_id"], "iteration": run["iteration"],
            "annotation_version": task["annotation_version"], "created_at": _now()}
        if metric_validation is not None:
            decision.update(model_summary=raw["summary"], summary=metric_validation["answer"],
                            metric_validation=metric_validation)
        if run["config"].get("artifact_review_version"):
            candidates = task["context_manifest"].get("artifact_candidates", [])
            index = {c["result_id"]: c for c in candidates}
            decision["presented_artifact_candidates"] = copy.deepcopy(candidates)
            decision["unpresented_artifact_count"] = task["context_manifest"].get("artifact_candidate_scope", {}).get("omitted_count", 0)
            history = {r["result_id"]: r for r in self._artifact_history(db, run, decision["domain"])}
            decision["artifact_decisions"] = [{**copy.deepcopy(r), "raw_hash": index[r["result_id"]]["raw_hash"],
                "information_hash": index[r["result_id"]]["information_hash"], "receiving_domain": decision["domain"],
                "previous_decision_id": history.get(r["result_id"], {}).get("decision_id", ""),
                "issuance": "not_requested" if r["disposition"] != "use" else "pending", "issued_task_id": ""}
                for r in raw.get("artifact_decisions", [])]
        if run["config"].get("analysis_interval_version"):
            groups = {}
            for assessment in raw["result_assessments"]:
                source = db.execute("SELECT state_json FROM orchestration_results WHERE result_id=? AND run_id=?",
                                    (assessment["result_id"], run["run_id"])).fetchone()
                lineage = json.loads(source[0]).get("interval_lineage") if source else None
                if lineage:
                    groups.setdefault(lineage["parent_topic_id"], []).append({**lineage,
                        "source_result_id": assessment["result_id"], "disposition": assessment["disposition"]})
            decision["topic_sources"] = groups
        if run["config"].get("artifact_review_version"):
            decision["review_results"] = []
            for assessment in raw["result_assessments"]:
                source = db.execute("SELECT raw_json,state_json FROM orchestration_results WHERE result_id=? AND run_id=?",
                                    (assessment["result_id"], run["run_id"])).fetchone()
                source_raw, source_meta = json.loads(source[0]), json.loads(source[1])
                if source_meta.get("derived_from"):
                    decision["review_results"].append({"result_id": source_meta["result_id"], "raw_hash": source_meta["raw_hash"],
                        "derived_from": source_meta["derived_from"], "input_manifest_hash": source_meta.get("context_manifest_hash"),
                        "interval_lineage": source_meta.get("interval_lineage"), "claim_verdicts": source_raw["claim_verdicts"],
                        "claim_evidence_scope": source_meta.get("claim_evidence_scope", []), "review_status": source_meta.get("review_status"),
                        "missing_inputs": source_raw["missing_inputs"], "limitations": source_raw["limitations"],
                        "disposition": assessment["disposition"], "independent_verification": False})
        self._commit_labels(db, run, raw.get("label_decisions", []), task=task, result_id=meta["result_id"], decision_id=decision["decision_id"])
        self._record_critique_responses(db, run, raw, decision["decision_id"])
        db.execute("INSERT INTO orchestration_decisions VALUES (?,?,?,?)", (decision["decision_id"], run["run_id"], meta["result_id"], _json(decision)))
        self._event(db, run["run_id"], "specialist_review_committed", raw["summary"], source="orchestrator", target="handler",
                    task_id=task["task_id"], domain=decision["domain"], assessed_result_ids=[a["result_id"] for a in raw["result_assessments"]])
        for intent in raw.get("intents", []):
            artifact_choice = next((r for r in decision.get("artifact_decisions", []) if r["disposition"] == "use"), None)
            def record_issuance(reason, issued_task=None):
                if artifact_choice is not None:
                    artifact_choice.update(issuance="issued" if issued_task else "not_issued",
                        not_issued_reason="" if issued_task else reason,
                        issued_task_id=issued_task["task_id"] if issued_task else "")
                    db.execute("UPDATE orchestration_decisions SET payload_json=? WHERE decision_id=?",
                               (_json(decision), decision["decision_id"]))
            if run["status"] in TERMINAL:
                record_issuance(run["stop_reason"])
                return
            domain = task["intent"]["scope"]["domain"]
            pending = self._review_pending(db, run, task)
            parents = {t["task_id"] for t in self._tasks(db, run["run_id"])
                       if t["role"] == "orchestrator" and t["intent"]["scope"]["domain"] == domain and t["iteration"] == task["iteration"]}
            issued = any(t["phase"] == "specialist_followup" and t.get("parent_task_id") in parents for t in self._tasks(db, run["run_id"]))
            if pending or issued:
                record_issuance("pending_results" if pending else "followup_already_issued")
                self._event(db, run["run_id"], "intent_deferred", "分野内の保存結果を先に読むため、またはこの段階の追加依頼を既に発注したため保留しました。",
                            intent=intent, review_result_id=meta["result_id"], remaining_result_count=len(pending))
                continue
            if run["config"]["stop_mode"] == "importance" and IMPORTANCE.get(intent.get("importance"), 0) < IMPORTANCE[run["config"]["importance_threshold"]]:
                record_issuance("importance_threshold")
                self._event(db, run["run_id"], "intent_deferred", "重要度の閾値未満の専門側の依頼を保存しました。", intent=intent, review_result_id=meta["result_id"])
                continue
            question = " ".join(unicodedata.normalize("NFKC", intent["question"]).casefold().split())
            original = " ".join(unicodedata.normalize("NFKC", run["config"]["question"]).casefold().split())
            similar = question == original or len(original) >= 30 and SequenceMatcher(None, question, original, autojunk=False).ratio() >= .85
            if intent.get("kind", "analysis") == "analysis" and not intent.get("label_dependent") and similar:
                record_issuance("same_question")
                self._event(db, run["run_id"], "intent_deferred", "元の問いと同一または文字列が近い再発注案を保留しました。具体的な不足を調べる問いが必要です。", intent=intent, review_result_id=meta["result_id"])
                continue
            if intent["role"] == "critic":
                intent = {**intent, "target_id": "view:" + run["run_id"], "target_version": run["view_version"]}
            if intent.get("kind") == "finding_review":
                intent = {**intent, "artifact_decision_id": decision["decision_id"]}
            issued_task = self._register(db, run, {**intent, "parent_task_id": task["task_id"]}, phase="specialist_followup")
            record_issuance(run.get("stop_reason") or "duplicate_suppressed", issued_task)
        run["phase"] = "specialists"
        self._write_run(db, run)

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
        self._check_input_manifest(run, task, meta)
        if task["role"] == "orchestrator":
            self._apply_specialist_review(db, run, task, raw, meta)
            return
        progress = None
        if run["config"].get("initial_label_definitions_version"):
            self._validate_result(db, run, task, raw)
        if run["config"].get("core_progress_version"):
            # Recheck the review references at the durable adoption boundary too.
            self._validate_result(db, run, task, raw)
            history = [json.loads(row[0]) for row in db.execute(
                "SELECT payload_json FROM orchestration_decisions WHERE run_id=? ORDER BY rowid", (run["run_id"],))
                if json.loads(row[0]).get("phase") != "initial_routing" and json.loads(row[0]).get("role", "core") == "core"]
            signature = self._core_progress_signature(raw)
            repeated = next((old for old in reversed(history)
                             if self._core_progress_signature(old) == signature
                             and old.get("after_annotation_version") == run["annotation_version"]), None)
            new_responses = [response["issue_id"] for response in raw.get("critique_responses", [])
                             if not db.execute("SELECT 1 FROM orchestration_responses WHERE run_id=? AND issue_id=?",
                                               (run["run_id"], response["issue_id"])).fetchone()]
            previous_proposals = {entry["proposal_id"] for old in history for entry in old.get("label_decisions", [])}
            new_labels = [entry["proposal_id"] for entry in raw.get("label_decisions", [])
                          if entry["proposal_id"] not in previous_proposals]
            assessments = [entry["result_id"] for entry in raw.get("result_assessments", [])]
            fresh_basis = self._new_result_basis(db, run, history, assessments)
            domain_reports = self._domain_reports(db, run) if run["config"].get("specialist_orchestration_version") else []
            domain_ids = [r["result_id"] for r in domain_reports]
            previous_domain_ids = {rid for old in history for rid in old.get("domain_report_ids", [])}
            # A new review ID is not new evidence. Reuse the same source/version/
            # scope/hash comparison as legacy review, including explicit repeats.
            previous_sources = [{"result_assessments": [{"result_id": rid} for rid in report["source_result_ids"]]}
                                for report in domain_reports if report["result_id"] in previous_domain_ids]
            fresh_basis.extend(self._new_result_basis(db, run, previous_sources,
                [rid for report in domain_reports if report["result_id"] not in previous_domain_ids for rid in report["source_result_ids"]]))
            prior_results = [entry["result_id"] for d in history for entry in d.get("result_assessments", [])]
            prior_results += [entry["result_id"] for d in previous_sources for entry in d["result_assessments"]]
            current_results = assessments + [rid for report in domain_reports if report["result_id"] not in previous_domain_ids for rid in report["source_result_ids"]]
            new_review_checks = self._new_review_checks(db, run, prior_results, current_results) if run["config"].get("artifact_review_version") else []
            reviewed_human_stop = (
                run.get("completion_protocol_version") and (raw.get("stop") or {}).get("reason") == "human_review_required"
                and not raw.get("intents") and run["reviewed_stop_versions"]
                and not self._pending_result_assessments(db, run)
                and self._analysis_processing_tasks_complete(db, run)
                and not db.execute("SELECT 1 FROM orchestration_issues WHERE run_id=? AND issue_id NOT IN "
                                   "(SELECT issue_id FROM orchestration_responses WHERE run_id=?) LIMIT 1",
                                   (run["run_id"], run["run_id"])).fetchone())
            if repeated and not reviewed_human_stop and not (fresh_basis or new_responses or new_labels or new_review_checks):
                meta.update(content_status="no_progress", repeated_decision_id=repeated["decision_id"])
                db.execute("UPDATE orchestration_results SET state_json=? WHERE result_id=?", (_json(meta), meta["result_id"]))
                self._event(db, run["run_id"], "core_no_progress",
                            "同じ根拠・判断・作業案の繰り返しを検出しました。進展として数えず停止します。",
                            task_id=task["task_id"], result_id=meta["result_id"],
                            repeated_decision_id=repeated["decision_id"], completed_core_iterations=len(history))
                self._stop(db, run, "no_progress")
                return
            progress = {"signature": signature, "assessed_result_ids": assessments,
                        "new_result_basis_ids": fresh_basis,
                        "new_review_check_ids": new_review_checks,
                        "responded_issue_ids": new_responses, "decided_proposal_ids": new_labels}
        decision = {**copy.deepcopy(raw), "decision_id": _id("decision"), "result_id": meta["result_id"],
                    "iteration": run["iteration"], "created_at": _now(),
                    "task_id": task["task_id"], "annotation_version": task["annotation_version"],
                    "before_annotation_version": run["annotation_version"],
                    "role": task["role"], "model": task.get("model"), "provider": task.get("provider")}
        if progress is not None:
            decision["progress"] = progress
            if run["config"].get("specialist_orchestration_version"):
                decision["domain_report_ids"] = domain_ids
        if run.get("initial_label_result_id"):
            decision["initial_label_result_id"] = run["initial_label_result_id"]
        self._commit_labels(db, run, raw.get("label_decisions", []), task=task,
                            result_id=meta["result_id"], decision_id=decision["decision_id"])
        decision["after_annotation_version"] = run["annotation_version"]
        self._record_critique_responses(db, run, raw, decision["decision_id"])
        claims_changed = bool(raw.get("claims")) and fingerprint(raw.get("claims", [])) != fingerprint(run["current_view"].get("claims", []))
        next_view = {"summary": raw.get("summary", ""), "claims": raw.get("claims", []),
                     "alternatives": raw.get("alternatives", []), "unresolved": raw.get("unresolved", [])}
        view_changed = next_view != run["current_view"]
        if run["config"].get("core_progress_version"):
            claims_changed = bool(raw.get("claims")) and self._core_progress_signature({"claims": raw["claims"]}) != self._core_progress_signature({"claims": run["current_view"].get("claims", [])})
            view_changed = not run["last_decision_id"] or self._core_progress_signature(next_view) != self._core_progress_signature(run["current_view"])
        if view_changed:
            run["view_version"] += 1
            run["current_view"] = next_view
            for row in db.execute("SELECT issue_id,payload_json FROM orchestration_issues WHERE run_id=?", (run["run_id"],)).fetchall():
                issue = json.loads(row[1])
                view_issue = not run["config"].get("specialist_orchestration_version") or issue["target_id"] == "view:" + run["run_id"]
                if view_issue and str(issue["target_version"]) != str(run["view_version"]):
                    issue["stale"] = True
                    db.execute("UPDATE orchestration_issues SET payload_json=? WHERE issue_id=?", (_json(issue), row[0]))
        decision["view_version"] = run["view_version"]
        db.execute("INSERT INTO orchestration_decisions VALUES (?,?,?,?)", (decision["decision_id"], run["run_id"], meta["result_id"], _json(decision)))
        run["last_decision_id"] = decision["decision_id"]
        self._event(db, run["run_id"], "core_decision", raw.get("summary", "Core判断を保存しました。"), source="core", target="handler", task_id=task["task_id"])
        if run["config"].get("core_progress_version") and self._pending_result_assessments(db, run):
            run["phase"] = "core"
            self._event(db, run["run_id"], "result_assessments_continued", "未提示の専門家結果の採否を次の判断で確認します。")
            self._write_run(db, run)
            return
        intents = raw.get("intents", [])
        if raw.get("stop") and any(not p["complete"] for p in self._required_methods_progress(db, run)):
            if self._schedule_required_methods(db, run):
                run["phase"] = "specialists"
                self._write_run(db, run)
            elif run["status"] not in TERMINAL:
                self._stop(db, run, "required_methods_incomplete")
            return
        if raw.get("stop") and not (intents and run.get("completion_protocol_version")):
            proposal = {**raw["stop"], "target_id": "view:" + run["run_id"], "target_version": run["view_version"],
                        "decision_id": decision["decision_id"], "unexecuted_intents": intents}
            # A reviewer cannot veto indefinitely. A reviewed unchanged view needs
            # only Core's explicit reasoned responses; no repeated critic call.
            reviewed = run["view_version"] in run["reviewed_stop_versions"]
            unanswered = db.execute("SELECT issue_id FROM orchestration_issues WHERE run_id=? AND issue_id NOT IN (SELECT issue_id FROM orchestration_responses WHERE run_id=?)",
                                    (run["run_id"], run["run_id"])).fetchall()
            # 分析処理の完了と、人による改訂版の確認待ちを区別する。
            # 前版をレビュー済みでも、改訂版を確認済みとは表示しない。
            tasks_finished = self._analysis_processing_tasks_complete(db, run)
            if (run.get("completion_protocol_version") and (raw["stop"]["reason"] == "human_review_required" or not reviewed)
                    and run["reviewed_stop_versions"] and not unanswered and tasks_finished
                    and not self._pending_result_assessments(db, run)):
                run["pending_stop"] = proposal
                if self._continue_minimum_iterations(db, run, raw["stop"]["reason"]):
                    return
                run["analysis_processing_complete"] = True
                run["human_review_status"] = "required"
                run["model_stop_reason"] = raw["stop"]["reason"]
                if not reviewed:
                    run["review_status"] = "incomplete"
                self._stop(db, run, "human_review_required")
                return
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

    def run(self, run_id: str) -> None:
        """Drive the initial stages and Core phases without duplicate local drivers."""
        with self._worker_lock:
            if run_id in self._driving:
                return
            self._driving.add(run_id)
        try:
            if self.execution_driver is not None:
                with self._db() as db:
                    run = self._read_run(db, run_id)
                    needs_driver = run["status"] not in TERMINAL and run["status"] != "recovery_required"
                if needs_driver:
                    self.execution_driver(
                        run_id, lambda: self._build_initial(run_id),
                        lambda: self._driver_evidence(run_id), lambda: self._run_analysis(run_id))
            elif self._build_initial(run_id):
                self._run_analysis(run_id)
            self._notify_completed(run_id)
        except Exception:
            if self.execution_driver is None:
                raise
            with self._db() as db:
                run = self._read_run(db, run_id)
                if run["status"] not in TERMINAL and run["status"] != "recovery_required":
                    run["error"] = "maf_driver_failed"
                    self._event(db, run_id, "driver_failed", "MAF分析の実行接続で停止しました。")
                    if any(task["status"] in {"running", "uncertain"} for task in self._tasks(db, run_id)):
                        run["status"] = "recovery_required"
                        self._write_run(db, run)
                    else:
                        self._stop(db, run, "execution_failure")
        finally:
            with self._worker_lock:
                self._driving.discard(run_id)

    def _driver_evidence(self, run_id):
        with self._db() as db:
            run = self._read_run(db, run_id)
            self._check_version(run)
            snapshot = self._initial(db, run["initial_id"])
            self._event(db, run_id, "driver_attached", "MAFとSQLで固定根拠の分析を開始します。",
                        driver="gurumoji-maf-dev-v1")
            return [row for row in snapshot["evidence"] if not row["excluded"]]

    def _prepare_intervals(self, run_id):
        """Freeze run-owned AI drafts and ownership without altering the input."""
        from .services import analysis_intervals as intervals
        from .services.model_context import digest
        with self._db() as db:
            run = self._read_run(db, run_id)
            if not run["config"].get("analysis_interval_version"):
                return
            if run.get("analysis_partition"):
                intervals.check_partition(run["analysis_partition"], run["config"], run["input_hash"])
                return
            if run.get("interval_preparation", {}).get("status") == "running":
                raise _error("議題生成の実行結果を照合してください。自動再生成しません。", "interval_recovery_required")
            initial = self._initial(db, run["initial_id"])
            rows = [e for e in initial["evidence"] if not e["excluded"]]
            source_outline = initial.get("source_outline")
            original = initial.get("archive_snapshot", {}).get("original_source", {}).get("segments")
            matched = isinstance(source_outline, dict) and (source_outline.get("dataset_version") == run["input_hash"]
                or original is not None and source_outline.get("provenance", {}).get("input_sha256") == hashlib.sha256(
                    json.dumps(original, ensure_ascii=False, sort_keys=True).encode()).hexdigest())
            outline = copy.deepcopy(source_outline) if matched else {"sections": []}
            spans = intervals.candidate_spans(rows, outline)
            config, generation = copy.deepcopy(run["config"]), run["generation"]
            run["interval_preparation"] = {"status": "running", "source_outline_sha256": digest(source_outline),
                                            "source_outline_matched": matched, "drafts": []}
            self._write_run(db, run)

        check = lambda: self._check(run_id, generation)

        def before_call():
            check()
            with self._db() as db:
                current = self._read_run(db, run_id)
                if current["calls_started"] >= config["max_calls"]:
                    raise _error("議題生成の呼出し予算が不足しています。", "context_budget_unavailable")
                current["calls_started"] += 1
                self._write_run(db, current)

        # Reuse valid explicit boundaries. Refine coarse topics; gaps and legacy
        # citation-only outlines are separate generation jobs on the same source.
        jobs, cursor = [], 0
        for first, last, topic, title in spans:
            if cursor < first:
                jobs.append((cursor, first, None, "generated"))
            if last - first > config["context_evidence_limit"] - 2 or sum(len(r["text"]) for r in rows[first:last]) > config["context_text_limit"]:
                jobs.append((first, last, topic, "refined"))
            cursor = last
        if cursor < len(rows):
            jobs.append((cursor, len(rows), None, "generated"))
        drafts = []
        for first, last, parent, method in jobs:
            check()
            if parent:
                replaced = {r["utterance_id"] for r in rows[first:last]}
                outline["sections"] = [s for s in outline["sections"] if s.get("start_segment_id") not in replaced]
            draft = {"generation_run_id": _id("outline"), "owner_run_id": run_id, "method": method,
                     "dataset_version": run["input_hash"], "owned_utterance_ids": [r["utterance_id"] for r in rows[first:last]],
                     "status": "unavailable", "reason": "outline_builder_unavailable"}
            if self.outline_builder is not None:
                segments = [{"id": r["utterance_id"], "text": r["text"], "speaker": r["speaker"],
                             "start": r["start"], "end": r["end"]} for r in rows[first:last]]
                try:
                    generated = self.outline_builder(segments, outline if matched else None, config, check, before_call,
                                                     lambda usage: None)
                    check()
                    if (not isinstance(generated, dict) or not generated.get("sections")
                            or len(intervals.candidate_spans(rows[first:last], generated)) != len(generated["sections"])):
                        raise _error("議題境界が対象発話と一致しません。", "outline_invalid")
                    generated = copy.deepcopy(generated)
                    for section in generated["sections"]:
                        section["partition_method"] = method
                    if parent:
                        for section in generated["sections"]:
                            section["parent_topic_id"] = parent
                        replaced = {r["utterance_id"] for r in rows[first:last]}
                        outline["sections"] = [s for s in outline["sections"] if s.get("start_segment_id") not in replaced]
                    outline["sections"].extend(generated["sections"])
                    draft.update(status="ai_draft", reason="", outline=generated, sha256=digest(generated))
                except ExecutionStopped:
                    raise
                except Exception as exc:
                    # Failed/unavailable candidates fall back to time; do not
                    # expose provider exception text or retry cancelled work.
                    check()
                    draft.update(status="failed", reason=getattr(exc, "code", type(exc).__name__))
            if parent and draft["status"] != "ai_draft":
                outline["sections"].append({"title": "", "parent_topic_id": parent, "partition_method": "time",
                    "start_segment_id": rows[first]["utterance_id"], "end_segment_id": rows[last - 1]["utterance_id"]})
            drafts.append(draft)
            with self._db() as db:
                current = self._read_run(db, run_id)
                current["interval_preparation"]["drafts"] = copy.deepcopy(drafts)
                self._write_run(db, current)
        check()
        partition = intervals.build_partition(rows, outline, dataset_version=run["input_hash"],
            time_width=config["analysis_interval_seconds"], row_limit=config["context_evidence_limit"],
            text_limit=config["context_text_limit"], outline_method="existing" if matched else "generated",
            provenance={"source_outline_sha256": digest(source_outline), "source_outline_matched": matched,
                        "drafts": [{k: v for k, v in d.items() if k != "outline"} for d in drafts]})
        partition["excluded_utterance_ids"] = [e["utterance_id"] for e in initial["evidence"] if e["excluded"]]
        partition["sha256"] = digest({k: v for k, v in partition.items() if k != "sha256"})
        with self._db() as db:
            current = self._read_run(db, run_id)
            if current["status"] in TERMINAL or current["generation"] != generation:
                raise ExecutionStopped()
            current.update(analysis_partition=partition)
            current["interval_preparation"]["status"] = "ready"
            self._write_run(db, current)
            self._event(db, run_id, "analysis_intervals_frozen", "分析区間と全発話の所属を固定しました。", partition_sha256=partition["sha256"])
            if any(i["status"] != "ready" for i in partition["intervals"]):
                current.update(status="recovery_required", error="時刻不正または1発話の入力上限超過があります。固定入力を確認して新規実行してください。")
                self._write_run(db, current)

    def _initial_specialist_intents(self, db, run):
        rows = [e for e in self._initial(db, run["initial_id"])["evidence"] if not e["excluded"]]
        pages = []
        if run["config"].get("analysis_interval_version"):
            from .services.analysis_intervals import interval_scope
            pages = [{"evidence_ids": i["owned_evidence_ids"] + i["boundary_evidence_ids"], "scope": interval_scope(i)}
                     for i in run["analysis_partition"]["intervals"]]
        elif run["config"].get("model_context_version"):
            start = 0
            while start < len(rows):
                end, size = start, 0
                while end < len(rows) and end - start < run["config"]["context_evidence_limit"]:
                    length = len(rows[end]["text"])
                    if end > start and size + length > run["config"]["context_text_limit"]:
                        break
                    size += length
                    end += 1
                owned = [e["evidence_id"] for e in rows[start:end]]
                visible = [e["evidence_id"] for e in rows[max(0, start - 1):min(len(rows), end + 1)]]
                pages.append({"evidence_ids": visible, "scope": {"page_number": len(pages) + 1,
                              "owned_evidence_ids": owned, "boundary_evidence_ids": [ref for ref in visible if ref not in owned]}})
                start = end
        else:
            pages = [{}]
        intents = []
        for role in ("interpretation", "verification", "critic"):
            for page in pages:
                page = copy.deepcopy(page)
                if role == "verification" and "scope" in page:
                    page["scope"].pop("title", None)
                intents.append({"role": role, "question": "初回の専門分析: " + run["config"]["question"],
                    **copy.deepcopy(page),
                    **({"target_id": run["initial_id"], "target_version": 0} if role == "critic" else {})})
        intents.extend({"role": "statistics", "method_id": method,
                       "question": "初回の数量・統計: " + method, "label_field": "codes"}
                       for method in sorted(INITIAL_METHODS))
        return intents

    def _run_analysis(self, run_id: str) -> None:
        """Drive persisted phases; safe to call synchronously with mock adapters."""
        try:
            with self._db() as db:
                run = self._read_run(db, run_id)
                if run["status"] in TERMINAL or run["status"] == "recovery_required":
                    return
                self._check_version(run)
                if self.initial_builder is not None:
                    validate_ready_initial(db, run["initial_id"], self.initial_builder)
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
            self._prepare_intervals(run_id)
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
                    if phase == "core" and run["iteration"] == 0 and run["config"].get("initial_label_definitions_version"):
                        if not run.get("initial_label_result_id"):
                            if run["config"].get("initial_specialist_analysis_version"):
                                initial_intents = self._initial_specialist_intents(db, run)
                                for initial_intent in initial_intents:
                                    self._register(db, run, initial_intent, phase="initial_analysis", automatic=True)
                                    if run["status"] in TERMINAL:
                                        return
                                run["phase"] = phase = "initial_analysis"
                            else:
                                self._register(db, run, {"role": "interpretation", "method_id": "label-design-v1",
                                    "question": "初回のラベル・尺度を設計する: " + run["config"]["question"],
                                    "importance": "high"}, phase="initial_labels", automatic=True)
                                run["phase"] = phase = "initial_labels"
                            self._write_run(db, run)
                    if run["config"].get("specialist_orchestration_version") and phase in {"core", "specialists"}:
                        if self._schedule_required_methods(db, run):
                            run["phase"] = phase = "specialists"
                            self._write_run(db, run)
                            tasks = self._tasks(db, run_id)
                        if run["status"] in TERMINAL:
                            return
                        pending = self._pending_result_assessments(db, run)
                        if pending:
                            queued = [t for t in tasks if t["role"] == "orchestrator" and t["status"] == "queued"]
                            if not queued:
                                domain = self._result_domain(db, pending[0])
                                batch = [rid for rid in pending if self._result_domain(db, rid) == domain][:20]
                                self._register(db, run, {"role": "orchestrator", "method_id": "result-review-v1",
                                    "question": "担当分野の保存結果を評価して具体的な所見と限界を報告する",
                                    "scope": {"domain": domain, "result_ids": batch}}, phase="specialist_review", automatic=True)
                            if run["status"] in TERMINAL:
                                return
                            run["phase"] = phase = "specialist_review"
                            self._write_run(db, run)
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
                    if run["config"].get("specialist_orchestration_version") and any(
                            t["phase"] == "specialist_followup" and t["status"] in {"failed", "quarantined", "blocked"}
                            and not t["stale"] for t in tasks):
                        self._stop(db, run, "execution_failure"); return
                    if run["phase"] == "initial_analysis":
                        try:
                            run["initial_analysis_report"] = self._collect_initial_analysis(db, run)
                        except AnalysisContractError as exc:
                            run["error"] = exc.code
                            self._stop(db, run, "initial_analysis_incomplete"); return
                        self._event(db, run_id, "initial_analysis_aggregated", "全専門家の初回分析と尺度要件を集約してCoreへ報告しました。",
                                    source="handler", target="core", report_count=len(run["initial_analysis_report"]["reports"]),
                                    requirement_count=len(run["initial_analysis_report"]["label_requirements"]))
                        self._register(db, run, {"role": "core", "question": "初回の尺度要件を担当へ振り分ける: " + run["config"]["question"],
                            "dependencies": [report["task_id"] for report in run["initial_analysis_report"]["reports"]]},
                            phase="initial_routing", automatic=True)
                        if run["status"] in TERMINAL:
                            return
                        run["phase"] = "initial_routing"
                        self._write_run(db, run)
                    elif run["phase"] == "initial_routing":
                        routing_tasks = [t for t in tasks if t["phase"] == "initial_routing"]
                        if not routing_tasks or any(t["status"] != "succeeded" for t in routing_tasks):
                            self._stop(db, run, "initial_routing_invalid"); return
                        for task in routing_tasks:
                            self._apply_initial_routing(db, run, task)
                            if run["status"] in TERMINAL:
                                return
                    elif run["phase"] == "initial_labels":
                        label_tasks = [t for t in tasks if t["phase"] == "initial_labels"]
                        if not label_tasks or any(t["status"] != "succeeded" for t in label_tasks):
                            self._stop(db, run, "initial_labels_missing"); return
                        task = label_tasks[0]
                        run["initial_label_result_id"] = task["result_id"]
                        if run["config"].get("model_context_version"):
                            run["initial_label_result_ids"] = [t["result_id"] for t in label_tasks]
                        catalog = self._initial_label_catalog(db, run)
                        self._event(db, run_id, "initial_labels_created", "専門家による初回のラベル・尺度定義をAI下書きとして保存しました。",
                                    source="interpretation", target="core", result_id=catalog["result_id"], raw_hash=catalog["raw_hash"])
                        if run["config"].get("specialist_orchestration_version"):
                            references = sorted({ref for definition in catalog["definitions"] for ref in definition["evidence_ids"]})
                            self._register(db, run, {"role": "critic", "question": "初回のラベル・尺度下書きを独立に検証する。欠測を低水準に含めていないか、否定の発話を高評価にしていないか、基準と尺度水準の妥当性を確認する。",
                                "scope": "label_review", "evidence_ids": references, "dependencies": [t["task_id"] for t in label_tasks],
                                "target_id": "labels:" + catalog["result_id"], "target_version": run["annotation_version"]}, phase="label_review", automatic=True)
                            if run["status"] in TERMINAL:
                                return
                            run["phase"] = "label_review"
                        else:
                            run["phase"] = "core"
                        self._write_run(db, run)
                    elif run["phase"] == "label_review":
                        reviews = [t for t in tasks if t["phase"] == "label_review"]
                        if not reviews or any(t["status"] != "succeeded" for t in reviews):
                            self._stop(db, run, "label_review_incomplete"); return
                        run["phase"] = "specialists"
                        self._write_run(db, run)
                    elif run["phase"] == "specialist_review":
                        reviews = [t for t in tasks if t["role"] == "orchestrator" and t["phase"] == "specialist_review" and t.get("result_id")
                            and not db.execute("SELECT 1 FROM orchestration_decisions WHERE result_id=?", (t["result_id"],)).fetchone()]
                        if not reviews or any(t["status"] != "succeeded" for t in reviews):
                            self._stop(db, run, "specialist_review_incomplete"); return
                        for task in reviews:
                            result = db.execute("SELECT * FROM orchestration_results WHERE task_id=?", (task["task_id"],)).fetchone()
                            self._apply_core(db, run, task, result)
                            if run["status"] in TERMINAL:
                                return
                    elif run["phase"] == "core":
                        task = next((t for t in reversed(tasks) if t["role"] == "core" and t["iteration"] == run["iteration"]), None)
                        if task is None or task["status"] != "succeeded":
                            reason = "unreviewed_results" if task and task.get("error") == "result_assessment_missing" else "execution_failure"
                            self._stop(db, run, reason); return
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
                        run["phase"] = "specialists" if run["config"].get("specialist_orchestration_version") else "core"
                        self._write_run(db, run)
                    else:
                        run["phase"] = "core"
                        self._write_run(db, run)
        except Exception as exc:
            with self._db() as db:
                run = self._read_run(db, run_id)
                if run["status"] not in TERMINAL:
                    run["error"] = getattr(exc, "code", type(exc).__name__)
                    if run["error"] == "initial_revalidation_required":
                        run["status"] = "recovery_required"
                        self._write_run(db, run)
                    else:
                        self._stop(db, run, "execution_failure")

