"""保存済み分析を再分析の入力として読み取り専用で固定する。"""
from __future__ import annotations

import copy
import json
import re
from contextlib import nullcontext

from ..analysis_core import AnalysisContractError, fingerprint

MAX_PROMPT = 8000
MAX_SOURCE_BYTES = 128 * 1024
_ID = re.compile(r"(?:run|result)_[A-Za-z0-9_-]{1,200}\Z")


def lookup_reanalysis_source(viewer, item_id, source_analysis_id, *, connection=None):
    if not isinstance(source_analysis_id, str) or not _ID.fullmatch(source_analysis_id):
        raise AnalysisContractError("分析IDの形式が正しくありません。", field="source_analysis_id")
    with (viewer._read(item_id) if connection is None else nullcontext(connection)) as db:
        if source_analysis_id.startswith("run_"):
            run_id = source_analysis_id
        else:
            if not viewer._table(db, "orchestration_results"):
                raise LookupError("分析結果が見つかりません。")
            row = db.execute("SELECT run_id FROM orchestration_results WHERE result_id=?", (source_analysis_id,)).fetchone()
            if row is None:
                raise LookupError("分析結果が見つかりません。")
            run_id = row[0]
        run = viewer._run(db, item_id, run_id)
        snapshot = viewer._snapshot(db, run)
        if snapshot is None:
            raise AnalysisContractError("固定入力を確認できません。", code="history_integrity_mismatch")
        result_id = source_analysis_id if source_analysis_id.startswith("result_") else None
        if result_id is None:
            decision_id = run.get("last_decision_id")
            row = db.execute("SELECT result_id FROM orchestration_decisions WHERE run_id=? AND decision_id=?", (run_id, decision_id)).fetchone() if decision_id else None
            if row is None:
                raise AnalysisContractError("この実行には再分析できる統合結果がありません。", field="source_analysis_id")
            result_id = row[0]
        row = db.execute("SELECT * FROM orchestration_results WHERE run_id=? AND result_id=?", (run_id, result_id)).fetchone()
        if row is None:
            raise LookupError("分析結果が見つかりません。")
        meta, raw = json.loads(row["state_json"]), json.loads(row["raw_json"])
        if (meta.get("run_id") != run_id or meta.get("result_id") != result_id
                or meta.get("task_id") != row["task_id"] or not meta.get("raw_hash")
                or fingerprint(raw) != meta["raw_hash"] or meta.get("dataset_version") != run.get("input_hash")):
            raise AnalysisContractError("保存された結果の所属またはhashが一致しません。", code="history_integrity_mismatch")
        task_row = db.execute("SELECT state_json FROM orchestration_tasks WHERE run_id=? AND task_id=?", (run_id, row["task_id"])).fetchone()
        task = json.loads(task_row[0]) if task_row else {}
        if (meta.get("validation_status") != "valid" or task.get("status") == "quarantined"
                or task.get("run_id") != run_id or task.get("task_id") != row["task_id"]):
            raise AnalysisContractError("隔離中または検証されていない結果は再分析できません。", field="source_analysis_id")
        content = viewer._entry(db, run, "result:" + result_id, detail=True)
        if content.get("truncated_fields"):
            raise AnalysisContractError("参照する結果が大きすぎるため固定できません。", field="source_analysis_id")
        source = {"source_analysis_id": source_analysis_id, "source_run_id": run_id,
                  "source_result_id": result_id, "original_question": run.get("config", {}).get("question"),
                  "input_hash": run.get("input_hash"), "source_revision": run.get("source_revision"),
                  "analysis_revision": run.get("analysis_revision"), "initial_id": run.get("initial_id"),
                  "snapshot_hash": fingerprint(snapshot), "raw_hash": meta["raw_hash"], "content": content}
        if len(json.dumps(source, ensure_ascii=False).encode("utf-8")) > MAX_SOURCE_BYTES:
            raise AnalysisContractError("参照する結果が大きすぎるため固定できません。", field="source_analysis_id")
        return source


def freeze_reanalysis(viewer, item_id, source_analysis_id, human_prompt, *, connection=None):
    if not isinstance(human_prompt, str) or not human_prompt.strip() or len(human_prompt) > MAX_PROMPT:
        raise AnalysisContractError("追加プロンプトを8000文字以内で入力してください。", field="human_prompt")
    return {**copy.deepcopy(lookup_reanalysis_source(viewer, item_id, source_analysis_id, connection=connection)),
            "human_prompt": human_prompt.strip()}
