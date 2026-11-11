"""終了済みの統計codec試験を別プロセス・読取専用で再検証する。"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import xml.etree.ElementTree as ET

ROOT = Path(os.environ.get("GURUMOJI_TEST_SOURCE_ROOT", Path.cwd())).resolve()
sys.path.insert(0, str(ROOT / "src"))
from verify_obussql_malatang_io import install_guard, save_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=ROOT / "output/validation/obussql-metric-20261109")
    args = parser.parse_args()
    folder = args.destination.resolve()
    denied = install_guard()
    from gurumoji.analysis_core import fingerprint
    from gurumoji.services import metric_delivery
    full = json.loads((folder / "full-io-r2/result.json").read_text(encoding="utf-8"))
    replay = json.loads((folder / "replay-r4/result.json").read_text(encoding="utf-8"))
    calls = json.loads((folder / "full-io-r2/metric-codec-calls.json").read_text(encoding="utf-8"))
    post_io = json.loads((folder / "full-io-r2/post-io-result.json").read_text(encoding="utf-8"))
    database = folder / "full-io-r2/data/library.sqlite3"
    receipts = []
    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as db:
        db.row_factory = sqlite3.Row
        run = json.loads(db.execute("SELECT state_json FROM orchestration_runs WHERE run_id=?", (full["run_id"],)).fetchone()[0])
        tasks = [json.loads(r[0]) for r in db.execute("SELECT state_json FROM orchestration_tasks WHERE run_id=?", (run["run_id"],))]
        for task in tasks:
            if "metric_contract" not in task.get("context_manifest", {}):
                continue
            row = db.execute("SELECT raw_json,state_json FROM orchestration_results WHERE task_id=?", (task["task_id"],)).fetchone()
            raw, meta = json.loads(row[0]), json.loads(row[1])
            decoded = metric_delivery.validate(db, run, task, raw)
            decision = json.loads(db.execute("SELECT payload_json FROM orchestration_decisions WHERE result_id=?", (meta["result_id"],)).fetchone()[0])
            receipts.append({"task_id": task["task_id"], "task_status": task["status"],
                "raw_hash_matches": fingerprint(raw) == meta["raw_hash"],
                "receipt_matches_fresh_decoder": fingerprint(decoded) == fingerprint(meta["metric_validation"]),
                "decision_matches_fresh_decoder": fingerprint(decoded) == fingerprint(decision["metric_validation"]),
                "decoder_summary_used": decision["summary"] == decoded["answer"],
                "original_model_summary_preserved": decision["model_summary"] == raw["summary"],
                "source_results": len(decoded["source_result_ids"]), "items": len(decoded["items"]),
                "record_count": len(task["context_manifest"]["metric_contract"]["state"]["bindings"]),
                "operations": [item["operation"] for item in decoded["items"]]})
        events = [json.loads(r[0]) for r in db.execute("SELECT payload_json FROM orchestration_events WHERE run_id=?", (run["run_id"],))]
    provenance = json.loads((folder / "tested-sources.json").read_text(encoding="utf-8"))
    source_match = all(hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == sha for path, sha in provenance.items())
    tests = {}
    for filename in ("regression-release.xml", "upstream-metric.xml"):
        cases = list(ET.parse(folder / filename).iter("testcase"))
        tests[filename] = {"tests": len(cases), "failures": sum(c.find("failure") is not None or c.find("error") is not None for c in cases),
                           "skipped": sum(c.find("skipped") is not None for c in cases)}
    checks = {"codec_contract_enabled": run["config"]["metric_codec_version"] == 1,
        "operation_schema_contract": run["config"]["adapter_version"].startswith("core-handler-prompts-47-metric-operations"),
        "real_replay_passed": replay["status"] == "passed", "real_encoder_called": calls.get("MetricEncoder.encode.succeeded", 0) > 0,
        "real_decoder_called": calls.get("MetricDecoder.decode.succeeded", 0) > 0,
        "no_decoder_rejection_in_final_run": calls.get("MetricDecoder.decode.rejected", 0) == 0,
        "codec_receipts_present": bool(receipts), "receipts_valid_after_restart": all(
            r["task_status"] == "succeeded" and all(r[k] for k in ("raw_hash_matches", "receipt_matches_fresh_decoder",
            "decision_matches_fresh_decoder", "decoder_summary_used", "original_model_summary_preserved")) for r in receipts),
        "codec_validation_events": sum(e["type"] == "metric_codec_validated" for e in events) == len(receipts),
        "three_statistics_methods_completed": {t["method_id"] for t in tasks if t["role"] == "statistics" and t["status"] == "succeeded"}
            == {"participation", "conversation_dynamics", "label_frequency"},
        "stopped_ledger_and_separate_static_io_passed": post_io["status"] == "passed",
        "source_unchanged": full["source_unchanged"] and post_io["original_source_unchanged"],
        "protected_writes_zero": not full["protected_write_attempts"] and not denied,
        "tested_sources_match": source_match, "all_regression_passed": all(t["failures"] == 0 and t["skipped"] == 0 for t in tests.values())}
    feature_passed = all(checks.values())
    report = {"status": ("passed" if full["status"] == "passed" else "partial_pass") if feature_passed else "failed",
        "metric_integration_status": "passed" if feature_passed else "failed", "checks": checks, "codec_calls": calls, "fresh_codec_receipts": receipts,
        "analysis": full["analysis"], "actual_ai_calls": len(full["calls"]), "elapsed_seconds": full["elapsed_seconds"], "run_id": full["run_id"],
        "exports": post_io.get("exports", post_io.get("export_hashes", {})), "post_io_status": post_io["status"],
        "autonomous_saved": full["analysis"]["save_status"] == "saved", "regression": tests, "tested_sources": provenance,
        "obussql_commit": "07128acfe13c1162552f7928b5ab0e7c954fac1b", "scope": "isolated_authorized_real_data_copy",
        "research_status": "ai_draft_not_researcher_approved", "not_run": ["browser_gui", "audio_retranscription", "external_postgres_numeric_reader"],
        "committed": False, "pushed": False}
    save_json(folder / "verification.json", report)
    print(json.dumps({"status": report["status"], "checks": checks, "codec_calls": calls, "fresh_codec_receipts": receipts}, ensure_ascii=False))
    return 0 if feature_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
