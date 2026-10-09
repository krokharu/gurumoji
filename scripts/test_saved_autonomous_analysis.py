"""Exercise the real autonomous analysis API on an isolated saved-data copy.

Uses the configured loopback LM Studio model. Never falls back to mock results.
The source SQLite database is opened read-only; publication to Vaults is disabled.
"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import uuid
from unittest.mock import patch
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def initialize_test_runtime(app, database: Path) -> None:
    if Path(app.DATABASE_FILE).resolve() != database.resolve():
        raise RuntimeError("Isolation failed before runtime initialization")
    # Mirror normal startup on the backup only, including the fixed-result
    # catalog and publication audit tables. Do not repair source provenance.
    app.initialize_library(repair_provenance=False)


def source_stamp(database: Path, item_id: str) -> str:
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        row = db.execute("SELECT segments_json,revision_count,analysis_revision FROM library_items WHERE id=?", (item_id,)).fetchone()
    if row is None:
        raise ValueError("Saved interview not found")
    return hashlib.sha256(json.dumps(list(row), ensure_ascii=False).encode()).hexdigest()


def assess_run(state: dict, decisions: list | None = None) -> dict:
    """Successful startup or deterministic initial analysis alone cannot pass."""
    tasks = state.get("tasks", [])
    completed = [t for t in tasks if t.get("status") == "succeeded"]
    core = [t for t in completed if t.get("role") == "core" and t.get("phase") != "initial_routing"]
    adopted_core_count = state.get("completed_core_iterations", len(core))
    failed = [t for t in tasks if t.get("status") in {"failed", "uncertain", "quarantined"}]
    checks = {
        "terminal_success": state.get("status") == "completed",
        "core_iteration_recorded": state.get("iteration", 0) > 0,
        "core_result_succeeded": bool(core),
        "core_iterations_repeated": adopted_core_count >= 2,
        "minimum_core_iterations_satisfied": adopted_core_count >= state.get("config", {}).get("min_iterations", 2),
        "ai_usage_recorded": state.get("usage", {}).get("measured_calls", 0) > 0,
        "no_failed_tasks": not failed,
    }
    if state.get("config", {}).get("specialist_orchestration_version"):
        reviews = [d for d in decisions or [] if d.get("role") == "orchestrator"]
        assessed = [a["result_id"] for d in reviews for a in d.get("result_assessments", [])]
        expected = {r["result_id"] for r in state.get("results", [])
                    if r.get("role") not in {"core", "orchestrator"} and r.get("validation_status") == "valid" and not r.get("stale")}
        checks.pop("core_iterations_repeated")
        checks["minimum_core_iterations_satisfied"] = adopted_core_count >= max(1, state["config"].get("min_iterations", 0))
        checks["specialist_results_reviewed"] = bool(expected and reviews and set(assessed) == expected and len(assessed) == len(set(assessed)))
        checks["core_does_not_assess_individual_results"] = bool(decisions) and all(
            not any(d.get(k) for k in ("result_assessments", "critique_responses", "label_decisions"))
            for d in decisions or [] if d.get("role", "core") == "core")
        checks["independent_label_review_saved"] = any(t.get("phase") == "label_review" and t.get("role") == "critic" for t in completed)
    catalog = state.get("initial_label_catalog") or {}
    if state.get("config", {}).get("initial_label_definitions_version"):
        design = next((t for t in completed if t.get("role") == "interpretation"
                       and t.get("method_id") == "label-design-v1" and t.get("result_id") == catalog.get("result_id")), None)
        checks["initial_specialist_labels_saved"] = bool(design and catalog.get("created_by") == "interpretation"
                                                        and catalog.get("status") == "ai_draft" and catalog.get("definitions"))
        first_core = next((t for t in tasks if t.get("role") == "core" and t.get("phase") != "initial_routing"), None)
        checks["initial_labels_before_core"] = bool(design and first_core and tasks.index(design) < tasks.index(first_core)
                                                   and design.get("ended_at") and first_core.get("started_at")
                                                   and design["ended_at"] <= first_core["started_at"])
    if state.get("config", {}).get("initial_specialist_analysis_version"):
        initial_tasks = [t for t in tasks if t.get("phase") == "initial_analysis"]
        routing = next((t for t in completed if t.get("phase") == "initial_routing"), None)
        expected = {("interpretation", "agent-v1"), ("verification", "agent-v1"), ("critic", "agent-v1"),
                    ("statistics", "participation"), ("statistics", "conversation_dynamics"), ("statistics", "label_frequency")}
        checks["all_initial_specialists_reported"] = bool(state.get("initial_analysis_report", {}).get("all_roles_reported")
            and (state.get("config", {}).get("model_context_version") == 1 or len(initial_tasks) == 6)
            and {(t.get("role"), t.get("method_id")) for t in initial_tasks} == expected
            and all(t.get("status") == "succeeded" for t in initial_tasks))
        checks["core_routes_after_reports_before_scale_design"] = bool(routing and design
            and routing.get("started_at") and routing.get("ended_at") and design.get("started_at")
            and all(t.get("ended_at") and t["ended_at"] <= routing["started_at"] for t in initial_tasks)
            and routing["ended_at"] <= design["started_at"])
    return {"passed": all(checks.values()), "checks": checks,
            "analysis_completed": state.get("status") == "completed",
            "loop_execution_verified": all(value for key, value in checks.items() if key != "terminal_success")
                and (state.get("status") == "completed" or
                     (state.get("status") == "stopped" and state.get("stop_reason") == "human_review_required")),
            "core_iterations_started": state.get("iteration", 0),
            "core_iterations_succeeded": len(core),
            "core_iterations_adopted": adopted_core_count,
            "initial_label_definition_count": len(catalog.get("definitions", [])),
            "succeeded_tasks_by_role": dict(Counter(t["role"] for t in completed)),
            "task_status_counts": dict(Counter(t.get("status", "unknown") for t in tasks)),
            "failed_task_count": len(failed)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / "runtime/data/library.sqlite3")
    parser.add_argument("--item-id", help="Required if more than one interview is saved")
    parser.add_argument("--model", help="Loaded local model; does not alter app configuration")
    parser.add_argument("--max-iterations", type=int, default=None,
                        help="Optional hard cap for Core integration rounds; specialist reviews are counted separately")
    parser.add_argument("--time-limit", type=int, default=600)
    parser.add_argument("--call-timeout", type=int, default=300)
    parser.add_argument("--model-context", action="store_true", help="Evaluate versioned token budgets and full-source paging")
    parser.add_argument("--max-calls", type=int, default=16)
    parser.add_argument("--max-tasks", type=int, default=32)
    parser.add_argument("--evidence-limit", type=int, default=24,
                        help="Evidence rows per AI call; full source stays in the fixed snapshot")
    parser.add_argument("--text-limit", type=int, default=6000)
    parser.add_argument("--index-limit", type=int, default=24,
                        help="Evidence IDs per call; 0 retains the complete index")
    parser.add_argument("--no-think", action="store_true",
                        help="Disable reasoning through the local model's advertised capability")
    parser.add_argument("--question", default="マーラータンについて、この会話で語られた選択理由・評価・懸念を根拠発話ID付きで分析し、反例と代替説明を検討してください。未確認の話者役割や研究対象全体への一般化は保留してください。")
    parser.add_argument("--output", type=Path, default=ROOT / "output/malatang-autonomous")
    args = parser.parse_args()
    source = args.database.resolve()
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        items = db.execute("SELECT id FROM library_items ORDER BY id").fetchall()
    item_id = args.item_id
    if item_id is None:
        if len(items) != 1:
            parser.error("Specify --item-id when the database does not contain exactly one interview")
        item_id = items[0][0]
    before = source_stamp(source, item_id)
    destination = args.output.resolve() / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8])
    destination.mkdir(parents=True, exist_ok=False)
    data = destination / "data"
    data.mkdir()
    copied_db = data / "library.sqlite3"
    with closing(sqlite3.connect(source.as_uri() + "?mode=ro", uri=True)) as original, closing(sqlite3.connect(copied_db)) as copy:
        original.execute("PRAGMA query_only=ON")
        original.backup(copy)
        # Media and old output files are not exercised by this analysis test.
        copy.execute("UPDATE library_items SET output_dir=?,media_path=NULL,files_json='[]'", (str(destination / "media-output"),))
        copy.commit()
    if source == copied_db.resolve():
        raise RuntimeError("Isolation failed")
    os.environ["MOJIOKOSI_DATA_DIR"] = str(data)
    os.environ["MOJIOKOSI_OUTPUT_DIR"] = str(destination / "media-output")
    os.environ["MOJIOKOSI_BACKUP_DIR"] = str(destination / "backups")
    sys.path.insert(0, str(ROOT / "src"))
    from gurumoji import app
    assert app.DATABASE_FILE.resolve() == copied_db.resolve()
    initialize_test_runtime(app, copied_db)
    report = {"status": "failed", "item_id": item_id,
              "tested_at": datetime.now(timezone.utc).isoformat(),
              "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "source_stamp_before": before, "test_directory": str(destination),
              "provider": "lmstudio", "mock_ai": False, "publication_targets": [],
              "no_think_requested": args.no_think,
              "calls": [], "not_run": ["audio transcription", "diarization", "browser UI", "Vault publication"]}
    report["code_sha256"] = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in (
        "scripts/test_saved_autonomous_analysis.py", "src/gurumoji/analysis_core.py",
        "src/gurumoji/analysis_orchestration.py", "src/gurumoji/services/analysis_orchestration_adapters.py",
        "src/gurumoji/services/model_context.py", "src/gurumoji/method_experts.py",
        "src/gurumoji/knowledge_builder/expert_knowledge_context.py", "src/gurumoji/services/ai/client.py", "src/gurumoji/app.py")}
    # Retain exactly the tested code bytes before any later local edits.
    code_archive = destination / "code-v25"
    for name, expected_hash in report["code_sha256"].items():
        data = (ROOT / name).read_bytes()
        if hashlib.sha256(data).hexdigest() != expected_hash:
            raise RuntimeError("Code changed before test archival")
        archived = code_archive / name
        archived.parent.mkdir(parents=True, exist_ok=True)
        archived.write_bytes(data)
    (code_archive / "sha256.json").write_text(json.dumps(report["code_sha256"], indent=2), encoding="utf-8")
    started = time.monotonic()
    try:
        config = app.load_token_config()
        base = app.lmstudio_base_url(config.lmstudio_base_url)
        headers = app.ai_client.lmstudio_headers(config.lmstudio_api_key)
        request = urllib.request.Request(base + "/models", headers=headers)
        with urllib.request.urlopen(request, timeout=10) as response:
            models = [m["id"] for m in json.load(response).get("data", [])]
        model = args.model or config.lmstudio_model
        if not model or model not in models:
            raise ValueError("Configured local model is not available")
        if args.no_think and not model.startswith("qwen/qwen3-"):
            raise ValueError("--no-think is only supported by this test for Qwen3 models")
        reasoning_payload = {}
        if args.no_think:
            capability = app.lmstudio_reasoning_settings(base, config.lmstudio_api_key, model)
            if "off" not in capability.get("allowed_options", []):
                raise ValueError("Loaded model does not advertise a reasoning-off option")
            reasoning_payload = app.ai_client.local_effort_payload("off", capability)
        report["reasoning_payload"] = reasoning_payload
        report["model"] = model
        # Optional native discovery records the actual loaded context, not only
        # the theoretical model maximum. Older servers may lack this endpoint.
        try:
            native = urllib.request.Request(base.removesuffix("/v1") + "/api/v1/models", headers=headers)
            with urllib.request.urlopen(native, timeout=10) as response:
                info = json.load(response)
            for entry in info.get("models", []):
                for instance in entry.get("loaded_instances", []):
                    if instance.get("id") == model:
                        report["model_context_length"] = instance.get("config", {}).get("context_length")
        except (OSError, ValueError):
            report["model_context_length"] = None
        service = app.analysis_orchestration_service()
        service.schedule = False
        client = app.app.test_client()
        actual_call = app.call_orchestration_ai_json
        actual_post = app.ai_client.post_json

        def configured_post(url, headers, payload, **keywords):
            return actual_post(url, headers, {**payload, **reasoning_payload}, **keywords)

        def observed_call(*positional, **keywords):
            if positional[0] != "lmstudio":
                raise RuntimeError("External provider is prohibited in this test")
            role = positional[5].removeprefix("analysis_orchestration_")
            from gurumoji.services.model_context import restored_reference_context
            context = restored_reference_context(positional[4], keywords.get("data_messages"))
            call = {"role": role, "iteration": context["task"].get("iteration"),
                    "phase": context["task"].get("phase"),
                    "task_id": context["task"]["task_id"], "method_id": context["task"].get("method_id"),
                    "evidence_count": len(context.get("raw_evidence", [])),
                    "coverage": {k: v for k, v in context.get("coverage", {}).items() if k != "evidence_index"},
                    "prompt_characters": len(positional[3]) + len(positional[4]) + sum(len(row) for row in keywords.get("data_messages", [])),
                    "instruction_characters": len(positional[3]) + len(positional[4]),
                    "data_message_count": len(keywords.get("data_messages", [])), "status": "running"}
            report["calls"].append(call)
            print(f"AI {role}, iteration {call['iteration']}, evidence {call['evidence_count']}", flush=True)
            tick = time.monotonic()
            try:
                actual_arguments = list(positional)
                if args.no_think and not args.model_context:
                    actual_arguments[3] += "\n/no_think"
                result = actual_call(*actual_arguments, **keywords)
                call["status"] = "returned"
                call["label_definition_count"] = len(result.get("label_definitions", []))
                call["label_requirement_count"] = len(result.get("label_requirements", []))
                return result
            except Exception as exc:
                call.update(status="failed", error_type=type(exc).__name__)
                if isinstance(exc, RuntimeError):
                    # Production transport errors contain sanitized diagnostics.
                    call["diagnostic"] = str(exc)[:500]
                    print(call["diagnostic"], flush=True)
                raise
            finally:
                call["seconds"] = round(time.monotonic() - tick, 2)
                print(f"AI {role}: {call['status']} ({call['seconds']}s)", flush=True)

        def prohibit_vault(*_args, **_kwargs):
            raise RuntimeError("Vault publication is prohibited in this test")

        with patch.object(app, "call_orchestration_ai_json", side_effect=observed_call), \
             patch.object(app.ai_client, "post_json", side_effect=configured_post), \
             patch.object(app.AnalysisStore, "_publish_generated_vaults", side_effect=prohibit_vault), \
             patch.object(app.AnalysisStore, "_publish_research", side_effect=prohibit_vault):
            url = f"/api/library/{item_id}/analysis/orchestration"
            response = client.post(url, json={"provider": "lmstudio", "model": model,
                "provider_policy": "local_only", "cloud_consent": False, "publication_targets": [],
                "question": args.question, "stop_mode": "auto", "max_iterations": args.max_iterations,
                "time_limit_seconds": args.time_limit, "call_timeout_seconds": args.call_timeout,
                  "context_evidence_limit": args.evidence_limit, "context_text_limit": args.text_limit,
                  "context_index_limit": args.index_limit,
                "model_context_version": int(args.model_context),
                "max_calls": args.max_calls, "max_tasks": args.max_tasks, "concurrency": 1, "request_id": uuid.uuid4().hex})
            report["start_http_status"] = response.status_code
            if response.status_code != 202:
                report["reason_code"] = (response.get_json() or {}).get("reason_code", "start_rejected")
            else:
                run_id = response.get_json()["run"]["run_id"]
                report["run_id"] = run_id
                print(f"Started {run_id}; isolated DB: {copied_db}", flush=True)
                service.run(run_id)
                status_response = client.get(url + "/" + run_id)
                report["status_http_status"] = status_response.status_code
                status_body = status_response.get_json() or {}
                if status_response.status_code != 200 or not isinstance(status_body.get("run"), dict):
                    raise RuntimeError("The saved-run status endpoint did not return a run")
                state = status_body["run"]
                report.update(assess_run(state, service.result(item_id, run_id)["decisions"]))
                report.update(run_status=state["status"], stop_reason=state.get("stop_reason"),
                              review_status=state.get("review_status"), usage=state.get("usage"),
                              publication=state.get("publication"))
                # Keep the complete fixed evidence and ledger in the isolated DB.
                count = len(report["calls"])
                for _ in range(2):
                    client.get(url + "/" + run_id)
                report["polling_did_not_call_ai"] = len(report["calls"]) == count
                report["status"] = "passed" if report["passed"] and report["polling_did_not_call_ai"] else "failed"
    except Exception as exc:
        report["error_type"] = type(exc).__name__
    finally:
        report["source_stamp_after"] = source_stamp(source, item_id)
        report["source_unchanged"] = report["source_stamp_after"] == before
        if not report["source_unchanged"]:
            report["status"] = "failed"
        report["elapsed_seconds"] = round(time.monotonic() - started, 2)
        path = destination / "result.json"
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Result: {report['status']}; report: {path}", flush=True)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
