"""統計codecの接続・出典束縛・不正応答拒否を一時DBで検証する。"""
import copy
import json
import sqlite3
from decimal import localcontext
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from gurumoji.analysis_core import AnalysisContractError, fingerprint
from gurumoji.services import metric_delivery as metrics, model_context


def case():
    task = {"task_id": "task-synthetic", "role": "orchestrator", "phase": "specialist_review", "iteration": 1,
            "annotation_version": 0, "intent": {"scope": {"domain": "statistics"}}}
    raw = [
        {"method": {"method_id": "participation"}, "datasets": {"speakers": {"rows": [
            {"speaker": "A", "speaker_name": "話者A", "turn_count": 2, "timed_turn_count": 1,
             "missing_time_turn_count": 1, "speaking_seconds": 1.2, "characters": 6},
            {"speaker": "B", "speaker_name": "話者B", "turn_count": 1, "timed_turn_count": 1,
             "missing_time_turn_count": 0, "speaking_seconds": 2, "characters": 5}]}}},
        {"method": {"method_id": "conversation_dynamics"}, "datasets": {
            "gaps": {"rows": [{"seconds": .1}, {"seconds": .2}]}, "overlaps": {"rows": []}}},
        {"method_id": "label_frequency", "dataset_version": "version", "annotation_version": 0,
         "codebook_version": 1, "label_field": "codes", "denominator": 3, "missing_count": 1,
         "rows": [{"label": "合成ラベル", "count": 2, "denominator": 3}], "limitations": ["合成の限界"]}]
    results = [{"result_id": "result-" + str(i), "role": "statistics", "raw_hash": fingerprint(value),
                "validation_status": "valid", "content": value} for i, value in enumerate(raw)]
    context = {"resources_origin": {"run_id": "run-synthetic"}, "initial": {"initial_id": "initial"},
               "data_version": "version", "annotation_version": 0, "task": task, "results": results,
               "iteration_review": {"pending_result_ids": [r["result_id"] for r in results], "omitted_pending_result_count": 0},
               "review_domain": "statistics", "raw_evidence": [], "question": "3種の集計を確認する"}
    return context


def encoded_case():
    context = case()
    public, contract, schema = metrics.prepare(context)
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE orchestration_results(result_id TEXT,run_id TEXT,raw_json TEXT,state_json TEXT)")
    for source in context["results"]:
        db.execute("INSERT INTO orchestration_results VALUES(?,?,?,?)", (source["result_id"], "run-synthetic",
                   json.dumps(source["content"]), json.dumps({k: v for k, v in source.items() if k != "content"})))
    task = context["task"]
    task["context_manifest"] = {"metric_contract": contract, "requested_result_ids": [r["result_id"] for r in context["results"]]}
    run = {"run_id": "run-synthetic", "initial_id": "initial", "input_hash": "version", "config": {"metric_codec_version": 1}}
    choices = {}
    for i, source in enumerate(contract["sources"]):
        binding = next(b for b in contract["state"]["bindings"] if b["record"]["result_id"] in source["record_ids"])
        choices["source_" + str(i + 1)] = {"operation": "value", "operands": [binding["ref"]], "value": binding["record"]["value"]}
    return db, run, task, {"claims": [], "metric_selections": choices}, public, schema


def test_all_three_methods_use_real_encoder_decoder_and_do_not_modify_source():
    original = case()
    before = copy.deepcopy(original)
    public, contract, schema = metrics.prepare(original)
    assert original == before
    assert len(contract["sources"]) == 3
    assert all("datasets" not in r["content"] and r["content"]["raw_result_preserved"] for r in public["results"])
    assert "query_hash" not in json.dumps(public["metric_context"])
    db, run, task, response, _, _ = encoded_case()
    with db:
        decoded = metrics.validate(db, run, task, response)
    assert decoded["status"] == "answered" and len(decoded["items"]) == 3
    assert decoded["encoder"].endswith("MetricEncoder") and decoded["decoder"].endswith("MetricDecoder")
    assert [item["value"] for item in decoded["items"]] == ["3", "2", "3"]


def test_decimal_duration_missing_timing_and_empty_table_remain_explicit():
    with localcontext() as arithmetic:
        arithmetic.prec = 2
        _, contract, _ = metrics.prepare(case())
    records = [b["record"] for b in contract["state"]["bindings"]]
    time = next(r for r in records if r["metric_id"] == "participation:speaking_seconds" and r["group"][0]["value"] == "話者A")
    assert (time["population_count"], time["observed_count"], time["missing_count"], time["value"]) == (2, 1, 1, "1.2")
    gap = next(r for r in records if r["metric_id"] == "conversation_dynamics:gaps_seconds")
    assert gap["value"] == "0.3"
    empty = next(r for r in records if r["metric_id"] == "conversation_dynamics:overlaps_count")
    assert empty["value"] is None and empty["observed_count"] == 0


@pytest.mark.parametrize("operation,expected", [("diff", "1"), ("ratio", "2.0000"), ("max", "2"), ("min", "1")])
def test_decoder_computes_supported_operations(operation, expected):
    db, run, task, response, _, _ = encoded_case()
    bindings = task["context_manifest"]["metric_contract"]["state"]["bindings"]
    refs = [b["ref"] for b in bindings if b["record"]["metric_id"] == "participation:turn_count"][1:]
    response["metric_selections"]["source_1"] = {"operation": operation, "operands": refs, "value": None}
    assert metrics.validate(db, run, task, response)["items"][0]["value"] == expected


@pytest.mark.parametrize("change", ["unknown_ref", "forged_value", "unit_mismatch", "missing_source", "source_hash", "foreign_run", "binding_tamper", "free_claim"])
def test_invalid_response_or_binding_never_returns_partial_result(change):
    db, run, task, response, _, _ = encoded_case()
    first = response["metric_selections"]["source_1"]
    if change == "unknown_ref": first["operands"] = ["M999"]
    if change == "forged_value": first["value"] = "999"
    if change == "unit_mismatch": first.update(operation="diff", operands=["M2", "M3"], value=None)
    if change == "missing_source": response["metric_selections"].pop("source_3")
    if change == "source_hash": db.execute("UPDATE orchestration_results SET raw_json='{}' WHERE result_id='result-0'")
    if change == "foreign_run": run["run_id"] = "other"
    if change == "binding_tamper":
        contract = task["context_manifest"]["metric_contract"]
        contract["state"]["bindings"][0]["record"]["value"] = "999"
        contract["state_sha256"] = fingerprint(contract["state"])
    if change == "free_claim": response["claims"] = [{"text": "数値を推測"}]
    with pytest.raises(AnalysisContractError): metrics.validate(db, run, task, response)


def test_not_found_cannot_skip_known_statistics_report():
    db, run, task, response, _, _ = encoded_case()
    response["metric_selections"] = {"status": "not_found", "items": []}
    with pytest.raises(AnalysisContractError) as error: metrics.validate(db, run, task, response)
    assert error.value.code == "metric_coverage_incomplete"


def test_generation_schema_binds_value_to_one_ref_and_its_original_value():
    from jsonschema import Draft202012Validator
    _, _, _, response, _, schema = encoded_case()
    validator = Draft202012Validator(schema)
    assert not list(validator.iter_errors(response["metric_selections"]))
    wrong = copy.deepcopy(response["metric_selections"])
    wrong["source_1"] = {"operation": "value", "operands": ["M1", "M2"], "value": None}
    assert list(validator.iter_errors(wrong))
    wrong = copy.deepcopy(response["metric_selections"])
    wrong["source_1"]["value"] = "999"
    assert list(validator.iter_errors(wrong))


@pytest.mark.parametrize("bad", ["NaN", -1, .0000000000001])
def test_unsupported_values_are_not_rounded_or_zero_filled(bad):
    context = case()
    source = context["results"][0]
    source["content"]["datasets"]["speakers"]["rows"][0]["speaking_seconds"] = bad
    source["raw_hash"] = fingerprint(source["content"])
    with pytest.raises(AnalysisContractError): metrics.prepare(context)


def test_packet_limit_is_explicit_and_no_records_are_truncated():
    context = case()
    source = context["results"][0]
    rows = source["content"]["datasets"]["speakers"]["rows"]
    rows[:] = [{**rows[0], "speaker_name": "話者" + str(i)} for i in range(60)]
    source["raw_hash"] = fingerprint(source["content"])
    with pytest.raises(AnalysisContractError) as error: metrics.prepare(context)
    assert error.value.code == "metric_codec_limit_or_invalid"


def test_actual_adapter_exposes_only_public_metrics_and_binds_response_schema(monkeypatch):
    from gurumoji.services.analysis_orchestration_adapters import make_orchestration_adapters
    monkeypatch.setenv("MOJIOKOSI_OBUSSQL_ENABLED", "1")
    calls, recorded = [], []
    def provider(*args, **kwargs):
        calls.append((args, kwargs))
        wire = model_context.restored_reference_context(args[4], kwargs.get("data_messages"))
        assert "metric_context" in wire
        assert all("datasets" not in row["content"] for row in wire["results"])
        assert "metric_selections" in args[6]["required"]
        assert args[6]["properties"]["claims"]["maxItems"] == 0
        metrics = wire["metric_context"]
        by_ref = {r["ref"]: r for r in metrics["records"]}
        selections = {source["key"]: {"operation": "value", "operands": [source["refs"][0]], "value": by_ref[source["refs"][0]]["value"]}
                      for source in metrics["sources"]}
        return {"summary": "検討手順", "claims": [], "metric_selections": selections}
    resolve, runner = make_orchestration_adapters(call_ai_json=provider, context_meter=lambda *a, **k: {"fits": True, "output_reserve": 3200},
        load_token_config=lambda: SimpleNamespace(lmstudio_base_url="http://127.0.0.1:1234/v1"),
        configured_ai_credentials=lambda *_: ("", "synthetic"))
    options = {**resolve({"model_context_version": 1}), "_run_id": "run-synthetic"}
    runner("orchestrator", case(), options, lambda: None, recorded.append)
    assert len(calls) == 1 and recorded[0]["context_manifest"]["metric_contract"]["version"] == 1
