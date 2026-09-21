"""Pure contracts and decisions for the milestone analysis pipeline.

This module deliberately has no Flask, SQLite, filesystem, environment, or
provider imports.  The HTTP/command adapters normalize requests, this module
decides whether they are admissible, and ``analysis_pipeline`` performs the
durable work.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any


CONTRACT_VERSION = "analysis-core-1"
PIPELINE_STATES = frozenset({
    "accepted", "running", "waiting", "cancelling", "completed", "failed",
    "cancelled",
})
STEP_STATES = frozenset({
    "planned", "checking", "ready", "running", "validating", "persisting",
    "committed", "reused", "waiting_resource", "awaiting_input", "retry_wait",
    "blocked", "failed", "cancelling", "cancelled", "interrupted",
    "not_applicable",
})
MILESTONE_STATES = frozenset({
    "pending", "active", "waiting", "committed", "failed", "cancelled",
})
PUBLICATION_STATES = frozenset({
    "pending", "publishing", "published", "failed", "conflict", "unknown",
    "not_selected",
})
WAIT_REASONS = frozenset({
    "data", "definition", "retry", "resource", "remote_unknown", "storage",
    "publication",
})

ALLOWED_TRANSITIONS = {
    "pipeline": {
        "accepted": {"running", "cancelling", "failed"},
        "running": {"waiting", "cancelling", "completed", "failed"},
        "waiting": {"running", "cancelling", "failed"},
        "cancelling": {"cancelled", "failed"},
        "completed": set(), "failed": set(), "cancelled": set(),
    },
    "step": {
        "planned": {"checking", "cancelled"},
        "checking": {"ready", "awaiting_input", "blocked", "failed",
                     "not_applicable", "cancelled"},
        "ready": {"running", "waiting_resource", "cancelled"},
        "waiting_resource": {"ready", "cancelled", "failed"},
        "running": {"validating", "retry_wait", "failed", "cancelling",
                    "interrupted"},
        "validating": {"persisting", "retry_wait", "failed", "cancelling"},
        "persisting": {"committed", "blocked", "failed", "cancelling"},
        "retry_wait": {"ready", "failed", "cancelled"},
        "awaiting_input": {"checking", "cancelled", "failed"},
        "blocked": {"checking", "failed", "cancelled"},
        "cancelling": {"cancelled", "committed", "failed"},
        "interrupted": {"ready", "failed", "cancelled"},
        "committed": set(), "reused": set(), "failed": set(),
        "cancelled": set(), "not_applicable": set(),
    },
    "milestone": {
        "pending": {"active", "cancelled"},
        "active": {"waiting", "committed", "failed", "cancelled"},
        "waiting": {"active", "failed", "cancelled"},
        "committed": set(), "failed": set(), "cancelled": set(),
    },
    "publication": {
        "pending": {"publishing", "not_selected"},
        "publishing": {"published", "failed", "conflict", "unknown"},
        "failed": {"publishing"}, "conflict": {"publishing"},
        "unknown": {"publishing"}, "published": set(), "not_selected": set(),
    },
}

CAPABILITIES = {
    "methods": {
        "participation": {"status": "available", "milestone": "M2", "llm": False},
        "conversation_dynamics": {"status": "available", "milestone": "M2", "llm": False},
        "manual_measurement": {"status": "available", "milestone": "M5", "llm": False},
        "outline": {"status": "unavailable", "reason": "初回範囲では既存確定アウトラインの閲覧のみです。"},
        "stance": {"status": "unavailable", "reason": "立場推定は未提供です。"},
        "interview_evaluation": {"status": "unavailable", "reason": "JEV8軸はEVALゲート未完了です。"},
        "inferential_statistics": {"status": "unavailable", "reason": "初回範囲は記述集計のみです。"},
    },
    "exports": {
        "json": {"status": "available"},
        "csv": {"status": "available"},
        "zip": {"status": "available"},
        "xlsx": {"status": "unavailable", "reason": "pipeline固定packageからのXLSXは未提供です。"},
        "sav": {"status": "unavailable", "reason": "pyreadstatを導入していません。"},
        "static_image": {"status": "unavailable", "reason": "初回範囲は画面SVGと代替表です。"},
    },
    "llm_roles": {
        "manual": {"status": "available", "external": False},
        "all": {"status": "unavailable", "reason": "初回pipelineは外部LLMを呼びません。"},
    },
}

DEFINITION_TYPES = frozenset({"string", "number", "boolean", "category"})
MEASUREMENT_LEVELS = frozenset({"nominal", "ordinal", "interval", "ratio"})
SOURCE_COLUMNS = frozenset({
    "speaker", "speaker_name", "role", "text", "duration", "characters",
    "question_candidate",
})
MEASUREMENT_RULES = frozenset({
    "identity", "text_length", "nonempty", "duration", "boolean_true",
})
SUPPORTED_METHODS = frozenset({"frequency", "descriptive"})


class AnalysisContractError(ValueError):
    """A structurally valid request that violates an analysis contract."""

    def __init__(self, message: str, *, code: str = "invalid_request", field: str = ""):
        super().__init__(message)
        self.code = code
        self.field = field


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def validate_transition(machine: str, current: str, target: str, guard_id: str) -> None:
    if machine not in ALLOWED_TRANSITIONS:
        raise AnalysisContractError("状態機械が正しくありません。", code="unknown_machine")
    if not isinstance(guard_id, str) or not re.fullmatch(r"[a-z][a-z0-9_.-]{2,80}", guard_id):
        raise AnalysisContractError("状態遷移にはguard IDが必要です。", code="missing_guard")
    if target not in ALLOWED_TRANSITIONS[machine].get(current, set()):
        raise AnalysisContractError(
            f"許可されていない状態遷移です: {machine} {current} -> {target}",
            code="invalid_transition",
        )


def validate_definition(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AnalysisContractError("定義はJSONオブジェクトで指定してください。", field="definition")
    result = dict(value)
    required_text = ("definition_id", "name", "description", "unit_of_analysis",
                     "output_column", "data_type", "measurement_level", "measurement_rule")
    for key in required_text:
        if not isinstance(result.get(key), str) or not result[key].strip():
            raise AnalysisContractError(f"{key}を指定してください。", field=key)
        result[key] = result[key].strip()
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{2,63}", result["definition_id"]):
        raise AnalysisContractError("definition_idが正しくありません。", field="definition_id")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{1,62}", result["output_column"]):
        raise AnalysisContractError("出力列名は英数字と_で指定してください。", field="output_column")
    columns = result.get("source_columns")
    if not isinstance(columns, list) or not columns or any(column not in SOURCE_COLUMNS for column in columns):
        raise AnalysisContractError("対応していない入力列が含まれています。", field="source_columns")
    if result["data_type"] not in DEFINITION_TYPES:
        raise AnalysisContractError("data_typeが正しくありません。", field="data_type")
    if result["measurement_level"] not in MEASUREMENT_LEVELS:
        raise AnalysisContractError("尺度水準が正しくありません。", field="measurement_level")
    if result["measurement_rule"] not in MEASUREMENT_RULES:
        raise AnalysisContractError("測定規則が正しくありません。", field="measurement_rule")
    method = result.get("method", "frequency")
    if method not in SUPPORTED_METHODS:
        raise AnalysisContractError("初回範囲で利用できない分析手法です。", code="method_unavailable", field="method")
    if method == "descriptive" and result["measurement_level"] not in {"interval", "ratio"}:
        raise AnalysisContractError(
            "名義・順序尺度へ記述統計の平均を適用できません。frequencyを選択してください。",
            code="incompatible_scale", field="method",
        )
    if result["measurement_rule"] in {"text_length", "duration"} and result["data_type"] != "number":
        raise AnalysisContractError("この測定規則のdata_typeはnumberです。", field="data_type")
    if result["measurement_rule"] == "duration" and "duration" not in columns:
        raise AnalysisContractError("duration規則にはduration列が必要です。", field="source_columns")
    if result["measurement_rule"] == "text_length" and "text" not in columns:
        raise AnalysisContractError("text_length規則にはtext列が必要です。", field="source_columns")
    levels = result.get("levels", [])
    if levels is not None and not isinstance(levels, list):
        raise AnalysisContractError("levelsは配列で指定してください。", field="levels")
    result["method"] = method
    result["source_columns"] = list(dict.fromkeys(columns))
    result["levels"] = list(levels or [])
    result["missing_rule"] = str(result.get("missing_rule") or "null_with_reason")
    result["aggregation"] = str(result.get("aggregation") or "none")
    result["denominator"] = str(result.get("denominator") or "all_included_segments")
    result["version"] = int(result.get("version") or 1)
    return result


def eligibility_assessment(definitions: list[dict[str, Any]], *, segment_count: int) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    checks.append({
        "dimension": "computability", "severity": "hard",
        "outcome": "pass" if segment_count > 0 else "fail",
        "reason_code": "input_available" if segment_count > 0 else "no_valid_input",
    })
    for definition in definitions:
        checks.append({
            "dimension": "inference_validity", "severity": "hard",
            "outcome": "pass", "reason_code": "descriptive_scope_only",
            "definition_id": definition["definition_id"],
        })
        checks.append({
            "dimension": "precision", "severity": "warning",
            "outcome": "unknown", "reason_code": "precision_not_predefined",
            "definition_id": definition["definition_id"],
        })
    blocked = any(
        check["severity"] == "hard" and check["outcome"] in {"fail", "unknown"}
        for check in checks
    )
    return {
        "contract": "EligibilityAssessment", "contract_version": CONTRACT_VERSION,
        "execution": "blocked" if blocked else "allowed",
        "inference_scope": "none" if blocked else "descriptive",
        "status": "ineligible" if blocked else (
            "eligible_with_warnings" if any(c["severity"] == "warning" and c["outcome"] != "pass" for c in checks)
            else "eligible"
        ),
        "checks": checks,
    }


def build_plan_envelope(
    *, item_id: str, source_revision: int, analysis_revision: int,
    input_fingerprint: str, payload: dict[str, Any], definitions: list[dict[str, Any]],
    segment_count: int,
) -> dict[str, Any]:
    mode = payload.get("mode", "automatic")
    if mode not in {"automatic", "manual"}:
        raise AnalysisContractError("modeはautomaticまたはmanualです。", field="mode")
    research = payload.get("research_protocol") or {"classification": "exploratory"}
    if not isinstance(research, dict) or research.get("classification", "exploratory") not in {
        "exploratory", "confirmatory",
    }:
        raise AnalysisContractError("研究区分が正しくありません。", field="research_protocol")
    if research.get("classification") == "confirmatory" and not research.get("preregistered"):
        raise AnalysisContractError(
            "検証的分析には事前固定した仮説・規則が必要です。",
            code="confirmatory_not_predefined", field="research_protocol",
        )
    targets = payload.get("publication_targets", ["input", "orchestrator", "visualization"])
    if not isinstance(targets, list) or any(t not in {"input", "orchestrator", "visualization"} for t in targets):
        raise AnalysisContractError("公開先が正しくありません。", field="publication_targets")
    provider_policy = payload.get("provider_policy", "local_only")
    if provider_policy != "local_only":
        raise AnalysisContractError(
            "初回pipelineはlocal_onlyだけを提供します。", code="provider_unavailable",
            field="provider_policy",
        )
    normalized_definitions = [validate_definition(value) for value in definitions]
    assessment = eligibility_assessment(normalized_definitions, segment_count=segment_count)
    steps = [
        {"step_id": "freeze_input", "milestone": "M0", "required": True, "parents": []},
        {"step_id": "outline_scope", "milestone": "M1", "required": False, "allow_not_applicable": True, "parents": ["freeze_input"]},
        {"step_id": "participation", "milestone": "M2", "required": True, "parents": ["freeze_input"]},
        {"step_id": "conversation_dynamics", "milestone": "M2", "required": True, "parents": ["freeze_input"]},
        {"step_id": "chart_specs", "milestone": "M3", "required": True, "parents": ["participation", "conversation_dynamics"]},
        {"step_id": "execution_binding", "milestone": "M4", "required": True, "parents": ["chart_specs"]},
        {"step_id": "manual_measurement", "milestone": "M5", "required": bool(normalized_definitions), "allow_not_applicable": not normalized_definitions, "parents": ["execution_binding"]},
        {"step_id": "comparison_scope", "milestone": "M6", "required": False, "allow_not_applicable": True, "parents": ["manual_measurement"]},
        {"step_id": "save_result", "milestone": "M7", "required": True, "parents": ["comparison_scope"]},
        {"step_id": "publish_result", "milestone": "M7", "required": bool(targets), "allow_not_applicable": not targets, "parents": ["save_result"]},
    ]
    envelope = {
        "contract": "PlanEnvelope", "contract_version": CONTRACT_VERSION,
        "item_id": item_id, "source_revision": int(source_revision),
        "analysis_revision": int(analysis_revision), "input_hash": input_fingerprint,
        "mode": mode, "provider_policy": provider_policy,
        "research_protocol": research, "publication_targets": list(dict.fromkeys(targets)),
        "capability_scope": {
            "selected": ["participation", "conversation_dynamics", "manual_measurement"],
            "catalog_version": CONTRACT_VERSION,
        },
        "binding_slots": [
            {"slot_id": f"definition:{value['definition_id']}", "allowed_methods": [value["method"]],
             "output_column": value["output_column"], "required": True}
            for value in normalized_definitions
        ],
        "steps": steps, "eligibility": assessment,
    }
    envelope["plan_hash"] = fingerprint(envelope)
    return envelope


def build_execution_binding(envelope: dict[str, Any], definitions: list[dict[str, Any]]) -> dict[str, Any]:
    values = [validate_definition(value) for value in definitions]
    by_id = {value["definition_id"]: value for value in values}
    resolved = []
    for slot in envelope.get("binding_slots", []):
        definition_id = str(slot["slot_id"]).split(":", 1)[-1]
        definition = by_id.get(definition_id)
        if definition is None:
            raise AnalysisContractError(
                f"必須の定義slotが未解決です: {definition_id}",
                code="unresolved_binding", field="definition_ids",
            )
        if definition["method"] not in slot["allowed_methods"]:
            raise AnalysisContractError("M0の許容範囲外の手法です。", code="binding_out_of_scope")
        resolved.append({
            "slot_id": slot["slot_id"], "definition_id": definition_id,
            "definition_version": definition["version"], "method": definition["method"],
            "output_column": definition["output_column"],
        })
    return {
        "contract": "ExecutionBinding", "contract_version": CONTRACT_VERSION,
        "plan_hash": envelope["plan_hash"], "resolved": resolved,
        "research_classification": envelope["research_protocol"]["classification"],
        "binding_hash": fingerprint(resolved),
    }


def capability_catalog() -> dict[str, Any]:
    return {"version": CONTRACT_VERSION, "capabilities": CAPABILITIES}

