"""終了済み実AI台帳と、独立した静的分析の保存・公開・再読込を検証する。"""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import runpy
import sqlite3
import subprocess
import sys
import time
import zipfile


ROOT = Path(os.environ.get("GURUMOJI_TEST_SOURCE_ROOT", Path.cwd())).resolve()
HELPER_PATH = Path(__file__).with_name("verify_obussql_malatang_io.py")
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"


class VerificationError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def require(condition, code):
    if not condition:
        raise VerificationError(code)


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_terminal(database, item_id, run_id):
    # 実行中の台帳へ初期化処理を入れず、最初は読取専用で終了を確かめる。
    with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.execute("PRAGMA query_only=ON")
        row = db.execute("SELECT state_json FROM orchestration_runs WHERE item_id=? AND run_id=?", (item_id, run_id)).fetchone()
    require(row is not None, "autonomous_run_missing")
    state = json.loads(row[0])
    require(state["status"] in {"stopped", "completed"}, "autonomous_not_stopped_or_completed")
    return state


def install_no_ai(app, attempts):
    def denied(*_args, **_kwargs):
        attempts.append("model_call")
        raise VerificationError("model_call_denied")
    for name in ("call_orchestration_ai_json", "call_ai_json"):
        if hasattr(app, name):
            setattr(app, name, denied)
    from gurumoji.services.ai import client
    client.call_ai_json = denied


def semantic_hash(kind, content):
    if kind == "xlsx":
        from openpyxl import load_workbook
        book = load_workbook(io.BytesIO(content), read_only=True, data_only=False)
        try:
            values = [{"sheet": sheet.title, "rows": [[cell.value for cell in row] for row in sheet.iter_rows()]}
                      for sheet in book.worksheets]
        finally:
            book.close()
        return sha(encoded(values))
    if kind == "zip":
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            require(archive.testzip() is None, "fixed_zip_crc_failure")
            names = archive.namelist()
            require(len(names) == len(set(names)), "fixed_zip_duplicate_member")
            return sha(encoded({name: sha(archive.read(name)) for name in sorted(names)}))
    return sha(content)


def get(client, url):
    response = client.get(url, base_url="http://127.0.0.1")
    require(response.status_code == 200, "http_" + str(response.status_code))
    content = response.get_data()
    require(bool(content), "empty_export")
    return content


def export(client, url, path, kind):
    content = get(client, url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return {"path": str(path), "url": url, "bytes": len(content), "sha256": sha(content),
            "semantic_sha256": semantic_hash(kind, content), "kind": kind}


def compare_exports(client, entries):
    result = {}
    for name, entry in entries.items():
        stored = Path(entry["path"]).read_bytes()
        require(sha(stored) == entry["sha256"], "stored_export_hash_mismatch_" + name)
        current = get(client, entry["url"])
        semantic = semantic_hash(entry["kind"], current)
        require(semantic == entry["semantic_sha256"], "fresh_semantic_hash_mismatch_" + name)
        if entry["kind"] not in {"xlsx", "zip"}:
            require(sha(current) == entry["sha256"], "fresh_export_hash_mismatch_" + name)
        result[name] = {"stored_bytes_hash_verified": True, "http_semantic_hash_verified": True,
                        "http_bytes_identical": sha(current) == entry["sha256"], "semantic_sha256": semantic}
    return result


def verify_static(app, saved_id):
    store = app.analysis_archive_store()
    saved = store.get(saved_id)
    require(saved is not None and saved["kind"] == "text_analysis", "static_saved_run_missing")
    snapshot, result, manifest, _ = store.verified_package(saved_id)
    require(len(snapshot["segments"]) == 323, "fixed_snapshot_count")
    table = store.read_table(saved_id, "segments_all")
    require(table["row_count"] == 323, "fixed_table_count")
    require(len(result["analysis"]["segments"]) == 323, "fixed_result_count")
    public = store.public(saved)
    require(public["vault_outputs_complete"] is True, "static_four_vault_publication_incomplete")
    outcomes = public["publication_outcomes"]
    require(set(outcomes) == {"research", "input", "orchestrator", "visualization"}, "four_vault_outcomes_missing")
    require(all(value["status"] == "published" for value in outcomes.values()), "static_vault_not_published")
    return {"status": "passed", "saved_run_id": saved_id, "kind": saved["kind"],
            "snapshot_segments": len(snapshot["segments"]), "typed_table_rows": table["row_count"],
            "package_version": manifest.get("schema_version"), "package_hash": saved["fingerprint"],
            "vault_outcomes": {key: value["status"] for key, value in outcomes.items()}}


def autonomous_metadata(app, item_id, run_id, state):
    publication = app.analysis_orchestration_publication_service().status(item_id, run_id)
    require(state["status"] in {"stopped", "completed"}, "autonomous_terminal_changed")
    if state["status"] == "stopped":
        require(not publication.get("result_run_id") and publication.get("save_status") != "saved",
                "stopped_autonomous_must_not_be_saved_as_completed")
    return {"status": state["status"], "stop_reason": state.get("stop_reason"),
            "completed": state["status"] == "completed", "save_status": publication["save_status"],
            "publication_status": publication["publication_status"],
            "result_run_id": publication.get("result_run_id", ""),
            "human_approval_supplied": False, "model_reexecuted": False}


def run_full(app, helper, destination, run_id, state, report):
    item_id = helper["ITEM_ID"]
    client = app.app.test_client()
    base = f"/api/library/{item_id}/analysis/orchestration/{run_id}"
    report["autonomous"] = autonomous_metadata(app, item_id, run_id, state)
    ledger = app.analysis_orchestration_service().result(item_id, run_id)
    require(ledger["run"]["status"] == state["status"], "autonomous_ledger_status_mismatch")
    require(len(ledger["initial"]["snapshot"]["analysis"]["segments"]) == 323, "autonomous_fixed_segment_count")
    folder = destination / "exports/post-io"
    entries = {"autonomous_" + kind: export(client, base + "/export." + kind,
               folder / ("autonomous-history." + kind), kind) for kind in ("json", "md")}
    # 自律runとは独立した決定論的な固定分析を、既存HTTP経路から保存する。
    item = app.library_row(item_id)
    response = client.post(f"/api/library/{item_id}/analysis/runs", base_url="http://127.0.0.1",
        headers={"X-Gurumoji-Request": "1"}, json={"request_id": "post-io-static-" + run_id,
        "source_revision": int(item["revision_count"]), "analysis_revision": int(item["analysis_revision"])})
    require(response.status_code == 200, "static_save_http_" + str(response.status_code))
    saved_id = response.get_json()["run"]["id"]
    report["static_fixed_analysis"] = verify_static(app, saved_id)
    artifacts = app.analysis_archive_store().artifacts(saved_id)
    result_artifact = next((entry for entry in artifacts if entry["name"] == "result.json"), None)
    require(result_artifact is not None, "fixed_result_artifact_missing")
    fixed_urls = {"json": "/api/analysis/artifacts/" + result_artifact["id"],
                  "csv": f"/api/analysis/runs/{saved_id}/tables/segments_all.csv",
                  "xlsx": f"/api/analysis/runs/{saved_id}/export.xlsx",
                  "zip": f"/api/analysis/runs/{saved_id}/export.zip"}
    for kind, url in fixed_urls.items():
        entries["static_" + kind] = export(client, url, folder / ("fixed-analysis." + kind), kind)
    report["exports"] = entries
    report["obussql_preview"] = helper["preview"](app)
    manifest = {"run_id": run_id, "autonomous": report["autonomous"], "saved_run_id": saved_id, "exports": entries}
    helper["save_json"](destination / "post-io-manifest.json", manifest)
    child = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--mode", "fresh",
        "--destination", str(destination)], env={**os.environ, "GURUMOJI_TEST_SOURCE_ROOT": str(ROOT)},
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, check=False)
    # 子プロセスの本文・例外メッセージをログへ流さず、メタデータだけを読む。
    require(child.returncode == 0, "fresh_child_failed")
    fresh = json.loads((destination / "post-io-fresh-result.json").read_text(encoding="utf-8"))
    require(fresh.get("status") == "passed", "fresh_read_failed")
    report["fresh_read"] = fresh


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, default=ROOT / "output/validation/obussql-update-20261109/io-standard")
    parser.add_argument("--mode", choices=("full", "fresh"), default="full")
    args = parser.parse_args()
    destination = args.destination.resolve()
    require(destination.is_relative_to(ROOT / "output/validation"), "destination_outside_validation")
    require((destination / "data/library.sqlite3").is_file(), "existing_copy_database_required")
    helper = runpy.run_path(str(HELPER_PATH))
    denied_writes = helper["install_guard"]()
    attempts = []

    def no_network(event, _args):
        if event == "socket.connect":
            attempts.append("network_connect")
            raise VerificationError("network_denied")
    sys.addaudithook(no_network)
    report = {"status": "running", "mode": args.mode, "mock_ai": False, "model_calls_allowed": False,
              "human_approval_supplied": False, "started_at": datetime.now(timezone.utc).isoformat()}
    started = time.monotonic()
    result_path = destination / ("post-io-fresh-result.json" if args.mode == "fresh" else "post-io-result.json")
    original_hash = None
    try:
        original_hash = helper["digest"](helper["source_state"](ROOT / "runtime/data/library.sqlite3"))
        if args.mode == "fresh":
            manifest = json.loads((destination / "post-io-manifest.json").read_text(encoding="utf-8"))
            run_id = manifest["run_id"]
        else:
            run_id = json.loads((destination / "result.json").read_text(encoding="utf-8"))["run_id"]
        require(isinstance(run_id, str) and run_id.startswith("run_"), "run_id_missing")
        state = read_terminal(destination / "data/library.sqlite3", helper["ITEM_ID"], run_id)
        app = helper["configure_app"](destination)
        install_no_ai(app, attempts)
        report["run_id"] = run_id
        if args.mode == "fresh":
            report["autonomous"] = autonomous_metadata(app, helper["ITEM_ID"], run_id, state)
            require(report["autonomous"] == manifest["autonomous"], "fresh_autonomous_state_mismatch")
            report["static_fixed_analysis"] = verify_static(app, manifest["saved_run_id"])
            report["export_hashes"] = compare_exports(app.app.test_client(), manifest["exports"])
            report["obussql_preview"] = helper["preview"](app)
        else:
            run_full(app, helper, destination, run_id, state, report)
        report["status"] = "passed"
    except Exception as exc:
        report.update(status="failed", error_type=type(exc).__name__, reason_code=getattr(exc, "code", ""))
    finally:
        if original_hash is not None:
            report["original_source_unchanged"] = original_hash == helper["digest"](helper["source_state"](ROOT / "runtime/data/library.sqlite3"))
            if not report["original_source_unchanged"]:
                report["status"] = "failed"
        report.update(protected_write_attempts=denied_writes, forbidden_ai_or_network_attempts=attempts,
                      elapsed_seconds=round(time.monotonic() - started, 2), raw_values_logged=False,
                      hash_policy="JSON/MD/CSVはHTTP bytes一致。XLSX/ZIPは保存bytesと、再生成時の時刻情報を除く内容hashを照合。")
        if denied_writes or attempts:
            report["status"] = "failed"
        helper["save_json"](result_path, report)
        print(json.dumps({"status": report["status"], "mode": args.mode, "reason_code": report.get("reason_code", ""),
                          "report": str(result_path)}), flush=True)
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
