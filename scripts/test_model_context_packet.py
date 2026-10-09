"""One real, read-only packet regression from an isolated prior test database.

Never resumes its run or changes any saved result. A passed packet contract does
not qualify the model for scientific integration or full-source analysis.
"""
from __future__ import annotations
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--first-half", action="store_true", help="Evaluate the first child page; record the remaining owned rows as unexecuted")
    args = parser.parse_args()
    database = args.database.resolve()
    # Require a test copy, not the user's original library.
    if ROOT / "output" not in database.parents:
        parser.error("Use an isolated database below output")
    args.output = args.output.resolve()
    if ROOT / "output" not in args.output.parents or args.output.suffix.lower() != ".json" or args.output.exists():
        parser.error("Use a new JSON artifact below output")
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = {"tested_at": datetime.now(timezone.utc).isoformat(), "model": args.model,
              "task_id": args.task_id, "mock_ai": False, "database_before": before,
              "not_run": ["full-source analysis", "Core iterations", "Vault publication", "scientific qualification"]}
    with tempfile.TemporaryDirectory(prefix="gurumoji-packet-") as temporary:
        for env, name in (("MOJIOKOSI_DATA_DIR", "data"), ("MOJIOKOSI_OUTPUT_DIR", "output"), ("MOJIOKOSI_BACKUP_DIR", "backups")):
            os.environ[env] = str(Path(temporary) / name)
        sys.path.insert(0, str(ROOT / "src"))
        from gurumoji import app
        from gurumoji.analysis_core import fingerprint
        from gurumoji.analysis_orchestration import AnalysisOrchestrationService
        service = AnalysisOrchestrationService.__new__(AnalysisOrchestrationService)
        captured = []
        with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True)) as db:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA query_only=ON")
            task = json.loads(db.execute("SELECT state_json FROM orchestration_tasks WHERE task_id=?", (args.task_id,)).fetchone()[0])
            run = service._read_run(db, task["run_id"])
            context = service._context(db, run, task)
            if not (task["role"] in {"interpretation", "verification", "critic"} and task["phase"] == "initial_analysis"
                    or task["role"] == "core" and task["phase"] == "core"):
                parser.error("Use an initial specialist or integration task")
            if args.first_half:
                if task["phase"] != "initial_analysis":
                    parser.error("Only initial source pages can be split here")
                owned = task["intent"]["scope"]["owned_evidence_ids"]
                first = owned[:max(1, len(owned) // 2)]
                rows = [row for row in service._initial(db, run["initial_id"])["evidence"] if not row["excluded"]]
                ids = [row["evidence_id"] for row in rows]
                a, b = ids.index(first[0]), ids.index(first[-1]) + 1
                visible = ids[max(0, a - 1):min(len(ids), b + 1)]
                report["subset_of_task"] = {"owned_evidence_ids": first, "unexecuted_owned_evidence_ids": owned[len(first):]}
                task["task_id"] += "_packet_probe"
                task["intent"].update(evidence_ids=visible, scope={"owned_evidence_ids": first,
                    "boundary_evidence_ids": [ref for ref in visible if ref not in first], "split_from_task_id": args.task_id})
                context = service._context(db, run, task)
            options = app.prepare_orchestration({**run["config"], "model_context_version": 1,
                "provider": "lmstudio", "model": args.model,
                "roles": {role: {"provider": "lmstudio", "model": args.model} for role in ("core", "interpretation", "verification", "critic")}})
            options["timeout_seconds"] = 180
            if task["role"] == "core":
                options["_source_evidence"] = [{key: row[key] for key in ("evidence_id", "utterance_id", "text", "speaker", "start", "end")}
                    for row in service._initial(db, run["initial_id"])["evidence"] if not row["excluded"]]
            token_config = app.load_token_config()
            capability = app.lmstudio_reasoning_settings(token_config.lmstudio_base_url, token_config.lmstudio_api_key, args.model)
            reasoning = app.ai_client.local_effort_payload("off", capability)
            actual_post = app.ai_client.post_json
            def post(url, headers, payload, **keywords):
                return actual_post(url, headers, {**payload, **reasoning}, **keywords)
            report.update(run_id=run["run_id"], input_hash=run["input_hash"], adapter_version=options["adapter_version"],
                          source_evidence_count=len(service._initial(db, run["initial_id"])["evidence"]))
            try:
                with patch.object(app.ai_client, "post_json", side_effect=post):
                    raw = app.run_orchestration_agent(task["role"], context, options, lambda: None, captured.append)
                report["raw"] = raw
                manifest = next(row["context_manifest"] for row in captured if "context_manifest" in row)
                task.update(context_manifest=manifest, context_manifest_hash=fingerprint(manifest))
                run["config"] = options
                service._validate_result(db, run, task, raw)
                report["contract_passed"] = True
            except Exception as exc:
                report.update(contract_passed=False, error_code=getattr(exc, "code", type(exc).__name__))
        report["records"] = captured
    report["database_after"] = hashlib.sha256(database.read_bytes()).hexdigest()
    report["database_unchanged"] = report["database_after"] == before
    report["code_sha256"] = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in (
        "scripts/test_model_context_packet.py", "src/gurumoji/services/model_context.py",
        "src/gurumoji/services/analysis_orchestration_adapters.py", "src/gurumoji/analysis_orchestration.py")}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("contract_passed", "database_unchanged", "adapter_version")}, ensure_ascii=False))
    return 0 if report.get("contract_passed") and report["database_unchanged"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
