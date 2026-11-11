"""保持した合成試験DBの入力予算を、推論を実行せず再計測する。"""
import argparse
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import tempfile
from types import SimpleNamespace

from runtime_isolation import configure_environment, protect_runtime

parser = argparse.ArgumentParser()
parser.add_argument("database", type=Path)
parser.add_argument("--role", choices=("failed", "orchestrator"), default="failed")
args = parser.parse_args()
os.environ.update(MOJIOKOSI_OBUSSQL_ENABLED="1", MOJIOKOSI_MAF_DEV_ENABLED="1")


class Ready(Exception):
    pass


with tempfile.TemporaryDirectory(prefix="gurumoji-maf-probe-") as directory:
    configure_environment(directory)
    protect_runtime(protected=(Path.cwd() / "runtime",))
    target = Path(directory) / "data" / "library.sqlite3"
    with closing(sqlite3.connect(f"file:{args.database.resolve().as_posix()}?mode=ro", uri=True)) as src, closing(sqlite3.connect(target)) as dst:
        src.backup(dst)
    derived = args.database.with_name(args.database.stem + "-derived.sqlite3")
    if derived.exists():
        with closing(sqlite3.connect(f"file:{derived.resolve().as_posix()}?mode=ro", uri=True)) as src, closing(sqlite3.connect(target.parent / "analysis-derived.sqlite3")) as dst:
            src.backup(dst)
    import app
    from gurumoji.analysis_core import AnalysisContractError
    from gurumoji.services import maf_dev_bridge as bridge, model_context
    from gurumoji.services.analysis_orchestration_adapters import ADAPTER_VERSION, make_orchestration_adapters
    from gurumoji import method_experts

    service = app.analysis_orchestration_service()
    service.schedule = False
    with service._db() as db:
        state = json.loads(db.execute("SELECT state_json FROM orchestration_runs ORDER BY rowid DESC LIMIT 1").fetchone()[0])
        service.adapter_version = state["config"]["adapter_version"]
        tasks = service._tasks(db, state["run_id"])
        task = next(task for task in reversed(tasks) if task["status"] == "failed")
        if args.role == "orchestrator":
            state.update(status="running", deadline=None, stop_reason="")
            service._write_run(db, state)
            pending = service._pending_result_assessments(db, state)
            domain = service._result_domain(db, pending[0])
            batch = [rid for rid in pending if service._result_domain(db, rid) == domain][:20]
            task = service._register(db, state, {"role": "orchestrator", "method_id": "result-review-v1",
                "question": "担当分野の保存結果を評価して具体的な所見と限界を報告する",
                "scope": {"domain": domain, "result_ids": batch}}, phase="specialist_review", automatic=True)
        context = service._context(db, state, task)
        snapshot = service._initial(db, state["initial_id"])
    context["expert_knowledge"] = method_experts.orchestration_context(stage=task["phase"])
    context["resources_origin"] = {"initial_id": state["initial_id"], "run_id": state["run_id"]}
    options = {**state["config"], **state["config"]["roles"][task["role"]],
        "adapter_version": ADAPTER_VERSION + ":" + bridge.DRIVER_VERSION, "_run_id": state["run_id"],
        "timeout_seconds": state["config"]["call_timeout_seconds"], "deadline": None,
        "_source_evidence": [{key: row[key] for key in ("evidence_id", "utterance_id", "text", "speaker", "start", "end")}
                             for row in snapshot["evidence"] if not row["excluded"]]}
    options["_reference_evidence"] = [{key: row[key] for key in ("evidence_id", "utterance_id")}
                                      for row in options["_source_evidence"]]
    model = options["model"]
    def meter(*values, **kwargs):
        budget = model_context.measure_local_context(*values, **kwargs)
        packet = model_context.restored_reference_context(values[3], kwargs.get("data_messages"))
        print(json.dumps({"budget": budget, "system_chars": len(values[2]),
            "fields": {key: len(json.dumps(value, ensure_ascii=False)) for key, value in packet.items()}}, ensure_ascii=False))
        return budget
    def provider(*values, **kwargs):
        raise Ready()
    _, runner = make_orchestration_adapters(call_ai_json=provider,
        load_token_config=lambda: SimpleNamespace(lmstudio_base_url="http://127.0.0.1:1234/v1"),
        configured_ai_credentials=lambda *_: ("", model), evidence_selector=bridge.select_evidence,
        context_meter=meter, contract_version=options["adapter_version"])
    bridge._indexes[state["run_id"]] = bridge.FixedEvidenceIndex(state["run_id"], [row for row in snapshot["evidence"] if not row["excluded"]])
    try:
        runner(task["role"], context, options, lambda: None, lambda *_: None)
    except Ready:
        print("READY_WITHOUT_INFERENCE")
    except AnalysisContractError as exc:
        print(exc.code)
        raise SystemExit(1)
    finally:
        bridge._indexes.pop(state["run_id"], None)
