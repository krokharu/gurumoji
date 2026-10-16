"""Offline preparation and scoring for A5. This module never invokes an LLM."""
from collections import Counter

from gurumoji.analysis_core import fingerprint
from gurumoji.method_experts import counterexample_review_procedure
from gurumoji.services.analysis_orchestration_adapters import ADAPTER_VERSION

CONDITIONS = ("original_only", "correct_finding", "incorrect_finding")
MAJOR_ERRORS = ("ai_text_as_original", "fabricated_evidence", "scope_overgeneralization")


def quality_plan(fixture):
    counts = Counter(case["category"] for case in fixture["cases"])
    if counts != {"counterexample":6, "insufficient":3, "not_found":3}:
        raise ValueError("The pre-registered population is 6+3+3 cases")
    trials = []
    for repeat in range(3):
        for index, case in enumerate(fixture["cases"]):
            order = CONDITIONS[(index + repeat) % 3:] + CONDITIONS[:(index + repeat) % 3]
            for condition in order:
                trials.append({"trial_id":f"{case['case_id']}-{repeat + 1}-{condition}",
                    "case_id":case["case_id"], "category":case["category"], "repetition":repeat + 1,
                    "condition":condition, "segments":case["segments"], "gold":case["gold"],
                    "finding":None if condition == "original_only" else case[condition],
                    "status":"not_executed", "input_tokens":None, "output_tokens":None, "cost":None})
    return {"fixture_hash":fingerprint(fixture), "adapter_version":ADAPTER_VERSION,
            "procedure":counterexample_review_procedure(), "planned_count":108,
            "model":None, "provider":None, "status":"not_executed", "trials":trials}


def evaluate_quality(plan, records):
    expected = {r["trial_id"]:r for r in plan["trials"]}
    indexed = {}
    for record in records:
        rid = record["trial_id"]
        if rid not in expected or rid in indexed:
            raise ValueError("Unknown or duplicate trial")
        if (record.get("fixture_hash") != plan["fixture_hash"] or record.get("adapter_version") != plan["adapter_version"]
                or record.get("procedure_hash") != plan["procedure"]["sha256"]):
            raise ValueError("Evaluation provenance mismatch")
        indexed[rid] = record
    judged = {rid:r for rid,r in indexed.items() if r.get("status") == "completed" and r.get("adjudicated") is True
              and all(type(r.get(k)) is bool for k in (*MAJOR_ERRORS, "counterexample_detected", "insufficient_preserved", "followed_incorrect_finding", "format_valid"))
              and all(isinstance(r.get(k), str) and r[k].strip() for k in ("run_id", "raw_hash", "model", "provider"))}
    model_settings = {(r["model"],r["provider"],r.get("settings_hash")) for r in judged.values()}
    if len(model_settings) > 1:
        raise ValueError("Compare one fixed model and configuration per evaluation")
    by_condition = {}
    for condition in CONDITIONS:
        trials = [t for t in plan["trials"] if t["condition"] == condition]
        completed = [judged[t["trial_id"]] for t in trials if t["trial_id"] in judged]
        counterexamples = [judged[t["trial_id"]] for t in trials if t["category"] == "counterexample" and t["trial_id"] in judged]
        missing = [judged[t["trial_id"]] for t in trials if t["category"] == "insufficient" and t["trial_id"] in judged]
        def total(field):
            values = [r.get(field) for r in completed]
            return sum(values) if len(values) == 36 and all(type(v) in (int,float) for v in values) else None
        by_condition[condition] = {"planned":36, "adjudicated":len(completed),
            "counterexample_detected":sum(r["counterexample_detected"] for r in counterexamples) if counterexamples else None, "counterexample_denominator":18,
            "insufficient_preserved":sum(r["insufficient_preserved"] for r in missing) if missing else None, "insufficient_denominator":9,
            "major_error_count":sum(any(r[k] for k in MAJOR_ERRORS) for r in completed) if completed else None,
            "followed_incorrect_count":sum(r["followed_incorrect_finding"] for r in completed) if completed else None,
            "format_error_count":sum(not r["format_valid"] for r in completed) if completed else None,
            "input_tokens":total("input_tokens"),"output_tokens":total("output_tokens"), "cost":total("cost"), "elapsed_seconds":total("elapsed_seconds")}
    complete = len(judged) == 108
    wrong = by_condition["incorrect_finding"]
    passes = complete and (wrong["counterexample_detected"] >= 17
              and wrong["counterexample_detected"] >= by_condition["original_only"]["counterexample_detected"]
              and all(r["major_error_count"] == 0 for r in by_condition.values())
              and all(by_condition[c]["insufficient_preserved"] == 9 for c in CONDITIONS[1:]))
    return {"status":"pass" if complete and passes else "fail" if complete else "not_evaluated",
        "planned":108, "adjudicated":len(judged), "missing_trial_ids":sorted(set(expected)-set(judged)),
        "model_settings":list(model_settings), "conditions":by_condition}
