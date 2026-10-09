"""Versioned, local-only context preparation. No inference or model loading here."""
from __future__ import annotations

import copy
import hashlib
import json
from urllib.parse import urlsplit

from ..analysis_core import AnalysisContractError
from .ai.client import lmstudio_base_url, json_messages

CONTEXT_VERSION = 1
OUTPUT_RESERVE = 1600
SAFETY_MARGIN = 512


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def reference_messages(context):
    """Handler-resolved immutable slices, separate from task instructions.

    Paths are logical DB/Vault locators, never a model filesystem permission.
    The source snapshot/results remain authoritative; this is a rendered slice.
    """
    control = copy.deepcopy(context)
    origin = control.pop("resources_origin", {})
    initial = origin.get("initial_id", context.get("data_version", "unknown"))
    resources, references = [], []
    for field in ("raw_evidence", "labels", "initial", "results", "issues", "label_proposals",
                  "initial_label_catalog", "initial_analysis_report", "domain_reports",
                  "prior_domain_reports", "current_view", "history", "stop_proposal", "expert_knowledge"):
        if field not in control or not control[field]:
            continue
        content = control.pop(field)
        if field == "expert_knowledge":
            path = "obsidian://software/50-Analysis-Methods/selected-context"
        elif field in {"raw_evidence", "labels", "initial"}:
            path = f"db://orchestration_initials/{initial}/{field}"
        else:
            path = f"db://orchestration_runs/{origin.get('run_id', 'current')}/{field}"
        sha = digest(content)
        reference = {"resource_id": field, "path": path, "sha256": sha,
                     "data_version": context.get("data_version"), "read_scope": "provided_slice"}
        if field == "raw_evidence":
            reference["evidence_ids"] = [row["evidence_id"] for row in content]
        if field == "expert_knowledge" and isinstance(content, dict):
            reference["sources"] = [{key: row[key] for key in ("note_id", "path", "vault_kind", "revision", "source_sha256") if key in row}
                                    for row in content.get("sources", [])]
            if (content.get("brief") or {}).get("source"):
                reference["sources"].append(content["brief"]["source"])
        references.append(reference)
        resources.append(json.dumps({"message_kind": "resource_data", "reference": reference,
                                     "content": content}, ensure_ascii=False, separators=(",", ":")))
    control.update(message_kind="task_instruction", resource_delivery="handler_preloaded",
                   resource_references=references)
    return json.dumps(control, ensure_ascii=False, separators=(",", ":")), resources


def restored_reference_context(user, data_messages=None):
    """Validate and reconstruct packets for diagnostics/tests; no filesystem read."""
    control = json.loads(user)
    if control.get("message_kind") != "task_instruction":
        return control
    references = control.pop("resource_references")
    control.pop("message_kind")
    control.pop("resource_delivery")
    if len(references) != len(data_messages or []):
        raise ValueError("Resource delivery incomplete")
    for reference, raw in zip(references, data_messages or []):
        resource = json.loads(raw)
        if resource.get("message_kind") != "resource_data" or resource.get("reference") != reference or digest(resource.get("content")) != reference["sha256"]:
            raise ValueError("Resource hash mismatch")
        control[reference["resource_id"]] = resource["content"]
    return control


def compact_context(context):
    value = copy.deepcopy(context)
    task = value.get("task", {})
    value["task"] = {key: task[key] for key in (
        "task_id", "role", "phase", "iteration", "method_id", "codebook_version", "intent") if key in task}
    coverage = value.get("coverage", {})
    # IDs of unread rows are planning information, never evidence for a claim.
    index = coverage.pop("evidence_index", [])
    if index:
        coverage["index_ref"] = {"data_version": value.get("data_version"), "sha256": digest(index)}
    value.pop("usage", None)
    value.pop("critique_responses", None)
    report = value.get("initial_analysis_report")
    if report:
        report["full_report_sha256"] = digest(report)
        # Requirements, their exceptions/reasons and sources remain complete.
        report["reports"] = [{key: row[key] for key in (
            "role", "method_id", "result_id", "raw_hash", "requirement_count") if key in row}
            for row in report.get("reports", [])]
    phase = task.get("phase")
    if phase in {"initial_analysis", "initial_routing", "initial_labels"}:
        value["task"].pop("intent", None)
    if phase == "initial_routing":
        return {key: value[key] for key in ("task", "question", "data_version",
                "initial_analysis_report", "research_mode", "execution_allowed", "expert_knowledge", "resources_origin") if key in value}
    if task.get("role") in {"core", "orchestrator"}:
        # The original report is already represented by immutable result references.
        value.pop("initial_analysis_report", None)
        pending = value.get("iteration_review", {}).get("pending_result_ids", [])
        value["results"] = [r for r in value.get("results", []) if r["result_id"] in pending]
        value["dependency_task_ids"] = [r["task_id"] for r in value["results"] if "task_id" in r]
        if task.get("role") == "core" and value.get("domain_reports"):
            value["dependency_task_ids"] = [r["task_id"] for r in value["domain_reports"]]
        catalog = value.get("initial_label_catalog")
        if catalog and "definition_sources" in catalog:
            all_definitions = catalog["definitions"]
            paired = [(definition, source) for definition, source in zip(all_definitions, catalog["definition_sources"])
                      if source in pending]
            catalog["omitted_definition_count"] = len(all_definitions) - len(paired)
            catalog["definitions"] = [definition for definition, source in paired]
            catalog["definition_sources"] = [source for definition, source in paired]
            catalog["full_catalog_sha256"] = digest(context["initial_label_catalog"])
            catalog["read_scope"] = "pending_result_definitions"
            catalog["result_ids"] = [key for key in catalog.get("result_ids", []) if key in pending]
            catalog["source_hashes"] = {key: row for key, row in catalog.get("source_hashes", {}).items() if key in pending}
    instruction = value.get("routing_instruction")
    if instruction:
        value["routing_instruction"] = {key: instruction[key] for key in (
            "question", "why_now", "success_criteria", "role", "method_id") if key in instruction}
    return value


def reduce_context(context):
    """Reduce complete units; do not shorten mandatory conditions or utterances."""
    value = copy.deepcopy(context)
    pending = value.get("iteration_review", {}).get("pending_result_ids", [])
    if len(pending) > 1:
        kept = pending[:max(1, len(pending) // 2)]
        value["iteration_review"]["pending_result_ids"] = kept
        value["iteration_review"]["omitted_pending_result_count"] += len(pending) - len(kept)
        value["results"] = [r for r in value.get("results", []) if r["result_id"] in kept]
        removed = set(pending) - set(kept)
        issues = value.get("issues", [])
        hidden = [row for row in issues if row["result_id"] in removed]
        value["issues"] = [row for row in issues if row["result_id"] not in removed]
        value["label_proposals"] = [row for row in value.get("label_proposals", []) if row.get("result_id") not in removed]
        if hidden:
            value.setdefault("issue_scope", {}).setdefault("unread_result_issue_count", 0)
            value["issue_scope"]["unread_result_issue_count"] += len(hidden)
        catalog = value.get("initial_label_catalog")
        if catalog and "definition_sources" in catalog:
            paired = [(definition, source) for definition, source in zip(catalog["definitions"], catalog["definition_sources"]) if source in kept]
            catalog["omitted_definition_count"] += len(catalog["definitions"]) - len(paired)
            catalog["definitions"] = [definition for definition, source in paired]
            catalog["definition_sources"] = [source for definition, source in paired]
        return value
    rows = value.get("raw_evidence", [])
    # Initial pages must be read in full, including boundary context. Hold an
    # oversized page before inference; never silently lose its owned rows.
    if len(rows) > 1 and value.get("task", {}).get("phase") != "initial_analysis":
        value["raw_evidence"] = rows[:max(1, len(rows) // 2)]
        coverage = value["coverage"]
        coverage.update(provided_count=len(value["raw_evidence"]),
                        omitted_count=coverage["available_count"] - len(value["raw_evidence"]), complete=False)
        return value
    return None


def hydrate_core_evidence(context, pool, row_limit, text_limit):
    """Read actual source rows cited by this result batch, in source order."""
    if not pool:
        return context
    wanted = {ref for result in context.get("results", [])
              for field in ("claims", "issues", "label_requirements")
              for item in result.get("content", {}).get(field, []) for ref in item.get("evidence_ids", [])}
    batch = {result["result_id"] for result in context.get("results", []) if "result_id" in result}
    wanted.update(ref for issue in context.get("issues", []) if issue.get("result_id") in batch
                  for ref in issue.get("evidence_ids", []))
    wanted.update(ref for definition in (context.get("initial_label_catalog") or {}).get("definitions", [])
                  for ref in definition.get("evidence_ids", []))
    wanted.update(ref for report in context.get("domain_reports", [])
                  for claim in report.get("claims", []) for ref in claim.get("evidence_ids", []))
    if not wanted:
        wanted = {ref for claim in context.get("current_view", {}).get("claims", []) for ref in claim.get("evidence_ids", [])}
    if not wanted:
        return context
    rows = [row for row in pool if row["evidence_id"] in wanted]
    provided, size = [], 0
    for row in rows:
        if len(provided) >= row_limit or size + len(row["text"]) > text_limit:
            break
        provided.append(copy.deepcopy(row))
        size += len(row["text"])
    value = copy.deepcopy(context)
    value["raw_evidence"] = provided
    value["coverage"].update(available_count=len(rows), provided_count=len(provided),
        omitted_count=len(rows) - len(provided), complete=len(rows) == len(provided),
        scope="result_evidence", dataset_available_count=len(pool))
    if "labels" in value:
        utterances = {row["utterance_id"] for row in provided}
        value["labels"] = {key: item for key, item in value["labels"].items() if key in utterances}
    return value


def context_manifest(context, schema, system, user, budget, data_messages=None):
    provided = [r["evidence_id"] for r in context.get("raw_evidence", [])]
    citations = set(provided)
    for claim in context.get("current_view", {}).get("claims", []):
        citations.update(claim.get("evidence_ids", []))
    for report in context.get("prior_domain_reports", []):
        for claim in report.get("claims", []):
            citations.update(claim.get("evidence_ids", []))
    if context.get("task", {}).get("role") not in {"core", "orchestrator"}:
        for result in context.get("results", []):
            for claim in result.get("content", {}).get("claims", []):
                citations.update(claim.get("evidence_ids", []))
    return {"version": CONTEXT_VERSION, "dataset_version": context.get("data_version"),
            "context_sha256": digest(context), "schema_sha256": digest(schema),
            "system_sha256": digest(system), "user_sha256": digest(user),
            "provided_evidence_ids": provided, "citation_ids": sorted(citations),
            "coverage": copy.deepcopy(context.get("coverage", {})),
            "requested_result_ids": context.get("iteration_review", {}).get("pending_result_ids", []),
            "provided_issue_ids": [row["issue_id"] for row in context.get("issues", [])],
            "provided_proposal_ids": [row["proposal_id"] for row in context.get("label_proposals", [])],
            "provided_domain_report_ids": [row["result_id"] for row in context.get("domain_reports", [])],
            "provided_prior_domain_report_ids": [row["result_id"] for row in context.get("prior_domain_reports", [])],
            "expert_knowledge": copy.deepcopy(context.get("expert_knowledge")), "budget": budget,
            **({"reference_version": 1, "data_messages_sha256": digest(data_messages),
                "resource_references": json.loads(user)["resource_references"]} if data_messages is not None else {})}


def measure_local_context(model, base_url, system, user, schema, output_reserve=OUTPUT_RESERVE, *, data_messages=None):
    """Use handles from list_loaded only; .model(key) would auto-load a model."""
    try:
        if "label_definitions" in schema.get("properties", {}) or "review_status" in schema.get("properties", {}):
            output_reserve = max(output_reserve, 3200)
        if "label_requirements" in schema.get("properties", {}):
            output_reserve = max(output_reserve, 3200)
        if "analysis_requests" in schema.get("properties", {}) and "label_requirements" not in schema["properties"]:
            output_reserve = max(output_reserve, 3200)
        assessments = schema.get("properties", {}).get("result_assessments", {}).get("minItems", 0)
        if "result_assessments" in schema.get("properties", {}) and schema["properties"].get("stop", {}).get("type") != "null":
            output_reserve = max(output_reserve, 3200)
        if assessments:
            responses = schema.get("properties", {}).get("critique_responses", {}).get("maxItems", 0)
            base_reserve = 3200
            output_reserve = max(output_reserve, base_reserve + 256 * (assessments - 1) + 192 * responses)
        import lmstudio as lms
        base = lmstudio_base_url(base_url, "http://127.0.0.1:1234/v1", {"localhost", "127.0.0.1", "::1"})
        address = urlsplit(base).netloc
        with lms.Client(api_host=address) as client:
            matches = [handle for handle in client.llm.list_loaded() if handle.identifier == model]
            if len(matches) != 1:
                raise ValueError("loaded instance unavailable")
            handle = matches[0]
            model_info = handle.get_info().to_dict()
            load_config = handle.get_load_config().to_dict()
            length = handle.get_context_length()
            chat = lms.Chat.from_history({"messages": json_messages(system, user, data_messages)})
            rendered = handle.apply_prompt_template(chat)
            input_tokens = len(handle.tokenize(rendered))
            schema_tokens = len(handle.tokenize(json.dumps(schema, ensure_ascii=False, separators=(",", ":"))))
            if handle.get_info().to_dict() != model_info or handle.get_context_length() != length:
                raise ValueError("loaded instance changed")
        return {"model": model, "loaded_context_length": length,
                "template_input_tokens": input_tokens, "schema_tokens": schema_tokens,
                "count_method": "loaded_model_tokenizer", "schema_accounting": "conservative_addition",
                "model_info_sha256": digest(model_info), "load_config_sha256": digest(load_config),
                "output_reserve": output_reserve, "safety_margin": SAFETY_MARGIN,
                "fits": input_tokens + schema_tokens + output_reserve + SAFETY_MARGIN <= length}
    except Exception as exc:
        # SDK/server exceptions may contain source text or credentials.
        raise AnalysisContractError("ロード済みモデルの入力予算を確認できません。モデルと接続を確認してください。",
                                    code="context_budget_unavailable") from None
