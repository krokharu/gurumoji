"""実会話のコピーでObusSQL・MAF分析と入出力を検証する。"""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import traceback
from urllib.parse import unquote, urlsplit
import uuid


ROOT = Path(os.environ.get("GURUMOJI_TEST_SOURCE_ROOT", Path.cwd())).resolve()
ITEM_ID = "bb5555800e4248d7a401fc97c85c6882"
MODEL = "google/gemma-4-12b-qat"
TARGETS = ["input", "orchestrator", "visualization"]
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
logging.disable(logging.CRITICAL)


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def save_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def require(condition, code):
    if not condition:
        raise VerificationError(code)


class VerificationError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def install_guard():
    """原本runtimeと資格情報を保護し、外部通信も拒否する。"""
    runtime = (ROOT / "runtime").resolve()
    credentials = {(ROOT / "config/tokens.json").resolve(), (ROOT / ".env").resolve()}
    denied = []

    def path_for(value):
        if not isinstance(value, (str, bytes, os.PathLike)):
            return None
        value = os.fsdecode(value)
        if value.startswith("file:"):
            parsed = urlsplit(value)
            value = unquote(parsed.path)
            if os.name == "nt" and value.startswith("/") and len(value) > 2 and value[2] == ":":
                value = value[1:]
        try:
            return Path(value).resolve()
        except (OSError, ValueError):
            return None

    def protected(value):
        path = path_for(value)
        return path is not None and (path == runtime or path.is_relative_to(runtime) or path in credentials)

    def reject(event):
        denied.append(event)
        raise VerificationError("protected_runtime_write")

    def hook(event, args):
        if event == "open":
            path, mode, flags = args
            resolved = path_for(path)
            if resolved in credentials:
                raise VerificationError("original_credentials_read_denied")
            writing = (isinstance(mode, str) and any(char in mode for char in "wax+")) or bool(
                isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            if writing and protected(path):
                reject(event)
        elif event == "sqlite3.connect" and args and protected(args[0]):
            if not (str(args[0]).startswith("file:") and "mode=ro" in str(args[0])):
                reject(event)
        elif event in {"os.remove", "os.rmdir", "os.mkdir", "os.chmod", "os.utime", "os.truncate"}:
            if args and protected(args[0]):
                reject(event)
        elif event in {"os.rename", "os.link", "os.symlink"}:
            if any(protected(value) for value in args[:2]):
                reject(event)
        elif event == "socket.connect" and len(args) > 1:
            address = args[1]
            # Windowsのasyncioは内部通知にもloopbackの一時ポートを使う。
            if isinstance(address, tuple) and address[0] not in {"127.0.0.1", "::1"}:
                raise VerificationError("nonlocal_network_denied")
    sys.addaudithook(hook)
    return denied


def configure_app(destination, *, imported=False):
    """設定はローカルモデルだけを注入し、実tokens.jsonを読まない。"""
    data = destination / ("import-data" if imported else "data")
    output = destination / ("roundtrip-output" if imported else "media-output")
    os.environ.update(MOJIOKOSI_DATA_DIR=str(data), MOJIOKOSI_OUTPUT_DIR=str(output),
        MOJIOKOSI_BACKUP_DIR=str(destination / "backups"), MOJIOKOSI_OBUSSQL_ENABLED="1",
        MOJIOKOSI_MAF_DEV_ENABLED="1", MOJIOKOSI_ALLOW_REMOTE="0", MOJIOKOSI_RUNTIME="local")
    sys.path.insert(0, str(ROOT / "src"))
    from gurumoji import app
    app.UPLOAD_DIRECTORY = destination / "uploads"
    app.INSTANCE_LOCK_FILE = app.UPLOAD_DIRECTORY / ".gurumoji.instance.lock"
    app.TOKEN_FILE = destination / "tokens-test-only.json"
    config = app.TokenConfig(lmstudio_base_url="http://127.0.0.1:1234/v1", lmstudio_model=MODEL)
    app.load_token_config = lambda *args, **kwargs: config
    app.app.config.update(TESTING=True)
    require(app.DATABASE_FILE.resolve() == (data / "library.sqlite3").resolve(), "database_isolation_failed")
    require(not data.resolve().is_relative_to((ROOT / "runtime").resolve()), "runtime_destination_rejected")
    return app


def source_state(database):
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as connection:
        connection.execute("PRAGMA query_only=ON")
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM library_items WHERE id=?", (ITEM_ID,)).fetchone()
        require(row is not None, "source_missing")
        return dict(row)


def text_rows(segments):
    return [{key: row.get(key) for key in ("id", "text", "speaker", "start", "end")} for row in segments]


def http_get(client, url):
    response = client.get(url, base_url="http://127.0.0.1")
    require(response.status_code == 200, "http_" + str(response.status_code))
    return response


def write_export(client, url, path):
    response = http_get(client, url)
    content = response.get_data()
    require(bool(content), "empty_export")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return {"bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(), "path": str(path)}


def static_exports(app, destination):
    """モデル実行の前に、全発話の静的集計と4形式を実出力する。"""
    import csv
    from openpyxl import load_workbook
    client = app.app.test_client()
    folder = destination / "exports/static"
    base = f"/api/library/{ITEM_ID}/analysis/export"
    exports = {kind: write_export(client, base + "." + kind + ("?dataset=segments_all" if kind == "csv" else ""),
                                folder / ("analysis." + kind)) for kind in ("json", "md", "csv", "xlsx")}
    analysis = json.loads((folder / "analysis.json").read_bytes())
    require(len(analysis["segments"]) == 323, "static_segment_count")
    csv_rows = list(csv.DictReader(io.StringIO((folder / "analysis.csv").read_text(encoding="utf-8-sig"))))
    require(len(csv_rows) == 323, "static_csv_row_count")
    book = load_workbook(folder / "analysis.xlsx", read_only=True, data_only=True)
    sheets = list(book.sheetnames)
    require(bool(sheets), "static_workbook_empty")
    book.close()
    return {"status": "passed", "segment_count": len(analysis["segments"]), "segment_csv_rows": len(csv_rows),
            "xlsx_sheets": sheets, "exports": exports}


def import_roundtrip(app, destination, original):
    """正規の出力writerと取込サービスを別DBで往復させる。"""
    segments = json.loads(original["segments_json"])
    paths = app.write_outputs(source_name=original["source_name"], output_dir=destination / "roundtrip-output",
        segments=segments, language=original["language"], speaker_names=json.loads(original["speaker_names_json"]),
        speaker_profiles=json.loads(original["speaker_profiles_json"]), session_profile=json.loads(original["session_profile_json"]),
        outline=json.loads(original["outline_json"]) if original["outline_json"] else None,
        emotion_analysis=None, write_json=True, write_srt=True)
    expected = {"rows_hash": digest(text_rows(segments)), "segment_count": len(segments),
                "output_files": [{"name": path.name, "bytes": path.stat().st_size} for path in paths]}
    save_json(destination / "roundtrip-expected.json", expected)
    child(destination, "import")
    result = json.loads((destination / "import-result.json").read_text(encoding="utf-8"))
    require(result.get("status") == "passed", "import_roundtrip_failed")
    return result


def child(destination, mode):
    result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--mode", mode,
        "--destination", str(destination)], env={**os.environ, "GURUMOJI_TEST_SOURCE_ROOT": str(ROOT)},
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120, check=False)
    # 子プロセスの出力本文は保存・表示せず、結果メタデータだけを読む。
    require(result.returncode == 0, mode + "_child_failed")


def import_child(app, destination):
    app.initialize_library(repair_provenance=False)
    app.import_existing_outputs()
    with app.database_connection() as db:
        rows = db.execute("SELECT segments_json FROM library_items").fetchall()
        require(len(rows) == 1, "roundtrip_item_count")
        actual = text_rows(json.loads(rows[0][0]))
        provenance = db.execute("SELECT COUNT(*) FROM output_import_provenance").fetchone()[0]
    expected = json.loads((destination / "roundtrip-expected.json").read_text(encoding="utf-8"))
    require(digest(actual) == expected["rows_hash"] and len(actual) == 323, "roundtrip_content_mismatch")
    require(provenance > 0, "roundtrip_provenance_missing")
    return {"status": "passed", "segments": len(actual), "rows_hash": digest(actual), "provenance_count": provenance}


def preview(app):
    client = app.app.test_client()
    notes = []
    offset = 0
    while offset is not None:
        listing = http_get(client, f"/api/obsidian/obussql/notes?offset={offset}").get_json()
        notes.extend(listing["notes"])
        offset = listing["next_offset"]
    selected = []
    for kind in TARGETS:
        candidate = next((note for note in notes if note["vault"] == kind), None)
        require(candidate is not None, "managed_note_missing_" + kind)
        selected.append({key: candidate[key] for key in ("note_id", "sha256")})
    response = client.post("/api/obsidian/obussql/preview", base_url="http://127.0.0.1",
        json={"notes": selected, "query": "分析"}, headers={"X-Gurumoji-Request": "1"})
    require(response.status_code == 200, "obussql_preview_http_" + str(response.status_code))
    body = response.get_json()
    require(body.get("stage") == "read_only_preview" and len(body.get("sources", [])) == 3, "preview_sources_missing")
    require(bool(body["context"].get("selection")), "preview_selection_empty")
    return {"status": "passed", "managed_notes": len(notes), "selected_notes": selected,
            "source_count": len(body["sources"]), "measurement": body["measurement"]}


def verify_saved(app, destination, manifest):
    """再解析せず、固定保存物を新しいプロセスで読み出す。"""
    from openpyxl import load_workbook
    run_id, saved_id = manifest["run_id"], manifest["saved_run_id"]
    client = app.app.test_client()
    base = f"/api/library/{ITEM_ID}/analysis/orchestration/{run_id}"
    service = app.analysis_orchestration_service()
    status = service.status(ITEM_ID, run_id)
    require(status["status"] == "completed", "fresh_status_not_completed")
    store = app.analysis_archive_store()
    _, result, package, _ = store.verified_package(saved_id)
    require(result["parameters"]["autonomous_run_id"] == run_id, "fresh_run_link_mismatch")
    hashes = {}
    for kind in ("json", "md"):
        content = http_get(client, base + "/export." + kind).get_data()
        hashes[kind] = hashlib.sha256(content).hexdigest()
        require(hashes[kind] == manifest["exports"][kind]["sha256"], "fresh_ledger_hash_mismatch_" + kind)
    table = store.read_table(saved_id, "autonomous_summary")
    require(table["row_count"] == 1, "fresh_summary_count")
    csv_content = http_get(client, f"/api/analysis/runs/{saved_id}/tables/autonomous_summary.csv").get_data()
    require(hashlib.sha256(csv_content).hexdigest() == manifest["exports"]["csv"]["sha256"], "fresh_csv_hash_mismatch")
    workbook = http_get(client, f"/api/analysis/runs/{saved_id}/export.xlsx").get_data()
    book = load_workbook(io.BytesIO(workbook), read_only=True, data_only=True)
    require("autonomous_summary" in book.sheetnames, "fresh_workbook_missing_summary")
    book.close()
    publication = app.analysis_orchestration_publication_service().status(ITEM_ID, run_id)
    require(publication["publication_status"] == "published" and publication["save_status"] == "saved", "fresh_publication_failed")
    require(all(value["status"] == "published" for value in publication["outcomes"].values()), "fresh_vault_outcome_failed")
    return {"status": "passed", "ledger_hashes": hashes, "verified_package": True,
            "typed_table_rows": table["row_count"], "vault_outcomes": {key: value["status"] for key, value in publication["outcomes"].items()},
            "obussql_preview": preview(app)}


def run_analysis(app, destination, report, update):
    from gurumoji.services import maf_dev_bridge
    from gurumoji.services.model_context import restored_reference_context
    require(maf_dev_bridge.status().get("execution_ready") is True, "maf_unavailable")
    calls = report["calls"] = []
    actual = app.call_orchestration_ai_json
    read_ids = set()
    actual_select = maf_dev_bridge.select_evidence

    def observed_select(*args, **kwargs):
        rows = actual_select(*args, **kwargs)
        read_ids.update(row["evidence_id"] for row in rows)
        return rows

    def observed(*args, **kwargs):
        require(args[0] == "lmstudio" and args[2] == MODEL, "unexpected_provider_or_model")
        call = {"schema": args[5], "status": "running", "started": datetime.now(timezone.utc).isoformat()}
        if str(args[5]).startswith("analysis_orchestration_"):
            context = restored_reference_context(args[4], kwargs.get("data_messages"))
            task = context.get("task", {})
            call.update(role=task.get("role"), phase=task.get("phase"), task_id=task.get("task_id"),
                        evidence_count=len(context.get("raw_evidence", [])))
        calls.append(call)
        update("model_call_started")
        tick = time.monotonic()
        try:
            result = actual(*args, **kwargs)
            call["status"] = "returned"
            return result
        except Exception as exc:
            call.update(status="failed", error_type=type(exc).__name__, reason_code=getattr(exc, "code", ""))
            raise
        finally:
            call["seconds"] = round(time.monotonic() - tick, 2)
            update("model_call_finished")
    app.call_orchestration_ai_json = observed
    maf_dev_bridge.select_evidence = observed_select
    service = app.analysis_orchestration_service()
    service.schedule = False
    client = app.app.test_client()
    url = f"/api/library/{ITEM_ID}/analysis/orchestration"
    response = client.post(url, base_url="http://127.0.0.1", headers={"X-Gurumoji-Request": "1"}, json={
        "provider": "lmstudio", "model": MODEL, "provider_policy": "local_only", "cloud_consent": False,
        "question": "マーラータン（会話内表記のマラタンを含む）について、全発話を対象に選択理由・評価・懸念を根拠発話ID付きで分析する。反例と代替説明を検討し、未確認の話者役割と研究対象全体への一般化は保留する。",
        "stop_mode": "auto", "max_iterations": 6, "time_limit_seconds": 3600, "call_timeout_seconds": 180,
        "model_context_version": 1, "context_reference_version": 1, "local_reasoning": "off",
        "analysis_interval_version": 0,
        "context_evidence_limit": 120, "context_text_limit": 16000, "context_index_limit": 120,
        "concurrency": 1, "max_calls": 160, "max_tasks": 400,
        "publication_targets": TARGETS, "request_id": uuid.uuid4().hex})
    report["start_http_status"] = response.status_code
    if response.status_code != 202:
        report["start_reason_code"] = (response.get_json() or {}).get("reason_code", "")
        raise VerificationError("analysis_start_rejected")
    run_id = response.get_json()["run"]["run_id"]
    report["run_id"] = run_id
    update("model_analysis_started")
    service.run(run_id)
    state = service.status(ITEM_ID, run_id)
    ledger = service.result(ITEM_ID, run_id)
    publication = app.analysis_orchestration_publication_service().status(ITEM_ID, run_id)
    succeeded = [task for task in state["tasks"] if task["status"] == "succeeded"]
    initial = [task for task in state["tasks"] if task.get("phase") == "initial_analysis"]
    expected = {("interpretation", "agent-v1"), ("verification", "agent-v1"), ("critic", "agent-v1"),
                ("statistics", "participation"), ("statistics", "conversation_dynamics"), ("statistics", "label_frequency")}
    checks = {"terminal_completed": state["status"] == "completed",
        "callback_completed": state.get("completion_callback_status") == "completed",
        "all_fixed_utterances": len(ledger["initial"]["snapshot"]["analysis"]["segments"]) == 323,
        "initial_specialists": {(task["role"], task.get("method_id")) for task in initial} == expected
            and all(task["status"] == "succeeded" for task in initial),
        "scale_design": bool(state.get("initial_label_catalog", {}).get("definitions")) and any(
            task.get("method_id") == "label-design-v1" for task in succeeded),
        "independent_scale_review": any(task.get("phase") == "label_review" for task in succeeded),
        "core_integration": any(task["role"] == "core" and task.get("phase") != "initial_routing" for task in succeeded),
        "obussql_fixed_evidence_used": bool(read_ids),
        "real_ai_usage": state.get("usage", {}).get("measured_calls", 0) > 0,
        "saved": publication.get("save_status") == "saved", "published": publication.get("publication_status") == "published"}
    report["analysis"] = {"status": state["status"], "stop_reason": state.get("stop_reason"), "checks": checks,
        "calls_started": state.get("calls_started"), "task_status_counts": dict(Counter(task["status"] for task in state["tasks"])),
        "succeeded_tasks_by_role": dict(Counter(task["role"] for task in succeeded)),
        "obussql_read_evidence_count": len(read_ids), "failed_tasks": [{key: task.get(key) for key in
            ("role", "phase", "status", "error")} for task in state["tasks"] if task["status"] in {"failed", "quarantined", "uncertain"}],
        "save_status": publication.get("save_status"), "publication_status": publication.get("publication_status")}
    update("model_analysis_finished")
    require(all(checks.values()), "analysis_acceptance_failed")
    saved_id = publication["result_run_id"]
    folder = destination / "exports/autonomous"
    exports = {kind: write_export(client, url + "/" + run_id + "/export." + kind, folder / ("analysis-history." + kind))
               for kind in ("json", "md")}
    exports["csv"] = write_export(client, f"/api/analysis/runs/{saved_id}/tables/autonomous_summary.csv", folder / "autonomous_summary.csv")
    exports["xlsx"] = write_export(client, f"/api/analysis/runs/{saved_id}/export.xlsx", folder / "analysis.xlsx")
    exports["zip"] = write_export(client, f"/api/analysis/runs/{saved_id}/export.zip", folder / "analysis-package.zip")
    manifest = {"run_id": run_id, "saved_run_id": saved_id, "exports": exports}
    save_json(destination / "execution.json", manifest)
    report["fixed_exports"] = exports
    report["obussql_preview"] = preview(app)
    count = len(calls)
    for _ in range(2):
        http_get(client, url + "/" + run_id)
    require(len(calls) == count, "read_called_model")
    update("exports_and_preview_finished")
    child(destination, "fresh")
    fresh = json.loads((destination / "fresh-result.json").read_text(encoding="utf-8"))
    require(fresh.get("status") == "passed", "fresh_read_failed")
    report["fresh_read"] = fresh


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=ROOT / "output/validation/obussql-update-20261109/io")
    parser.add_argument("--mode", choices=("full", "static", "fresh", "import"), default="full")
    args = parser.parse_args()
    destination = args.destination.resolve()
    require(destination != ROOT and not destination.is_relative_to(ROOT / "runtime"), "invalid_destination")
    destination.mkdir(parents=True, exist_ok=True)
    denied = install_guard()
    report = {"status": "running", "mode": args.mode, "model": MODEL, "mock_ai": False,
              "source_root": str(ROOT), "destination": str(destination), "stages": []}
    started = time.monotonic()
    output = destination / ({"fresh": "fresh-result.json", "import": "import-result.json"}.get(args.mode, "result.json"))

    def update(stage):
        report["stages"].append({"stage": stage, "elapsed_seconds": round(time.monotonic() - started, 2)})
        save_json(output, report)
        print(json.dumps({"stage": stage, "calls": len(report.get("calls", []))}), flush=True)

    original = None
    source = ROOT / "runtime/data/library.sqlite3"
    try:
        if args.mode == "import":
            app = configure_app(destination, imported=True)
            report.update(import_child(app, destination))
        elif args.mode == "fresh":
            app = configure_app(destination)
            manifest = json.loads((destination / "execution.json").read_text(encoding="utf-8"))
            def no_model(*_args, **_kwargs):
                raise VerificationError("fresh_model_call_denied")
            app.call_orchestration_ai_json = no_model
            report.update(verify_saved(app, destination, manifest))
        else:
            original = source_state(source)
            report["source_hash_before"] = digest(original)
            segments = json.loads(original["segments_json"])
            require(len(segments) == 323, "unexpected_original_segment_count")
            report["source"] = {"item_id": ITEM_ID, "segments": len(segments),
                "speakers": len({row.get("speaker") for row in segments}),
                "text_characters": sum(len(row.get("text", "")) for row in segments),
                "rows_hash": digest(text_rows(segments))}
            data = destination / "data"
            data.mkdir(exist_ok=True)
            database = data / "library.sqlite3"
            require(not database.exists(), "test_database_already_exists")
            with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as src, closing(sqlite3.connect(database)) as dst:
                src.execute("PRAGMA query_only=ON")
                src.backup(dst)
                dst.execute("UPDATE library_items SET output_dir=?,media_path=NULL,files_json='[]'", (str(destination / "media-output"),))
                dst.commit()
            update("source_copied")
            app = configure_app(destination)
            app.initialize_library(repair_provenance=False)
            require(digest(text_rows(app.row_segments(app.library_row(ITEM_ID)))) == report["source"]["rows_hash"], "copied_segments_changed")
            report["import_roundtrip"] = import_roundtrip(app, destination, original)
            update("import_roundtrip_finished")
            report["static_analysis"] = static_exports(app, destination)
            update("static_exports_finished")
            if args.mode == "full":
                run_analysis(app, destination, report, update)
            report["status"] = "passed"
    except Exception as exc:
        report.update(status="failed", error_type=type(exc).__name__, reason_code=getattr(exc, "code", ""))
        report["error_frames"] = [{"file": Path(frame.filename).name, "line": frame.lineno,
                                   "function": frame.name} for frame in traceback.extract_tb(exc.__traceback__)]
    finally:
        if original is not None:
            report["source_hash_after"] = digest(source_state(source))
            report["source_unchanged"] = report["source_hash_after"] == report["source_hash_before"]
            if not report["source_unchanged"]:
                report["status"] = "failed"
        report["protected_write_attempts"] = denied
        if denied:
            report["status"] = "failed"
        report["elapsed_seconds"] = round(time.monotonic() - started, 2)
        save_json(output, report)
        print(json.dumps({"status": report["status"], "reason_code": report.get("reason_code", ""), "report": str(output)}), flush=True)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
