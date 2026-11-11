from __future__ import annotations

import copy
import json
import unicodedata

from .analysis_core import AnalysisContractError, fingerprint
from .orchestration_shared import (
    INITIAL_SECTIONS,
    LABEL_FIELDS,
    SCHEMA_VERSION,
    _error,
    _json,
    _scope,
)
from .services import artifact_review


class ReviewContextMixin:
    def _completed_core_iterations(self, db, run):
        # Count adopted decisions, never queued attempts or quarantined results.
        return sum(json.loads(row[0]).get("phase") != "initial_routing" and json.loads(row[0]).get("role", "core") == "core" for row in db.execute(
            "SELECT payload_json FROM orchestration_decisions WHERE run_id=?", (run["run_id"],)))

    def _pending_result_assessments(self, db, run):
        assessed = {entry["result_id"] for row in db.execute(
            "SELECT payload_json FROM orchestration_decisions WHERE run_id=?", (run["run_id"],))
            for entry in json.loads(row[0]).get("result_assessments", [])}
        return [meta["result_id"] for row in db.execute(
            "SELECT state_json FROM orchestration_results WHERE run_id=? ORDER BY rowid", (run["run_id"],))
            if (meta := json.loads(row[0]))["role"] not in {"core", "orchestrator"}
            and meta["validation_status"] == "valid" and not meta.get("stale")
            and meta["result_id"] not in assessed]

    def _review_pending(self, db, run, task):
        pending = self._pending_result_assessments(db, run)
        if task["role"] != "orchestrator":
            return pending
        domain = task["intent"]["scope"]["domain"]
        return [rid for rid in pending if self._result_domain(db, rid) == domain]

    @staticmethod
    def _result_domain(db, result_id):
        row = db.execute("SELECT t.state_json,r.raw_json FROM orchestration_tasks t JOIN orchestration_results r ON r.task_id=t.task_id WHERE r.result_id=?", (result_id,)).fetchone()
        task = json.loads(row[0])
        return "labels" if task["phase"] == "initial_labels" or task.get("intent", {}).get("scope") == "label_review" or json.loads(row[1]).get("label_patches") else task["role"]

    def _domain_reports(self, db, run):
        reports = []
        events = [json.loads(r[0]) for r in db.execute("SELECT payload_json FROM orchestration_events WHERE run_id=?", (run["run_id"],))]
        followups = self._tasks(db, run["run_id"])
        for (encoded,) in db.execute("SELECT payload_json FROM orchestration_decisions WHERE run_id=? ORDER BY rowid", (run["run_id"],)):
            decision = json.loads(encoded)
            if decision.get("role") != "orchestrator":
                continue
            row = db.execute("SELECT raw_json,state_json FROM orchestration_results WHERE result_id=?", (decision["result_id"],)).fetchone()
            meta = json.loads(row[1])
            if meta["validation_status"] != "valid" or fingerprint(json.loads(row[0])) != meta["raw_hash"]:
                raise _error("専門オーケストレータ報告の整合性を確認できません。", "result_integrity_mismatch")
            task = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (meta["task_id"],)).fetchone()[0])
            self._check_input_manifest(run, task, meta)
            reports.append({"domain": decision["domain"], "task_id": meta["task_id"], "result_id": meta["result_id"], "raw_hash": meta["raw_hash"],
                "source_result_ids": [a["result_id"] for a in decision["result_assessments"]],
                "summary": decision["summary"], "claims": decision.get("claims", []),
                "alternatives": decision.get("alternatives", []), "unresolved": decision.get("unresolved", []),
                "dispositions": {value: sum(a["disposition"] == value for a in decision["result_assessments"]) for value in ("adopt", "reject", "defer")},
                "annotation_version": decision["annotation_version"], "status": "ai_draft", "read_scope": "specialist_result_review"})
            if decision.get("topic_sources"):
                reports[-1]["topic_sources"] = copy.deepcopy(decision["topic_sources"])
            if run["config"].get("artifact_review_version"):
                reports[-1]["artifact_decisions"] = copy.deepcopy(decision.get("artifact_decisions", []))
                reports[-1]["review_results"] = copy.deepcopy(decision.get("review_results", []))
                reports[-1]["independent_support_count"] = None
                reports[-1]["review_limit"] = "派生レビューは先行所見と独立した裏付けではない。範囲内未検出は真実性の確認ではない。"
            reports[-1]["deferred_followup_count"] = sum(e["type"] == "intent_deferred" and e.get("review_result_id") == meta["result_id"] for e in events)
            statuses = [t["status"] for t in followups if t.get("parent_task_id") == task["task_id"]]
            reports[-1]["followup_status_counts"] = {status: statuses.count(status) for status in sorted(set(statuses))}
        return reports

    @staticmethod
    def _core_progress_signature(raw):
        # IDs, order, punctuation and summary-only paraphrases do not add evidence.
        def text(value):
            # Preserve internal punctuation, signs and word boundaries: -1 and
            # 1 or 1.2 and 12 must never be collapsed into the same assertion.
            return " ".join(unicodedata.normalize("NFKC", value).casefold().split()).rstrip("。.!?！？")
        def items(values):
            return sorted({_json(value) for value in values})
        return fingerprint({
            "claims": items({"text": text(claim["text"]), "kind": claim["kind"],
                              "evidence_ids": sorted(set(claim["evidence_ids"]))}
                             for claim in raw.get("claims", [])),
            "alternatives": sorted({text(value) for value in raw.get("alternatives", [])}),
            "unresolved": sorted({text(value) for value in raw.get("unresolved", [])}),
            "intents": items({**{key: intent.get(key) for key in (
                "role", "kind", "result_id", "method_id", "label_field", "scope", "label_dependent", "replicate_id")},
                "question": text(intent["question"]), "evidence_ids": sorted(set(intent.get("evidence_ids", []))),
                "initial_sections": sorted(set(intent.get("initial_sections", [])))}
                for intent in raw.get("intents", [])),
        })

    def _new_result_basis(self, db, run, history, assessments):
        def basis(result_id):
            row = db.execute("SELECT raw_json,state_json FROM orchestration_results WHERE run_id=? AND result_id=?",
                             (run["run_id"], result_id)).fetchone()
            metadata = json.loads(row[1])
            if fingerprint(json.loads(row[0])) != metadata["raw_hash"]:
                raise _error("専門家結果のhashが一致しません。", "result_integrity_mismatch")
            task = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=? AND run_id=?",
                                        (metadata["task_id"], run["run_id"])).fetchone()[0])
            if task.get("input_artifacts"):
                return None
            return fingerprint({"role": metadata["role"], "raw_hash": metadata["raw_hash"],
                "data_version": metadata["dataset_version"], "annotation_version": metadata["annotation_version"],
                "scope": task["intent"].get("scope"), "target_version": task["intent"].get("target_version"),
                "evidence_ids": sorted(set(task["intent"].get("evidence_ids", [])))})
        seen = {basis(entry["result_id"]) for decision in history for entry in decision.get("result_assessments", [])}
        fresh = []
        for result_id in assessments:
            key = basis(result_id)
            if key is not None and key not in seen:
                fresh.append(result_id)
                seen.add(key)
        return fresh

    def _new_review_checks(self, db, run, previous_ids, assessed_ids):
        def signature(rid):
            row = db.execute("SELECT raw_json,state_json FROM orchestration_results WHERE result_id=? AND run_id=?", (rid, run["run_id"])).fetchone()
            raw, meta = json.loads(row[0]), json.loads(row[1])
            if not meta.get("derived_from"):
                return None
            if fingerprint(raw) != meta["raw_hash"]:
                artifact_review.reject("派生レビューの保存hashが一致しません。")
            return artifact_review.review_progress(raw)
        seen = {signature(rid) for rid in previous_ids}
        fresh = []
        for rid in assessed_ids:
            key = signature(rid)
            if key is not None and key not in seen:
                fresh.append(rid)
                seen.add(key)
        return fresh

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

    def _source_review_binding(self, db, run, result_id, scope=None):
        from .method_experts import counterexample_review_procedure
        row = db.execute("SELECT raw_json,state_json,task_id FROM orchestration_results WHERE result_id=? AND run_id=?",
                         (result_id, run["run_id"])).fetchone()
        if row is None:
            artifact_review.reject("同じrunの先行所見が見つかりません。")
        raw, meta = json.loads(row[0]), json.loads(row[1])
        source = db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=? AND run_id=?",
                            (row[2], run["run_id"])).fetchone()
        if source is None:
            artifact_review.reject("先行所見の生成タスクが見つかりません。")
        task = json.loads(source[0])
        scope = copy.deepcopy(scope if scope is not None else _scope(task["intent"]))
        from .services.analysis_intervals import interval_scope
        intervals = run.get("analysis_partition", {}).get("intervals", []) + run.get("interval_refinements", [])
        interval = next((i for i in intervals if i["interval_id"] == scope.get("interval_id")), None)
        if interval is None or interval_scope(interval) != scope:
            artifact_review.reject("先行所見の固定区間が不正です。")
        self._check_input_manifest(run, task, meta)
        binding = artifact_review.validate_source(run, task, meta, raw, scope, counterexample_review_procedure())
        return binding, raw, meta

    def _artifact_history(self, db, run, domain):
        return [{**entry, "decision_id": d["decision_id"]}
                for (encoded,) in db.execute("SELECT payload_json FROM orchestration_decisions WHERE run_id=? ORDER BY rowid", (run["run_id"],))
                if (d := json.loads(encoded)).get("role") == "orchestrator" and d.get("domain") == domain
                for entry in d.get("artifact_decisions", [])]

    def _artifact_candidates(self, db, run, domain):
        history = self._artifact_history(db, run, domain)
        latest = {r["result_id"]: r for r in history}
        candidates = []
        # Stable insertion order and complete index units. No result body here.
        information = fingerprint({"annotation_version": run["annotation_version"],
            "results": [m["raw_hash"] for (s,) in db.execute("SELECT state_json FROM orchestration_results WHERE run_id=? ORDER BY rowid", (run["run_id"],))
                        if (m := json.loads(s)).get("role") not in {"core", "orchestrator"}
                        and m.get("validation_status") == "valid"]})
        for (rid,) in db.execute("SELECT result_id FROM orchestration_results WHERE run_id=? ORDER BY rowid", (run["run_id"],)).fetchall():
            old = latest.get(rid)
            if old and old["disposition"] != "defer":
                continue
            try:
                binding, _, meta = self._source_review_binding(db, run, rid)
            except AnalysisContractError:
                continue
            candidates.append({"result_id": rid, "raw_hash": binding["raw_hash"], "run_id": run["run_id"],
                "task_id": binding["task_id"], "created_by": "interpretation", "interval_id": binding["interval"]["interval_id"],
                "dataset_version": binding["dataset_version"], "schema_version": binding["schema_version"],
                "codebook_version": binding["codebook_version"], "annotation_version": binding["annotation_version"],
                "scope": binding["interval"], "provided_evidence_ids": binding["source_provided_evidence_ids"],
                "claim_count": len(binding["claim_ids"]), "content_status": meta.get("content_status", "unreviewed"),
                "coverage": next(t["context_manifest"]["coverage"] for t in self._tasks(db, run["run_id"]) if t["task_id"] == binding["task_id"]),
                "information_hash": fingerprint([binding, information]),
                "previous_decision_id": old.get("decision_id", "") if old else ""})
        return candidates[:6], len(candidates) - min(6, len(candidates))

    def resolve_review_input(self, db, run, intent):
        if (run["config"].get("artifact_review_version") != 1 or intent.get("role") != "interpretation"
                or intent.get("artifact_purpose") != artifact_review.PURPOSE or intent.get("label_dependent")
                or intent.get("result_id") or intent.get("initial_sections") or intent.get("method_id")):
            artifact_review.reject("専用の解釈役レビュー依頼だけが先行所見を利用できます。")
        row = db.execute("SELECT payload_json FROM orchestration_decisions WHERE decision_id=? AND run_id=?",
                         (intent.get("artifact_decision_id"), run["run_id"])).fetchone()
        decision = json.loads(row[0]) if row else {}
        rid = intent.get("review_target_result_id")
        choice = next((r for r in decision.get("artifact_decisions", []) if r["result_id"] == rid and r["disposition"] == "use"), None)
        if decision.get("role") != "orchestrator" or choice is None or intent.get("interval_ids") != [choice["interval_id"]]:
            artifact_review.reject("提示候補のuse判断に結び付いた依頼が必要です。")
        binding, _, _ = self._source_review_binding(db, run, rid)
        if choice.get("raw_hash") != binding["raw_hash"]:
            artifact_review.reject("提示した先行所見の版が変わりました。")
        return binding

    def _recheck_review_binding(self, db, run, task):
        if task.get("role") != "interpretation" or task.get("intent", {}).get("kind") != "finding_review":
            artifact_review.reject("この役割へ先行所見を配送できません。")
        bindings = task.get("input_artifacts", [])
        if not isinstance(bindings, list) or len(bindings) != 1:
            artifact_review.reject("先行所見の束縛は1件です。")
        current, raw, _ = self._source_review_binding(db, run, bindings[0]["result_id"], _scope(task["intent"]))
        if current != bindings[0] or self.resolve_review_input(db, run, task["intent"]) != current:
            artifact_review.reject("固定した先行所見の入力版・hash・手順が変わりました。")
        return current, raw

    @staticmethod
    def _safe_section(value, evidence):
        """Filter excluded IDs, referenced rows/maps and verbatim excluded text.

        Complete original sections remain available through the owner-only result
        export. This bounded AI view is deliberately allowed to omit more data.
        """
        excluded = {identifier for e in evidence if e["excluded"]
                    for identifier in (e["utterance_id"], e["evidence_id"])}
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
                    if (key in {"id", "segment_id", "utterance_id", "evidence_id"} or key.endswith(("_segment_id", "_utterance_id", "_evidence_id"))) and str(child) in excluded:
                        return omitted
                    if key.endswith(("segment_ids", "utterance_ids", "evidence_ids")) and isinstance(child, list) and any(str(v) in excluded for v in child):
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

    def build_review_resources(self, db, run, task, context):
        from .method_experts import counterexample_review_procedure
        binding, raw = self._recheck_review_binding(db, run, task)
        delivered = [r["evidence_id"] for r in context["raw_evidence"]]
        expected = binding["interval"]["owned_evidence_ids"] + binding["interval"]["boundary_evidence_ids"]
        if set(delivered) != set(expected):
            artifact_review.reject("原文の担当区間と文脈を完全に配送する必要があります。")
        packet = {"result_id": binding["result_id"], "raw_hash": binding["raw_hash"],
            "claims": copy.deepcopy(raw["claims"]), "summary": raw.get("summary", ""),
            "coverage": copy.deepcopy(next(t["context_manifest"]["coverage"] for t in self._tasks(db, run["run_id"])
                                         if t["task_id"] == binding["task_id"])),
            "limitations": raw.get("limitations", ""), "unresolved": raw.get("unresolved", []),
            "content_status": self._source_review_binding(db, run, binding["result_id"])[2].get("content_status", "unreviewed")}
        if binding["annotation_version"] is not None:
            definitions = self._initial_label_catalog(db, run)
            if not definitions:
                artifact_review.reject("先行所見に必要な定義がありません。")
            packet["definitions"] = definitions
            packet["labels"] = copy.deepcopy(context.get("labels", {}))
        return {"schema_version": SCHEMA_VERSION, "task": copy.deepcopy(task), "question": task["title"],
            "data_version": run["input_hash"], "annotation_version": task["annotation_version"],
            "raw_evidence": context["raw_evidence"], "coverage": context["coverage"],
            "input_artifacts": [binding], "finding_resource": packet,
            "review_procedure": counterexample_review_procedure(), "research_mode": "exploratory",
            "execution_allowed": False, "blind_first": False,
            "resources_origin": {"run_id": run["run_id"], "initial_id": run["initial_id"]}}

    def _context(self, db, run, task):
        if task.get("input_artifacts") or task["intent"].get("kind") == "finding_review":
            self._recheck_review_binding(db, run, task)
        context = self._base_context(db, run, task)
        if task["intent"].get("kind") == "finding_review":
            context = self.build_review_resources(db, run, task, context)
        if run["config"].get("reanalysis"):
            source = run["config"]["reanalysis"]
            context["human_prompt"] = source["human_prompt"]
            if task["role"] == "verification" or task["intent"].get("kind") == "finding_review":
                context["reanalysis_origin"] = {key: source[key] for key in (
                    "source_analysis_id", "source_run_id", "source_result_id", "input_hash", "raw_hash")}
            else:
                delivered = copy.deepcopy(source)
                delivered["content"] = self._safe_section(source["content"], self._initial(db, run["initial_id"])["evidence"])
                if delivered["content"] != source["content"]:
                    delivered["excluded_content_omitted"] = True
                    delivered["delivery_content_hash"] = fingerprint(delivered["content"])
                context["reanalysis"] = delivered
        if run["config"].get("required_methods"):
            context["required_methods_progress"] = self._required_methods_progress(db, run)
        if run["config"].get("artifact_review_version"):
            context["artifact_review_version"] = artifact_review.VERSION
            if task["role"] == "orchestrator":
                domain = task["intent"]["scope"]["domain"]
                candidates, omitted = self._artifact_candidates(db, run, domain)
                context["artifact_candidates"] = candidates
                context["artifact_candidate_scope"] = {"omitted_count": omitted, "ordering": "result_insertion"}
                latest = {r["result_id"]: r for r in self._artifact_history(db, run, domain)}
                context["unresolved_artifact_decisions"] = [r for r in latest.values() if r["disposition"] == "defer"]
        return context

    def _base_context(self, db, run, task):
        initial = self._initial(db, run["initial_id"])
        raw = [e for e in initial["evidence"] if not e["excluded"]]
        selected = task["intent"].get("evidence_ids", [])
        if run["config"].get("specialist_orchestration_version") and task["role"] == "critic" and task["phase"] == "stop_review":
            selected = sorted({ref for claim in run["current_view"].get("claims", []) for ref in claim["evidence_ids"]})
        if selected:
            raw = [e for e in raw if e["evidence_id"] in selected]
        available_count = len(raw)
        bounded, size = [], 0
        for evidence in raw:
            page = task["kind"] == "ai" and (run["config"].get("model_context_version") and task["phase"] == "initial_analysis"
                    or _scope(task["intent"]).get("interval_id"))
            if not page and (len(bounded) >= run["config"]["context_evidence_limit"] or size + len(evidence["text"]) > run["config"]["context_text_limit"]):
                break
            bounded.append(evidence); size += len(evidence["text"])
        raw = bounded
        # The immutable snapshot retains per-row hashes and versions.
        raw = [{key: entry[key] for key in ("evidence_id", "utterance_id", "text", "speaker", "start", "end")}
               for entry in raw]
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
        initial_report = copy.deepcopy(run.get("initial_analysis_report"))
        scope = _scope(task["intent"])
        if run["config"].get("model_context_version") and initial_report and "requirement_keys" in scope:
            initial_report["full_report_hash"] = fingerprint(initial_report)
            initial_report["label_requirements"] = [entry for entry in initial_report["label_requirements"] if fingerprint(entry) in scope["requirement_keys"]]
            source_results = {source["result_id"] for entry in initial_report["label_requirements"] for source in entry["sources"]}
            initial_report["reports"] = [report for report in initial_report["reports"] if report["result_id"] in source_results]
            initial_report["requirement_scope"] = "selected; remaining requirements have separate Handler tasks"
        if isinstance(task["intent"].get("scope"), dict) and task["intent"]["scope"].get("owned_evidence_ids"):
            coverage["page"] = copy.deepcopy(task["intent"]["scope"])
            if task["role"] == "verification":
                coverage["page"].pop("title", None)
            coverage["owned_count"] = len(coverage["page"]["owned_evidence_ids"])
            coverage["boundary_count"] = len(coverage["page"].get("boundary_evidence_ids", []))
        if task["role"] == "interpretation" and task["phase"] == "initial_labels" and task["method_id"] == "label-design-v1":
            return {"schema_version": SCHEMA_VERSION, "task": copy.deepcopy(task),
                    "question": run["config"]["question"], "data_version": run["input_hash"],
                    "annotation_version": task["annotation_version"], "raw_evidence": copy.deepcopy(raw),
                    "coverage": coverage, "research_mode": "exploratory", "execution_allowed": False,
                    "initial_analysis_report": initial_report,
                    "definition_feedback": copy.deepcopy(scope.get("definition_feedback")),
                    "routing_instruction": copy.deepcopy(task["intent"]),
                    "budget": {"iteration": run["iteration"], "completed_core_iterations": self._completed_core_iterations(db, run)}}
        if task["phase"] == "initial_analysis" and task["role"] in {"interpretation", "critic"}:
            # Initial specialists inspect the same source independently, even
            # when a faster worker has already reported to the Handler.
            context = {"schema_version": SCHEMA_VERSION, "task": copy.deepcopy(task),
                       "question": run["config"]["question"], "data_version": run["input_hash"],
                       "annotation_version": task["annotation_version"], "raw_evidence": copy.deepcopy(raw),
                       "coverage": coverage, "research_mode": "exploratory", "execution_allowed": False}
            if task["role"] == "critic":
                context["review_target"] = {"target_id": task["intent"]["target_id"],
                    "target_version": task["intent"]["target_version"],
                    "view": {"question": run["config"]["question"], "scope": "initial_analysis_plan"}}
            return context
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
                    "annotation_version": metadata["annotation_version"], "raw_evidence": [
                        {key: row[key] for key in ("evidence_id", "utterance_id", "text", "speaker", "start", "end")}
                        for row in provided],
                    "coverage": {"available_count": len(relevant), "provided_count": len(provided),
                                 "omitted_count": len(relevant) - len(provided), "complete": len(relevant) == len(provided),
                                 "scope": "saved_verification_result"},
                    "clarification_target": {"metadata": metadata,
                        "content": content if len(target[0]) <= 16000 else {"content_excerpt": target[0][:16000], "truncated": True}},
                    "blind_first": False, "execution_allowed": False, "research_mode": "exploratory"}
        if task["role"] == "verification":
            return {"schema_version": SCHEMA_VERSION, "task": {"task_id": task["task_id"], "role": "verification",
                    **({"phase": "initial_analysis"} if task["phase"] == "initial_analysis" else {})},
                    "question": run["config"]["question"] if task["phase"] == "initial_analysis" else "原文から観察事実、矛盾、判断できない点を独立に確認してください。",
                    "data_version": run["input_hash"], "annotation_version": task["annotation_version"],
                    "raw_evidence": copy.deepcopy(raw), "coverage": coverage, "blind_first": True,
                    "research_mode": "exploratory"}
        if task["phase"] == "label_review":
            return {"schema_version": SCHEMA_VERSION, "task": copy.deepcopy(task),
                    "question": task["title"], "data_version": run["input_hash"],
                    "annotation_version": task["annotation_version"], "raw_evidence": copy.deepcopy(raw),
                    "coverage": coverage, "initial_label_catalog": self._initial_label_catalog(db, run),
                    "review_target": {"target_id": task["intent"]["target_id"], "target_version": task["intent"]["target_version"]},
                    "research_mode": "exploratory"}
        public = self._public(db, run)
        accepted = []
        for result in public["results"]:
            if result["validation_status"] == "valid":
                row = db.execute("SELECT raw_json FROM orchestration_results WHERE result_id=?", (result["result_id"],)).fetchone()
                content = json.loads(row[0])
                if fingerprint(content) != result["raw_hash"]:
                    raise _error("保存済み結果のhashが一致しません。", "result_integrity_mismatch")
                if result["result_id"] in run.get("initial_label_result_ids", [run.get("initial_label_result_id")]):
                    content = {"summary": content.get("summary", ""), "claims": content.get("claims", []),
                               "label_definitions_ref": "initial_label_catalog"}
                elif (len(row[0]) > 16000 and not result.get("derived_from")
                      and not (run["config"].get("metric_codec_version") == 1 and result.get("role") == "statistics"
                               and task["role"] == "orchestrator" and scope.get("domain") == "statistics")):
                    content = {"summary": content.get("summary", ""), "claims": content.get("claims", [])[:24], "omitted_full_result": True}
                accepted.append({**result, "content": content})
        pending_results = self._review_pending(db, run, task) if run["config"].get("core_progress_version") else []
        pending_batch = pending_results[:20]
        if task["role"] in {"core", "orchestrator"} and run["config"].get("core_progress_version"):
            batch = [result for result in accepted if result["result_id"] in pending_batch]
            previous = [result for result in accepted if result["result_id"] not in pending_batch]
            accepted = batch + (previous[-(20 - len(batch)):] if len(batch) < 20 else [])
        else:
            accepted = accepted[-20:]
        context = {"schema_version": SCHEMA_VERSION, "task": copy.deepcopy(task), "question": run["config"]["question"],
                   "data_version": run["input_hash"], "annotation_version": task["annotation_version"],
                   "raw_evidence": copy.deepcopy(raw), "coverage": coverage, "research_mode": "exploratory",
                   "current_view": run["current_view"], "view_version": run["view_version"],
                   "initial": {"initial_id": run["initial_id"], "available_sections": [section for section in initial["analysis"] if section in INITIAL_SECTIONS],
                               "full_results_preserved": True, "read_scope": "index_only"},
                   "results": accepted, "issues": public["issues"], "critique_responses": public["critique_responses"],
                   "dependency_task_ids": [entry["task_id"] for entry in public["tasks"] if entry["status"] == "succeeded"],
                   "label_proposals": public["label_proposals"], "usage": public["usage"],
                   "budget": {"remaining_calls": run["config"]["max_calls"] - run["calls_started"],
                              "remaining_tasks": run["config"]["max_tasks"] - len(public["tasks"]),
                              "max_iterations": run["config"]["max_iterations"], "iteration": run["iteration"],
                              "min_iterations": run["config"].get("min_iterations", 0),
                              "completed_core_iterations": self._completed_core_iterations(db, run),
                              "deadline": run["deadline"]}, "stop_proposal": run["pending_stop"]}
        if run.get("analysis_partition") and task["role"] in {"core", "orchestrator"}:
            context["analysis_interval_index"] = [{k: i[k] for k in ("interval_id", "parent_topic_id", "start", "end")}
                for i in run["analysis_partition"]["intervals"]]
        if run["config"].get("initial_label_definitions_version"):
            context["initial_label_catalog"] = self._initial_label_catalog(db, run)
            if task["role"] == "core" and task["phase"] != "initial_routing" and not context["initial_label_catalog"]:
                raise _error("初回の専門家によるラベル・尺度出力が必要です。", "initial_labels_missing")
        if run.get("initial_analysis_report"):
            context["initial_analysis_report"] = initial_report
        if task["role"] in {"core", "orchestrator"} and run["config"].get("core_progress_version"):
            context["iteration_review"] = {
                "previous_decision_id": run["last_decision_id"],
                "pending_result_ids": pending_batch,
                "omitted_pending_result_count": len(pending_results) - len(pending_batch),
                "progress_required": True,
            }
            if task["phase"] == "initial_routing":
                context["iteration_review"].update(pending_result_ids=[], omitted_pending_result_count=0, progress_required=False)
            if run["config"].get("model_context_version"):
                unread = set(pending_results) - set(pending_batch)
                all_issues = context["issues"]
                context["issues"] = [issue for issue in all_issues if issue["status"] == "open" and issue["result_id"] not in unread]
                context["issue_scope"] = {"unread_result_issue_count": sum(issue["status"] == "open" and issue["result_id"] in unread for issue in all_issues),
                    "resolved_issue_count": sum(issue["status"] != "open" for issue in all_issues), "full_issue_index_hash": fingerprint(all_issues)}
        context["labels"] = json.loads(db.execute("SELECT payload_json FROM orchestration_label_versions WHERE run_id=? AND annotation_version=?",
                                                    (run["run_id"], task["annotation_version"])).fetchone()[0])
        included_ids = {e["utterance_id"] for e in raw}
        context["labels"] = {key: value for key, value in context["labels"].items() if key in included_ids}
        if run["config"].get("initial_label_definitions_version"):
            context["labels"] = {key: {field: item for field, item in value.items() if field in LABEL_FIELDS}
                                 for key, value in context["labels"].items() if isinstance(value, dict)}
        if run["config"].get("specialist_orchestration_version"):
            if task["role"] == "orchestrator":
                context["review_domain"] = task["intent"]["scope"]["domain"]
                context["prior_domain_reports"] = [r for r in self._domain_reports(db, run)
                    if r["domain"] == context["review_domain"] and r["annotation_version"] == task["annotation_version"]]
                context.pop("initial_analysis_report", None)
                context.pop("current_view", None)
                context.pop("stop_proposal", None)
                context.pop("critique_responses", None)
                context["results"] = [r for r in accepted if r["result_id"] in pending_batch]
                context["issues"] = [i for i in context["issues"] if i["result_id"] in pending_batch]
                context["label_proposals"] = [p for p in context["label_proposals"] if p["result_id"] in pending_batch]
                if context["review_domain"] != "labels":
                    context["label_proposals"] = []
                    context.pop("initial_label_catalog", None)
                context["dependency_task_ids"] = [r["task_id"] for r in context["results"]]
            elif task["role"] == "core" and task["phase"] != "initial_routing":
                context["domain_reports"] = self._domain_reports(db, run)
                context["results"] = []
                context["issues"] = []
                context["label_proposals"] = []
                context["review_scope"] = "specialist_reports_not_full_raw_results"
            elif task["role"] in {"interpretation", "critic"} and task["phase"] != "initial_analysis":
                # New analysis reads its scoped source. Saved-result dialogue is
                # supplied separately by the clarification contract below.
                context.pop("initial_analysis_report", None)
                context["results"] = []
                context["issues"] = []
                context["critique_responses"] = []
                context["label_proposals"] = []
                context["dependency_task_ids"] = task["dependencies"]
                if not task["label_dependent"]:
                    context.pop("initial_label_catalog", None)
                if task["role"] == "interpretation":
                    context.pop("current_view", None)
                    context.pop("stop_proposal", None)
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

