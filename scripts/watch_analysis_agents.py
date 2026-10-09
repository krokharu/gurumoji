"""Read saved Gurumoji analysis roles in an Orca terminal; never execute analysis."""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gurumoji.analysis_core import AnalysisContractError
from gurumoji.services.analysis_history import AnalysisHistoryService


@contextmanager
def readonly_connection(database):
    db = sqlite3.connect(Path(database).resolve().as_uri() + "?mode=ro", uri=True, timeout=2)
    try:
        db.execute("PRAGMA query_only=ON")
        yield db
    finally:
        db.close()


def snapshot(database, *, item_id=None, run_id=None):
    # Missing databases are never created. No app import, schema initialization,
    # recovery, provider call or publication is involved in this entry point.
    with readonly_connection(database) as db:
        if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='orchestration_runs'").fetchone():
            return {"status": "no_history", "roles": [], "observation": "saved_ledger_only"}
        filters, values = [], []
        for key, value in (("item_id", item_id), ("run_id", run_id)):
            if value:
                filters.append(key + "=?")
                values.append(value)
        where = " WHERE " + " AND ".join(filters) if filters else ""
        row = db.execute("SELECT item_id,run_id FROM orchestration_runs" + where + " ORDER BY rowid DESC LIMIT 1", values).fetchone()
    if row is None:
        if item_id or run_id:
            raise LookupError("指定した会話・分析履歴が見つかりません。")
        return {"status": "no_history", "roles": [], "observation": "saved_ledger_only"}
    selected_item, selected_run = row

    def find_item(identifier):
        with readonly_connection(database) as db:
            return db.execute("SELECT id FROM library_items WHERE id=?", (identifier,)).fetchone()

    service = AnalysisHistoryService(connect=lambda: readonly_connection(database), find_item=find_item)
    return service.agents(selected_item, selected_run)


def clean(value):
    # Database strings must not become terminal escape sequences or extra rows.
    return re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", str(value if value is not None else "未記録"))


def render(value):
    lines = ["Gurumoji 分析エージェント — 保存台帳の読み取り専用表示",
             "保存状態はプロセスの生存確認ではありません。Ctrl+Cで表示だけを終了します。"]
    if value["status"] == "no_history":
        return "\n".join(lines + ["分析履歴はまだありません。"])
    lines.extend([f"会話: {clean(value['item_id'])}  Run: {clean(value['run_id'])}",
                  f"状態: {clean(value['status'])}  段階: {clean(value['phase'])}  台帳更新: {clean(value['updated_at'])}",
                  f"入力hash: {clean(value['input_hash'])}  停止理由: {clean(value['stop_reason'])}"])
    for role in value["roles"]:
        counts = role["status_counts"]
        lines.append(f"{role['label']} [{role['kind'].upper()}] {clean(role['status'])} | "
                     f"成功 {counts.get('succeeded', 0)}/{role['assigned']} | "
                     f"失敗 {counts.get('failed', 0)} 隔離 {counts.get('quarantined', 0)} 不明 {counts.get('uncertain', 0)} | "
                     f"{clean(role['provider'])} / {clean(role['model'])}")
        if counts:
            lines.append("  内訳: " + ", ".join(f"{clean(key)}={count}" for key, count in sorted(counts.items())))
        for task in role["active_tasks"]:
            lines.append(f"  {clean(task['task_id'])}: {clean(task['status'])} ({clean(task['method_id'])})")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path(os.environ.get("MOJIOKOSI_DATA_DIR", ROOT / "runtime/data")) / "library.sqlite3")
    parser.add_argument("--item-id")
    parser.add_argument("--run-id", help="Pin a run; otherwise show the latest saved run for the selected conversation")
    parser.add_argument("--watch", action="store_true")
    parser.add_argument("--interval", type=float, default=3)
    parser.add_argument("--json", action="store_true", help="JSON snapshot; with --watch emit one JSON object per update")
    args = parser.parse_args(argv)
    if not math.isfinite(args.interval) or args.interval < 1:
        parser.error("--interval must be a finite number of at least 1 second")
    previous = None
    try:
        while True:
            try:
                value = snapshot(args.database, item_id=args.item_id, run_id=args.run_id)
            except (sqlite3.Error, OSError, ValueError, LookupError, TypeError, AttributeError, AnalysisContractError) as exc:
                value = {"status": "unavailable", "error": str(exc), "roles": [], "observation": "saved_ledger_only"}
            serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
            if serialized != previous:
                if args.json:
                    print(serialized, flush=True)
                elif value["status"] == "unavailable":
                    print("台帳を取得できません: " + clean(value["error"]), flush=True)
                else:
                    print(render(value) + "\n", flush=True)
                previous = serialized
            if not args.watch:
                return 1 if value["status"] == "unavailable" else 0
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
