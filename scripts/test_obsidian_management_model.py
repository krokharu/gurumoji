"""Run a real loopback model through Core/Handler and isolated Obsidian management.

Only synthetic input is used. No mock AI, real Vault, or app settings are changed.
The caller owns loading/unloading the requested LM Studio model.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from urllib.parse import urlsplit
import urllib.request
import uuid

from test_saved_autonomous_analysis import assess_run, initialize_test_runtime

ROOT = Path(__file__).resolve().parents[1]
SYNTHETIC_TEXTS = [
    ("A", "この店を選んだ理由は、昼休みに近くて、注文から受け取りまで早かったからです。"),
    ("B", "私も近さは便利でしたが、初めての注文は選択肢が多くて時間がかかりました。"),
    ("A", "二回目は具材を決めていたので早かったです。価格は安いというより、量を調整できる点が良かったです。"),
    ("B", "量を増やすと予想より高くなりました。ただ、野菜を多く選べる点は気に入っています。"),
    ("A", "混む時間だと待つかもしれません。私が行ったのは午後二時で、待っている人はいませんでした。"),
    ("B", "私は正午に十分ほど待ちました。この二回だけでは、いつも早いとは言えないと思います。"),
]
DEFAULT_QUESTION = (
    "この合成会話6発話だけから、店の選択理由と評価の違いを根拠ID付きで整理し、"
    "速さ・価格・量についての反例と代替説明を検討してください。対象外への一般化は保留してください。"
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="google/gemma-4-12b")
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--time-limit", type=int, default=900)
    parser.add_argument("--call-timeout", type=int, default=240)
    parser.add_argument("--ground-evidence-ids", action="store_true",
                        help="Compare generation-time evidence ID enums; does not change the production adapter or adoption checks")
    parser.add_argument("--preserve-reviewed-view", action="store_true",
                        help="Compare an explicit Core instruction to preserve an unchanged reviewed view")
    parser.add_argument("--output", type=Path, default=ROOT / "output/obsidian-management-model")
    args = parser.parse_args()
    destination = args.output.resolve() / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8])
    destination.mkdir(parents=True, exist_ok=False)
    data = destination / "data"
    data.mkdir()
    os.environ.update(MOJIOKOSI_DATA_DIR=str(data), MOJIOKOSI_OUTPUT_DIR=str(destination / "media-output"),
                      MOJIOKOSI_BACKUP_DIR=str(destination / "backups"))
    sys.path.insert(0, str(ROOT / "src"))
    from gurumoji import app

    database = data / "library.sqlite3"
    initialize_test_runtime(app, database)
    segments = [{"id": f"synthetic-u{index}", "speaker": speaker, "text": text,
                 "start": index * 10, "end": index * 10 + 8, "annotation": {}, "excluded": False}
                for index, (speaker, text) in enumerate(SYNTHETIC_TEXTS, 1)]
    item_id = "synthetic-obsidian-management"
    app.upsert_library_item(item_id=item_id, source_name="Synthetic interview (no media)",
        output_dir=destination / "media-output", media_path=None, language="ja", segments=segments,
        speaker_names={"A": "合成参加者A", "B": "合成参加者B"}, files=[], outline=None,
        emotion_analysis=None, write_srt=False, write_json=True)
    source_before = app.archive_source_stamp(app.library_row(item_id))
    report = {"status": "failed", "tested_at": datetime.now(timezone.utc).isoformat(),
              "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "source_state": "uncommitted", "test_directory": str(destination),
              "model": args.model, "provider": "lmstudio", "mock_ai": False,
              "input": "synthetic", "utterance_count": len(segments), "question": args.question,
              "source_stamp_before": source_before, "publication_targets": [], "obsidian_management": True,
              "generation_evidence_id_enums": args.ground_evidence_ids,
              "preserve_reviewed_view_instruction": args.preserve_reviewed_view,
              "calls": [], "not_run": ["real interview", "audio processing", "browser UI", "Obsidian GUI",
                  "real Vault writes", "Linux/cloud runtime"]}
    paths = subprocess.check_output(["git", "-c", "core.quotepath=false", "diff", "--name-only"], cwd=ROOT,
                                    encoding="utf-8").splitlines()
    paths += ["scripts/test_obsidian_management_model.py", "src/gurumoji/services/obsidian_management.py"]
    report["source_sha256"] = {p: digest(ROOT / p) for p in sorted(set(paths)) if (ROOT / p).is_file()}
    report_path = destination / "result.json"
    (destination / "runner.py").write_bytes(Path(__file__).read_bytes())

    def save_report():
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    started = time.monotonic()
    original_call = app.call_orchestration_ai_json
    try:
        config = app.load_token_config()
        base = app.lmstudio_base_url(config.lmstudio_base_url)
        if urlsplit(base).hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise RuntimeError("Only a loopback LM Studio endpoint is allowed")
        headers = app.ai_client.lmstudio_headers(config.lmstudio_api_key)
        request = urllib.request.Request(base + "/models", headers=headers)
        with urllib.request.urlopen(request, timeout=10) as response:
            ids = [entry["id"] for entry in json.load(response).get("data", [])]
        if args.model not in ids:
            raise RuntimeError("The requested model is not available")
        native = urllib.request.Request(base.removesuffix("/v1") + "/api/v1/models", headers=headers)
        with urllib.request.urlopen(native, timeout=10) as response:
            models = json.load(response).get("models", [])
        report["loaded_model"] = next((instance for model in models for instance in model.get("loaded_instances", [])
                                       if instance.get("id") == args.model), None)
        if not report["loaded_model"]:
            raise RuntimeError("The requested model is not loaded; load it explicitly first")

        def observed_call(*positional, **keywords):
            if positional[0] != "lmstudio" or positional[2] != args.model:
                raise RuntimeError("An unexpected provider/model was requested")
            context = json.loads(positional[4])
            call = {"role": positional[5].removeprefix("analysis_orchestration_"),
                    "iteration": context["task"].get("iteration"),
                    "evidence_count": len(context.get("raw_evidence", [])),
                    "prompt_characters": len(positional[3]) + len(positional[4]),
                    "management_descriptor": context.get("management"), "status": "running"}
            report["calls"].append(call)
            save_report()
            print(f"AI {call['role']}, iteration {call['iteration']}, evidence {call['evidence_count']}", flush=True)
            tick = time.monotonic()
            try:
                actual_arguments = list(positional)
                if args.preserve_reviewed_view and call["role"] == "core":
                    actual_arguments[3] += (
                        "\n終了案のレビュー後、新しい根拠や必要な修正がなく現在の見解を維持すると判断した場合は、"
                        "context.current_viewのsummary・claims・alternatives・unresolvedを完全に同じ値で返してください。"
                        "言い換えや並べ替えだけでも新しい版になり再レビューが必要になります。"
                        "終了説明はstop.summaryに書き、見解を変える必要がない場合は現在の見解を言い換えないでください。"
                        "根拠や批判への対応として内容を修正する必要があれば、その修正は行い、再レビューを受けてください。"
                        "停止理由や最低回数を無視せず、Core自身が継続・終了を判断してください。"
                    )
                if args.ground_evidence_ids:
                    known = sorted({entry["evidence_id"] for entry in context.get("raw_evidence", [])}
                        | {entry["evidence_id"] for entry in context.get("coverage", {}).get("evidence_index", [])})
                    schema = copy.deepcopy(positional[6])
                    def bind_ids(node):
                        if isinstance(node, dict):
                            refs = node.get("properties", {}).get("evidence_ids")
                            if refs is not None:
                                if known:
                                    refs["items"] = {"type": "string", "enum": known}
                                else:
                                    refs["maxItems"] = 0
                            for child in node.values():
                                bind_ids(child)
                        elif isinstance(node, list):
                            for child in node:
                                bind_ids(child)
                    bind_ids(schema)
                    actual_arguments[6] = schema
                    call["generation_evidence_id_count"] = len(known)
                result = original_call(*actual_arguments, **keywords)
                call.update(status="returned", result_sha256=app.fingerprint(result) if hasattr(app, "fingerprint")
                            else hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest())
                return result
            except Exception as exc:
                call.update(status="failed", error_type=type(exc).__name__)
                if isinstance(exc, RuntimeError):
                    call["diagnostic"] = str(exc)[:500]
                raise
            finally:
                call["seconds"] = round(time.monotonic() - tick, 2)
                save_report()
                print(f"AI {call['role']}: {call['status']} ({call['seconds']}s)", flush=True)

        app.call_orchestration_ai_json = observed_call
        service = app.analysis_orchestration_service()
        service.schedule = False
        client = app.app.test_client()
        url = f"/api/library/{item_id}/analysis/orchestration"
        response = client.post(url, json={"provider": "lmstudio", "model": args.model,
            "provider_policy": "local_only", "cloud_consent": False, "publication_targets": [],
            "obsidian_management": True, "question": args.question, "stop_mode": "auto", "max_iterations": None,
            "time_limit_seconds": args.time_limit, "call_timeout_seconds": args.call_timeout,
            "context_evidence_limit": 6, "context_text_limit": 6000, "context_index_limit": 6,
            "max_calls": 16, "max_tasks": 32, "concurrency": 1, "request_id": uuid.uuid4().hex})
        report["start_http_status"] = response.status_code
        if response.status_code != 202:
            report["start_error"] = response.get_json()
            raise RuntimeError("Start was rejected")
        run_id = response.get_json()["run"]["run_id"]
        report["run_id"] = run_id
        print(f"Started {run_id}; synthetic DB: {database}", flush=True)
        service.run(run_id)
        response = client.get(url + "/" + run_id)
        report["status_http_status"] = response.status_code
        state = (response.get_json() or {}).get("run")
        if response.status_code != 200 or not isinstance(state, dict):
            raise RuntimeError("Saved state could not be read")
        (destination / "state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        report.update(assess_run(state))
        report.update(run_status=state["status"], stop_reason=state.get("stop_reason"), error=state.get("error"),
                      review_status=state.get("review_status"), usage=state.get("usage"),
                      publication=state.get("publication"), obsidian_management=state["obsidian_management"])
        calls_before_read = len(report["calls"])
        db_before = digest(database)
        registry = app.vault_registry()
        catalog_before = digest(registry.catalog_file)
        note_response = client.get(url + "/" + run_id + "/memory/note")
        report["note_http_status"] = note_response.status_code
        client.get(url + "/" + run_id)
        client.get(url + "/" + run_id + "/export.json")
        checks = report["checks"]
        checks.update(management_linked=state["obsidian_management"].get("status") == "linked",
            verified_note_download=note_response.status_code == 200,
            read_did_not_call_ai=len(report["calls"]) == calls_before_read,
            read_did_not_write_db=digest(database) == db_before,
            read_did_not_write_catalog=digest(registry.catalog_file) == catalog_before,
            fixed_package_saved=state.get("publication", {}).get("save_status") == "saved")
        catalog = registry.load()
        note_id = state["obsidian_management"].get("note_id")
        entity = catalog["entities"].get(note_id, {})
        checks["core_and_handler_references"] = bool(entity.get("decisions") and entity.get("tasks") and entity.get("results"))
        checks["saved_artifact_links"] = bool(entity.get("package", {}) and entity["package"].get("artifacts"))
        checks["four_vault_output_not_selected"] = state.get("publication", {}).get("publication_status") == "not_selected"
        report["management_reference_counts"] = entity.get("counts")
        entry = catalog["notes"].get(note_id)
        if entry:
            note_path = registry.root("orchestrator", catalog) / entry["path"]
            checks["note_inside_isolated_data"] = note_path.resolve().is_relative_to(data)
            report["management_note"] = {"note_id": note_id, "relative_path": note_path.relative_to(destination).as_posix(),
                                         "sha256": digest(note_path)}
        retry = client.post(url + "/" + run_id + "/memory/retry", json={})
        checks["management_retry_without_ai"] = retry.status_code == 200 and len(report["calls"]) == calls_before_read
        checks["independent_verification_is_blind"] = all(call["management_descriptor"] is None
            for call in report["calls"] if call["role"] == "verification")
        report["task_errors"] = [{key: task.get(key) for key in ("task_id", "role", "status", "error")}
                                 for task in state.get("tasks", []) if task.get("status") != "succeeded"]
        report["passed"] = all(checks.values())
        report["status"] = "passed" if report["passed"] else "failed"
    except Exception as exc:
        report["error_type"] = type(exc).__name__
        report["passed"] = False
    finally:
        app.call_orchestration_ai_json = original_call
        report["source_stamp_after"] = app.archive_source_stamp(app.library_row(item_id))
        report["source_unchanged"] = report["source_stamp_after"] == source_before
        if not report["source_unchanged"]:
            report["status"] = "failed"
            report["passed"] = False
        report["elapsed_seconds"] = round(time.monotonic() - started, 2)
        save_report()
        print(f"Result: {report['status']}; report: {report_path}", flush=True)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
