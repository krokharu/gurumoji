"""実統計の専用codec呼出しを計数し、実モデルと全体経路を検証する。"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
import json
import os
from pathlib import Path
import runpy
import sqlite3
import sys
import uuid

ROOT = Path(os.environ.get("GURUMOJI_TEST_SOURCE_ROOT", Path.cwd())).resolve()
sys.path.insert(0, str(ROOT / "src"))
from verify_obussql_malatang_io import configure_app, install_guard, save_json, MODEL


def counters():
    from obusql_agent.metric_codec import MetricEncoder, MetricDecoder
    counts = Counter()
    for cls, method, label in ((MetricEncoder, "encode", "MetricEncoder.encode"), (MetricDecoder, "decode", "MetricDecoder.decode")):
        original = getattr(cls, method)
        def wrapped(self, *args, _original=original, _label=label, **kwargs):
            counts[_label + ".started"] += 1
            try:
                result = _original(self, *args, **kwargs)
            except Exception:
                counts[_label + ".rejected"] += 1
                raise
            counts[_label + ".succeeded"] += 1
            return result
        setattr(cls, method, wrapped)
    return counts


def replay(destination, counts):
    denied = install_guard()
    app = configure_app(destination / "app")
    from gurumoji.services import metric_delivery, model_context
    from gurumoji.services.analysis_orchestration_adapters import make_orchestration_adapters
    source = ROOT / "output/validation/obussql-context-20261109/full-io/data/library.sqlite3"
    with sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        run = json.loads(db.execute("SELECT state_json FROM orchestration_runs").fetchone()[0])
        tasks = [json.loads(r[0]) for r in db.execute("SELECT state_json FROM orchestration_tasks")]
        task = copy.deepcopy(next(t for t in tasks if t["role"] == "orchestrator" and t["intent"]["scope"]["domain"] == "statistics"))
        task.update(task_id="task_" + uuid.uuid4().hex, phase="specialist_review", status="replay")
        task.pop("context_manifest", None)
        task.pop("context_manifest_hash", None)
        results = []
        for raw, meta in db.execute("SELECT raw_json,state_json FROM orchestration_results"):
            metadata = json.loads(meta)
            if metadata["role"] == "statistics":
                results.append({**metadata, "content": json.loads(raw)})
        context = {"task": task, "question": "提示された全ての統計元から最低1件ずつ参照を選び、数値と母数・欠測を確認してください。",
            "data_version": run["input_hash"], "annotation_version": task["annotation_version"],
            "resources_origin": {"run_id": run["run_id"], "initial_id": run["initial_id"]},
            "initial": {"initial_id": run["initial_id"], "available_sections": []}, "review_domain": "statistics",
            "results": results, "raw_evidence": [], "coverage": {}, "issues": [], "label_proposals": [],
            "dependency_task_ids": [r["task_id"] for r in results],
            "iteration_review": {"pending_result_ids": [r["result_id"] for r in results], "omitted_pending_result_count": 0}}
        manifests, usage, requests = [], [], []
        def record(item):
            (manifests if "context_manifest" in item else usage).append(item)
        def provider(*args, **kwargs):
            request = {"system": args[3], "user": args[4], "schema": args[6], "data_messages": kwargs.get("data_messages")}
            requests.append(request)
            save_json(destination / "request-private.json", request)
            return app.call_orchestration_ai_json(*args, **kwargs)
        resolve, runner = make_orchestration_adapters(call_ai_json=provider, load_token_config=app.load_token_config,
            configured_ai_credentials=lambda *_: ("", MODEL))
        options = {**resolve({"provider": "lmstudio", "model": MODEL, "provider_policy": "local_only",
            "model_context_version": 1, "context_reference_version": 1, "local_reasoning": "off"}),
            "_run_id": run["run_id"], "timeout_seconds": 240}
        response = runner("orchestrator", context, options, lambda: None, record)
        save_json(destination / "response-private.json", response)
        task["context_manifest"] = manifests[-1]["context_manifest"]
        run["config"]["metric_codec_version"] = 1
        decoded = metric_delivery.validate(db, run, task, response)
        save_json(destination / "decoded-private.json", decoded)
        save_json(destination / "manifest-private.json", task["context_manifest"])
        wire = model_context.restored_reference_context(requests[0]["user"], requests[0]["data_messages"])
        checks = {"one_real_model_call": len(requests) == 1, "decoder_answered": decoded["status"] == "answered",
            "all_three_sources": len(decoded["source_result_ids"]) == 3,
            "claims_not_invented": not response.get("claims"),
            "raw_stat_tables_not_delivered": all("datasets" not in r["content"] for r in wire["results"]),
            "host_binding_not_delivered": "query_hash" not in json.dumps(wire["metric_context"]),
            "fits_loaded_model": task["context_manifest"]["budget"]["fits"], "guard_violations_zero": not denied,
            "actual_encoder_succeeded": counts["MetricEncoder.encode.succeeded"] >= 1,
            "actual_decoder_succeeded": counts["MetricDecoder.decode.succeeded"] >= 1}
        report = {"status": "passed" if all(checks.values()) else "failed", "checks": checks,
            "basis": "readonly_replay_of_authorized_real_statistics", "model": MODEL, "codec_calls": dict(counts),
            "metric_records": len(task["context_manifest"]["metric_contract"]["state"]["bindings"]),
            "decoded_items": [{k: v for k, v in item.items() if k != "source_records"} for item in decoded["items"]],
            "budget": task["context_manifest"]["budget"], "guard_violations": denied}
        save_json(destination / "result.json", report)
        print(json.dumps(report, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    args.destination = args.destination.resolve()
    args.destination.mkdir(parents=True, exist_ok=True)
    counts = counters()
    try:
        if args.full:
            script = Path(__file__).with_name("verify_obussql_malatang_io.py")
            sys.argv = [str(script), "--destination", str(args.destination), "--mode", "full"]
            runpy.run_path(str(script), run_name="__main__")
        else:
            replay(args.destination, counts)
    finally:
        save_json(args.destination / "metric-codec-calls.json", dict(counts))


if __name__ == "__main__":
    main()
