"""停止済みコピーから入力を再構築し、本文を表示せず配送を検証する。"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import sqlite3
import sys
from types import SimpleNamespace

ROOT = Path(os.environ.get("GURUMOJI_TEST_SOURCE_ROOT", Path.cwd())).resolve()
sys.path.insert(0, str(ROOT / "src"))
from verify_obussql_malatang_io import configure_app, install_guard, save_json


def reconstruct(database):
    from gurumoji.analysis_orchestration import AnalysisOrchestrationService
    from gurumoji import method_experts
    service = object.__new__(AnalysisOrchestrationService)
    service.initial_builder = None
    cases = []
    with sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        run = json.loads(db.execute("SELECT state_json FROM orchestration_runs").fetchone()[0])
        initial = service._initial(db, run["initial_id"])
        source = [{k: row[k] for k in ("evidence_id", "utterance_id", "text", "speaker", "start", "end")}
                  for row in initial["evidence"] if not row["excluded"]]
        for (raw,) in db.execute("SELECT state_json FROM orchestration_tasks WHERE run_id=?", (run["run_id"],)):
            task = json.loads(raw)
            if task.get("error") != "context_budget_exceeded":
                continue
            context = service._context(db, run, task)
            brief = None
            if task["role"] == "interpretation":
                brief = method_experts.ai_context(initial["analysis"].get("experts"),
                    step_ids=run["config"].get("expert_step_ids"))
            context["expert_knowledge"] = method_experts.orchestration_context(stage=task["phase"], brief=brief)
            context["resources_origin"] = {"initial_id": run["initial_id"], "run_id": run["run_id"]}
            options = {**copy.deepcopy(run["config"]), **run["config"]["roles"][task["role"]],
                "timeout_seconds": run["config"]["call_timeout_seconds"], "_run_id": run["run_id"],
                "_reference_evidence": [{k: row[k] for k in ("evidence_id", "utterance_id")} for row in source]}
            if task["role"] in {"core", "orchestrator"}:
                options["_source_evidence"] = source
            cases.append((task["role"], context, options))
    return run["run_id"], source, cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / "output/validation/obussql-update-20261109/io-standard/data/library.sqlite3")
    parser.add_argument("--destination", type=Path, default=ROOT / "output/validation/obussql-context-20261109")
    parser.add_argument("--infer", action="store_true", help="再構築した停止タスク2件を実モデルへ送る")
    args = parser.parse_args()
    args.destination.mkdir(parents=True, exist_ok=True)
    denied = install_guard()
    from gurumoji.services import model_context, maf_dev_bridge
    from gurumoji.services.analysis_orchestration_adapters import make_orchestration_adapters, ADAPTER_VERSION
    from gurumoji.analysis_core import AnalysisContractError
    app = configure_app(args.destination / "app") if args.infer else None
    run_id, source, cases = reconstruct(args.database)
    report = {"basis": "reconstructed_from_stopped_snapshot", "inference_calls": 0, "cases": []}
    packets = []
    class MeasurementOnly(Exception):
        pass
    for role, context, options in cases:
        observations = []
        manifests, calls = [], []
        reply_checks = {}
        def save_reply(role, reply):
            if not args.infer:
                return
            save_json(args.destination / (role + "-response-private.json"), reply)
            from gurumoji.analysis_orchestration import AnalysisOrchestrationService
            from gurumoji.analysis_core import fingerprint
            service = object.__new__(AnalysisOrchestrationService)
            manifest = [m["context_manifest"] for m in manifests if "context_manifest" in m][-1]
            task = {**copy.deepcopy(context["task"]), "context_manifest": manifest,
                    "context_manifest_hash": fingerprint(manifest)}
            with sqlite3.connect(args.database.resolve().as_uri() + "?mode=ro", uri=True) as db:
                db.row_factory = sqlite3.Row
                run = json.loads(db.execute("SELECT state_json FROM orchestration_runs WHERE run_id=?", (run_id,)).fetchone()[0])
                try:
                    service._validate_result(db, run, task, reply)
                except AnalysisContractError as exc:
                    reply_checks["contract_error"] = exc.code
                else:
                    reply_checks["contract_valid"] = True
            reply_checks.update(nonempty_summary=bool(reply.get("summary")), claim_count=len(reply.get("claims", [])))
        def meter(model, base, system, user, schema, **kwargs):
            budget = model_context.measure_local_context(model, base, system, user, schema, **kwargs)
            observations.append({"system": system, "user": user, "schema": schema,
                                 "data_messages": kwargs.get("data_messages"), "budget": budget})
            return budget
        def provider(*arguments, **keywords):
            calls.append({"system": arguments[3], "user": arguments[4], "schema": arguments[6],
                          "data_messages": keywords.get("data_messages")})
            if not args.infer:
                raise MeasurementOnly()
            report["inference_calls"] += 1
            save_json(args.destination / (role + "-request-private.json"), calls[-1])
            save_json(args.destination / "progress.json", {"phase": "model_call", "role": role, "calls": report["inference_calls"]})
            return app.call_orchestration_ai_json(*arguments, **keywords)
        _, runner = make_orchestration_adapters(call_ai_json=provider,
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url="http://127.0.0.1:1234/v1"),
            configured_ai_credentials=lambda *_: ("", options["model"]), context_meter=meter,
            evidence_selector=maf_dev_bridge.select_evidence)
        options["adapter_version"] = ADAPTER_VERSION
        try:
            maf_dev_bridge.drive(run_id, lambda: True, lambda: source,
                lambda: save_reply(role, runner(role, context, options, lambda: None, manifests.append)))
        except AnalysisContractError as exc:
            error = exc.code
        except MeasurementOnly:
            error = None
        else:
            error = None
        if not observations:
            report["cases"].append({"role": role, "error": error, "meter_called": False})
            continue
        packet = {**observations[-1], "role": role}
        packets.append({"role": role, **packet})
        manifest_records = [m["context_manifest"] for m in manifests if "context_manifest" in m]
        item = {"role": role, "error": error, "measurement_count": len(observations),
                "dispatch_count": len(calls), "budget": manifest_records[-1]["budget"] if manifest_records else packet["budget"]}
        if calls:
            manifest = manifest_records[-1]
            restored = model_context.restored_reference_context(calls[-1]["user"], calls[-1]["data_messages"])
            item["provided_evidence_count"] = len(manifest["provided_evidence_ids"])
            item["restored_evidence_count"] = len(restored.get("raw_evidence", []))
            item["actual_user_hash_matches"] = manifest["user_sha256"] == model_context.digest(calls[-1]["user"])
            save_json(args.destination / (role + "-manifest.json"), manifest)
            save_json(args.destination / (role + "-context-private.json"), restored)
        item["reply_checks"] = reply_checks
        report["cases"].append(item)
        save_json(args.destination / "measurement.json", report)
    report["guard_violations"] = denied
    report["status"] = "passed" if (len(report["cases"]) == 2 and not denied
        and all(c.get("error") is None and c.get("budget", {}).get("fits")
                and (not args.infer or c["reply_checks"].get("contract_valid")) for c in report["cases"])) else "partial_pass"
    save_json(args.destination / "packets-private.json", packets)
    save_json(args.destination / "measurement.json", report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
