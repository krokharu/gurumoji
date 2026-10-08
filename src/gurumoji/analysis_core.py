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
    "planning_roles": {
        "o01": {"status": "available", "engines": ["transformer", "lmstudio", "openai", "google"]},
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


def validate_definition(value: Any, *, require_version: bool = False) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AnalysisContractError("定義はJSONオブジェクトで指定してください。", field="definition")
    result = {key: item for key, item in value.items() if key not in {
        "status", "revision", "updated_at", "last_trial", "expected_revision", "expected_trial",
    }}
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
    if result["output_column"] in {"segment_id", "speaker", "speaker_name"} or "__missing_reason" in result["output_column"]:
        raise AnalysisContractError("根拠列・欠測理由列は出力列に使えません。", code="output_column_conflict", field="output_column")
    columns = result.get("source_columns")
    if not isinstance(columns, list) or not columns or any(not isinstance(column, str) or column not in SOURCE_COLUMNS for column in columns):
        raise AnalysisContractError("対応していない入力列が含まれています。", field="source_columns")
    if len(set(columns)) != 1:
        raise AnalysisContractError("現在の測定規則は1種類の入力列だけを扱います。", code="source_columns_unsupported", field="source_columns")
    if result["data_type"] not in DEFINITION_TYPES:
        raise AnalysisContractError("data_typeが正しくありません。", field="data_type")
    if result["measurement_level"] not in MEASUREMENT_LEVELS:
        raise AnalysisContractError("尺度水準が正しくありません。", field="measurement_level")
    if result["measurement_rule"] not in MEASUREMENT_RULES:
        raise AnalysisContractError("測定規則が正しくありません。", field="measurement_rule")
    method = result.get("method", "frequency")
    if not isinstance(method, str) or method not in SUPPORTED_METHODS:
        raise AnalysisContractError("初回範囲で利用できない分析手法です。", code="method_unavailable", field="method")
    if method == "descriptive" and result["data_type"] != "number":
        raise AnalysisContractError("記述統計にはnumber型が必要です。", code="incompatible_type", field="data_type")
    if result["data_type"] in {"string", "category", "boolean"} and result["measurement_level"] not in {"nominal", "ordinal"}:
        raise AnalysisContractError("文字・カテゴリ・真偽値には名義または順序尺度を指定してください。", code="incompatible_scale", field="measurement_level")
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
    if result["measurement_rule"] in {"nonempty", "boolean_true"} and result["data_type"] != "boolean":
        raise AnalysisContractError("この測定規則のdata_typeはbooleanです。", code="incompatible_type", field="data_type")
    if result["measurement_rule"] == "nonempty" and columns[0] not in {"text", "speaker", "speaker_name", "role"}:
        raise AnalysisContractError("nonempty規則は文字列の入力列に対応しています。", code="source_columns_unsupported", field="source_columns")
    if result["measurement_rule"] == "boolean_true" and columns[0] != "question_candidate":
        raise AnalysisContractError("boolean_true規則にはquestion_candidate列が必要です。", code="source_columns_unsupported", field="source_columns")
    supported_behavior = {"unit_of_analysis": "segment", "missing_rule": "null_with_reason",
                          "aggregation": "none", "denominator": "all_included_segments"}
    for field, supported in supported_behavior.items():
        if result.get(field, supported) != supported:
            raise AnalysisContractError(f"現在対応している{field}は{supported}です。", code="definition_behavior_unsupported", field=field)
        result[field] = supported
    levels = result.get("levels", [])
    if levels is not None and not isinstance(levels, list):
        raise AnalysisContractError("levelsは配列で指定してください。", field="levels")
    result["method"] = method
    result["source_columns"] = list(dict.fromkeys(columns))
    result["levels"] = list(levels or [])
    result["missing_rule"] = str(result.get("missing_rule") or "null_with_reason")
    result["aggregation"] = str(result.get("aggregation") or "none")
    result["denominator"] = str(result.get("denominator") or "all_included_segments")
    version = result.get("version") if require_version else result.get("version", 1)
    if type(version) is not int or version < 1:
        raise AnalysisContractError("定義versionは1以上の整数で指定してください。", code="definition_version_invalid", field="version")
    result["version"] = version
    return result


def validate_definitions(values: list[dict[str, Any]], *, require_version: bool = True) -> list[dict[str, Any]]:
    """Protect evidence IDs, missingness columns, and every output namespace."""
    normalized = [validate_definition(value, require_version=require_version) for value in values]
    ids: set[str] = set()
    columns: set[str] = set()
    for value in normalized:
        identifier, column = value["definition_id"], value["output_column"]
        names = {column, column + "__missing_reason"}
        if identifier in ids or names & columns:
            raise AnalysisContractError("定義IDまたは出力列が重複しています。", code="output_column_conflict", field="definition_ids")
        ids.add(identifier)
        columns.update(names)
    return normalized


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


def validate_planning_proposal(
    proposal: Any, *, input_hash: str, source_revision: int,
    analysis_revision: int, provider_policy: str,
) -> dict[str, Any]:
    """Accept O01 advice as a bounded annotation, never as executable steps."""
    from .analysis_plan_advisor import ADVISOR_VERSION, normalize_candidate

    if not isinstance(proposal, dict) or proposal.get("version") != ADVISOR_VERSION:
        raise AnalysisContractError("計画候補の版が正しくありません。", code="invalid_proposal")
    if (proposal.get("input_hash") != input_hash
            or proposal.get("source_revision") != source_revision
            or proposal.get("analysis_revision") != analysis_revision):
        raise AnalysisContractError("計画候補の入力版が変わっています。再提案してください。", code="revision_conflict")
    engine = proposal.get("engine")
    provider = proposal.get("provider")
    model = proposal.get("model")
    if not isinstance(engine, str) or engine not in {"transformer", "llm"} or not isinstance(model, str) or not model.strip() or len(model) > 200:
        raise AnalysisContractError("計画候補の実行モデルが正しくありません。", code="invalid_proposal")
    if not isinstance(provider, str):
        raise AnalysisContractError("計画候補の実行先が正しくありません。", code="invalid_proposal")
    if engine == "transformer" and provider != "local_transformer":
        raise AnalysisContractError("Transformer計画候補の実行先が正しくありません。", code="invalid_proposal")
    if engine == "llm" and provider not in {"lmstudio", "openai", "google"}:
        raise AnalysisContractError("計画候補のLLMが正しくありません。", code="invalid_proposal")
    if provider in {"openai", "google"} and provider_policy != "cloud_allowed":
        raise AnalysisContractError("クラウドLLMにはcloud_allowedが必要です。", code="provider_unavailable")
    objective = proposal.get("objective")
    if not isinstance(objective, str) or not 3 <= len(objective.strip()) <= 500:
        raise AnalysisContractError("計画候補の分析目的が正しくありません。", code="invalid_proposal")
    return {
        "version": ADVISOR_VERSION, "input_hash": input_hash,
        "source_revision": source_revision, "analysis_revision": analysis_revision,
        "engine": engine, "provider": provider, "model": model.strip(),
        "objective": objective.strip(), **normalize_candidate(proposal),
    }


PUBLICATION_TARGETS = ("input", "orchestrator", "visualization")
EFFECTIVE_PUBLICATION_WRITERS = ("research", *PUBLICATION_TARGETS)


def validate_publication_targets(value: Any) -> list[str]:
    # The existing publisher is one four-Vault operation, not independent writers.
    if (not isinstance(value, list) or any(not isinstance(target, str) for target in value)
            or value and (len(value) != len(PUBLICATION_TARGETS) or set(value) != set(PUBLICATION_TARGETS))):
        raise AnalysisContractError("公開先は空配列またはinput・orchestrator・visualizationの全3件を指定してください。", field="publication_targets")
    return list(PUBLICATION_TARGETS) if value else []


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
    targets = validate_publication_targets(payload.get("publication_targets", list(PUBLICATION_TARGETS)))
    provider_policy = payload.get("provider_policy", "local_only")
    if not isinstance(provider_policy, str) or provider_policy not in {"local_only", "cloud_allowed"}:
        raise AnalysisContractError(
            "送信方針が正しくありません。", code="provider_unavailable",
            field="provider_policy",
        )
    proposal = payload.get("planning_proposal")
    if proposal is not None:
        proposal = validate_planning_proposal(
            proposal, input_hash=input_fingerprint, source_revision=source_revision,
            analysis_revision=analysis_revision, provider_policy=provider_policy,
        )
    if provider_policy == "cloud_allowed" and (
        proposal is None or proposal["provider"] not in {"openai", "google"}
    ):
        raise AnalysisContractError("local_only が既定です。クラウド送信方針には選択したLLMの計画候補が必要です。", code="provider_unavailable")
    normalized_definitions = validate_definitions(definitions)
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
        "research_protocol": research, "publication_targets": targets,
        "effective_publication_writers": list(EFFECTIVE_PUBLICATION_WRITERS) if targets else [],
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
    if proposal is not None:
        envelope["planning_proposal"] = proposal
    envelope["plan_hash"] = fingerprint(envelope)
    return envelope


def build_execution_binding(envelope: dict[str, Any], definitions: list[dict[str, Any]]) -> dict[str, Any]:
    values = validate_definitions(definitions)
    by_id = {value["definition_id"]: value for value in values}
    revisions = {value["definition_id"]: value.get("revision") for value in definitions}
    resolved = []
    snapshots = {}
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
        revision = revisions[definition_id]
        if revision is not None and (type(revision) is not int or revision < 1):
            raise AnalysisContractError("定義revisionが正しくありません。", code="revision_conflict")
        snapshots[definition_id] = {"payload": definition, "definition_hash": fingerprint(definition),
                                    "revision": revision, "status": "adopted"}
        resolved.append({
            "slot_id": slot["slot_id"], "definition_id": definition_id,
            "definition_version": definition["version"], "definition_revision": revision,
            "definition_hash": fingerprint(definition), "method": definition["method"],
            "output_column": definition["output_column"],
        })
    return {
        "contract": "ExecutionBinding", "contract_version": "analysis-binding-2",
        "plan_hash": envelope["plan_hash"], "resolved": resolved,
        "research_classification": envelope["research_protocol"]["classification"],
        "definition_snapshots": snapshots,
        "binding_hash": fingerprint({"resolved": resolved, "definition_snapshots": snapshots}),
    }


def capability_catalog(*, connections: bool = False) -> dict[str, Any]:
    result = {"version": CONTRACT_VERSION, "capabilities": CAPABILITIES}
    if connections:
        from .analysis_method_registry import METHODS, connection_method_descriptor
        result["connections"] = {"version": CONNECTION_VERSION, "kinds": sorted(ASSET_KINDS),
                                 "roles": sorted(REFERENCE_ROLES),
                                 "methods": [connection_method_descriptor(key) for key, _, _ in METHODS]}
    return result


CONNECTION_VERSION = "analysis-connections-1"
TABLE_PILOT_VERSION = "table-pilot-1"
TABLE_PILOT_MAX_BYTES = 131072
ASSET_KINDS = frozenset({"observation_table", "claim_set", "relation_graph", "event_sequence", "embedding_matrix"})
REFERENCE_ROLES = frozenset({"data_input", "selection_basis", "evidence_context", "parameter_source"})
ORIGINAL_SOURCE_TYPES = frozenset({"snapshot", "utterance", "raw_text", "media", "researcher_memo", "definition"})
CONNECTION_UNITS = frozenset({"utterance", "conversation_speaker", "participant", "conversation", "episode", "dataset_claim", "event", "vector_row", "report_claim"})
HASH_DOMAINS = frozenset({"raw-bytes-v1", "canonical-json-v1", "utf8-text-v1", "ta-candidate-content-v1", "ta-theme-content-v1", "human-record-v1"})
CONNECTION_PURPOSES = frozenset({"exploratory", "descriptive", "qualitative_compare", "confirmatory"})


def _connection_object(value, keys, optional=()):
    return isinstance(value, dict) and set(keys) <= set(value) <= set(keys) | set(optional)


def _connection_id(value):
    return isinstance(value, str) and bool(value.strip())


def _connection_hash(value):
    return isinstance(value, str) and re.fullmatch(r"sha256:[0-9a-f]{64}", value) is not None


def _connection_list(value, allowed=None, *, empty=True):
    return (isinstance(value, list) and (empty or bool(value))
            and all(_connection_id(v) for v in value) and len(set(value)) == len(value)
            and (allowed is None or set(value) <= allowed))


def _connection_schema(value):
    return (_connection_object(value, ("schema_id", "version", "schema_hash"))
            and _connection_id(value["schema_id"]) and type(value["version"]) is int
            and value["version"] >= 1 and _connection_hash(value["schema_hash"]))


def _connection_adapter(value):
    return (_connection_object(value, ("adapter_id", "version"))
            and all(_connection_id(v) for v in value.values()))


def validate_connection_actor(actor):
    extras = {"model_id", "revision", "provider"}
    if (not _connection_object(actor, ("kind", "actor_id", "step_ids"), extras)
            or not _connection_id(actor["kind"]) or actor["kind"] not in {"ai", "code", "researcher", "system"}
            or not _connection_id(actor["actor_id"]) or not _connection_list(actor["step_ids"])
            or (actor["kind"] == "ai" and not all(_connection_id(actor.get(k)) for k in extras))
            or (actor["kind"] != "ai" and extras & set(actor))):
        raise AnalysisContractError("actorの型・条件が不正です。", code="connection_actor_invalid")
    return actor


def validate_connection_slot(slot: Any) -> dict:
    """Strict Slot metadata from common S1/r3; no persistence or resolver."""
    fields = ("slot_id", "required", "min_items", "max_items", "roles", "accept_kinds", "accept_schemas",
              "accept_units", "scope_modes", "actors", "adapter", "purposes", "max_bytes")
    valid = _connection_object(slot, fields, ("accept_source_types",))
    if valid:
        valid = (_connection_id(slot["slot_id"]) and type(slot["required"]) is bool
                 and all(type(slot[k]) is int for k in ("min_items", "max_items", "max_bytes"))
                 and 0 <= slot["min_items"] <= slot["max_items"] and slot["max_items"] >= 1
                 and slot["max_bytes"] >= 1 and (not slot["required"] or slot["min_items"] >= 1)
                 and _connection_list(slot["roles"], REFERENCE_ROLES, empty=False)
                 and _connection_list(slot["accept_kinds"], ASSET_KINDS)
                 and isinstance(slot["accept_schemas"], list) and bool(slot["accept_schemas"])
                 and all(_connection_schema(v) for v in slot["accept_schemas"])
                 and len({fingerprint(v) for v in slot["accept_schemas"]}) == len(slot["accept_schemas"])
                 and _connection_list(slot["accept_units"], CONNECTION_UNITS, empty=False)
                 and _connection_list(slot["scope_modes"], {"dataset", "selection", "section", "episode"}, empty=False)
                 and _connection_list(slot["actors"], {"ai", "code", "researcher", "system"}, empty=False)
                 and _connection_adapter(slot["adapter"])
                 and _connection_list(slot["purposes"], CONNECTION_PURPOSES, empty=False))
    if valid:
        valid = ("accept_source_types" not in slot if slot["accept_kinds"] else
                 _connection_list(slot.get("accept_source_types"), ORIGINAL_SOURCE_TYPES, empty=False))
    if not valid:
        raise AnalysisContractError("入力slotの型・条件が不正です。", code="connection_slot_invalid")
    return json.loads(canonical(slot))


def _connection_source_ref(ref):
    if not _connection_object(ref, ("target_type", "target_id", "version", "content_hash", "hash_domain"),
                              ("library_id", "utterance_id", "locator")):
        return False
    if (not _connection_id(ref["target_type"]) or not _connection_id(ref["hash_domain"])
            or ref["target_type"] not in ORIGINAL_SOURCE_TYPES or not _connection_id(ref["target_id"])
            or not _connection_id(ref["version"]) or not _connection_hash(ref["content_hash"])
            or ref["hash_domain"] not in HASH_DOMAINS):
        return False
    if ref["target_type"] in {"snapshot", "utterance"} and not _connection_id(ref.get("library_id")):
        return False
    if ref["target_type"] == "utterance":
        if not _connection_id(ref.get("utterance_id")): return False
    elif "utterance_id" in ref:
        return False
    return all(_connection_id(ref[k]) for k in ("library_id", "utterance_id", "locator") if k in ref)


def assess_connection_inputs(slot: Any, inputs: Any, descriptor: Any) -> dict:
    """Assess declared metadata only, before G4b resolution/adoption.

    Inputs are a closed, internal selection envelope (not the full proposed
    InputRef/Asset schema). Selected candidates carry schema/unit/scope/actor/
    adapter/purpose plus a SourceRef or artifact hash. No metadata is inferred
    from old runs, labels, receipts or free text; eligibility enables no calls.
    """
    def result(decision, reason):
        return {"version": CONNECTION_VERSION, "decision": decision, "reason": reason,
                "execution_enabled": False, "adoption_performed": False,
                "unexecuted_checks": ["content_resolution", "state_policy_pre_adoption", "actual_payload_byte_limit"]}
    try:
        slot = validate_connection_slot(slot)
    except (AnalysisContractError, TypeError, ValueError):
        return result("rejected", "connection_slot_invalid")
    if not isinstance(descriptor, dict): return result("rejected", "method_unregistered")
    from .analysis_method_registry import connection_method_descriptor
    method_id = descriptor.get("method_id")
    if not _connection_id(method_id): return result("rejected", "method_unregistered")
    registered = connection_method_descriptor(method_id)
    try:
        if registered is None or canonical(registered) != canonical(descriptor):
            return result("rejected", "capability_descriptor_mismatch")
    except (TypeError, ValueError, UnicodeError):
        return result("rejected", "capability_descriptor_mismatch")
    if not isinstance(inputs, list): return result("rejected", "input_shape")
    try:
        encoded = canonical(inputs)
    except (TypeError, ValueError, UnicodeError):
        return result("rejected", "input_encoding")
    if len(encoded) > slot["max_bytes"]: return result("needs_input", "metadata_byte_limit")
    selected, ids = [], set()
    for ref in inputs:
        if not _connection_object(ref, ("input_ref_id", "selection", "role", "omission_reason"), ("candidate",)):
            return result("rejected", "input_shape")
        if not _connection_id(ref["input_ref_id"]) or ref["input_ref_id"] in ids or ref["role"] not in slot["roles"]:
            return result("rejected", "input_identity_or_role")
        ids.add(ref["input_ref_id"])
        if ref["selection"] == "omitted":
            if slot["required"] or "candidate" in ref or not _connection_id(ref["omission_reason"]):
                return result("rejected", "illegal_omission")
            continue
        if ref["selection"] != "selected" or ref["omission_reason"] is not None:
            return result("rejected", "selection_invalid")
        if "candidate" not in ref: return result("needs_input", "selected_input_unresolved")
        if ref["role"] not in descriptor.get("reference_roles", []):
            return result("unsupported", "method_reference_role_unimplemented")
        selected.append(ref["candidate"])
    if not slot["min_items"] <= len(selected) <= slot["max_items"]:
        return result("needs_input" if len(selected) < slot["min_items"] else "rejected", "slot_cardinality")
    for candidate in selected:
        fields = ("source_type", "schema", "unit", "scope_mode", "scope_policy", "actor", "adapter", "purpose", "meaning_status", "human_review_state")
        if not _connection_object(candidate, fields, ("source_ref", "kind", "content_hash", "content_domain")):
            return result("rejected", "candidate_shape")
        if not all(_connection_id(candidate[k]) for k in ("source_type", "unit", "scope_mode", "scope_policy", "purpose", "meaning_status", "human_review_state")):
            return result("rejected", "candidate_enum_shape")
        actor = candidate["actor"]
        try:
            validate_connection_actor(actor)
        except AnalysisContractError:
            return result("rejected", "actor_shape")
        if not _connection_schema(candidate["schema"]) or not _connection_adapter(candidate["adapter"]):
            return result("rejected", "schema_or_adapter_shape")
        if candidate["unit"] not in CONNECTION_UNITS or candidate["scope_mode"] not in {"dataset", "selection", "section", "episode"}:
            return result("rejected", "unit_or_scope_invalid")
        if candidate["purpose"] not in CONNECTION_PURPOSES or candidate["meaning_status"] not in {"declared", "unknown"} or candidate["human_review_state"] not in {"structural_checked", "human_pending", "human_reviewed"}:
            return result("rejected", "purpose_or_review_invalid")
        if candidate["source_type"] == "original":
            if (set(candidate) != set(fields) | {"source_ref"} or slot["accept_kinds"]
                    or not _connection_source_ref(candidate["source_ref"])
                    or candidate["source_ref"]["target_type"] not in slot["accept_source_types"]):
                return result("rejected", "original_source_invalid")
        elif candidate["source_type"] == "artifact":
            if (set(candidate) != set(fields) | {"kind", "content_hash", "content_domain"}
                    or not _connection_id(candidate["kind"]) or not _connection_id(candidate["content_domain"])
                    or candidate["kind"] not in ASSET_KINDS or not _connection_hash(candidate["content_hash"])
                    or candidate["content_domain"] not in HASH_DOMAINS or candidate["kind"] not in slot["accept_kinds"]):
                return result("rejected", "artifact_kind_or_hash")
        else: return result("rejected", "source_type")
        if (candidate["schema"] not in slot["accept_schemas"] or candidate["unit"] not in slot["accept_units"]
                or candidate["scope_mode"] not in slot["scope_modes"] or actor["kind"] not in slot["actors"]
                or candidate["adapter"] != slot["adapter"] or candidate["purpose"] not in slot["purposes"]):
            return result("rejected", "slot_incompatible")
        if candidate["meaning_status"] == "unknown" or candidate["human_review_state"] == "human_pending":
            return result("human_pending", "meaning_or_human_unconfirmed")
        if (candidate["schema"] != descriptor.get("native_input_schema")
                or actor["kind"] not in descriptor.get("input_actor_kinds", [])
                or candidate["adapter"] != descriptor.get("native_adapter") or candidate["unit"] not in descriptor.get("units", [])
                or candidate["scope_mode"] not in descriptor.get("scope_modes", [])
                or candidate["purpose"] not in descriptor.get("purposes", [])
                or candidate["scope_policy"] != descriptor.get("scope_policy")):
            return result("unsupported", "method_capability_unavailable")
        if candidate["source_type"] == "artifact" and not descriptor.get("typed_asset_adapter_supported"):
            return result("unsupported", "typed_asset_adapter_unimplemented")
        if candidate["source_type"] == "original" and (not descriptor.get("native_adapter_supported") or candidate["source_ref"]["target_type"] not in descriptor.get("original_source_types", [])):
            return result("unsupported", "original_adapter_unimplemented")
    return result("eligible", "metadata_compatible")


def validate_table_pilot_request(method_id, request):
    """Closed opt-in code request. No AI expressions or implicit conversion."""
    from .analysis_method_registry import TABLE_PILOT_METHODS, table_pilot_slot
    def reject(code="table_request_invalid"):
        raise AnalysisContractError("表パイロットの固定契約と一致しません。", code=code)
    if method_id not in TABLE_PILOT_METHODS: reject("table_method_unsupported")
    if not _connection_object(request, ("version", "actor", "parameters", "bindings")):
        reject()
    if request["version"] != TABLE_PILOT_VERSION or request["actor"] != "code": reject("table_actor_or_version")
    parameters = request["parameters"]
    if not _connection_object(parameters, TABLE_PILOT_METHODS[method_id]): reject("table_parameters")
    if method_id == "table_projection":
        if (not _connection_list(parameters["columns"], empty=False)
                or not _connection_list(parameters["row_ids"], empty=False)
                or not {"utterance_id", "conversation_id", "value_status"} <= set(parameters["columns"])):
            reject("table_projection_parameters")
    elif method_id == "table_join":
        if parameters["key"] != "utterance_id": reject("table_join_key")
    else:
        if parameters["status_column"] != "value_status": reject("table_status_column")
        if any(not _connection_id(parameters[k]) for k in parameters if k.endswith("_column")):
            reject("table_column")
        if method_id == "table_aggregate" and any(parameters[k] != v for k,v in
                (("operation", "count"), ("group_by", "utterance_id"), ("unit", "utterance"))):
            reject("table_unit_or_operation_unsupported")
    bindings = request["bindings"]
    if not _connection_object(bindings, ("slot", "inputs", "context")): reject("table_bindings")
    if canonical(bindings["slot"]) != canonical(table_pilot_slot(method_id)): reject("table_slot")
    inputs = bindings["inputs"]
    if (not isinstance(inputs, list) or len(inputs) != bindings["slot"]["min_items"]
            or any(not isinstance(ref, dict) or ref.get("selection") != "selected"
                   or ref.get("role") != "data_input" or not isinstance(ref.get("source"), dict)
                   or ref["source"].get("type") != "frozen" for ref in inputs)):
        reject("table_frozen_inputs_required")
    context = bindings["context"]
    context_fields = ("plan_id", "plan_version", "plan_hash", "generation", "consumer_task_id", "purpose",
                      "destination", "scope_id", "scope_manifest_hash", "cancelled")
    if (not _connection_object(context, context_fields)
            or any(type(context[k]) is not int or context[k] < 1 for k in ("plan_version", "generation"))
            or type(context["cancelled"]) is not bool
            or not all(_connection_id(context[k]) for k in ("plan_id", "consumer_task_id", "scope_id", "destination"))
            or not all(_connection_hash(context[k]) for k in ("plan_hash", "scope_manifest_hash"))
            or context["purpose"] not in {"exploratory", "descriptive"} or context["destination"] != "local"):
        reject("table_context")
    seen = set()
    for ref in inputs:
        required = ("plan_id", "plan_version", "plan_hash", "generation", "consumer_task_id", "slot_id",
                    "input_ref_id", "role", "selection", "omission_reason", "source", "selector")
        if (not _connection_object(ref, required) or ref["omission_reason"] is not None
                or not _connection_id(ref["input_ref_id"]) or ref["input_ref_id"] in seen
                or ref["slot_id"] != "table"
                or any(type(ref[k]) is not type(context[k]) or ref[k] != context[k] for k in
                       ("plan_id", "plan_version", "plan_hash", "generation", "consumer_task_id"))):
            reject("table_input_identity")
        seen.add(ref["input_ref_id"])
        source = ref["source"]
        if (not _connection_object(source, ("type", "asset_key", "content_hash", "content_domain"))
                or source["content_domain"] != "raw-bytes-v1" or not _connection_hash(source["content_hash"])
                or not _connection_object(source["asset_key"], ("library_id", "store_run_id", "artifact_id", "output_name"))
                or not all(_connection_id(v) for v in source["asset_key"].values())):
            reject("table_frozen_source")
        selector = ref["selector"]
        if (not _connection_object(selector, ("row_ids", "column_ids", "range_ref", "selection_hash"))
                or not _connection_list(selector["row_ids"]) or not _connection_list(selector["column_ids"])
                or selector["range_ref"] is not None
                or selector["selection_hash"] != fingerprint({k:v for k,v in selector.items() if k != "selection_hash"})):
            reject("table_selector_unsupported")
    if len(canonical(request)) > TABLE_PILOT_MAX_BYTES: reject("table_request_byte_limit")
    return json.loads(canonical(request))
