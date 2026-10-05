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


def assess_run(state: dict) -> dict:
    """Successful startup or deterministic initial analysis alone cannot pass."""
    tasks = state.get("tasks", [])
    completed = [t for t in tasks if t.get("status") == "succeeded"]
    core = [t for t in completed if t.get("role") == "core"]
    failed = [t for t in tasks if t.get("status") in {"failed", "uncertain", "quarantined"}]
    checks = {
        "terminal_success": state.get("status") == "completed",
        "core_iteration_recorded": state.get("iteration", 0) > 0,
        "core_result_succeeded": bool(core),
        "core_iterations_repeated": len(core) >= 2,
        "minimum_core_iterations_satisfied": len(core) >= state.get("config", {}).get("min_iterations", 2),
        "ai_usage_recorded": state.get("usage", {}).get("measured_calls", 0) > 0,
        "no_failed_tasks": not failed,
    }
    return {"passed": all(checks.values()), "checks": checks,
            "analysis_completed": state.get("status") == "completed",
            "loop_execution_verified": all(value for key, value in checks.items() if key != "terminal_success")
                and (state.get("status") == "completed" or
                     (state.get("status") == "stopped" and state.get("stop_reason") == "human_review_required")),
            "core_iterations_started": state.get("iteration", 0),
            "core_iterations_succeeded": len(core),
            "succeeded_tasks_by_role": dict(Counter(t["role"] for t in completed)),
            "task_status_counts": dict(Counter(t.get("status", "unknown") for t in tasks)),
            "failed_task_count": len(failed)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=ROOT / "runtime/data/library.sqlite3")
    parser.add_argument("--item-id", help="Required if more than one interview is saved")
    parser.add_argument("--model", help="Loaded local model; does not alter app configuration")
    parser.add_argument("--max-iterations", type=int, default=None,
                        help="Optional hard cap; auto mode performs at least three valid Core decisions")
    parser.add_argument("--time-limit", type=int, default=600)
    parser.add_argument("--call-timeout", type=int, default=300)
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
            context = json.loads(positional[4])
            call = {"role": role, "iteration": context["task"].get("iteration"),
                    "evidence_count": len(context.get("raw_evidence", [])),
                    "coverage": {k: v for k, v in context.get("coverage", {}).items() if k != "evidence_index"},
                    "prompt_characters": len(positional[3]) + len(positional[4]), "status": "running"}
            report["calls"].append(call)
            print(f"AI {role}, iteration {call['iteration']}, evidence {call['evidence_count']}", flush=True)
            tick = time.monotonic()
            try:
                actual_arguments = list(positional)
                if args.no_think:
                    actual_arguments[3] += "\n/no_think"
                result = actual_call(*actual_arguments, **keywords)
                call["status"] = "returned"
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
                "max_calls": 16, "max_tasks": 32, "concurrency": 1, "request_id": uuid.uuid4().hex})
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
                report.update(assess_run(state))
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
