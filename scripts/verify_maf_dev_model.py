"""ロード済みローカルモデルと合成会話でMAF分析の終端・保存を検証する。"""
import json
from contextlib import closing
import os
import sqlite3
from pathlib import Path
import tempfile

from runtime_isolation import configure_environment, protect_runtime

os.environ.update(MOJIOKOSI_OBUSSQL_ENABLED="1", MOJIOKOSI_MAF_DEV_ENABLED="1")
temporary = tempfile.TemporaryDirectory(prefix="gurumoji-maf-real-")
configure_environment(temporary.name)
protect_runtime(protected=(Path.cwd() / "runtime",))

import lmstudio
import app
from gurumoji.services import maf_dev_bridge as bridge
from gurumoji.services import model_context
from gurumoji.services.analysis_orchestration_adapters import ADAPTER_VERSION, make_orchestration_adapters
from test_orchestration_publication import OrchestrationPublicationTests, TARGETS

fixture = OrchestrationPublicationTests("test_full_ledger_roundtrip_artifacts_and_four_writers")
fixture.setUp()
try:
    with lmstudio.Client(api_host="127.0.0.1:1234") as client:
        loaded = list(client.llm.list_loaded())
        if not loaded:
            raise RuntimeError("ロード済みモデルがありません。自動ロードは行いません。")
        desired = os.environ.get("MOJIOKOSI_MAF_TEST_MODEL")
        matches = [item for item in loaded if not desired or item.identifier == desired]
        if not matches:
            raise RuntimeError("指定モデルはロード済みではありません。")
        model = matches[0].identifier
    original_transport = app.call_orchestration_ai_json
    def transport(*args, **kwargs):
        try:
            result = original_transport(*args, **kwargs)
            print(json.dumps({"stage": args[5], "status": "returned"}), flush=True)
            return result
        except Exception as exc:
            print(json.dumps({"stage": args[5], "error_type": type(exc).__name__,
                              "detail": str(exc)[:1000]}, ensure_ascii=False), flush=True)
            raise
    app.call_orchestration_ai_json = transport
    def meter(*args, **kwargs):
        budget = model_context.measure_local_context(*args, **kwargs)
        if not budget["fits"]:
            packet = model_context.restored_reference_context(args[3], kwargs.get("data_messages"))
            print(json.dumps({"status": "context_budget_rejected", "budget": budget,
                "fields": {key: len(json.dumps(value, ensure_ascii=False)) for key, value in packet.items()}}, ensure_ascii=False), flush=True)
        return budget
    app._prepare_orchestration, app.run_orchestration_agent = make_orchestration_adapters(
        call_ai_json=lambda *args, **kwargs: app.call_orchestration_ai_json(*args, **kwargs),
        load_token_config=app.load_token_config, configured_ai_credentials=app.configured_ai_credentials,
        evidence_selector=bridge.select_evidence, context_meter=meter,
        contract_version=ADAPTER_VERSION + ":" + bridge.DRIVER_VERSION)
    fixture.runtime = app.analysis_orchestration_service()
    fixture.runtime.schedule = False
    fixture.publisher = app.analysis_orchestration_publication_service()
    payload = app.prepare_orchestration({"question": os.environ.get("MOJIOKOSI_MAF_TEST_QUESTION",
                       "この会話で比較や改善の基準として何が述べられているか、原文の根拠付きで比較する。"),
                       "model": model, "stop_mode": "auto", "max_iterations": 6,
                       "time_limit_seconds": int(os.environ.get("MOJIOKOSI_MAF_TEST_TIME_LIMIT", "1200")),
                       "call_timeout_seconds": int(os.environ.get("MOJIOKOSI_MAF_TEST_TIMEOUT", "120")), "local_reasoning": "off",
                       "model_context_version": 1, "context_reference_version": 1,
                       "analysis_interval_version": 1, "analysis_interval_seconds": 300,
                       "context_evidence_limit": 24, "context_text_limit": 6000,
                       "concurrency": 1, "max_calls": 160, "max_tasks": 400, "publication_targets": TARGETS})
    run = fixture.runtime.start("content", payload)
    print(json.dumps({"model": model, "run_id": run["run_id"], "status": "started"}), flush=True)
    fixture.runtime.run(run["run_id"])
    final = fixture.runtime.status("content", run["run_id"])
    exported = fixture.runtime.result("content", run["run_id"])
    publication = fixture.publisher.status("content", run["run_id"])
    report = {"model": model, "run": final, "publication": publication, "ledger": exported}
    target = Path("output/validation/maf-dev-real-model-20261102-" + model.replace("/", "_") + "-" + run["run_id"] + ".json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if final["status"] != "completed":
        if not app.DATABASE_FILE.resolve().is_relative_to(Path(tempfile.gettempdir()).resolve()):
            raise RuntimeError("試験DBが一時領域外です。")
        for source, suffix in ((app.DATABASE_FILE, ""), (app.DATABASE_FILE.parent / "analysis-derived.sqlite3", "-derived")):
            if source.is_file():
                destination = target.with_name(target.stem + suffix + ".sqlite3")
                with closing(sqlite3.connect(f"file:{source.as_posix()}?mode=ro", uri=True)) as src, closing(sqlite3.connect(destination)) as dst:
                    src.backup(dst)
    print(json.dumps({"status": final["status"], "stop_reason": final.get("stop_reason"),
                      "error": final.get("error"), "calls_started": final.get("calls_started"),
                      "tasks": [{k: t.get(k) for k in ("role", "phase", "status", "error")} for t in final["tasks"]],
                      "publication": publication.get("publication_status"), "report": str(target)}, ensure_ascii=False), flush=True)
    if (final["status"] != "completed" or final.get("completion_callback_status") != "completed"
            or publication.get("save_status") != "saved"
            or publication.get("publication_status") != "published"):
        raise SystemExit(1)
finally:
    fixture.doCleanups()
    temporary.cleanup()
