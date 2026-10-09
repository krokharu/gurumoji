"""One real specialist call through the production Handler, using synthetic data.

No Core/model loop is simulated: the specialist is explicitly dispatched for
this test. The caller owns loading/unloading the loopback LM Studio model.
"""
from __future__ import annotations

import argparse
import copy
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
from statistics import median
import subprocess
import sys
import tempfile
import time
import urllib.request
from urllib.parse import urlsplit
import uuid

ROOT = Path(__file__).resolve().parents[1]

# F03 CPU preparation is deliberately separate from the legacy real-model CLI.
# These are test-driver contracts, never new application APIs or DB schemas.
F03_SCHEMA_HASH = "7291d1edc30cdc7642bc5f966b9278490b092d1d447018f9e20c9fe047d478ea"
F03_SPEC_HASH = "e9202b27ed9b7cae8931f09ca508bddb9089591b5ec899b3c105445296fee0bb"
F03_PLAN_HASH = "2ab048079d75ed55d5b737cf4d8a6735e52fa2728daec6dbe7f44d8deb9cf86d"
F03_CORRECTIONS_HASH = "a957ac10e53f98ce13c790e3c2e7ebbe8be9cbc7f6a4d5d7ecb7fb301bd4ff6c"
F03_GUARD_FINDINGS_HASH = "378fc4a70ae26ba45987536cf6ce1b87d1534a53c82378665225cc1b774e2bab"
F03_RESULT_SCHEMA = json.loads(r'''{"$schema":"https://json-schema.org/draft/2020-12/schema","$id":"urn:gurumoji:f03-result:1","type":"object","additionalProperties":false,"required":["schema_version","comparison_id","spec_hash","plan_hash","preparation_commit","baseline_commit","corpus_hash","model_condition_hash","measurement_ready","ready_blockers","limits","trials","totals","verdict","not_run"],"properties":{"schema_version":{"const":"f03-result-1"},"comparison_id":{"type":"string","minLength":1},"spec_hash":{"type":"string","pattern":"^(sha256:)?[0-9a-f]{64}$"},"plan_hash":{"type":"string","pattern":"^(sha256:)?[0-9a-f]{64}$"},"preparation_commit":{"type":"string","pattern":"^[0-9a-f]{40}$"},"baseline_commit":{"type":["string","null"],"pattern":"^[0-9a-f]{40}$"},"corpus_hash":{"type":"string","pattern":"^(sha256:)?[0-9a-f]{64}$"},"model_condition_hash":{"type":["string","null"],"pattern":"^(sha256:)?[0-9a-f]{64}$"},"measurement_ready":{"type":"boolean"},"ready_blockers":{"type":"array","items":{"type":"string"}},"limits":{"type":"object","additionalProperties":false,"required":["initial_trials","total_trials","max_revision","calls_per_trial","calls_total","code_tasks_per_trial","hook_rounds_per_task","hook_requests_per_round","task_timeout_seconds","run_timeout_seconds","gpu_owners","effective_context_tokens","input_cap_tokens","output_including_reasoning_cap_tokens","total_token_cap"],"properties":{"initial_trials":{"const":18},"total_trials":{"const":36},"max_revision":{"const":1},"calls_per_trial":{"const":6},"calls_total":{"const":216},"code_tasks_per_trial":{"const":2},"hook_rounds_per_task":{"const":2},"hook_requests_per_round":{"const":3},"task_timeout_seconds":{"const":240},"run_timeout_seconds":{"const":600},"gpu_owners":{"const":1},"effective_context_tokens":{"type":["integer","null"],"minimum":0},"input_cap_tokens":{"type":["integer","null"],"minimum":0},"output_including_reasoning_cap_tokens":{"type":["integer","null"],"minimum":0},"total_token_cap":{"type":["integer","null"],"minimum":0}}},"trials":{"type":"array","maxItems":36,"items":{"$ref":"#/$defs/trial"}},"totals":{"type":"object","additionalProperties":false,"required":["trials_started","model_transport_attempts","handler_reserved_calls","code_executions","failed_trials","uncertain_calls","complete_usage_calls","missing_usage_calls","input_tokens","output_tokens","reasoning_tokens","total_tokens","measured_partial_total_tokens","elapsed_seconds"],"properties":{"trials_started":{"type":"integer","minimum":0},"model_transport_attempts":{"type":["integer","null"],"minimum":0},"handler_reserved_calls":{"type":["integer","null"],"minimum":0},"code_executions":{"type":["integer","null"],"minimum":0},"failed_trials":{"type":"integer","minimum":0},"uncertain_calls":{"type":"integer","minimum":0},"complete_usage_calls":{"type":"integer","minimum":0},"missing_usage_calls":{"type":"integer","minimum":0},"input_tokens":{"type":["integer","null"],"minimum":0},"output_tokens":{"type":["integer","null"],"minimum":0},"reasoning_tokens":{"type":["integer","null"],"minimum":0},"total_tokens":{"type":["integer","null"],"minimum":0},"measured_partial_total_tokens":{"type":["integer","null"],"minimum":0},"elapsed_seconds":{"type":["number","null"],"minimum":0}}},"verdict":{"enum":["unmeasured","continue","rework","stop","hold"]},"not_run":{"type":"array","items":{"type":"string"}}},"$defs":{"call":{"type":"object","additionalProperties":false,"required":["task_id","attempt_id","phase","round","dispatch_state","request_hash","full_input_tokens_preflight","raw_usage_exists","present_usage_fields","input_tokens","output_tokens","reasoning_tokens","total_tokens","token_completeness","elapsed_seconds","error_kind"],"properties":{"task_id":{"type":"string"},"attempt_id":{"type":"string"},"phase":{"enum":["plan","explanation"]},"round":{"type":"integer","minimum":0,"maximum":2},"dispatch_state":{"enum":["not_dispatched","started","returned","failed","uncertain"]},"request_hash":{"type":"string","pattern":"^(sha256:)?[0-9a-f]{64}$"},"full_input_tokens_preflight":{"type":["integer","null"],"minimum":0},"raw_usage_exists":{"type":["boolean","null"]},"present_usage_fields":{"type":"array","uniqueItems":true,"items":{"enum":["prompt_tokens","completion_tokens","total_tokens","cached_tokens","reasoning_tokens"]}},"input_tokens":{"type":["integer","null"],"minimum":0},"output_tokens":{"type":["integer","null"],"minimum":0},"reasoning_tokens":{"type":["integer","null"],"minimum":0},"total_tokens":{"type":["integer","null"],"minimum":0},"token_completeness":{"enum":["complete","partial","unavailable","unverified_semantics"]},"elapsed_seconds":{"type":["number","null"],"minimum":0},"error_kind":{"type":["string","null"]}}},"trial":{"type":"object","additionalProperties":false,"required":["trial_id","revision","case_id","pair","condition","fixture_hash","app_run_id","state","calls","code_tasks","quality","input_tokens","output_tokens","reasoning_tokens","total_tokens","complete_usage_calls","missing_usage_calls","hook_rounds","hook_requests","knowledge_receipts","elapsed_seconds","initial_cpu_seconds","queue_wait_seconds","source_unchanged","error_kind"],"properties":{"trial_id":{"type":"string","pattern":"^r[01]-C[123]-p[123]-[AB]$"},"revision":{"type":"integer","minimum":0,"maximum":1},"case_id":{"enum":["C1","C2","C3"]},"pair":{"type":"integer","minimum":1,"maximum":3},"condition":{"enum":["A","B"]},"fixture_hash":{"type":"string","pattern":"^(sha256:)?[0-9a-f]{64}$"},"app_run_id":{"type":["string","null"]},"state":{"enum":["planned","running","completed","failed","blocked","uncertain"]},"calls":{"type":"array","maxItems":6,"items":{"$ref":"#/$defs/call"}},"code_tasks":{"type":"array","maxItems":2,"items":{"type":"object","additionalProperties":false,"required":["task_id","method_id","result_id","raw_hash","status"],"properties":{"task_id":{"type":"string"},"method_id":{"enum":["pearson","spearman"]},"result_id":{"type":["string","null"]},"raw_hash":{"type":["string","null"],"pattern":"^(sha256:)?[0-9a-f]{64}$"},"status":{"type":"string"}}}},"quality":{"type":"object","additionalProperties":false,"required":["status","critical_errors","unnecessary_rejections","item_checks"],"properties":{"status":{"enum":["unmeasured","pass","fail","review_pending"]},"critical_errors":{"type":"array","items":{"type":"string"}},"unnecessary_rejections":{"type":["integer","null"],"minimum":0},"item_checks":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["item_id","status","evidence_ref"],"properties":{"item_id":{"type":"string"},"status":{"enum":["met","unmet","unknown"]},"evidence_ref":{"type":["string","null"]}}}}}},"input_tokens":{"type":["integer","null"],"minimum":0},"output_tokens":{"type":["integer","null"],"minimum":0},"reasoning_tokens":{"type":["integer","null"],"minimum":0},"total_tokens":{"type":["integer","null"],"minimum":0},"complete_usage_calls":{"type":"integer","minimum":0},"missing_usage_calls":{"type":"integer","minimum":0},"hook_rounds":{"type":["integer","null"],"minimum":0},"hook_requests":{"type":["integer","null"],"minimum":0},"knowledge_receipts":{"type":"array","items":{"type":"object","additionalProperties":false,"required":["phase","note_id","section_id","source_hash","section_hash","characters","elapsed_seconds"],"properties":{"phase":{"enum":["plan","explanation"]},"note_id":{"type":"string"},"section_id":{"type":"string"},"source_hash":{"type":"string","pattern":"^(sha256:)?[0-9a-f]{64}$"},"section_hash":{"type":"string","pattern":"^(sha256:)?[0-9a-f]{64}$"},"characters":{"type":"integer","minimum":0},"elapsed_seconds":{"type":["number","null"],"minimum":0}}}},"elapsed_seconds":{"type":["number","null"],"minimum":0},"initial_cpu_seconds":{"type":["number","null"],"minimum":0},"queue_wait_seconds":{"type":["number","null"],"minimum":0},"source_unchanged":{"type":["boolean","null"]},"error_kind":{"type":["string","null"]}}}}}''')
F03_EVIDENCE_VERSION = "f03-evidence-1"
F03_TIME_SCOPE = {
    "run": "initial_cpu_before_to_receipt_saved_and_cleanup",
    "task": "context_before_to_all_rounds_validation_and_cleanup",
    "included": ["queue", "code", "knowledge", "retry_wait"],
    "load": "separate",
}
F03_CASES = {
    "C1": ((2, 3, 4, 5, 6, 8), (4, 6, 5, 9, 8, 13), tuple(f"S{i}" for i in range(1, 7))),
    "C2": ((2, 4, None, None, None, None), (4, 4, 4, 4, 4, 4), tuple(f"S{i}" for i in range(1, 7))),
    "C3": ((1, 2, 3, 8, 9, 10), (11, 10, 9, 21, 20, 19), ("A", "A", "A", "B", "B", "B")),
}
# Presentation gaps are graded separately from validity of every adopted claim.
F03_GAP_CATALOG = {
    "C1": ("pair_units", "n_missing", "cell_references", "small_sample_limit"),
    "C2": ("n_missing", "constant_column", "null_not_computed", "additional_inputs"),
    "C3": ("nested_participants", "unadjusted_family", "causal_alternative", "unread_scope"),
}
F03_CRITICAL = ("numeric", "references", "scope", "actor", "phase", "excluded",
                "not_computed", "prohibited_values")
F03_SHARED_HASHES = ("input", "case", "corpus", "profile", "knowledge", "schema",
                     "validator", "script", "model_condition", "guard")
F03_TRIAL_HASHES = (*F03_SHARED_HASHES, "sections", "prompt", "condition")
F03_READY_FLAGS = ("a06_accepted", "guard_accepted", "guard_tests_passed", "model_loaded",
                   "tokenizer_verified", "template_verified", "schema_coverage_verified",
                   "output_cap_enforced", "usage_semantics_verified", "reservation_enabled",
                   "deadline_enabled", "prefix_cache_comparable")
F03_WIRE_COVERAGE = ("messages", "system", "template", "special_tokens", "response_schema")


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _hash_ok(value):
    return isinstance(value, str) and re.fullmatch(r"(?:sha256:)?[0-9a-f]{64}", value) is not None


def _finite_number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def _token(value):
    if not _finite_number(value) or value < 0 or int(value) != value:
        return None
    return int(value)


def load_comparison_spec(path):
    """Read once; keep selected fixed values and exact acquisition byte hash."""
    raw = Path(path).read_bytes()
    packet = json.loads(raw.decode("utf-8-sig"))
    selected = {name: copy.deepcopy(packet[name]) for name in (
        "f03_specification", "f03_result_schema", "f03_spec_corrections", "f03_guard_findings")}
    hashes = {name: canonical_hash(value) for name, value in selected.items()}
    hashes["f03_specification"] = hashlib.sha256(selected["f03_specification"].encode()).hexdigest()
    if hashes["f03_specification"] != F03_SPEC_HASH or hashes["f03_result_schema"] != F03_SCHEMA_HASH:
        raise ValueError("F03 fixed specification/schema hash mismatch")
    if (hashes["f03_spec_corrections"] != F03_CORRECTIONS_HASH
            or hashes["f03_guard_findings"] != F03_GUARD_FINDINGS_HASH):
        raise ValueError("F03 corrections/guard findings require a new accepted fixed version")
    if canonical_hash(F03_RESULT_SCHEMA) != F03_SCHEMA_HASH:
        raise ValueError("Embedded result schema differs from the fixed contract")
    return {"file_hash": hashlib.sha256(raw).hexdigest(), "body_hashes": hashes, **selected}


def build_comparison_case(case_id):
    """Only the inquiry and synthetic input go to a future model, never oracle values."""
    durations, characters, speakers = F03_CASES[case_id]
    segments = [{"id": f"{case_id}-u{i}", "speaker": speaker, "text": "あ" * count,
                 "start": 100 * i if duration is not None else None,
                 "end": 100 * i + duration if duration is not None else None,
                 "time_unknown": duration is None, "annotation": {}, "excluded": False}
                for i, (duration, count, speaker) in enumerate(zip(durations, characters, speakers), 1)]
    segments.append({"id": f"{case_id}-excluded", "speaker": "EX", "text": "あ" * 4000,
                     "start": 9999, "end": 19999, "time_unknown": False,
                     "annotation": {}, "excluded": True})
    inquiry = {
        "C1": "発話時間と文字数のPearson・Spearman相関を探索的に確認してください。",
        "C2": "発話時間と文字数の相関を計算可能か確認し、追加の観測・入力を示してください。",
        "C3": "2話者の発話時間と文字数の関連、多重比較と因果の可能性を検討してください。",
    }[case_id]
    return {"case_id": case_id, "segments": segments,
            "annotations": {f"{case_id}-excluded": {"excluded": True}},
            "config": {"statistics_group_by": "speaker", "excluded_speakers": []},
            "question": inquiry}


def comparison_order(revision=0):
    if type(revision) is not int or revision not in (0, 1):
        raise ValueError("Only revision 0 and the single revision 1 are allowed")
    pairs = (("C1", 1, "AB"), ("C2", 1, "BA"), ("C3", 1, "AB"),
             ("C1", 2, "BA"), ("C2", 2, "AB"), ("C3", 2, "BA"),
             ("C1", 3, "AB"), ("C2", 3, "BA"), ("C3", 3, "AB"))
    return [{"trial_id": f"r{revision}-{case_id}-p{pair}-{condition}", "revision": revision,
             "case_id": case_id, "pair": pair, "condition": condition}
            for case_id, pair, order in pairs for condition in (order if revision == 0 else order[::-1])]


def comparison_options(case_id, model="google/gemma-4-12b"):
    """Payload for a later accepted driver at the existing prepare/start boundary.

    This does not resolve settings, contact a provider, or start a task.
    The real driver must additionally require accepted a06/transport receipts.
    """
    return {"provider": "lmstudio", "provider_policy": "local_only", "model": model,
            "publication_targets": [], "obsidian_management": False, "expert_ids": ["exp-correlation"],
            "expert_inputs": {"exp-correlation": {"analysis_premises":
                "合成発話の探索的分析。話者内の独立性は未確認、因果と母集団一般化は保留。"}},
            "question": build_comparison_case(case_id)["question"], "max_calls": 6, "max_tasks": 4,
            "time_limit_seconds": 600, "call_timeout_seconds": 240, "concurrency": 1,
            "context_evidence_limit": 6, "context_text_limit": 6000, "context_index_limit": 6}


def comparison_oracle(case_id):
    """Independent SciPy call; policy excludes N<3 or constant-column computations."""
    from scipy import stats
    x, y, speakers = F03_CASES[case_id]
    pairs = [(a, b) for a, b in zip(x, y) if a is not None and b is not None]
    computable = (len(pairs) >= 3 and len({a for a, _ in pairs}) > 1
                  and len({b for _, b in pairs}) > 1)
    result = {"n": len(pairs), "missing": 6 - len(pairs), "speaker_count": len(set(speakers))}
    for method, function in (("pearson", stats.pearsonr), ("spearman", stats.spearmanr)):
        coefficient, p_value = function(*zip(*pairs)) if computable else (None, None)
        result[method] = {"coefficient": float(coefficient) if coefficient is not None else None,
                          "p_value": float(p_value) if p_value is not None else None,
                          "status": "computed" if computable else "not_computable"}
    return result


def prepare_cpu_case(case_id, database, *, save_exclusion=True):
    """Fresh temporary DB only; use the application's existing save and CPU boundaries."""
    sys.path.insert(0, str(ROOT / "src")) if str(ROOT / "src") not in sys.path else None
    from gurumoji import transcript_preparation as preparation
    from gurumoji.services.library_schema import make_library_schema
    from gurumoji.services.analysis_annotations import make_analysis_annotation_save
    from gurumoji.services import group_analysis as group
    from gurumoji.services.library_rows import row_segments
    from gurumoji.services.analysis_orchestration_methods import run_statistical_tool
    database = Path(database)
    if database.exists():
        raise ValueError("CPU fixture refuses an existing database")
    database.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect():
        connection = sqlite3.connect(database)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    _, initialize = make_library_schema(
        data_directory=lambda: database.parent, media_directory=lambda: database.parent / "media",
        thumbnail_directory=lambda: database.parent / "thumbnails",
        training_audio_directory=lambda: database.parent / "training",
        database_connection=connect, repair_output_import_provenance=lambda _: None)
    initialize(repair_provenance=False)
    fixture = build_comparison_case(case_id)

    def library_row(item_id):
        with connect() as db:
            return db.execute("SELECT * FROM library_items WHERE id=?", (item_id,)).fetchone()

    with connect() as db:
        db.execute("""INSERT INTO library_items
            (id, source_name, output_dir, segments_json, original_segments_json,
             original_segments_status, speaker_names_json, files_json, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (case_id, "F03 synthetic CPU", str(database.parent / "media"), json.dumps(fixture["segments"]),
             json.dumps(fixture["segments"]), "synthetic_fixed", "{}", "[]", "synthetic", "synthetic"))
    if save_exclusion:
        _, save = make_analysis_annotation_save(
            AnalysisConflictError=ValueError, database_connection=connect, library_row=library_row,
            row_segments=row_segments,
            group_analysis_for_row=lambda row: {"analysis_revision": row["analysis_revision"]})
        save(case_id, {"source_revision": 0, "analysis_revision": 0,
                       "config": fixture["config"], "annotations": fixture["annotations"]})
    row = library_row(case_id)
    config = group.row_analysis_config(row)
    annotations, orphaned = group.row_analysis_annotation_state(row, fixture["segments"], config)
    if orphaned:
        raise ValueError("Unexpected orphaned fixture annotations")
    with connect() as db:
        prepared = preparation.view(db, row, fixture["segments"])
    timeline, _, _, _ = group._analysis_timeline(
        fixture["segments"], prepared=prepared,
        original_segments={s["id"]: s for s in fixture["segments"]}, original_segments_status="synthetic_fixed",
        annotations=annotations, profiles={}, speaker_names={}, session_profile={},
        excluded_speakers=set(config["excluded_speakers"]))
    included = {s["id"] for s in timeline if not s["excluded"]}
    excluded = {s["id"] for s in timeline if s["excluded"]}
    if save_exclusion and (included != {f"{case_id}-u{i}" for i in range(1, 7)}
                           or excluded != {f"{case_id}-excluded"}):
        raise ValueError("F03 exclusion/ID preflight failed before any model dispatch")
    analysis = {"segments": timeline, "config": config, "manual": {},
                "research": {"linguistics": {"morphemes": []}}}
    evidence = [{"evidence_id": s["id"], "utterance_id": s["id"], "excluded": s["excluded"]} for s in timeline]
    primary, calculation_raws, family_rows = {}, {}, 0
    for method in ("pearson", "spearman"):
        raw = run_statistical_tool(method, {"analysis": analysis, "evidence": evidence,
                                          "orchestration_task": {"dataset_version": prepared["input_version"]}})
        rows = raw["datasets"]["correlations"]["rows"]
        calculation_raws[method] = raw
        family_rows += len(rows)
        primary[method] = next(r for r in rows if r["variable_a"] == "duration_seconds"
                               and r["variable_b"] == "characters")
    oracle = comparison_oracle(case_id)
    if save_exclusion:
        if family_rows != 30:
            raise ValueError("Expected 15 variable pairs x 2 methods, not 30 independent pairs")
        for method, row in primary.items():
            expected = oracle[method]
            if row["n"] != oracle["n"] or row["missing"] != oracle["missing"] or row["status"] != expected["status"]:
                raise ValueError("CPU count/status differs from independent oracle")
            for field in ("coefficient", "p_value"):
                actual, wanted = row[field], expected[field]
                if (wanted is None and actual is not None) or (wanted is not None and
                        (actual is None or not math.isclose(actual, wanted, rel_tol=1e-8, abs_tol=5e-9))):
                    raise ValueError("CPU numeric cell differs from independent SciPy oracle")
    return {"case_id": case_id, "fixture_hash": canonical_hash(fixture), "input_version": prepared["input_version"],
            "input_hash": canonical_hash({"case_id": case_id, "segments": fixture["segments"],
                                         "annotations": annotations, "config": config}),
            "included_ids": sorted(included), "excluded_ids": sorted(excluded), "family_results": family_rows,
            "primary": primary, "oracle": oracle, "saved_exclusion": save_exclusion,
            "cpu_calculation_raws": calculation_raws,
            "morphology": "synthetic empty checkpoint; primary pair and counts only"}


def inspect_raw_usage(raw, semantics):
    """Keep unknowns null. Completion/reasoning inclusion needs explicit evidence."""
    exists = isinstance(raw, dict)
    raw = raw if exists else {}
    semantics = semantics if isinstance(semantics, dict) else {}
    details = raw.get("completion_tokens_details")
    reasoning = details.get("reasoning_tokens") if isinstance(details, dict) else None
    present = [name for name in ("prompt_tokens", "completion_tokens", "total_tokens") if name in raw]
    if isinstance(details, dict) and "reasoning_tokens" in details:
        present.append("reasoning_tokens")
    prompt_details = raw.get("prompt_tokens_details")
    cache_key = next((k for k in ("cached_tokens", "cached_tokens_count") if isinstance(prompt_details, dict)
                      and k in prompt_details), None)
    cached = prompt_details[cache_key] if cache_key else None
    if cache_key is not None:
        present.append("cached_tokens")
    input_tokens, output_tokens, total_tokens, reasoning_tokens = map(
        _token, (raw.get("prompt_tokens"), raw.get("completion_tokens"), raw.get("total_tokens"), reasoning))
    if "reasoning_tokens" not in present and semantics.get("absent_reasoning_is_zero") is True:
        reasoning_tokens = 0
    verified = (type(semantics.get("completion_includes_reasoning")) is bool
                and semantics.get("total_includes_reasoning") is True)
    known = input_tokens is not None and output_tokens is not None and reasoning_tokens is not None
    expected = (input_tokens + output_tokens +
                (0 if semantics.get("completion_includes_reasoning") else reasoning_tokens)) if verified and known else None
    field_values = {**raw, "reasoning_tokens": reasoning, "cached_tokens": cached}
    bad_field = any(_token(field_values[name]) is None for name in present)
    bad_field |= cached is not None and input_tokens is not None and (
        _token(cached) is None or _token(cached) > input_tokens)
    if total_tokens is None and "total_tokens" not in present and expected is not None:
        total_tokens = expected
    complete = exists and verified and known and not bad_field and total_tokens == expected
    if semantics.get("completion_includes_reasoning") is True and known and reasoning_tokens > output_tokens:
        complete = False
    return {"raw_usage_exists": exists, "present_usage_fields": present,
            "input_tokens": input_tokens, "output_tokens": output_tokens,
            "reasoning_tokens": reasoning_tokens, "total_tokens": total_tokens if complete else None,
            "token_completeness": "complete" if complete else (
                "unavailable" if not exists else "unverified_semantics" if not verified else "partial"),
            "measured_partial_total_tokens": sum(v for v in (input_tokens, output_tokens) if v is not None)
                if any(v is not None for v in (input_tokens, output_tokens)) else None}


def _shape_errors(value, schema, root=None, path="$"):
    """Validate only the fixed schema's vocabulary; no optional package dependency."""
    root = root or schema
    if "$ref" in schema:
        target = root
        for part in schema["$ref"].removeprefix("#/").split("/"):
            target = target[part]
        return _shape_errors(value, target, root, path)
    errors = []
    kinds = schema.get("type")
    kinds = [kinds] if isinstance(kinds, str) else kinds or []
    type_checks = {"object": type(value) is dict, "array": type(value) is list,
                   "string": type(value) is str, "boolean": type(value) is bool,
                   "integer": type(value) is int, "number": _finite_number(value), "null": value is None}
    if kinds and not any(type_checks[k] for k in kinds):
        return [f"shape:{path}:type"]
    if "const" in schema and (value != schema["const"] or type(value) is bool):
        errors.append(f"shape:{path}:const")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"shape:{path}:enum")
    if type(value) is dict:
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"shape:{path}.{key}:required")
        if schema.get("additionalProperties") is False and set(value) - set(props):
            errors.append(f"shape:{path}:additionalProperties")
        for key in value.keys() & props.keys():
            errors.extend(_shape_errors(value[key], props[key], root, f"{path}.{key}"))
    if type(value) is list:
        if len(value) > schema.get("maxItems", len(value)):
            errors.append(f"shape:{path}:maxItems")
        if schema.get("uniqueItems"):
            try:
                if len({canonical_hash(v) for v in value}) != len(value):
                    errors.append(f"shape:{path}:uniqueItems")
            except (TypeError, ValueError, OverflowError):
                errors.append(f"shape:{path}:non_json_value")
        for i, entry in enumerate(value):
            errors.extend(_shape_errors(entry, schema.get("items", {}), root, f"{path}[{i}]"))
    if type(value) is str:
        if len(value) < schema.get("minLength", 0) or not re.search(schema.get("pattern", ""), value):
            errors.append(f"shape:{path}:string")
    if _finite_number(value):
        if value < schema.get("minimum", value) or value > schema.get("maximum", value):
            errors.append(f"shape:{path}:range")
    return errors


def bind_comparison_evidence(result, payload):
    """Sidecar hash binds all mandatory receipts to this exact result, without changing result-1."""
    return {"schema_version": F03_EVIDENCE_VERSION, "result_hash": canonical_hash(result),
            "payload_hash": canonical_hash(payload), "payload": copy.deepcopy(payload)}


def _strict_object(properties, required=None):
    return {"type": "object", "additionalProperties": False, "properties": properties,
            "required": list(properties) if required is None else required}


def _sidecar_errors(payload, trials):
    """Strict driver-owned objects; provider usage and calculation raws stay original."""
    text = {"type": "string", "minLength": 1}
    nullable_text = {"type": ["string", "null"]}
    boolean = {"type": "boolean"}
    number = {"type": "number", "minimum": 0}
    nullable_number = {"type": ["number", "null"], "minimum": 0}
    integer = {"type": "integer", "minimum": 0}
    nullable_integer = {"type": ["integer", "null"], "minimum": 0}
    hash_value = {"type": "string", "pattern": r"^(sha256:)?[0-9a-f]{64}$"}
    nullable_hash = {**hash_value, "type": ["string", "null"]}
    strings = {"type": "array", "items": text}
    clock = _strict_object({"started": number, "ended": nullable_number})
    segment = _strict_object({"kind": {"type": "string", "enum": ["initial_cpu", "queue", "context",
        "wire", "code", "knowledge", "retry_wait", "validation", "cleanup"]},
        "task_id": nullable_text, "attempt_id": nullable_text, "started": number, "ended": nullable_number})
    usage = _strict_object({**{k: nullable_integer for k in ("input_tokens", "output_tokens", "reasoning_tokens",
        "total_tokens", "measured_partial_total_tokens")}, "raw_usage_exists": boolean,
        "present_usage_fields": F03_RESULT_SCHEMA["$defs"]["call"]["properties"]["present_usage_fields"],
        "token_completeness": F03_RESULT_SCHEMA["$defs"]["call"]["properties"]["token_completeness"]})
    call = _strict_object({"entrance_id": text, "wire_sequence": nullable_integer, "request_hash": hash_value,
        "raw_usage": {"type": ["object", "null"]}, "usage": usage,
        "usage_semantics": _strict_object({k: {"type": ["boolean", "null"]} for k in (
            "completion_includes_reasoning", "total_includes_reasoning", "absent_reasoning_is_zero")}),
        "count_coverage": _strict_object({k: boolean for k in F03_WIRE_COVERAGE}),
        "output_cap_tokens": nullable_integer, "reserved_tokens": integer, "reservation_retained": boolean,
        **{k: nullable_number for k in ("sent_monotonic", "finished_monotonic", "task_started_monotonic",
            "task_remaining_seconds", "run_remaining_seconds", "wire_timeout_seconds", "cleanup_seconds")}})
    receipt_schemas = {}
    for trial in trials:
        tid = trial["trial_id"]
        receipt = payload["trials"][tid]
        properties = {"started": boolean, "hashes": _strict_object({k: nullable_hash if k == "model_condition"
            else hash_value for k in F03_TRIAL_HASHES}), "calls": _strict_object({c["attempt_id"]: call
            for c in trial["calls"]}), "handler_reserved_calls": integer, "call_ai_entrances": integer,
            "code_executed_ids": strings, "task_clocks": _strict_object({k: clock for k in receipt["task_clocks"]}),
            "hooks": _strict_object({k: {"type": "array", "items": integer} for k in ("plan", "explanation")}),
            "clock_segments": {"type": "array", "items": segment}}
        required = list(properties)
        properties.update({"input_version": integer, "final_status": text, "calculation_result_ids": strings,
            "missing_inputs": strings, "route_evaluated": boolean, "included_ids": strings, "excluded_ids": strings,
            "critical_checks": _strict_object({k: {"type": "string", "enum": ["met", "unmet", "unknown"]}
                for k in F03_CRITICAL}), "run_started_monotonic": number, "run_ended_monotonic": nullable_number,
            "quality_reviewer": text, "quality_review_kind": {"type": "string", "const": "independent"},
            "calculation_raws": _strict_object({k: {"type": "object"} for k in ("pearson", "spearman")})})
        if receipt["started"]:
            required += ["run_started_monotonic", "run_ended_monotonic"]
        if trial["state"] == "completed":
            required = list(properties)
        receipt_schemas[tid] = _strict_object(properties, required)
    schema = _strict_object({"fixed_hashes": _strict_object({**{k: hash_value for k in (
        "spec", "schema", "corrections", "guard_findings", "script", "validator")},
        "runtime_guard": nullable_hash, "case_inputs": _strict_object({k: hash_value for k in F03_CASES})}),
        "readiness": _strict_object({**{k: boolean for k in F03_READY_FLAGS}, "model_instance_id": nullable_text,
            "parallel": integer, "baseline_commit": {"type": ["string", "null"], "pattern": r"^[0-9a-f]{40}$"},
            "kv_reused": boolean, "generated_warmup_calls": integer}),
        "time_scope": {"const": F03_TIME_SCOPE}, "revision1_authorized": boolean,
        "condition_hashes": _strict_object({str(r): _strict_object({c: hash_value for c in ("A", "B")})
            for r in (0, 1)}), "preaccepted_manifest_hash": nullable_hash,
        "trials": _strict_object(receipt_schemas), "core_calls": integer})
    return _shape_errors(payload, schema, path="$evidence.payload")


def _manifest_errors(result, payload, manifest):
    """External C0 trust anchor; never inferred from observed receipts.

    The caller verifies acceptance independently. Unit controls use a fictitious
    receipt; hashing alone cannot grant actual runtime or research acceptance.
    """
    if manifest is None:
        return (["preaccepted_manifest_missing"] if result["measurement_ready"] or any(
            r["started"] for r in payload["trials"].values()) else []) + (
            ["preaccepted_manifest_binding"] if payload["preaccepted_manifest_hash"] is not None else [])
    hash_schema = {"type": "string", "pattern": r"^(sha256:)?[0-9a-f]{64}$"}
    condition = _strict_object({k: hash_schema for k in F03_TRIAL_HASHES})
    revision = _strict_object({"acceptance_receipt_id": {"type": "string", "minLength": 1},
        "accepted_monotonic": {"type": "number", "minimum": 0},
        "conditions": _strict_object({cid: _strict_object({c: condition for c in ("A", "B")})
                                      for cid in F03_CASES})})
    schema = _strict_object({"schema_version": {"type": "string", "const": "f03-preaccepted-1"},
        "comparison_id": {"type": "string", "const": result["comparison_id"]},
        "revisions": _strict_object({"0": revision, "1": {**revision, "type": ["object", "null"]}})})
    errors = _shape_errors(manifest, schema, path="$preaccepted_manifest")
    if errors:
        return errors
    if canonical_hash(manifest) != payload["preaccepted_manifest_hash"]:
        errors.append("preaccepted_manifest_binding")
    for trial in result["trials"]:
        receipt = payload["trials"][trial["trial_id"]]
        frozen = manifest["revisions"][str(trial["revision"])]
        if frozen is None:
            if receipt["started"]:
                errors.append("preaccepted_revision_missing")
            continue
        expected = frozen["conditions"][trial["case_id"]][trial["condition"]]
        if receipt["hashes"] != expected:
            errors.append(f"preaccepted_conditions:{trial['trial_id']}")
        if receipt["started"] and frozen["accepted_monotonic"] > receipt["run_started_monotonic"]:
            errors.append(f"manifest_accepted_after_start:{trial['trial_id']}")
    first, second = (manifest["revisions"][str(r)] for r in (0, 1))
    if second is not None:
        for cid in F03_CASES:
            a0, b0 = (first["conditions"][cid][c] for c in ("A", "B"))
            a1, b1 = (second["conditions"][cid][c] for c in ("A", "B"))
            if a0 != a1 or any(b0[k] != b1[k] for k in F03_SHARED_HASHES) or b0["condition"] == b1["condition"]:
                errors.append("preaccepted_revision_mutation")
    return errors


def _clock_errors(trial, receipt):
    """One monotonic partition contains queue, all rounds, code, reads and cleanup."""
    tid, errors = trial["trial_id"], []
    segments = receipt["clock_segments"]
    if not receipt["started"]:
        return [f"unstarted_clock:{tid}"] if segments or receipt["task_clocks"] else []
    start, end = receipt["run_started_monotonic"], receipt["run_ended_monotonic"]
    if not segments:
        return [f"clock_segments_missing:{tid}"]
    cursor = start
    for index, segment in enumerate(segments):
        stop, task = segment["ended"], segment["task_id"]
        if not math.isclose(segment["started"], cursor, rel_tol=0, abs_tol=1e-6):
            errors.append(f"clock_partition:{tid}")
        if stop is None:
            if index != len(segments) - 1 or end is not None or trial["state"] == "completed":
                errors.append(f"clock_open_interval:{tid}")
        elif stop < segment["started"] or stop > start + 600:
            errors.append(f"clock_segment_bounds:{tid}")
        if task is not None and task not in receipt["task_clocks"]:
            errors.append(f"clock_segment_task:{tid}")
        if segment["kind"] in {"queue", "context", "wire", "code", "knowledge", "retry_wait"} and task is None:
            errors.append(f"clock_task_scope:{tid}")
        if (segment["kind"] == "wire") != (segment["attempt_id"] is not None):
            errors.append(f"clock_attempt_scope:{tid}")
        cursor = stop if stop is not None else segment["started"]
    if segments[0]["kind"] != "initial_cpu" or segments[0]["task_id"] is not None:
        errors.append(f"initial_cpu_clock:{tid}")
    if sum(s["kind"] == "initial_cpu" for s in segments) != 1:
        errors.append(f"initial_cpu_clock:{tid}")
    if end is not None and (not math.isclose(cursor, end, rel_tol=0, abs_tol=1e-6) or not start <= end <= start + 600):
        errors.append(f"clock_run_coverage:{tid}")
    if trial["state"] == "completed" and (segments[-1]["kind"] != "cleanup" or segments[-1]["task_id"] is not None):
        errors.append(f"clock_run_cleanup:{tid}")
    for field, kind in (("initial_cpu_seconds", "initial_cpu"), ("queue_wait_seconds", "queue")):
        spans = [s for s in segments if s["kind"] == kind]
        measured = sum(s["ended"] - s["started"] for s in spans) if all(s["ended"] is not None for s in spans) else None
        if trial[field] is not None and (measured is None or not math.isclose(trial[field], measured, rel_tol=0, abs_tol=1e-6)):
            errors.append(f"clock_breakdown:{tid}:{field}")
    for phase in ("plan", "explanation"):
        task_ids = {c["task_id"] for c in trial["calls"] if c["phase"] == phase}
        reads = [s for s in segments if s["kind"] == "knowledge" and s["task_id"] in task_ids]
        receipts = [r for r in trial["knowledge_receipts"] if r["phase"] == phase]
        if all(r["elapsed_seconds"] is not None for r in receipts):
            if any(s["ended"] is None for s in reads) or not math.isclose(
                    sum(r["elapsed_seconds"] for r in receipts),
                    sum(s["ended"] - s["started"] for s in reads if s["ended"] is not None), abs_tol=1e-6):
                errors.append(f"knowledge_clock_coverage:{tid}:{phase}")
    for task, clock in receipt["task_clocks"].items():
        spans = [s for s in segments if s["task_id"] == task]
        if (not spans or not math.isclose(spans[0]["started"], clock["started"], rel_tol=0, abs_tol=1e-6)
                or spans[-1]["ended"] != clock["ended"] or any(s["ended"] is None for s in spans[:-1])
                or any(a["ended"] != b["started"] for a, b in zip(spans, spans[1:]))
                or (clock["ended"] is not None and not clock["started"] <= clock["ended"] <= clock["started"] + 240)):
            errors.append(f"clock_task_coverage:{tid}")
        if spans and (spans[0]["kind"] not in {"queue", "context", "knowledge", "code"}
                or (clock["ended"] is not None and spans[-1]["kind"] not in {"validation", "cleanup"})):
            errors.append(f"clock_task_lifecycle:{tid}")
        is_code = task in receipt["code_executed_ids"]
        if spans and ((is_code and spans[0]["kind"] != "code") or (not is_code and spans[0]["kind"] == "code")
                      or any(s["kind"] == "code" for s in spans) != is_code):
            errors.append(f"clock_code_actor:{tid}")
    wire_segments = [s for s in segments if s["kind"] == "wire"]
    sent_calls = [c for c in trial["calls"] if c["dispatch_state"] != "not_dispatched"]
    if (len(wire_segments) != len(sent_calls) or {s["attempt_id"] for s in wire_segments}
            != {c["attempt_id"] for c in sent_calls}):
        errors.append(f"clock_wire_coverage:{tid}")
    for call in sent_calls:
        attempt = receipt["calls"][call["attempt_id"]]
        matches = [s for s in wire_segments if s["attempt_id"] == call["attempt_id"]]
        if len(matches) != 1 or any(matches[0][k] != value for k, value in (
                ("task_id", call["task_id"]), ("started", attempt["sent_monotonic"]),
                ("ended", attempt["finished_monotonic"]))):
            errors.append(f"clock_wire_binding:{tid}")
    codes = [receipt["task_clocks"][c["task_id"]] for c in trial["code_tasks"]
             if c["task_id"] in receipt["code_executed_ids"]]
    phase_clocks = {phase: [receipt["task_clocks"][c["task_id"]] for c in trial["calls"] if c["phase"] == phase]
                    for phase in ("plan", "explanation")}
    if codes and phase_clocks["plan"]:
        if any(p["ended"] is None or p["ended"] > c["started"] for p in phase_clocks["plan"] for c in codes):
            errors.append(f"code_before_plan_complete:{tid}")
    if phase_clocks["explanation"] and (len(codes) != 2 or any(c["ended"] is None or c["ended"] > e["started"]
            for c in codes for e in phase_clocks["explanation"])):
        errors.append(f"explanation_before_code_complete:{tid}")
    return errors


def comparison_totals(trials, trial_receipts):
    calls = [c for t in trials for c in t["calls"] if c["dispatch_state"] != "not_dispatched"]
    complete = [c for c in calls if c["token_completeness"] == "complete"]
    def measured(field):
        return sum(c[field] for c in calls) if calls and all(c[field] is not None for c in calls) else None
    partial = [c["total_tokens"] if c["token_completeness"] == "complete" else
               trial_receipts[t["trial_id"]]["calls"][c["attempt_id"]]["usage"]["measured_partial_total_tokens"]
               for t in trials for c in t["calls"] if c["dispatch_state"] != "not_dispatched"]
    return {"trials_started": sum(r["started"] for r in trial_receipts.values()),
            "model_transport_attempts": len(calls),
            "handler_reserved_calls": sum(r["handler_reserved_calls"] for r in trial_receipts.values()),
            "code_executions": sum(len(r["code_executed_ids"]) for r in trial_receipts.values()),
            "failed_trials": sum(t["state"] == "failed" for t in trials),
            "uncertain_calls": sum(c["dispatch_state"] in {"started", "uncertain"} for c in calls),
            "complete_usage_calls": len(complete), "missing_usage_calls": len(calls) - len(complete),
            "input_tokens": measured("input_tokens"), "output_tokens": measured("output_tokens"),
            "reasoning_tokens": measured("reasoning_tokens"), "total_tokens": measured("total_tokens"),
            "measured_partial_total_tokens": sum(v for v in partial if v is not None)
                if any(v is not None for v in partial) else None,
            "elapsed_seconds": sum(t["elapsed_seconds"] for t in trials if trial_receipts[t["trial_id"]]["started"])
                if any(r["started"] for r in trial_receipts.values()) and all(
                    t["elapsed_seconds"] is not None for t in trials if trial_receipts[t["trial_id"]]["started"]) else None}


def _measurement_ready(result, payload):
    readiness = payload["readiness"]
    limits = result["limits"]
    return (all(readiness.get(k) is True for k in F03_READY_FLAGS)
            and isinstance(readiness.get("model_instance_id"), str) and bool(readiness["model_instance_id"].strip())
            and readiness.get("parallel") == 1 and type(readiness.get("parallel")) is int
            and readiness.get("kv_reused") is False and type(readiness.get("generated_warmup_calls")) is int
            and readiness.get("generated_warmup_calls") == 0
            and readiness.get("baseline_commit") == result["baseline_commit"]
            and result["baseline_commit"] is not None and _hash_ok(result["model_condition_hash"])
            and result["model_condition_hash"] != "0" * 64 and result["corpus_hash"] != "0" * 64
            and all(type(limits[k]) is int and limits[k] > 0 for k in (
                "effective_context_tokens", "input_cap_tokens", "output_including_reasoning_cap_tokens", "total_token_cap"))
            and limits["input_cap_tokens"] + limits["output_including_reasoning_cap_tokens"] + 4096
                <= limits["effective_context_tokens"]
            and limits["input_cap_tokens"] <= 24576 and limits["output_including_reasoning_cap_tokens"] <= 4096
            and limits["total_token_cap"] <= 6193152)


def assess_comparison(result, evidence, *, preaccepted_manifest=None):
    """Pure structural/semantic judgment; never queries or calls a model.

    The evidence sidecar is mandatory. Self-asserted flags cannot establish real
    model or research acceptance: C0 must supply independently accepted receipts.
    """
    errors = _shape_errors(result, F03_RESULT_SCHEMA)
    if errors:
        return {"valid": False, "errors": errors, "verdict": "hold", "measurement_ready": False}
    try:
        if set(evidence) != {"schema_version", "result_hash", "payload_hash", "payload"}:
            raise ValueError("sidecar shape")
        if evidence["schema_version"] != F03_EVIDENCE_VERSION:
            raise ValueError("sidecar version")
        payload = evidence["payload"]
        if evidence["result_hash"] != canonical_hash(result) or evidence["payload_hash"] != canonical_hash(payload):
            raise ValueError("sidecar hash")
        if set(payload) != {"fixed_hashes", "readiness", "time_scope", "revision1_authorized",
                            "condition_hashes", "preaccepted_manifest_hash", "trials", "core_calls"}:
            raise ValueError("sidecar payload shape")
        errors.extend(_sidecar_errors(payload, result["trials"]))
        if errors:
            return {"valid": False, "errors": errors, "verdict": "hold", "measurement_ready": False}
        errors.extend(_manifest_errors(result, payload, preaccepted_manifest))
        if payload["fixed_hashes"]["spec"] != result["spec_hash"] or result["spec_hash"] != F03_SPEC_HASH:
            errors.append("fixed_spec_hash")
        if result["plan_hash"] != F03_PLAN_HASH or payload["fixed_hashes"]["schema"] != F03_SCHEMA_HASH:
            errors.append("fixed_plan_schema_hash")
        if (payload["fixed_hashes"].get("corrections") != F03_CORRECTIONS_HASH
                or payload["fixed_hashes"].get("guard_findings") != F03_GUARD_FINDINGS_HASH):
            errors.append("fixed_corrections_guard_findings")
        if not all(_hash_ok(payload["fixed_hashes"].get(k)) for k in ("script", "validator")):
            errors.append("fixed_driver_validator_hash")
        if (payload["time_scope"] != F03_TIME_SCOPE or type(payload["core_calls"]) is not int
                or payload["core_calls"] != 0):
            errors.append("clock_scope_or_core")
        guard_ready = _measurement_ready(result, payload)
        if result["measurement_ready"] and (not guard_ready or result["ready_blockers"]):
            errors.append("measurement_ready_without_evidence")
        ready = guard_ready and result["measurement_ready"] and not result["ready_blockers"]
        ids = [t["trial_id"] for t in result["trials"]]
        schedule = comparison_order(0) + comparison_order(1)
        expected = {t["trial_id"]: t for t in schedule}
        if len(ids) != len(set(ids)) or set(payload["trials"]) != set(ids):
            errors.append("trial_ids_unique_receipts")
        if ids != [t["trial_id"] for t in schedule if t["trial_id"] in ids]:
            errors.append("fixed_corresponding_order")
        revision1_started = any(t["revision"] == 1 and t["state"] != "planned" for t in result["trials"])
        if revision1_started and payload["revision1_authorized"] is not True:
            errors.append("revision1_not_authorized")
        if revision1_started and (len([t for t in result["trials"] if t["revision"] == 0]) != 18
                or any(t["state"] != "completed" for t in result["trials"] if t["revision"] == 0)
                or payload["condition_hashes"]["1"]["A"] != payload["condition_hashes"]["0"]["A"]
                or payload["condition_hashes"]["1"]["B"] == payload["condition_hashes"]["0"]["B"]):
            errors.append("revision1_history_or_candidate_version")
        receipts, attempted = payload["trials"], []
        for trial in result["trials"]:
            tid = trial["trial_id"]
            if any(trial[k] != expected[tid][k] for k in ("revision", "case_id", "pair", "condition")):
                errors.append(f"trial_id_attributes:{tid}")
            receipt = receipts[tid]
            errors.extend(_clock_errors(trial, receipt))
            started = receipt["started"]
            if type(started) is not bool or started != (trial["app_run_id"] is not None):
                errors.append(f"started_denominator:{tid}")
            if not started and (trial["calls"] or trial["code_tasks"] or trial["state"] == "completed"):
                errors.append(f"execution_without_started_trial:{tid}")
            if trial["state"] == "planned" and (started or trial["calls"] or trial["code_tasks"]):
                errors.append(f"planned_trial_executed:{tid}")
            code_ids = [c["task_id"] for c in trial["code_tasks"]]
            executed = receipt["code_executed_ids"]
            if (len(code_ids) != len(set(code_ids)) or len(executed) != len(set(executed))
                    or not set(executed) <= set(code_ids)):
                errors.append(f"code_execution_denominator:{tid}")
            hashes = receipt["hashes"]
            if not all(_hash_ok(hashes.get(k)) or (k == "model_condition" and not started
                       and not result["measurement_ready"] and hashes.get(k) is None) for k in F03_TRIAL_HASHES):
                errors.append(f"trial_hashes:{tid}")
            if trial["fixture_hash"] != canonical_hash(build_comparison_case(trial["case_id"])):
                errors.append(f"fixed_case_fixture:{tid}")
            if (hashes["input"] != payload["fixed_hashes"]["case_inputs"][trial["case_id"]]
                    or hashes["script"] != payload["fixed_hashes"]["script"]
                    or hashes["validator"] != payload["fixed_hashes"]["validator"]
                    or started and hashes["guard"] != payload["fixed_hashes"]["runtime_guard"]):
                errors.append(f"fixed_input_code_guard_hash:{tid}")
            if (hashes["case"] != trial["fixture_hash"] or hashes["corpus"] != result["corpus_hash"]
                    or hashes["schema"] != F03_SCHEMA_HASH or hashes["model_condition"] != result["model_condition_hash"]
                    or hashes["condition"] != payload["condition_hashes"][str(trial["revision"])][trial["condition"]]):
                errors.append(f"frozen_conditions:{tid}")
            if set(receipt["calls"]) != {c["attempt_id"] for c in trial["calls"]}:
                errors.append(f"call_receipts:{tid}")
            entries = {}
            for call in trial["calls"]:
                attempt = receipt["calls"][call["attempt_id"]]
                entrance = attempt["entrance_id"]
                key = (call["phase"], call["round"], call["task_id"])
                if entrance in entries and entries[entrance] != key:
                    errors.append(f"entrance_binding:{tid}")
                entries[entrance] = key
                usage = inspect_raw_usage(attempt["raw_usage"], attempt["usage_semantics"])
                if attempt["usage"] != usage:
                    errors.append(f"raw_usage_receipt:{tid}")
                if any(call[k] != usage[k] for k in ("raw_usage_exists", "present_usage_fields",
                       "input_tokens", "output_tokens", "reasoning_tokens", "total_tokens", "token_completeness")):
                    errors.append(f"raw_usage_completeness:{tid}")
                if call["dispatch_state"] == "not_dispatched":
                    continue
                attempted.append((attempt["wire_sequence"], call, attempt, trial))
                if (attempt["request_hash"] != call["request_hash"]
                        or not all(attempt["count_coverage"].get(k) is True for k in F03_WIRE_COVERAGE)
                        or call["full_input_tokens_preflight"] is None):
                    errors.append(f"wire_coverage:{tid}")
                limits = result["limits"]
                full, cap = call["full_input_tokens_preflight"], attempt["output_cap_tokens"]
                if (type(cap) is not int or cap <= 0 or cap != limits["output_including_reasoning_cap_tokens"]
                        or full > limits["input_cap_tokens"]
                        or attempt["reserved_tokens"] != full + cap):
                    errors.append(f"token_reservation:{tid}")
                sent, finished = attempt["sent_monotonic"], attempt["finished_monotonic"]
                run_start, task_start = receipt["run_started_monotonic"], attempt["task_started_monotonic"]
                clock = receipt["task_clocks"][call["task_id"]]
                if task_start != clock["started"]:
                    errors.append(f"task_clock_reset:{tid}")
                if not all(_finite_number(v) for v in (sent, run_start, task_start,
                       attempt["task_remaining_seconds"], attempt["run_remaining_seconds"],
                       attempt["wire_timeout_seconds"], attempt["cleanup_seconds"])):
                    errors.append(f"deadline_evidence:{tid}")
                else:
                    task_left, run_left = 240 - (sent - task_start), 600 - (sent - run_start)
                    if (task_start < run_start or sent < task_start
                            or not math.isclose(attempt["task_remaining_seconds"], task_left, abs_tol=1e-6)
                            or not math.isclose(attempt["run_remaining_seconds"], run_left, abs_tol=1e-6)
                            or attempt["cleanup_seconds"] < 5 or attempt["wire_timeout_seconds"] < 1
                            or attempt["wire_timeout_seconds"] + attempt["cleanup_seconds"] > min(task_left, run_left)):
                        errors.append(f"remaining_deadline:{tid}")
                    if finished is not None and (not _finite_number(finished) or finished < sent
                            or finished > min(task_start + 240, run_start + 600)
                            or not math.isclose(call["elapsed_seconds"], finished - sent, abs_tol=1e-6)):
                        errors.append(f"late_or_invalid_call_clock:{tid}")
                    if call["dispatch_state"] == "returned" and (finished is None or clock["ended"] is None
                            or finished > clock["ended"]):
                        errors.append(f"returned_clock_missing:{tid}")
                    if call["dispatch_state"] == "returned" and finished is not None and (
                            finished > sent + attempt["wire_timeout_seconds"] + attempt["cleanup_seconds"]):
                        errors.append(f"returned_after_wire_deadline:{tid}")
                if usage["token_completeness"] != "complete" and attempt["reservation_retained"] is not True:
                    errors.append(f"unknown_reservation_released:{tid}")
                if usage["token_completeness"] == "complete":
                    if call["output_tokens"] + (0 if attempt["usage_semantics"]["completion_includes_reasoning"]
                                                else call["reasoning_tokens"]) > cap:
                        errors.append(f"output_cap:{tid}")
                    if call["input_tokens"] > min(full, limits["input_cap_tokens"]):
                        errors.append(f"input_cap:{tid}")
            if (any(sum(key[0] == phase for key in entries.values()) > 3 for phase in ("plan", "explanation"))
                    or len(entries) != receipt["call_ai_entrances"]
                    or type(receipt["handler_reserved_calls"]) is not int
                    or not len(entries) <= receipt["handler_reserved_calls"] <= 6):
                errors.append(f"phase_entrance_budget:{tid}")
            if trial["complete_usage_calls"] != sum(c["token_completeness"] == "complete" for c in trial["calls"]
                                                     if c["dispatch_state"] != "not_dispatched"):
                errors.append(f"trial_complete_usage_count:{tid}")
            ncalls = sum(c["dispatch_state"] != "not_dispatched" for c in trial["calls"])
            if trial["missing_usage_calls"] != ncalls - trial["complete_usage_calls"]:
                errors.append(f"trial_missing_usage_count:{tid}")
            for field in ("input_tokens", "output_tokens", "reasoning_tokens", "total_tokens"):
                values = [c[field] for c in trial["calls"] if c["dispatch_state"] != "not_dispatched"]
                wanted = sum(values) if values and all(v is not None for v in values) else None
                if trial[field] != wanted:
                    errors.append(f"trial_usage_sum:{tid}:{field}")
            if trial["state"] == "completed":
                methods = [c["method_id"] for c in trial["code_tasks"]]
                result_ids = {c["result_id"] for c in trial["code_tasks"]}
                phase_tasks = {phase: {c["task_id"] for c in trial["calls"] if c["phase"] == phase}
                               for phase in ("plan", "explanation")}
                if (set(methods) != {"pearson", "spearman"} or len(methods) != 2 or len(result_ids) != 2
                        or None in result_ids or set(executed) != set(code_ids)
                        or {c["phase"] for c in trial["calls"] if c["dispatch_state"] == "returned"}
                            != {"plan", "explanation"}
                        or any(len(task_ids) != 1 for task_ids in phase_tasks.values())
                        or len(set(code_ids) | set().union(*phase_tasks.values())) != 4
                        or receipt["final_status"] != ("needs_input" if trial["case_id"] == "C2" else "draft")
                        or set(receipt["calculation_result_ids"]) != result_ids
                        or receipt["route_evaluated"] is not True):
                    errors.append(f"completed_phase_and_calculation_route:{tid}")
                errors.extend(_calculation_errors(trial, receipt))
                if trial["case_id"] == "C2" and not receipt["missing_inputs"]:
                    errors.append(f"C2_missing_inputs:{tid}")
                if receipt["included_ids"] != [f"{trial['case_id']}-u{i}" for i in range(1, 7)] or (
                        receipt["excluded_ids"] != [f"{trial['case_id']}-excluded"]):
                    errors.append(f"exclusion_ids:{tid}")
                if receipt["critical_checks"] != {k: "met" for k in F03_CRITICAL}:
                    errors.append(f"critical_unresolved:{tid}")
                end = receipt["run_ended_monotonic"]
                start = receipt["run_started_monotonic"]
                if (not all(_finite_number(v) for v in (start, end)) or end < start or end - start > 600
                        or not math.isclose(trial["elapsed_seconds"], end - start, abs_tol=1e-6)):
                    errors.append(f"run_clock:{tid}")
                wanted_task_ids = {c["task_id"] for c in trial["calls"]} | set(executed)
                if set(receipt["task_clocks"]) != wanted_task_ids:
                    errors.append(f"task_clock_scope:{tid}")
                for clock in receipt["task_clocks"].values():
                    if (not all(_finite_number(v) for v in (clock["started"], clock["ended"]))
                            or not start <= clock["started"] <= clock["ended"] <= end
                            or clock["ended"] - clock["started"] > 240):
                        errors.append(f"task_clock:{tid}")
                if (type(receipt["quality_reviewer"]) is not str or not receipt["quality_reviewer"].strip()
                        or receipt["quality_review_kind"] != "independent"):
                    errors.append(f"quality_review_provenance:{tid}")
            if trial["source_unchanged"] is False or (trial["hook_rounds"] is not None and trial["hook_rounds"] > 4
                    or trial["hook_requests"] is not None and trial["hook_requests"] > 12):
                errors.append(f"source_or_hook_budget:{tid}")
            for phase in receipt["hooks"].values():
                if len(phase) > 2 or any(type(n) is not int or not 0 <= n <= 3 for n in phase):
                    errors.append(f"hook_budget_per_task:{tid}")
            if set(receipt["hooks"]) != {"plan", "explanation"}:
                errors.append(f"hook_phase_scope:{tid}")
            if (trial["hook_rounds"] != sum(len(v) for v in receipt["hooks"].values())
                    or trial["hook_requests"] != sum(sum(v) for v in receipt["hooks"].values())):
                errors.append(f"hook_totals:{tid}")
        expected_totals = comparison_totals(result["trials"], receipts)
        if result["totals"] != expected_totals:
            errors.append("totals_denominators_and_measurement")
        if (len(attempted) > 216 or sum(t["handler_reserved_calls"] for t in receipts.values()) > 216
                or result["totals"]["model_transport_attempts"] is not None
                and result["totals"]["model_transport_attempts"] > 216):
            errors.append("batch_call_budget")
        attempted.sort(key=lambda item: item[0])
        if [a[0] for a in attempted] != list(range(len(attempted))):
            errors.append("wire_sequence")
        ordered_runs = [receipts[t["trial_id"]] for t in result["trials"] if receipts[t["trial_id"]]["started"]]
        for previous, current in zip(ordered_runs, ordered_runs[1:]):
            if (previous["run_ended_monotonic"] is None
                    or previous["run_ended_monotonic"] > current["run_started_monotonic"]):
                errors.append("trial_clock_schedule_or_overlap")
        for previous, current in zip(attempted, attempted[1:]):
            if (previous[2]["sent_monotonic"] >= current[2]["sent_monotonic"]
                    or previous[2]["finished_monotonic"] is None
                    or previous[2]["finished_monotonic"] > current[2]["sent_monotonic"]):
                errors.append("wire_clock_order_or_overlap")
        reserved = 0
        for index, (_, call, attempt, trial) in enumerate(attempted):
            reserved += attempt["reserved_tokens"]
            if result["limits"]["total_token_cap"] is None or reserved > result["limits"]["total_token_cap"]:
                errors.append("batch_token_reservation")
            if (call["token_completeness"] != "complete" or call["dispatch_state"] != "returned") and index < len(attempted) - 1:
                errors.append("post_after_unknown_usage_or_outcome")
            if call["token_completeness"] != "complete" or call["dispatch_state"] != "returned":
                stop = attempt["finished_monotonic"] if attempt["finished_monotonic"] is not None else attempt["sent_monotonic"]
                if any(other[2]["sent_monotonic"] >= stop for other in attempted if other[1] is not call):
                    errors.append("post_after_unknown_clock")
        if len({c["attempt_id"] for _, c, _, _ in attempted}) != len(attempted):
            errors.append("unique_wire_attempt_ids")
        assessment = _evaluate_thresholds(result, payload, ready and result["measurement_ready"], errors)
        if result["verdict"] not in ("hold", assessment["verdict"]) and not (
                result["verdict"] == "unmeasured" and not attempted):
            errors.append("declared_verdict_without_evidence")
        return {"valid": not errors, "errors": list(dict.fromkeys(errors)),
                **assessment, "verdict": "hold" if errors else assessment["verdict"], "measurement_ready": ready and not errors}
    except (KeyError, TypeError, ValueError, OverflowError, AttributeError, IndexError) as exc:
        return {"valid": False, "errors": [*errors, "mandatory_sidecar_evidence:" + type(exc).__name__],
                "verdict": "hold", "measurement_ready": False}


def _calculation_errors(trial, receipt):
    """Validate saved deterministic cells and IDs, rather than an AI's success label."""
    errors, tid, cid = [], trial["trial_id"], trial["case_id"]
    expected = {
        "C1": (6, 0, (.9340038280798552, .006389519073392986),
                     (.8857142857142857, .01884548104956266)),
        "C2": (2, 4, (None, None), (None, None)),
        "C3": (6, 0, (.9245069112270482, .008333684329394844),
                     (.5428571428571428, .26570262390670546)),
    }[cid]
    for task in trial["code_tasks"]:
        method = task["method_id"]
        raw = receipt["calculation_raws"][method]
        manifest = raw["manifest"]
        rows = raw["datasets"]["correlations"]["rows"]
        policy = {"mode": "exploratory", "p_value_adjustment": "none", "comparison_family": None,
                  "independence_verified": False,
                  "note": "発話単位の探索的・未補正p値です。参加者/会話内の依存を補正しておらず、独立した参加者数ではありません。比較familyは未指定です。効果量・N・欠測と研究デザインを先に確認してください。"}
        if (manifest["analysis_unit"] != "発話" or manifest["group_variable"] != "speaker"
                or type(manifest["group_count"]) is not int or manifest["group_count"] != (2 if cid == "C3" else 6)
                or manifest["inference_policy"] != policy
                or manifest["inference_policy"]["independence_verified"] is not False):
            errors.append(f"calculation_analysis_scope_policy:{tid}")
        if (task["raw_hash"].removeprefix("sha256:") != canonical_hash(raw)
                or raw["method_id"] != method or raw["status"] != task["status"]
                or manifest["method_id"] != method or manifest["scope"] != "all_included_initial"
                or manifest["included_count"] != 6 or manifest["excluded_count"] != 1
                or set(manifest["evidence_ids"]) != set(receipt["included_ids"])
                or manifest["dataset_version"] != receipt["input_version"]
                or manifest["rows_hash"].removeprefix("sha256:") != canonical_hash(rows)
                or manifest["row_count"] != len(rows) or len(rows) != 15):
            errors.append(f"calculation_hash_scope:{tid}")
        for index, row in enumerate(rows):
            if row["row_id"] != "sha256:" + canonical_hash([method, index, {k: v for k, v in row.items() if k != "row_id"}]):
                errors.append(f"calculation_row_id:{tid}")
        primary = [r for r in rows if r["variable_a"] == "duration_seconds" and r["variable_b"] == "characters"]
        if len(primary) != 1:
            errors.append(f"calculation_primary_pair:{tid}")
            continue
        row = primary[0]
        coefficient, p_value = expected[2 if method == "pearson" else 3]
        if (row["n"] != expected[0] or row["missing"] != expected[1]
                or row["analysis_unit"] != "発話"
                or row["method"] != ("Pearson" if method == "pearson" else "Spearman")
                or row["unit_a"] != "秒" or row["unit_b"] != "文字"
                or row["p_value_adjustment"] != "none" or row["exploratory"] is not True
                or row["status"] != ("not_computable" if cid == "C2" else "computed")):
            errors.append(f"calculation_N_null_units:{tid}")
        for field, wanted in (("coefficient", coefficient), ("p_value", p_value)):
            actual = row[field]
            tolerance = 5e-9 if field == "coefficient" else 1e-12
            if ((wanted is None and actual is not None) or (wanted is not None and
                    (not _finite_number(actual) or not math.isclose(actual, wanted, rel_tol=1e-10, abs_tol=tolerance)))):
                errors.append(f"calculation_numeric:{tid}:{field}")
    return errors


def _evaluate_thresholds(result, payload, ready, errors):
    """Never compute adoption medians on just the successful subset."""
    blockers, case_results = [], {}
    if not ready:
        blockers.append("measurement_not_ready")
    if errors:
        blockers.append("semantic_validation_failed")
    active = [t for t in result["trials"] if t["state"] != "planned"]
    revision = max((t["revision"] for t in active), default=0)
    selected = [t for t in result["trials"] if t["revision"] == revision]
    if len(selected) != 18 or any(t["state"] != "completed" for t in selected):
        blockers.append("three_valid_pairs_required_for_every_case")
    if any(t["state"] in {"failed", "blocked", "uncertain", "running"} for t in active):
        blockers.append("failed_or_incomplete_trial_retained")
    if blockers:
        return {"verdict": "hold", "blockers": blockers, "cases": case_results}
    quality_bad = False
    for case_id in F03_CASES:
        A, B = ([next(t for t in selected if t["case_id"] == case_id and t["pair"] == p
                     and t["condition"] == condition) for p in (1, 2, 3)] for condition in ("A", "B"))
        for a, b in zip(A, B):
            ar, br = payload["trials"][a["trial_id"]], payload["trials"][b["trial_id"]]
            if any(ar["hashes"][k] != br["hashes"][k] for k in F03_SHARED_HASHES):
                blockers.append(f"paired_conditions_mismatch:{case_id}")
        gaps = []
        for trials in (A, B):
            values = []
            for t in trials:
                quality = t["quality"]
                if quality["status"] in {"review_pending", "unmeasured"}:
                    blockers.append(f"quality_pending:{case_id}")
                if quality["unnecessary_rejections"] is None:
                    blockers.append(f"normal_control_unmeasured:{case_id}")
                quality_bad |= bool(quality["critical_errors"] or quality["unnecessary_rejections"])
                if quality["status"] == "fail":
                    quality_bad = True
                items = {i["item_id"]: i for i in quality["item_checks"]}
                if (len(items) != len(quality["item_checks"]) or set(items) != set(F03_GAP_CATALOG[case_id])
                        or any(i["status"] == "unknown" or not i["evidence_ref"] for i in items.values())):
                    blockers.append(f"gap_catalog_unknown_or_changed:{case_id}")
                values.append(sum(i["status"] == "unmet" for i in items.values()))
            gaps.append(values)
        fields = ("input_tokens", "total_tokens", "elapsed_seconds", "initial_cpu_seconds", "queue_wait_seconds")
        if any(t[field] is None for t in A + B for field in fields) or any(
                t["missing_usage_calls"] or t["source_unchanged"] is not True or any(
                    r["elapsed_seconds"] is None for r in t["knowledge_receipts"]) for t in A + B):
            blockers.append(f"missing_metric:{case_id}")
            continue
        a_input, b_input = [t["input_tokens"] for t in A], [t["input_tokens"] for t in B]
        a_total, b_total = [t["total_tokens"] for t in A], [t["total_tokens"] for t in B]
        a_time, b_time = [t["elapsed_seconds"] for t in A], [t["elapsed_seconds"] for t in B]
        if any(v <= 0 for v in (median(a_input), median(a_total), median(a_time), max(a_time))):
            blockers.append(f"zero_baseline:{case_id}")
            continue
        input_better = median(b_input) <= .9 * median(a_input) and sum(b < a for a, b in zip(a_input, b_input)) >= 2
        gap_better = (median(gaps[0]) - median(gaps[1]) >= 1 and median(b_input) <= median(a_input)
                      and sum(b < a for a, b in zip(gaps[0], gaps[1])) >= 2)
        def wire_calls(t):
            return sum(c["dispatch_state"] != "not_dispatched" for c in t["calls"])
        constraints = (median(b_total) <= 1.1 * median(a_total) and median(b_time) <= 1.2 * median(a_time)
                       and max(b_time) <= 1.5 * max(a_time)
                       and all(wire_calls(b) <= min(6, wire_calls(a) + 1) for a, b in zip(A, B)))
        case_results[case_id] = {"input_improved": input_better, "gap_improved": gap_better,
                                "bounds_met": constraints, "gap_A": gaps[0], "gap_B": gaps[1],
                                "passed": (input_better or gap_better) and constraints}
    if blockers:
        verdict = "hold"
    elif quality_bad:
        verdict = "stop"
    elif all(case_results[c]["passed"] for c in F03_CASES):
        verdict = "continue"
    else:
        verdict = "rework" if revision == 0 else "stop"
    return {"verdict": verdict, "blockers": blockers, "cases": case_results}


def comparison_preflight(packet_path, comparison_id, revision=0):
    fixed = load_comparison_spec(packet_path)
    cpu = {}
    with tempfile.TemporaryDirectory(prefix="gurumoji-f03-cpu-") as directory:
        for case_id in F03_CASES:
            cpu[case_id] = prepare_cpu_case(case_id, Path(directory) / case_id / "library.sqlite3")
            control = prepare_cpu_case(case_id, Path(directory) / (case_id + "-raw-control") / "library.sqlite3",
                                       save_exclusion=False)
            if len(control["included_ids"]) != 7 or control["excluded_ids"]:
                raise ValueError("Raw-flag exclusion regression control changed")
    order = comparison_order(0) + (comparison_order(1) if revision == 1 else [])
    limits = {k: p.get("const") for k, p in F03_RESULT_SCHEMA["properties"]["limits"]["properties"].items()}
    trials, receipts = [], {}
    zero_hash = "0" * 64
    script_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    for entry in order:
        trial = {**entry, "fixture_hash": cpu[entry["case_id"]]["fixture_hash"], "app_run_id": None,
                 "state": "planned", "calls": [], "code_tasks": [],
                 "quality": {"status": "unmeasured", "critical_errors": [], "unnecessary_rejections": None,
                             "item_checks": []},
                 **{k: None for k in ("input_tokens", "output_tokens", "reasoning_tokens", "total_tokens",
                                      "elapsed_seconds", "initial_cpu_seconds", "queue_wait_seconds")},
                 "complete_usage_calls": 0, "missing_usage_calls": 0, "hook_rounds": 0, "hook_requests": 0,
                 "knowledge_receipts": [], "source_unchanged": None, "error_kind": None}
        trials.append(trial)
        hashes = {k: zero_hash for k in F03_TRIAL_HASHES}
        hashes.update(input=cpu[entry["case_id"]]["input_hash"], case=trial["fixture_hash"],
                      schema=F03_SCHEMA_HASH, validator=script_hash, script=script_hash, model_condition=None)
        receipts[entry["trial_id"]] = {"started": False, "hashes": hashes, "calls": {},
                                      "handler_reserved_calls": 0, "call_ai_entrances": 0,
                                      "code_executed_ids": [], "task_clocks": {},
                                      "clock_segments": [],
                                      "hooks": {"plan": [], "explanation": []}}
    result = {"schema_version": "f03-result-1", "comparison_id": comparison_id, "spec_hash": F03_SPEC_HASH,
              "plan_hash": F03_PLAN_HASH, "preparation_commit": subprocess.check_output(
                  ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "baseline_commit": None, "corpus_hash": zero_hash, "model_condition_hash": None,
              "measurement_ready": False, "ready_blockers": ["a06_and_runtime_guard_pending",
                 "model_context_tokenizer_template_usage_unverified", "condition_corpus_not_frozen"],
              "limits": limits, "trials": trials, "totals": comparison_totals(trials, receipts),
              "verdict": "hold", "not_run": ["model discovery/load/inference", "runtime transport guard",
                                             "actual A/B knowledge delivery", "human semantic adoption"]}
    payload = {"fixed_hashes": {"spec": F03_SPEC_HASH, "schema": F03_SCHEMA_HASH,
                "corrections": fixed["body_hashes"]["f03_spec_corrections"],
                "guard_findings": fixed["body_hashes"]["f03_guard_findings"],
                "script": script_hash, "validator": script_hash, "runtime_guard": None,
                "case_inputs": {cid: cpu[cid]["input_hash"] for cid in F03_CASES}},
               "readiness": {**{k: False for k in F03_READY_FLAGS}, "model_instance_id": None, "parallel": 1,
                             "baseline_commit": None, "kv_reused": False, "generated_warmup_calls": 0},
               "time_scope": copy.deepcopy(F03_TIME_SCOPE), "revision1_authorized": False,
               "preaccepted_manifest_hash": None,
               "condition_hashes": {str(r): {"A": zero_hash, "B": zero_hash} for r in (0, 1)},
               "trials": receipts, "core_calls": 0}
    evidence = bind_comparison_evidence(result, payload)
    assessment = assess_comparison(result, evidence)
    if not assessment["valid"]:
        raise ValueError("CPU preflight ledger validation failed: " + ",".join(assessment["errors"]))
    return {"cpu_preflight": "passed", "measurement_ready": False, "model_calls": 0,
            "fixed_hashes": {"packet_file": fixed["file_hash"], **fixed["body_hashes"]},
            "cpu_cases": cpu, "comparison_result": result, "evidence": evidence,
            "assessment": assessment, "not_run": result["not_run"]}




GUARDED_SOURCE_FILES = (
    "src/gurumoji/app.py", "src/gurumoji/analysis_orchestration.py",
    "src/gurumoji/services/analysis_orchestration_adapters.py",
    "src/gurumoji/services/ai/client.py", "src/gurumoji/services/ai/request_budget.py",
    "src/gurumoji/ai_http_worker.py", "scripts/test_expert_agent_model.py",
    "scripts/test_saved_autonomous_analysis.py",
)


def current_guarded_manifest():
    """Current raw source bytes, never an acceptance receipt by themselves."""
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in GUARDED_SOURCE_FILES}


def prepare_guarded_entry(manifest, receipt_ref, *, verify_receipt=None,
                          token_counter=None, batch=None, policy=None):
    """External caller supplies trusted proof and frozen policy, before start().

    No tokenizer discovery, client load or HTTP lives here. CLI JSON cannot
    manufacture the external verifier/counter. Synthetic proof enables only
    isolated CPU transport tests and always leaves measurement_ready false.
    """
    held = {"measurement_ready": False, "factory": None, "model_calls": 0}
    if manifest != current_guarded_manifest():
        return {**held, "blockers": ["current_source_manifest_required"]}
    if not isinstance(receipt_ref, str) or not receipt_ref or not callable(verify_receipt) or not callable(token_counter):
        return {**held, "blockers": ["external_acceptance_and_full_payload_counter_required"]}
    try:
        evidence = verify_receipt(copy.deepcopy(manifest), receipt_ref)
        required = ("accepted", "model_verified", "context_verified", "tokenizer_verified",
                    "template_verified", "full_schema_verified")
        if not isinstance(evidence, dict) or any(evidence.get(key) is not True for key in required):
            return {**held, "blockers": ["external_model_evidence_incomplete"]}
        from gurumoji.services.ai.request_budget import RequestBudget, BatchQuota
        # These limits are an external comparison caller's policy, not M's.
        if (not isinstance(batch, BatchQuota) or not isinstance(policy, dict)
                or set(policy) != {"trial_call_limit", "trial_token_limit"}):
            return {**held, "blockers": ["external_frozen_budget_policy_required"]}
        conditions = evidence["conditions"]
        condition_keys = {"model", "context_tokens", "tokenizer", "template", "source", "acceptance_anchor",
                          "model_conditions_hash", "synthetic_only", "usage_policy"}
        if (not isinstance(conditions, dict) or set(conditions) != condition_keys
                or type(conditions["synthetic_only"]) is not bool
                or type(conditions["context_tokens"]) is not int or not 4096 <= conditions["context_tokens"] <= 32768
                or conditions["usage_policy"] not in {"output_includes_reasoning", "reasoning_disabled"}
                or conditions["acceptance_anchor"] != receipt_ref
                or any(not isinstance(conditions[key], str) or not conditions[key] or len(conditions[key]) > 200
                       for key in ("model", "tokenizer", "template", "source", "acceptance_anchor", "model_conditions_hash"))
                or re.fullmatch(r"sha256:[0-9a-f]{64}", conditions["model_conditions_hash"]) is None):
            return {**held, "blockers": ["external_evidence_invalid"]}
        def factory(*, run_id, run_started_at, clock):
            return RequestBudget(budget_id="F03:" + run_id, run_id=run_id,
                run_started_at=run_started_at, clock=clock, batch=batch,
                token_counter=token_counter, acceptance_anchor=receipt_ref,
                model=conditions["model"], context_tokens=conditions["context_tokens"],
                tokenizer_id=conditions["tokenizer"], template_id=conditions["template"],
                proof_source=conditions["source"], model_conditions_hash=conditions["model_conditions_hash"],
                synthetic_only=conditions["synthetic_only"], usage_policy=conditions["usage_policy"], **policy)
        return {"measurement_ready": conditions["synthetic_only"] is False,
                "factory": factory, "model_calls": 0,
                "blockers": ["synthetic_evidence_only"] if conditions["synthetic_only"] else []}
    except (KeyError, TypeError, ValueError):
        return {**held, "blockers": ["external_evidence_invalid"]}


def guarded_cli_entry(args, trusted_inputs=None):
    if not args.guarded_manifest and not args.guarded_receipt:
        return None
    try:
        manifest = json.loads(args.guarded_manifest.read_text(encoding="utf-8")) if args.guarded_manifest else None
    except (OSError, ValueError):
        manifest = None
    return prepare_guarded_entry(manifest, args.guarded_receipt, **(trusted_inputs or {}))


def main(*, trusted_guarded_inputs=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--guarded-manifest", type=Path)
    parser.add_argument("--guarded-receipt", help="Externally verified C0 acceptance receipt reference")
    parser.add_argument("--model", default="google/gemma-4-12b")
    parser.add_argument("--expert-id", default="exp-thematic-analysis")
    parser.add_argument("--statistical-cycle", action="store_true",
                        help="Test plan, Handler calculation, and explanation (two real specialist calls; no Core AI)")
    parser.add_argument("--output", type=Path, default=ROOT / "output/expert-agent-model")
    parser.add_argument("--call-timeout", type=int, default=240)
    parser.add_argument("--comparison-preflight", action="store_true",
                        help="F03 CPU fixtures and planned ledger only; never loads or calls a model")
    parser.add_argument("--comparison-id", default=None)
    parser.add_argument("--comparison-packet", type=Path, default=None)
    parser.add_argument("--revision", type=int, choices=(0, 1), default=None)
    args = parser.parse_args()
    guarded_entry = guarded_cli_entry(args, trusted_guarded_inputs)
    if guarded_entry is not None and (guarded_entry["factory"] is None or not guarded_entry["measurement_ready"]):
        print(json.dumps({key: value for key, value in guarded_entry.items() if key != "factory"}))
        return 2
    if args.comparison_preflight:
        if args.statistical_cycle:
            parser.error("--comparison-preflight cannot run the real statistical-cycle")
        packet_path = args.comparison_packet or ROOT.parent / "artifacts/obsidian-skill-plan/revision-5/execution-packet.json"
        report = comparison_preflight(packet_path, args.comparison_id or "f03-cpu-preflight", args.revision or 0)
        print(json.dumps(report, ensure_ascii=False, allow_nan=False), flush=True)
        return 0
    if args.comparison_id is not None or args.revision is not None or args.comparison_packet is not None:
        parser.error("F03 model comparison is not wired; use --comparison-preflight")
    from test_saved_autonomous_analysis import initialize_test_runtime
    from test_obsidian_management_model import SYNTHETIC_TEXTS
    dest = args.output.resolve() / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8])
    dest.mkdir(parents=True)
    data = dest / "data"
    os.environ.update(MOJIOKOSI_DATA_DIR=str(data), MOJIOKOSI_OUTPUT_DIR=str(dest / "media"), MOJIOKOSI_BACKUP_DIR=str(dest / "backup"))
    sys.path.insert(0, str(ROOT / "src"))
    from gurumoji import app
    from gurumoji.services.analysis_orchestration_methods import EXPERT_STATISTICAL_TOOLS
    if args.statistical_cycle and args.expert_id not in EXPERT_STATISTICAL_TOOLS:
        parser.error("--statistical-cycle requires a statistical expert ID")
    initialize_test_runtime(app, data / "library.sqlite3")
    report = {"status": "failed", "model": args.model, "expert_id": args.expert_id,
              "provider": "lmstudio", "synthetic_input": True, "real_specialist_ai": True,
              "core_calls": 0, "test_scope": "explicit Handler statistical cycle, not autonomous Core routing" if args.statistical_cycle else "single explicit Handler specialist task, not a complete autonomous analysis",
              "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "source_state": "uncommitted", "not_run": ["Core routing with real AI", "semantic quality evaluation",
                  "real interviews", "real Vault", "Obsidian GUI", "cloud inference"], "calls": []}
    report["source_sha256"] = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in (
        "src/gurumoji/services/expert_agents.py", "src/gurumoji/analysis_orchestration.py",
        "src/gurumoji/services/analysis_orchestration_adapters.py", "src/gurumoji/app.py", "scripts/test_expert_agent_model.py")}
    (dest / "runner.py").write_bytes(Path(__file__).read_bytes())
    def save():
        (dest / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    original = app.call_orchestration_ai_json
    try:
        config = app.load_token_config()
        base = app.lmstudio_base_url(config.lmstudio_base_url)
        if urlsplit(base).hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise RuntimeError("Only a loopback endpoint is allowed")
        headers = app.ai_client.lmstudio_headers(config.lmstudio_api_key)
        req = urllib.request.Request(base.removesuffix("/v1") + "/api/v1/models", headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            loaded = [instance for model in json.load(response).get("models", []) for instance in model.get("loaded_instances", [])]
        report["loaded_model"] = next((model for model in loaded if model.get("id") == args.model), None)
        if report["loaded_model"] is None:
            raise RuntimeError("Requested model must already be loaded")
        def observed(*positional, **keywords):
            if positional[0] != "lmstudio" or positional[2] != args.model or positional[5] != "analysis_orchestration_interpretation":
                raise RuntimeError("Unexpected model or role")
            packet = json.loads(positional[4])["expert_request"]
            call = {"expert_id": packet["expert_id"], "profile_hash": packet["profile_hash"],
                    "knowledge_hash": packet["knowledge_hash"], "note_count": len(packet["knowledge"]["knowledge"]),
                    "prompt_characters": len(positional[3]) + len(positional[4]), "status": "running"}
            report["calls"].append(call)
            number = len(report["calls"])
            (dest / f"request-{number:02d}.json").write_text(positional[4], encoding="utf-8")
            (dest / f"schema-{number:02d}.json").write_text(json.dumps(positional[6], ensure_ascii=False, indent=2), encoding="utf-8")
            (dest / "request.json").write_text(positional[4], encoding="utf-8")
            (dest / "schema.json").write_text(json.dumps(positional[6], ensure_ascii=False, indent=2), encoding="utf-8")
            save()
            tick = time.monotonic()
            print("Dispatching one real specialist call", flush=True)
            try:
                result = original(*positional, **keywords)
                (dest / f"response-{number:02d}.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                (dest / "response.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
                call["status"] = "returned"
                return result
            except Exception as exc:
                call.update(status="failed", error_type=type(exc).__name__)
                if isinstance(exc, RuntimeError):
                    call["diagnostic"] = str(exc)[:600]
                raise
            finally:
                call["seconds"] = round(time.monotonic() - tick, 2)
                save()
        app.call_orchestration_ai_json = observed
        item_id = "synthetic-specialist-test"
        segments = [{"id": f"u{i}", "speaker": speaker, "text": text, "start": i * 10, "end": i * 10 + 8,
                     "annotation": {}, "excluded": False} for i, (speaker, text) in enumerate(SYNTHETIC_TEXTS, 1)]
        app.upsert_library_item(item_id=item_id, source_name="Synthetic specialist test", output_dir=dest / "media",
            media_path=None, language="ja", segments=segments, speaker_names={"A": "合成A", "B": "合成B"}, files=[],
            outline=None, emotion_analysis=None, write_srt=False, write_json=True)
        stamp = app.archive_source_stamp(app.library_row(item_id))
        service = app.analysis_orchestration_service()
        service.schedule = False
        inputs = {args.expert_id: {"analysis_premises": "合成6発話の探索用。研究者の指定として帰納的・意味的水準を用い、候補の確定と一般化は保留する。"}}
        question = "この合成会話の店の選択理由と評価の違いを、原文根拠・反例付きの分析下書きとして整理してください。"
        if args.statistical_cycle:
            inputs = {args.expert_id: {"analysis_premises": "検証用の合成6発話。発話単位の探索的分析で、話者内の独立性は未確認。母集団への一般化・因果推論は行わない。"}}
            question = {
                "exp-correlation": "検証用の合成会話です。発話単位の文字数と形態素数のPearson・Spearman相関を探索的に確認してください。計算できない指標はそのまま明示してください。",
                "exp-descriptive-statistics": "検証用の合成会話の発話単位の記述統計と度数を確認してください。欠測と対象の分母を明示してください。",
                "exp-group-comparison-statistics": "検証用の合成会話の話者ごとの群間比較を探索的に確認してください。適用条件、計算不能な状態、入れ子と多重比較の限界を明示してください。",
            }[args.expert_id]
        options = app.prepare_orchestration({"provider": "lmstudio", "model": args.model, "publication_targets": [],
            "obsidian_management": True, "expert_ids": [args.expert_id], "expert_inputs": inputs,
            "question": question,
            "time_limit_seconds": 600, "call_timeout_seconds": args.call_timeout, "concurrency": 1,
            "context_evidence_limit": 6, "context_text_limit": 6000, "context_index_limit": 6})
        run = service.start(item_id, options, **({"budget_factory": guarded_entry["factory"]} if guarded_entry else {}))
        report["run_id"] = run["run_id"]
        if not service._build_initial(run["run_id"]):
            raise RuntimeError("Initial construction failed")
        with service._db() as db:
            saved = service._read_run(db, run["run_id"])
            task = service._register(db, saved, {"role": "interpretation", "expert_id": args.expert_id,
                "question": saved["config"]["question"], "why_now": "利用者が依頼した専門家接続の実モデル試験",
                "success_criteria": "根拠・適用条件・限界と指定入出力形式を確認する"}, phase="specialists")
        service._execute(run["run_id"], task["task_id"])
        state = service.status(item_id, run["run_id"])
        completed = next(t for t in state["tasks"] if t["task_id"] == task["task_id"])
        if args.statistical_cycle and completed["status"] == "succeeded":
            plan = service.result(item_id, run["run_id"], completed["result_id"])["raw"]
            report["planning_status"] = plan["expert_report"]["status"]
            if plan["expert_report"]["status"] != "needs_calculation" or not plan["analysis_requests"]:
                raise RuntimeError("Expected a validated calculation proposal")
            calculations = []
            for proposal in plan["analysis_requests"]:
                with service._db() as db:
                    saved = service._read_run(db, run["run_id"])
                    calculation = service._register(db, saved, proposal, phase="specialists")
                if calculation is None:
                    continue
                service._execute(run["run_id"], calculation["task_id"])
                current = service.status(item_id, run["run_id"])
                calculation = next(t for t in current["tasks"] if t["task_id"] == calculation["task_id"])
                if calculation["status"] != "succeeded":
                    raise RuntimeError("Handler calculation failed")
                calculations.append(calculation)
            report["calculation_tasks"] = [{key: value[key] for key in ("task_id", "result_id", "method_id", "status")}
                                            for value in calculations]
            with service._db() as db:
                saved = service._read_run(db, run["run_id"])
                explanation = service._register(db, saved, {
                    "role": "interpretation", "expert_id": args.expert_id,
                    "question": "検証済みの計算結果を説明し、N・欠測・適用条件・探索的扱いの限界を明記してください。",
                    "why_now": "計算結果が保存・検証されたため", "success_criteria": "計算結果IDと根拠を示し説明を下書きする",
                    "dependencies": [value["task_id"] for value in calculations]}, phase="specialists")
            service._execute(run["run_id"], explanation["task_id"])
            state = service.status(item_id, run["run_id"])
            completed = next(t for t in state["tasks"] if t["task_id"] == explanation["task_id"])
        report.update(task_status=completed["status"], task_error=completed["error"], usage=state["usage"],
                      knowledge_catalog=state["expert_agents"], source_unchanged=app.archive_source_stamp(app.library_row(item_id)) == stamp)
        (dest / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        if completed["status"] == "succeeded":
            raw = service.result(item_id, run["run_id"], completed["result_id"])["raw"]
            report.update(expert_report_status=raw["expert_report"]["status"], output_fields=list(raw["expert_report"]["outputs"]))
            if args.statistical_cycle:
                report["calculation_result_ids"] = raw["expert_report"]["calculation_result_ids"]
                report["status"] = "passed" if (report["source_unchanged"] and len(report["calls"]) == 2
                    and raw["expert_report"]["status"] == "draft" and report["calculation_result_ids"]
                    and set(report["calculation_result_ids"]) <= {value["result_id"] for value in calculations}) else "failed"
            else:
                report["status"] = "passed" if report["source_unchanged"] and len(report["calls"]) == 1 else "failed"
        # End the test run explicitly without claiming full-analysis completion.
        service.cancel(item_id, run["run_id"])
    except Exception as exc:
        report["error_type"] = type(exc).__name__
        if getattr(exc, "code", None):
            report["error_code"] = exc.code
        if isinstance(exc, RuntimeError):
            report["diagnostic"] = str(exc)[:300]
    finally:
        app.call_orchestration_ai_json = original
        if report.get("run_id"):
            try:
                service.cancel(item_id, report["run_id"])
            except Exception as exc:
                report["cleanup_error"] = type(exc).__name__
        save()
    print(json.dumps({"status": report["status"], "task_status": report.get("task_status"),
                      "error": report.get("task_error", report.get("error_type")), "evidence": str(dest)}, ensure_ascii=False), flush=True)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
