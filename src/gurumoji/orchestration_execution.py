from __future__ import annotations

import copy
import json
import math
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from .analysis_core import AnalysisContractError, fingerprint
from .orchestration_shared import (
    AI_ROLES,
    INITIAL_SECTIONS,
    LABEL_FIELDS,
    METHODS,
    TERMINAL,
    ExecutionStopped,
    _error,
    _id,
    _json,
    _now,
    _scope,
)
from .services import artifact_review
from .services.orchestration_required_methods import LABEL_METHODS


class ExecutionMixin:
    def _register(self, db, run, intent: dict, *, phase: str, automatic=False) -> dict | None:
        binding = None
        if intent.get("input_artifacts"):
            artifact_review.reject("入力束縛はHandlerだけが作成します。")
        if intent.get("kind") == "finding_review":
            binding = self.resolve_review_input(db, run, intent)
            if any(d != binding["task_id"] for d in intent.get("dependencies", [])):
                artifact_review.reject("初期レビューの依存は生成済みの先行所見1件だけです。")
            intent = {**copy.deepcopy(intent), "scope": copy.deepcopy(binding["interval"]),
                      "dependencies": [binding["task_id"]]}
        elif intent.get("review_target_result_id") or intent.get("artifact_purpose"):
            artifact_review.reject("先行所見の指定は専用レビュー依頼だけに許可されます。")
        if run["config"].get("analysis_interval_version") and _scope(intent).get("interval_id"):
            from .services.analysis_intervals import interval_scope
            supplied = intent["scope"]
            known_intervals = run["analysis_partition"]["intervals"] + run.get("interval_refinements", [])
            interval = next((i for i in known_intervals if i["interval_id"] == supplied["interval_id"]), None)
            canonical_scope = interval_scope(interval, blind=intent["role"] == "verification") if interval else None
            if supplied != canonical_scope:
                raise _error("タスクの区間と固定所属が一致しません。", "interval_scope_invalid")
            intent = copy.deepcopy(intent)
            intent["evidence_ids"] = supplied["owned_evidence_ids"] + supplied["boundary_evidence_ids"]
        if (run["config"].get("analysis_interval_version") and intent.get("role") in {"interpretation", "verification", "critic"}
                and intent.get("kind", "analysis") != "clarification"
                and phase not in {"initial_labels", "label_review", "stop_review"}
                and not _scope(intent).get("interval_id")):
            from .services.analysis_intervals import check_partition, interval_scope
            partition = run.get("analysis_partition")
            if not partition:
                raise _error("原文の区間が確定していません。", "interval_missing")
            check_partition(partition, run["config"], run["input_hash"])
            selected = set(intent.get("evidence_ids", []))
            requested = intent.get("interval_ids", _scope(intent).get("interval_ids", []))
            available = {i["interval_id"] for i in partition["intervals"]}
            if not isinstance(requested, list) or any(i not in available for i in requested):
                raise _error("存在する区間IDを指定してください。", "interval_missing")
            # A cited row selects its owning interval, never just the citation.
            intervals = [i for i in partition["intervals"] if (not requested or i["interval_id"] in requested)
                         and (not selected or selected.intersection(i["owned_evidence_ids"]))]
            if not intervals:
                raise _error("対象区間がありません。", "interval_missing")
            first_task = None
            for interval in intervals:
                if interval["status"] != "ready":
                    self._stop(db, run, "interval_unprocessable")
                    return first_task
                child = copy.deepcopy(intent)
                scope = interval_scope(interval, blind=intent["role"] == "verification")
                child.update(scope=scope, evidence_ids=scope["owned_evidence_ids"] + scope["boundary_evidence_ids"])
                task = self._register(db, run, child, phase=phase, automatic=automatic)
                first_task = first_task or task
                if run["status"] in TERMINAL:
                    break
            return first_task
        role = intent.get("role")
        if role not in AI_ROLES | {"statistics"}:
            raise _error("未対応の専門家です。", "invalid_intent")
        method = intent.get("method_id") or ("participation" if role == "statistics" else "agent-v1")
        if (method == "cross_tabulation" and "cross_tabulation" in run["config"].get("required_methods", [])
                and intent.get("label_field", "codes") != "codes"):
            raise _error("必須クロス集計の列はcodesに固定されています。", "required_method_spec_mismatch")
        if method == "cross_tabulation" and intent.get("scope"):
            raise _error("クロス集計の部分範囲は根拠IDで指定してください。", "method_scope_unavailable")
        if role == "statistics" and method not in LABEL_METHODS and (intent.get("evidence_ids") or intent.get("scope") or intent.get("label_dependent")):
            raise _error("既存コード計算は初期版の全範囲専用です。部分範囲・ラベル再計算は未対応です。", "method_scope_unavailable")
        if method in LABEL_METHODS and (role != "statistics" or intent.get("label_field", "codes") not in LABEL_FIELDS):
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
        if intent.get("kind", "analysis") not in {"analysis", "clarification", "finding_review", ""}:
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
        label_dependent = bool(intent.get("label_dependent", False)) if role != "statistics" else method in LABEL_METHODS
        identity = {"input": run["input_hash"], "annotation_version": run["annotation_version"] if label_dependent else None,
                    "role": role, "method": method, "question": question.strip(), "evidence_ids": sorted(evidence_ids),
                    "scope": intent.get("scope"), "label_field": intent.get("label_field", "codes") if method in LABEL_METHODS else None, "target_id": intent.get("target_id"), "target_version": intent.get("target_version"),
                    "evidence_version": fingerprint([run["input_hash"], run["annotation_version"]]) if role == "critic" else intent.get("evidence_version", run["input_hash"]), "replicate_id": intent.get("replicate_id") or None,
                    "round": run["iteration"] if role == "core" else None, "options": run["config"]["roles"].get(role), "kind": intent.get("kind", "analysis"), "result_id": intent.get("result_id"), "initial_sections": intent.get("initial_sections", []),
                    "dependencies": sorted(dependencies)}
        key = fingerprint(identity)
        if binding:
            identity["input_artifacts"] = [binding]
            key = fingerprint(identity)
        existing = db.execute("SELECT state_json FROM orchestration_tasks WHERE run_id=? AND idempotency_key=?", (run["run_id"], key)).fetchone()
        if existing:
            task = json.loads(existing[0])
            self._event(db, run["run_id"], "duplicate_suppressed", "同じ入力・目的・対象版のタスクを再発注しません。", task_id=task["task_id"])
            return None
        if run["config"].get("specialist_orchestration_version") and role == "statistics" and method in {"participation", "conversation_dynamics"} and phase != "initial_analysis":
            reusable = next((t for t in tasks if t["role"] == "statistics" and t["method_id"] == method and t["status"] == "succeeded" and t["dataset_version"] == run["input_hash"]), None)
            if reusable:
                self._event(db, run["run_id"], "duplicate_suppressed", "固定入力の同じ全件集計は保存済み結果を参照し、再計算しません。", task_id=reusable["task_id"], result_id=reusable["result_id"])
                return None
        if role == "statistics" and method == "cross_tabulation" and (not evidence_ids or set(evidence_ids) == valid_evidence):
            reusable = next((t for t in tasks if t["role"] == "statistics" and t["method_id"] == method
                and t["status"] == "succeeded" and t.get("validation_status") == "valid" and not t.get("stale")
                and t["dataset_version"] == run["input_hash"] and t["annotation_version"] == run["annotation_version"]
                and t["codebook_version"] == run["codebook_version"]
                and (t["intent"].get("label_field") or "codes") == (intent.get("label_field") or "codes")
                and not t["intent"].get("scope")
                and (not t["intent"].get("evidence_ids") or set(t["intent"]["evidence_ids"]) == valid_evidence)), None)
            if reusable:
                self._event(db, run["run_id"], "duplicate_suppressed", "同じ対象・列・ラベル版のクロス集計は保存結果を参照します。",
                            task_id=reusable["task_id"], result_id=reusable["result_id"])
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
        if binding:
            task["input_artifacts"] = [copy.deepcopy(binding)]
        db.execute("INSERT INTO orchestration_tasks VALUES (?,?,?,?)", (task["task_id"], run["run_id"], key, _json(task)))
        self._event(db, run["run_id"], "task_registered", task["title"], target=role, task_id=task["task_id"])
        return task

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
        if "context_manifest" in data:
            manifest = copy.deepcopy(data["context_manifest"])
            with self._db() as db:
                run = self._read_run(db, run_id)
                task = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=? AND run_id=?",
                                             (task_id, run_id)).fetchone()[0])
                if manifest.get("version") != (artifact_review.MANIFEST_VERSION if run["config"].get("artifact_review_version") else 1) or manifest.get("dataset_version") != run["input_hash"]:
                    raise _error("入力パケットの版が一致しません。", "context_manifest_invalid")
                scope = _scope(task["intent"])
                if scope.get("interval_id") and (manifest.get("analysis_interval") != scope or
                        set(scope["owned_evidence_ids"] + scope["boundary_evidence_ids"]) != set(manifest.get("provided_evidence_ids", []))):
                    raise _error("担当原文または文脈原文が入力から欠落しています。", "context_manifest_invalid")
                if manifest.get("evidence_transport_version") == 1:
                    from .services.model_context import digest
                    mapping = manifest.get("reference_map")
                    if not isinstance(mapping, dict) or digest(mapping) != manifest.get("reference_map_sha256"):
                        raise _error("根拠対応表のhashが一致しません。", "context_manifest_invalid")
                pending = self._review_pending(db, run, task)
                if task.get("input_artifacts"):
                    binding, _ = self._recheck_review_binding(db, run, task)
                    from .services.model_context import digest, transform_references
                    packet = self.build_review_resources(db, run, task, self._base_context(db, run, task))["finding_resource"]
                    mapping = manifest.get("reference_map")
                    packet_hash = digest(transform_references(packet, mapping)) if mapping is not None else digest(packet)
                    if (manifest.get("input_artifacts") != [binding]
                            or manifest.get("finding_packet_sha256") != packet_hash or manifest.get("review_procedure") != binding["procedure"]):
                        artifact_review.reject("資料packetと入力manifestの束縛が不正です。", "context_manifest_invalid")
                if run["config"].get("artifact_review_version") and task["role"] == "orchestrator":
                    candidates, omitted = self._artifact_candidates(db, run, task["intent"]["scope"]["domain"])
                    presented = manifest.get("artifact_candidates", [])
                    expected_omitted = omitted + len(candidates) - len(presented)
                    if (presented != candidates[:len(presented)] or candidates and not presented
                            or manifest.get("artifact_candidate_scope", {}).get("omitted_count") != expected_omitted):
                        artifact_review.reject("候補の提示範囲と未提示件数が不正です。", "context_manifest_invalid")
                requested = manifest.get("requested_result_ids", [])
                if task["role"] in {"core", "orchestrator"} and task["phase"] != "initial_routing" and (requested != pending[:len(requested)] or pending and not requested):
                    raise _error("未評価結果の先頭から順に処理してください。", "context_manifest_invalid")
                task["context_manifest"] = manifest
                task["context_manifest_hash"] = fingerprint(manifest)
                self._write_task(db, task)
                self._event(db, run_id, "context_prepared", "入力範囲とモデルの予算を保存しました。",
                            task_id=task_id, context_manifest_hash=task["context_manifest_hash"])
            return
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
            if task.get("input_artifacts"):
                try:
                    self._recheck_review_binding(db, run, task)
                except AnalysisContractError as exc:
                    task.update(status="failed", validation_status="rejected", error=exc.code, ended_at=_now())
                    self._write_task(db, task)
                    self._event(db, run_id, "preflight_rejected", exc.code, task_id=task_id)
                    run["error"] = exc.code
                    self._stop(db, run, "execution_failure")
                    return
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
            ai_snapshot = self._initial(db, run["initial_id"]) if task["kind"] == "ai" else None
            experts = ai_snapshot["analysis"].get("experts") if ai_snapshot and run["config"].get("model_context_version") and task["role"] == "interpretation" else None
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
                if task["phase"] == "initial_analysis":
                    # Existing code methods use saved participation/time/label
                    # fields; they do not invent new research scales.
                    raw = {**raw, "label_requirements": [],
                           "requirement_scope": "既存の入力項目による集計。研究概念の尺度設計は専門家の報告を参照する。"}
                    if (task["method_id"] == "label_frequency" and raw.get("denominator", 0) > 0
                            and raw.get("missing_count") == raw["denominator"] and context["raw_evidence"]):
                        raw["label_requirements"] = [{"requirement_id": "codes_for_frequency", "kind": "label",
                            "name": "研究質問に対応する分類ラベル", "analysis": "研究質問に対応する分類別の度数集計",
                            "reason": f"既存codesは対象{raw['denominator']}発話の全件が欠測で、分類別集計ができない。原文に基づく定義と、その後の発話への付与が必要。",
                            "evidence_ids": [context["raw_evidence"][0]["evidence_id"]]}]
            else:
                references = run["config"].get("context_reference_version") == 1
                brief = None
                if run["config"].get("model_context_version") and task["role"] == "interpretation" and not task.get("input_artifacts") and (references or task["phase"] != "initial_labels"):
                    from . import method_experts
                    if method_experts.ai_block_reason(experts):
                        raise _error("選択した専門家のAI補助条件が未成立です。", "expert_knowledge_unavailable")
                    try:
                        brief = method_experts.ai_context(experts, step_ids=run["config"].get("expert_step_ids"))
                    except method_experts.ExpertDefinitionError:
                        raise _error("専門家の定義・知識・許可手順を再確認してください。", "expert_knowledge_unavailable") from None
                    context["expert_knowledge"] = {"version": 1, "stage": task["phase"],
                        "status": "method_brief" if brief else "generic", "brief": brief}
                if references and not task.get("input_artifacts"):
                    from . import method_experts
                    try:
                        context["expert_knowledge"] = method_experts.orchestration_context(stage=task["phase"], brief=brief)
                    except method_experts.ExpertDefinitionError:
                        raise _error("参照するObsidian知識のID・状態・必須節・入力上限を確認してください。", "expert_knowledge_unavailable") from None
                    context["resources_origin"] = {"initial_id": run["initial_id"], "run_id": run["run_id"]}
                options = {**copy.deepcopy(run["config"]), **run["config"]["roles"][task["role"]], "timeout_seconds": run["config"]["call_timeout_seconds"],
                           "deadline": run["deadline"], "research_mode": "exploratory", "provider_policy": run["config"]["provider_policy"]}
                options["_run_id"] = run_id
                options["_reference_evidence"] = [
                    {key: row[key] for key in ("evidence_id", "utterance_id")}
                    for row in ai_snapshot["evidence"] if not row["excluded"]]
                if (run["config"].get("model_context_version") or run["config"].get("analysis_interval_version")) and task["role"] in {"core", "orchestrator"} and task["phase"] != "initial_routing":
                    options["_source_evidence"] = [{key: row[key] for key in ("evidence_id", "utterance_id", "text", "speaker", "start", "end")}
                        for row in ai_snapshot["evidence"] if not row["excluded"]]
                from .services.model_context import ReferenceResponseError
                reference_error = ""
                try:
                    raw = self.agent_runner(task["role"], context, options, check,
                                            lambda usage=None, **kw: self._record_usage(run_id, task_id, usage, **kw))
                except ReferenceResponseError as exc:
                    raw, reference_error = exc.response, exc.code
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
                scope = _scope(task["intent"])
                if scope.get("interval_id"):
                    metadata["interval_lineage"] = {k: scope.get(k) for k in
                        ("interval_id", "parent_interval_id", "parent_topic_id", "dataset_version", "ownership_sha256")}
                if task["kind"] == "ai" and reference_error:
                    metadata["reference_error"] = reference_error
                if task.get("input_artifacts"):
                    metadata["derived_from"] = copy.deepcopy(task["input_artifacts"])
                    metadata["independent_verification"] = False
                if (latest["config"].get("model_context_version") or latest["config"].get("analysis_interval_version")) and task["kind"] == "ai":
                    stored_task = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (task_id,)).fetchone()[0])
                    metadata["context_manifest_hash"] = stored_task.get("context_manifest_hash")
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
                before_dispatch = getattr(exc, "code", "") in {"context_budget_exceeded", "context_budget_unavailable", "context_manifest_invalid", "expert_knowledge_unavailable", "artifact_input_invalid", "result_integrity_mismatch", "provider_unavailable", "evidence_index_unavailable", "template_invalid"}
                owned = current["intent"].get("scope", {}).get("owned_evidence_ids", []) if isinstance(current["intent"].get("scope"), dict) else []
                latest = self._read_run(db, run_id)
                if (getattr(exc, "code", "") == "context_budget_exceeded" and current["phase"] in {"initial_routing", "initial_labels"}
                        and latest["config"].get("model_context_version") and latest["status"] not in TERMINAL):
                    selected_keys = _scope(current["intent"]).get("requirement_keys")
                    if selected_keys is None:
                        selected_keys = [fingerprint(entry) for entry in latest["initial_analysis_report"]["label_requirements"]]
                    if len(selected_keys) > 1:
                        child_phase = current["phase"]
                        current.update(status="blocked", phase=child_phase + "_split", ended_at=_now(), error="context_requirement_split")
                        self._write_task(db, current)
                        latest["calls_started"] -= 1
                        for keys in (selected_keys[:len(selected_keys) // 2], selected_keys[len(selected_keys) // 2:]):
                            intent = copy.deepcopy(current["intent"])
                            intent.update(parent_task_id=task_id, scope={"requirement_keys": keys, "split_from_task_id": task_id})
                            if child_phase == "initial_labels":
                                requirements = [entry for entry in latest["initial_analysis_report"]["label_requirements"] if fingerprint(entry) in keys]
                                intent["evidence_ids"] = sorted({ref for entry in requirements for ref in entry["evidence_ids"]})
                            self._register(db, latest, intent, phase=child_phase, automatic=True)
                        self._write_run(db, latest)
                        self._event(db, run_id, "context_requirement_split", "必須要件を保持したまま、Coreへの報告を分割して保存しました。", task_id=task_id)
                        return
                if (getattr(exc, "code", "") == "context_budget_exceeded" and not current.get("input_artifacts") and (current["phase"] == "initial_analysis" or
                        _scope(current["intent"]).get("interval_id"))
                        and len(owned) > 1 and latest["status"] not in TERMINAL):
                    child_phase = current["phase"]
                    current.update(status="blocked", phase=child_phase + "_split", ended_at=_now(), error="context_page_split")
                    self._write_task(db, current)
                    rows = [e["evidence_id"] for e in self._initial(db, latest["initial_id"])["evidence"] if not e["excluded"]]
                    latest["calls_started"] -= 1  # This attempt never reached inference.
                    for part in (owned[:len(owned) // 2], owned[len(owned) // 2:]):
                        first, last = rows.index(part[0]), rows.index(part[-1]) + 1
                        visible = rows[max(0, first - 1):min(len(rows), last + 1)]
                        intent = copy.deepcopy(current["intent"])
                        intent.update(evidence_ids=visible, parent_task_id=task_id,
                            scope={"owned_evidence_ids": part, "boundary_evidence_ids": [ref for ref in visible if ref not in part],
                                   "split_from_task_id": task_id})
                        if latest["config"].get("analysis_interval_version"):
                            from .services.analysis_intervals import make_interval, interval_scope
                            pool = [e for e in self._initial(db, latest["initial_id"])["evidence"] if not e["excluded"]]
                            parent = current["intent"]["scope"]
                            source_interval = next(i for i in latest["analysis_partition"]["intervals"] + latest.get("interval_refinements", [])
                                                   if i["interval_id"] == parent["interval_id"])
                            interval = make_interval(pool, first, last, dataset_version=latest["input_hash"],
                                parent_topic_id=parent["parent_topic_id"], title=source_interval.get("title", ""),
                                method="budget_split", parent_interval_id=parent["interval_id"])
                            refinements = latest.setdefault("interval_refinements", [])
                            if not any(i["interval_id"] == interval["interval_id"] for i in refinements):
                                refinements.append(interval)
                            intent["scope"] = interval_scope(interval, blind=current["role"] == "verification")
                        self._register(db, latest, intent, phase=child_phase, automatic=True)
                    self._write_run(db, latest)
                    self._event(db, run_id, "context_page_split", "未送信の範囲を分割し、次の専門家タスクとして保存しました。", task_id=task_id)
                    return
                current.update(status="uncertain" if task["kind"] == "ai" and not before_dispatch else "failed", ended_at=_now(), error=getattr(exc, "code", type(exc).__name__))
                self._write_task(db, current)
                if before_dispatch:
                    latest["calls_started"] -= 1
                    self._write_run(db, latest)
                if latest["status"] not in TERMINAL and task["kind"] == "ai" and not before_dispatch:
                    latest.update(status="recovery_required", error="外部呼出しの実行結果が不明です。自動再試行しません。")
                    self._write_run(db, latest)
                event = "preflight_rejected" if before_dispatch else "execution_uncertain" if task["kind"] == "ai" else "task_failed"
                self._event(db, run_id, event, getattr(exc, "code", type(exc).__name__), task_id=task_id)

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
                self._check_input_manifest(run, task, meta)
                if meta.get("reference_error"):
                    raise _error("対応表にない根拠参照です。", "evidence_missing")
                if len(row["raw_json"].encode("utf-8")) > run["config"]["max_result_bytes"]:
                    raise _error("結果が保存上限を超えています。", "result_size_limit")
                if run["status"] in TERMINAL:
                    raise _error("停止後の結果は採用しません。", "late_response_after_stop")
                metric_validation = self._validate_result(db, run, task, raw)
                if task['kind'] == 'ai' and run['config'].get('evidence_mode', 'sql') == 'hybrid':
                    from .services.evidence_retrieval import resolve_citations
                    source = self._initial(db, run['initial_id'])
                    sources = [{key: e[key] for key in ('evidence_id', 'utterance_id', 'text', 'speaker', 'start', 'end')}
                               for e in source['evidence'] if not e['excluded']]
                    manifest = task.get('context_manifest')
                    allowed = set(manifest['citation_ids']) if manifest else {
                        e['evidence_id'] for e in self._context(db, run, task).get('raw_evidence', [])}
                    meta['evidence_resolution'] = resolve_citations(sources, raw, allowed_ids=allowed,
                        dataset_version=run['input_hash'], row_limit=run['config']['context_evidence_limit'],
                        text_limit=run['config']['context_text_limit'])
                    self._event(db, run_id, 'evidence_sql_resolved', 'AIの引用IDからSQLで原文を取得しました。',
                                task_id=task_id, source_count=len(meta['evidence_resolution']['sources']))
                if metric_validation is not None:
                    meta["metric_validation"] = metric_validation
                    self._event(db, run_id, "metric_codec_validated", "統計専用デコーダーで参照・演算・集計値を検証しました。",
                        source="handler", target="orchestrator", task_id=task_id,
                        profile=metric_validation["profile"], state_sha256=metric_validation["state_sha256"],
                        decoded_item_count=len(metric_validation["items"]), metric_status=metric_validation["status"])
                meta.update(validation_status="valid", error="")
                if task["role"] == "statistics" and task["method_id"] == "cross_tabulation":
                    meta["calculation"] = {key: raw[key] for key in
                        ("availability", "denominator", "observed_count", "missing_count")}
                task.update(status="succeeded", validation_status="valid", error="")
                if task.get("input_artifacts"):
                    scope = task["input_artifacts"][0]["interval"]
                    meta["review_status"] = "insufficient" if any(r["verdict"] == "insufficient" for r in raw["claim_verdicts"]) else "checked_in_scope"
                    meta["claim_evidence_scope"] = [{"claim_id": r["claim_id"],
                        "owned_evidence_ids": [e for e in r["evidence_ids"] if e in scope["owned_evidence_ids"]],
                        "boundary_evidence_ids": [e for e in r["evidence_ids"] if e in scope["boundary_evidence_ids"]]}
                        for r in raw["claim_verdicts"]]
                if task["role"] == "critic":
                    self._save_issues(db, run, task, raw, meta)
                for patch in raw.get("label_patches", []):
                    self._save_patch(db, run, task, patch, meta)
                delegated = run["config"].get("specialist_orchestration_version") and task["role"] not in {"core", "orchestrator"}
                self._event(db, run_id, "result_validated", "保存済み・形式確認済みとして専門側へ渡します。" if delegated else "保存済み・内容未検証としてCoreへ渡します。",
                            source="handler", target="orchestrator" if delegated else "core", task_id=task_id)
                if task["phase"] == "initial_analysis":
                    self._event(db, run_id, "initial_requirements_reported", "初回分析の結果とラベル・尺度の必要性をハンドラーが受領しました。",
                                source=task["role"], target="handler", task_id=task_id,
                                result_id=meta["result_id"], raw_hash=meta["raw_hash"],
                                requirement_count=len(raw["label_requirements"]))
            except (AnalysisContractError, ValueError, TypeError, KeyError) as exc:
                code = getattr(exc, "code", "invalid_result")
                meta.update(validation_status="quarantined", error=code)
                task.update(status="quarantined", validation_status="quarantined", error=code)
                self._event(db, run_id, "result_quarantined", code, task_id=task_id)
                if (code == "initial_label_definitions_invalid" and task["phase"] == "initial_labels"
                        and run["status"] not in TERMINAL
                        and _scope(task["intent"]).get("repair_attempt", 0) < run["config"].get("label_repair_limit", 0)):
                    intent = copy.deepcopy(task["intent"])
                    definitions = raw.get("label_definitions")
                    rejected = set()
                    for definition in definitions if isinstance(definitions, list) else []:
                        levels = definition.get("levels") if isinstance(definition, dict) else None
                        for entry in levels if isinstance(levels, list) else []:
                            value = entry.get("value") if isinstance(entry, dict) else None
                            if isinstance(value, str) and value.strip().casefold() in {"欠測", "未読", "missing", "null", "none", "n/a"}:
                                rejected.add(value.strip().casefold())
                    intent["scope"] = {**_scope(intent), "repair_attempt": 1,
                        "definition_feedback": {"rejected_result_id": meta["result_id"], "forbidden_values": sorted(rejected),
                            "instruction": "受理検査で不合格です。欠測を表す分類値を削除し、実質値2件以上・型・尺度水準・欠測の分離を満たす定義を作り直してください。"}}
                    intent.update(parent_task_id=task_id, replicate_id="label-repair:" + meta["result_id"])
                    child = self._register(db, run, intent, phase="initial_labels", automatic=True)
                    if child is not None:
                        task["phase"] = "initial_labels_rejected"
                        self._event(db, run_id, "label_definition_repair", "隔離した尺度下書きの修正を1回だけ別タスクで依頼しました。",
                                    task_id=child["task_id"], rejected_result_id=meta["result_id"])
            db.execute("UPDATE orchestration_results SET state_json=? WHERE result_id=?", (_json(meta), meta["result_id"]))
            self._write_task(db, task)

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

