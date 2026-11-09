"""全自動分析で要求された手法の検証と進捗。"""
from __future__ import annotations

from ..analysis_core import AnalysisContractError

LABEL_METHODS = frozenset({"label_frequency", "cross_tabulation"})


_CATALOG = (
    {"id": "participation", "name": "発話量・参加バランス", "requirements": "対象発話と話者情報", "available": True, "reason": ""},
    {"id": "conversation_dynamics", "name": "会話の時間構造", "requirements": "対象発話と時刻・話者情報", "available": True, "reason": ""},
    {"id": "label_frequency", "name": "ラベル度数", "requirements": "対象発話とコードラベル（欠測は別途表示）", "available": True, "reason": "codes欄を集計します。"},
    {"id": "cross_tabulation", "name": "クロス集計（話者×コード）", "requirements": "話者IDとコードラベル", "available": True,
     "reason": "発話単位の件数・行内割合・列内割合を集計します。全件欠測は集計不可です。"},
)
_IDS = frozenset(item["id"] for item in _CATALOG)


def method_catalog():
    return [dict(item) for item in _CATALOG]


def validate_required_methods(value):
    if (not isinstance(value, list) or any(not isinstance(v, str) or v not in _IDS for v in value)
            or len(value) != len(set(value))):
        raise AnalysisContractError("必須分析手法は対応するIDの重複しない配列で指定してください。",
                                    code="invalid_required_methods", field="required_methods")
    return list(value)


def required_method_intent(method_id, question):
    validate_required_methods([method_id])
    label = method_id in LABEL_METHODS
    return {"role": "statistics", "kind": "analysis", "method_id": method_id,
            "question": question, "why_now": "利用者が必須分析に指定しました。",
            "success_criteria": "固定入力に対する集計と限界を記録します。",
            "evidence_ids": [], "label_field": "codes" if label else "",
            "label_dependent": label, "dependencies": [], "importance": "high",
            "importance_reason": "利用者指定の必須分析です。"}


def required_intents(methods, question):
    return [required_method_intent(method, question) for method in validate_required_methods(methods)]


def required_progress(methods, tasks, results, decisions, *, dataset_version, annotation_version,
                      codebook_version=None, run_stale=False):
    """有効な実行、専門担当の採否、Coreの報告取込をそれぞれ確認する。"""
    methods = validate_required_methods(methods)
    result_index = {r.get("result_id"): r for r in results}
    output = []
    for method in methods:
        candidates = [t for t in tasks if t.get("role") == "statistics" and t.get("method_id") == method
                      and (method != "cross_tabulation" or (
                          not t.get("intent", {}).get("evidence_ids") and not t.get("intent", {}).get("scope")
                          and (t.get("intent", {}).get("label_field") or "codes") == "codes"))]
        current = [t for t in candidates if not run_stale and not t.get("stale")
                   and t.get("dataset_version") == dataset_version
                   and (method not in LABEL_METHODS or (t.get("annotation_version") == annotation_version
                        and (codebook_version is None or t.get("codebook_version") == codebook_version)))]
        successful = [t for t in current if t.get("status") == "succeeded" and t.get("validation_status") == "valid"
                      and (r := result_index.get(t.get("result_id"))) and r.get("validation_status") == "valid"
                      and not r.get("stale")]
        task = successful[-1] if successful else (current[-1] if current else None)
        state = "not_run" if not candidates else ("stale" if not current else task.get("status", "not_run"))
        entry = {"id": method, "status": state, "task_id": task.get("task_id") if task else None,
                 "result_id": task.get("result_id") if task else None, "error": task.get("error", "") if task else "",
                 "review": None, "core_integrated": False, "complete": False}
        if successful:
            rid = task["result_id"]
            reviews = [(d, a) for d in decisions if d.get("role") == "orchestrator"
                       for a in d.get("result_assessments", []) if a.get("result_id") == rid]
            if reviews:
                decision, assessment = reviews[-1]
                entry["review"] = {"disposition": assessment.get("disposition"), "reason": assessment.get("reason", ""),
                                   "result_id": decision.get("result_id")}
                entry["core_integrated"] = any(decision.get("result_id") in d.get("domain_report_ids", [])
                                               for d in decisions if d.get("role", "core") == "core")
            entry["complete"] = bool(entry["review"] and entry["review"]["disposition"] in {"adopt", "reject"}
                                     and entry["review"]["reason"] and entry["core_integrated"])
            if method == "cross_tabulation":
                entry["calculation"] = result_index[rid].get("calculation", {})
                if entry["calculation"].get("availability") not in {"computed", "partial"}:
                    entry["complete"] = False
        output.append(entry)
    return output
