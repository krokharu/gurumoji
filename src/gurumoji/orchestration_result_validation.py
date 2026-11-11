from __future__ import annotations

import copy
import json

from .analysis_core import fingerprint, validate_label_definitions
from .orchestration_shared import (
    IMPORTANCE,
    INITIAL_METHODS,
    LABEL_FIELDS,
    METHODS,
    TERMINAL,
    _error,
    _id,
    _json,
    _now,
    _scope,
)
from .services import artifact_review
from .services.orchestration_required_methods import LABEL_METHODS


class ResultValidationMixin:
    def _label_design_evidence_ids(self, db, run, task=None):
        if task and (run["config"].get("model_context_version") or run["config"].get("analysis_interval_version")):
            manifest = task.get("context_manifest")
            if manifest:
                if fingerprint(manifest) != task.get("context_manifest_hash"):
                    raise _error("入力記録のhashが一致しません。", "context_manifest_invalid")
                return set(manifest["provided_evidence_ids"])
            if task["intent"].get("evidence_ids"):
                return set(task["intent"]["evidence_ids"])
        included, size = set(), 0
        for entry in self._initial(db, run["initial_id"])["evidence"]:
            if entry["excluded"]:
                continue
            if len(included) >= run["config"]["context_evidence_limit"] or size + len(entry["text"]) > run["config"]["context_text_limit"]:
                break
            included.add(entry["evidence_id"])
            size += len(entry["text"])
        return included

    def _collect_initial_analysis(self, db, run):
        reports, requirements = [], {}
        tasks = [task for task in self._tasks(db, run["run_id"]) if task["phase"] == "initial_analysis"]
        expected = {("interpretation", "agent-v1"), ("verification", "agent-v1"), ("critic", "agent-v1"),
                    *(("statistics", method) for method in INITIAL_METHODS)}
        paged = run["config"].get("model_context_version") or run["config"].get("analysis_interval_version")
        if {(task["role"], task["method_id"]) for task in tasks} != expected or not paged and len(tasks) != len(expected):
            raise _error("初回分析の担当が揃っていません。", "initial_analysis_incomplete")
        if paged:
            all_ids = {e["evidence_id"] for e in self._initial(db, run["initial_id"])["evidence"] if not e["excluded"]}
            for role in ("interpretation", "verification", "critic"):
                owned = [ref for task in tasks if task["role"] == role
                         for ref in task["intent"].get("scope", {}).get("owned_evidence_ids", [])]
                if len(owned) != len(set(owned)) or set(owned) != all_ids:
                    raise _error("初回分析の分割範囲に欠落または重複があります。", "initial_analysis_incomplete")
                for task in tasks:
                    if task["role"] == role and not set(task["intent"]["scope"]["owned_evidence_ids"]).issubset(self._label_design_evidence_ids(db, run, task)):
                        raise _error("担当範囲に未読の発話が残っています。", "initial_analysis_incomplete")
        for task in tasks:
            row = db.execute("SELECT raw_json,state_json FROM orchestration_results WHERE task_id=?", (task["task_id"],)).fetchone()
            if task["status"] != "succeeded" or row is None:
                raise _error("初回分析に未実行または失敗した担当があります。", "initial_analysis_incomplete")
            raw, meta = json.loads(row[0]), json.loads(row[1])
            if (fingerprint(raw) != meta.get("raw_hash") or meta.get("validation_status") != "valid"
                    or meta.get("task_id") != task["task_id"] or meta.get("attempt_id") != task["attempt_id"]
                    or meta.get("run_id") != run["run_id"] or meta.get("dataset_version") != run["input_hash"]):
                raise _error("初回分析結果の保存hashまたは版が不正です。", "result_integrity_mismatch")
            self._validate_result(db, run, task, raw)
            self._check_input_manifest(run, task, meta)
            source = {"role": task["role"], "method_id": task["method_id"], "task_id": task["task_id"],
                      "result_id": meta["result_id"], "raw_hash": meta["raw_hash"]}
            if _scope(task["intent"]).get("interval_id"):
                source.update(interval_id=task["intent"]["scope"]["interval_id"],
                              parent_topic_id=task["intent"]["scope"]["parent_topic_id"],
                              ownership_sha256=task["intent"]["scope"]["ownership_sha256"])
            reports.append({**source, "summary": raw.get("summary", ""),
                            "requirement_count": len(raw["label_requirements"])})
            for entry in raw["label_requirements"]:
                key = fingerprint({k: v for k, v in entry.items() if k != "requirement_id"})
                aggregate = requirements.setdefault(key, {**copy.deepcopy(entry), "sources": []})
                aggregate["sources"].append({**source, "requirement_id": entry["requirement_id"]})
        return {"status": "ai_draft", "dataset_version": run["input_hash"], "reports": reports,
                "label_requirements": list(requirements.values()), "all_roles_reported": True,
                "full_evidence_coverage": bool(paged)}

    def _apply_initial_routing(self, db, run, task):
        row = db.execute("SELECT * FROM orchestration_results WHERE task_id=?", (task["task_id"],)).fetchone()
        raw, meta = json.loads(row["raw_json"]), json.loads(row["state_json"])
        if fingerprint(raw) != meta.get("raw_hash") or meta.get("validation_status") != "valid":
            raise _error("担当指示の保存結果が不正です。", "result_integrity_mismatch")
        self._validate_result(db, run, task, raw)
        self._check_input_manifest(run, task, meta)
        decision = {**copy.deepcopy(raw), "decision_id": _id("decision"), "result_id": meta["result_id"],
                    "task_id": task["task_id"], "phase": "initial_routing", "iteration": 0,
                    "role": "core", "created_at": _now(), "annotation_version": run["annotation_version"],
                    "before_annotation_version": run["annotation_version"], "after_annotation_version": run["annotation_version"]}
        db.execute("INSERT OR IGNORE INTO orchestration_decisions VALUES (?,?,?,?)",
                   (decision["decision_id"], run["run_id"], meta["result_id"], _json(decision)))
        instruction = copy.deepcopy(raw["intents"][0])
        if run["config"].get("model_context_version"):
            scope = _scope(task["intent"])
            instruction["scope"] = {"requirement_keys": scope.get("requirement_keys",
                [fingerprint(entry) for entry in run["initial_analysis_report"]["label_requirements"]])}
            requirements = [entry for entry in run["initial_analysis_report"]["label_requirements"] if fingerprint(entry) in instruction["scope"]["requirement_keys"]]
            instruction["evidence_ids"] = sorted({ref for entry in requirements for ref in entry["evidence_ids"]})
        instruction.update(parent_task_id=task["task_id"],
            dependencies=sorted(set(instruction.get("dependencies", [])) | {task["task_id"]}
                | {report["task_id"] for report in run["initial_analysis_report"]["reports"]}))
        self._register(db, run, instruction, phase="initial_labels")
        if run["status"] in TERMINAL:
            return
        self._event(db, run["run_id"], "initial_routing_dispatched", "Coreの担当指示を受け、ハンドラーが尺度設計専門家へ発注しました。",
                    source="core", target="handler", result_id=meta["result_id"], raw_hash=meta["raw_hash"])
        run["phase"] = "initial_labels"
        self._write_run(db, run)

    def _initial_label_catalog(self, db, run):
        result_id = run.get("initial_label_result_id")
        if not result_id:
            return None
        catalogs = [self._initial_label_result(db, run, key) for key in run.get("initial_label_result_ids", [result_id])]
        if len(catalogs) == 1 and not run["config"].get("model_context_version"):
            return catalogs[0]
        definitions, sources, by_id = [], [], {}
        for catalog in catalogs:
            for definition in catalog["definitions"]:
                definitions.append(definition)
                sources.append(catalog["result_id"])
                by_id.setdefault(definition["definition_id"], set()).add(fingerprint(definition))
        return {**catalogs[0], "definitions": definitions, "definition_sources": sources,
                "result_ids": [catalog["result_id"] for catalog in catalogs],
                "source_hashes": {catalog["result_id"]: catalog["raw_hash"] for catalog in catalogs},
                "definition_conflicts": sorted(key for key, values in by_id.items() if len(values) > 1)}

    def _initial_label_result(self, db, run, result_id):
        row = db.execute("SELECT * FROM orchestration_results WHERE run_id=? AND result_id=?", (run["run_id"], result_id)).fetchone()
        if row is None:
            raise _error("初回の尺度作成結果が見つかりません。", "initial_labels_missing")
        metadata, raw = json.loads(row["state_json"]), json.loads(row["raw_json"])
        task_row = db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=? AND run_id=?", (row["task_id"], run["run_id"])).fetchone()
        task = json.loads(task_row[0]) if task_row else {}
        if (fingerprint(raw) != metadata.get("raw_hash") or metadata.get("validation_status") != "valid"
                or metadata.get("role") != "interpretation" or task.get("role") != "interpretation"
                or metadata.get("run_id") != run["run_id"] or metadata.get("result_id") != result_id
                or metadata.get("task_id") != row["task_id"] or task.get("task_id") != row["task_id"]
                or task.get("status") != "succeeded" or task.get("phase") != "initial_labels"
                or task.get("method_id") != "label-design-v1" or task.get("iteration") != 0
                or metadata.get("dataset_version") != run["input_hash"]
                or metadata.get("attempt_id") != task.get("attempt_id")):
            raise _error("初回の尺度作成結果の保存hashまたは作成主体が不正です。", "result_integrity_mismatch")
        validate_label_definitions(raw.get("label_definitions"), evidence_ids=self._label_design_evidence_ids(db, run, task))
        self._check_input_manifest(run, task, metadata)
        return {"status": "ai_draft", "created_by": "interpretation", "specialization": "label_design",
                "result_id": result_id, "raw_hash": metadata["raw_hash"], "dataset_version": run["input_hash"],
                "base_codebook_version": task["codebook_version"], "definitions": copy.deepcopy(raw["label_definitions"])}

    def _check_input_manifest(self, run, task, metadata=None):
        if not (run["config"].get("model_context_version") or run["config"].get("analysis_interval_version")) or task["kind"] != "ai":
            return
        manifest = task.get("context_manifest") or {}
        if (manifest.get("version") != (artifact_review.MANIFEST_VERSION if run["config"].get("artifact_review_version") else 1) or manifest.get("dataset_version") != run["input_hash"]
                or fingerprint(manifest) != task.get("context_manifest_hash")
                or metadata is not None and metadata.get("context_manifest_hash") != task.get("context_manifest_hash")):
            raise _error("保存結果と入力パケットの来歴が一致しません。", "context_manifest_invalid")
        scope = _scope(task["intent"])
        if scope.get("interval_id") and (manifest.get("analysis_interval") != scope or
                not set(scope["owned_evidence_ids"] + scope["boundary_evidence_ids"]).issubset(manifest.get("provided_evidence_ids", []))):
            raise _error("区間の実配送記録が所属と一致しません。", "context_manifest_invalid")

    def _validate_result(self, db, run, task, raw):
        self._check_input_manifest(run, task)
        if not isinstance(raw, dict):
            raise _error("結果はJSONオブジェクトで返してください。", "invalid_result")
        if task.get("input_artifacts"):
            binding, _ = self._recheck_review_binding(db, run, task)
            manifest = task.get("context_manifest", {})
            if manifest.get("input_artifacts") != [binding] or manifest.get("review_procedure") != binding["procedure"]:
                artifact_review.reject("点検の入力manifestが束縛と一致しません。", "context_manifest_invalid")
            artifact_review.validate_review_output(raw, binding, manifest)
        elif raw.get("claim_verdicts"):
            artifact_review.reject("主張別の反例判定は専用レビューだけが返せます。", "artifact_output_invalid")
        if raw.get("research_mode", "exploratory") != "exploratory":
            raise _error("確認的主張には未対応です。", "confirmatory_unavailable")
        if raw.get("dataset_version", run["input_hash"]) != run["input_hash"]:
            raise _error("結果の入力版が一致しません。", "revision_conflict")
        evidence = {e["evidence_id"]: e for e in self._initial(db, run["initial_id"])["evidence"] if not e["excluded"]}
        if task["phase"] == "initial_analysis":
            if task["kind"] == "ai" and (not isinstance(raw.get("summary"), str) or not raw["summary"].strip()
                    or (task["role"] in {"interpretation", "verification"} and not raw.get("claims"))):
                raise _error("初回の解釈・独立検証には空でない要約と根拠付きの主張が必要です。", "initial_analysis_empty")
            requirements = raw.get("label_requirements")
            if not isinstance(requirements, list) or len(requirements) > 12:
                raise _error("初回分析ではラベル・尺度の必要性を明示して報告してください。", "initial_requirements_missing")
            known = set()
            provided = self._label_design_evidence_ids(db, run, task)
            for entry in requirements:
                if (not isinstance(entry, dict) or any(not isinstance(entry.get(key), str) or not entry[key].strip()
                        for key in ("requirement_id", "name", "analysis", "reason"))
                        or entry.get("kind") not in {"label", "scale"}
                        or not isinstance(entry.get("evidence_ids"), list) or not entry["evidence_ids"]
                        or any(ref not in provided for ref in entry["evidence_ids"])
                        or entry["requirement_id"] in known):
                    raise _error("尺度要件には種類・分析用途・理由・読んだ根拠IDと一意IDが必要です。", "invalid_initial_requirement")
                known.add(entry["requirement_id"])
            if raw.get("label_patches") or raw.get("label_definitions"):
                raise _error("初回の予備分析は尺度の必要性を報告し、採用ラベルを変更しません。", "invalid_initial_requirement")
        label_design = task["role"] == "interpretation" and task["phase"] == "initial_labels" and task["method_id"] == "label-design-v1"
        if label_design:
            validate_label_definitions(raw.get("label_definitions"), evidence_ids=self._label_design_evidence_ids(db, run, task))
            if raw.get("label_patches"):
                raise _error("尺度設計では確定ラベルを変更しません。", "invalid_label_patch")
        elif raw.get("label_definitions"):
            raise _error("尺度定義は初回の専門家タスクだけが作成します。", "label_definition_author_invalid")
        for key in ("claims", "issues", "label_patches", "intents", "critique_responses", "label_decisions", "result_assessments"):
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
            if (run["config"].get("model_context_version") or task.get("input_artifacts")) and task["kind"] == "ai":
                manifest = task.get("context_manifest", {})
                if fingerprint(manifest) != task.get("context_manifest_hash") or any(ref not in manifest.get("citation_ids", []) for ref in refs):
                    raise _error("読んでいない発話は根拠として採用できません。", "evidence_not_provided")
        if task["role"] in {"core", "orchestrator"}:
            if run["config"].get("artifact_review_version") and task["role"] == "orchestrator":
                artifact_review.validate_decisions(raw, task["context_manifest"].get("artifact_candidates", []),
                    prior=self._artifact_history(db, run, task["intent"]["scope"]["domain"]))
            elif raw.get("artifact_decisions") or any(i.get("kind") == "finding_review" for i in raw.get("intents", [])):
                artifact_review.reject("先行所見の利用は専門側の専用判断で指示してください。")
            if task["role"] == "orchestrator" and (raw.get("stop") is not None or raw.get("label_patches") or raw.get("label_decisions") and task["intent"]["scope"]["domain"] != "labels"):
                raise _error("専門側は終了判断や担当外ラベルの採否を決めません。", "orchestrator_authority_invalid")
            if task["role"] == "core" and run["config"].get("specialist_orchestration_version") and any(raw.get(k) for k in ("result_assessments", "critique_responses", "label_decisions")):
                raise _error("個別結果・批判・ラベルの判断は専門側の責務です。", "core_authority_invalid")
            routing = task["phase"] == "initial_routing"
            if run["config"].get("initial_label_definitions_version") and not routing and not self._initial_label_catalog(db, run):
                raise _error("初回の専門家によるラベル・尺度出力が必要です。", "initial_labels_missing")
            if routing:
                intents = raw.get("intents", [])
                if (not isinstance(intents, list) or len(intents) != 1
                        or intents[0].get("role") != "interpretation" or intents[0].get("method_id") != "label-design-v1"
                        or intents[0].get("kind", "analysis") != "analysis" or intents[0].get("evidence_ids")
                        or intents[0].get("label_dependent") or raw.get("stop") is not None
                        or any(raw.get(key) for key in ("claims", "critique_responses", "label_decisions", "result_assessments"))):
                    raise _error("初回の担当指示は尺度設計専門家への1件の依頼です。統合・終了・ラベル更新は後続判断で行います。", "initial_routing_invalid")
            if not isinstance(raw.get("summary"), str) or not raw["summary"].strip():
                raise _error("空でない統合要約が必要です。", "invalid_result")
            for key in ("alternatives", "unresolved"):
                if key in raw and (not isinstance(raw[key], list) or any(not isinstance(value, str) for value in raw[key])):
                    raise _error("代替説明・未解決点は文字列の配列です。", "invalid_result")
            if run["config"].get("core_progress_version"):
                expected = set() if routing else set(self._review_pending(db, run, task)[:20])
                if run["config"].get("model_context_version") and not routing:
                    manifest = task.get("context_manifest", {})
                    requested = manifest.get("requested_result_ids", [])
                    pending = self._review_pending(db, run, task)
                    if fingerprint(manifest) != task.get("context_manifest_hash") or requested != pending[:len(requested)] or pending and not requested:
                        raise _error("評価範囲の保存記録が不正です。", "context_manifest_invalid")
                    expected = set(requested)
                received = []
                for assessment in raw.get("result_assessments", []):
                    if (assessment.get("result_id") not in expected
                            or assessment.get("disposition") not in {"adopt", "reject", "defer"}
                            or any(not isinstance(assessment.get(key), str) or not assessment[key].strip()
                                   for key in ("reason", "impact"))):
                        raise _error("新しい専門家結果には実在ID・採否・理由・影響が必要です。", "invalid_result_assessment")
                    received.append(assessment["result_id"])
                if len(received) != len(set(received)):
                    raise _error("同じ専門家結果を重複して評価できません。", "invalid_result_assessment")
                if set(received) != expected:
                    raise _error("新しい専門家結果の採否が未記録です。", "result_assessment_missing")
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
                    if (method == "cross_tabulation" and "cross_tabulation" in run["config"].get("required_methods", [])
                            and intent.get("label_field", "codes") != "codes"):
                        raise _error("必須クロス集計の列はcodesに固定されています。", "required_method_spec_mismatch")
                    if method not in METHODS or (method not in LABEL_METHODS and (intent.get("evidence_ids") or intent.get("scope") or intent.get("label_dependent"))):
                        raise _error("既存コード計算は初期版の全範囲専用です。", "method_scope_unavailable")
                    if method in LABEL_METHODS and intent.get("label_field", "codes") not in LABEL_FIELDS:
                        raise _error("対応するラベル集計列を指定してください。", "label_field_unavailable")
                elif intent.get("method_id") in LABEL_METHODS:
                    raise _error("ラベル集計はstatisticsへ指定してください。", "label_field_unavailable")
                if not isinstance(intent.get("evidence_ids", []), list) or any(ref not in evidence for ref in intent.get("evidence_ids", [])):
                    raise _error("タスクの根拠が存在しません。", "evidence_missing")
            for response in raw.get("critique_responses", []):
                if run["config"].get("model_context_version") and response.get("issue_id") not in task["context_manifest"].get("provided_issue_ids", []):
                    raise _error("未提示の批判は評価できません。", "issue_not_provided")
                if response.get("disposition") not in {"adopt", "reject", "defer"} or not response.get("reason") or not response.get("impact"):
                    raise _error("批判への応答には採否・理由・結論への影響が必要です。", "invalid_critique_response")
                if not db.execute("SELECT 1 FROM orchestration_issues WHERE issue_id=? AND run_id=?", (response.get("issue_id"), run["run_id"])).fetchone():
                    raise _error("応答先の批判が存在しません。", "issue_missing")
            if task["role"] == "orchestrator" and "context_manifest" in task:
                expected_issues = set(task["context_manifest"].get("provided_issue_ids", []))
                responses = [entry["issue_id"] for entry in raw.get("critique_responses", [])]
                if len(responses) != len(set(responses)) or set(responses) != expected_issues:
                    raise _error("専門側は提示された全指摘へ重複なく応答してください。", "critique_response_missing")
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
            scope = _scope(task["intent"])
            if scope.get("interval_id"):
                owned = {evidence[e]["utterance_id"] for e in scope["owned_evidence_ids"]}
                if str(patch.get("utterance_id")) not in owned:
                    raise _error("文脈用発話へラベルを付与できません。", "invalid_label_patch")
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

        from .services import metric_delivery
        return metric_delivery.validate(db, run, task, raw)

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

