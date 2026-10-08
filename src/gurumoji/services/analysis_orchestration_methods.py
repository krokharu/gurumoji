"""Allowlisted deterministic computations for Handler-issued statistics tasks."""
from __future__ import annotations

from collections import defaultdict
import math
from typing import Any

from .analysis_pipeline_adapters import run_analysis_pipeline_method
from ..analysis_core import AnalysisContractError, fingerprint

# Code-owned capabilities: Markdown may describe these tools, never add executors.
STATISTICAL_TOOLS = {
    "descriptive_statistics": ("descriptives", None, None),
    "frequency_statistics": ("frequencies", None, None),
    "crosstabs": ("crosstabs", None, None),
    "anova": ("tests", "test", "一元配置分散分析（ANOVA）"),
    "kruskal_wallis": ("tests", "test", "Kruskal–Wallis検定"),
    "chi_square": ("tests", "test", "Pearsonのカイ二乗検定"),
    "pearson": ("correlations", "method", "Pearson"),
    "spearman": ("correlations", "method", "Spearman"),
}
EXPERT_STATISTICAL_TOOLS = {
    "exp-descriptive-statistics": ("descriptive_statistics", "frequency_statistics"),
    "exp-group-comparison-statistics": ("crosstabs", "anova", "kruskal_wallis", "chi_square"),
    "exp-correlation": ("pearson", "spearman"),
}
STATISTICAL_TOOL_VERSION = "statistical-tools-1"


def validate_statistical_result(raw, task, evidence):
    method_id = task["method_id"]
    manifest = raw.get("manifest", {})
    dataset = STATISTICAL_TOOLS[method_id][0]
    table = raw.get("datasets", {}).get(dataset, {})
    rows = table.get("rows")
    included = {row["evidence_id"] for row in evidence if not row["excluded"]}
    if (raw.get("method_id") != method_id or raw.get("method_version") != STATISTICAL_TOOL_VERSION
            or raw.get("dataset_version") != task["dataset_version"]
            or manifest.get("dataset_version") != task["dataset_version"]
            or manifest.get("kind") != "deterministic_code" or manifest.get("method_id") != method_id
            or manifest.get("method_version") != STATISTICAL_TOOL_VERSION
            or manifest.get("scope") != "all_included_initial"
            or set(manifest.get("evidence_ids", [])) != included
            or manifest.get("included_count") != len(included)
            or not isinstance(rows, list) or manifest.get("row_count") != len(rows)
            or manifest.get("rows_hash") != fingerprint(rows)
            or any(not isinstance(row, dict) or not row.get("row_id") for row in rows)
            or len({row["row_id"] for row in rows}) != len(rows)):
        raise AnalysisContractError("統計計算の入力版・対象・結果hashが一致しません。", code="statistics_result_mismatch")


def calculation_packet(raw, metadata, *, max_chars=10000):
    """A bounded view; SQLite retains all original rows and their hash."""
    limit, remaining = 40, max_chars
    tables = {}
    for name, table in raw["datasets"].items():
        provided = []
        for row in table["rows"]:
            import json
            size = len(json.dumps(row, ensure_ascii=False))
            if len(provided) >= limit or size > remaining:
                break
            provided.append(row)
            remaining -= size
        tables[name] = {"fields": table["fields"], "rows": provided,
                       "total_rows": len(table["rows"]), "omitted_rows": len(table["rows"]) - len(provided)}
    manifest = {**raw["manifest"], "evidence_ids": raw["manifest"]["evidence_ids"][:40],
                "evidence_count": len(raw["manifest"]["evidence_ids"]),
                "omitted_evidence_ids": max(0, len(raw["manifest"]["evidence_ids"]) - 40)}
    return {"result_id": metadata["result_id"], "task_id": metadata["task_id"], "raw_hash": metadata["raw_hash"],
            "method_id": raw["method_id"], "status": raw["status"], "manifest": manifest,
            "datasets": tables, "limitations": raw["limitations"]}


def run_statistical_tool(method_id, snapshot):
    """Recompute through the existing engine on immutable input, then project.

    The shared engine computes the statistical family; only the requested table
    is returned. No model-provided code, variable expressions or mutable labels.
    """
    import copy
    from ..research_analysis import build_research_statistics, RESEARCH_ALGORITHM_VERSION
    analysis = copy.deepcopy(snapshot["analysis"])
    linguistics = analysis.get("research", {}).get("linguistics", {})
    if not isinstance(linguistics.get("morphemes"), list):
        raise AnalysisContractError("固定版の形態素解析が必要です。", code="statistics_input_missing")
    stage = build_research_statistics(analysis, linguistics)
    statistics = stage["statistics"]
    dataset, column, selection = STATISTICAL_TOOLS[method_id]
    rows = statistics[dataset]
    if column:
        rows = [row for row in rows if row.get(column) == selection]
    rows = [{**row, "row_id": fingerprint([method_id, i, row])} for i, row in enumerate(rows)]
    evidence = [row for row in snapshot["evidence"] if not row["excluded"]]
    task = snapshot["orchestration_task"]
    statuses = {row.get("status") for row in rows if "status" in row}
    status = ("not_computed" if not rows or (statuses and "computed" not in statuses)
              else "partial" if statuses - {"computed"} else "computed")
    manifest = {
        "kind": "deterministic_code", "method_id": method_id, "method_version": STATISTICAL_TOOL_VERSION,
        "research_algorithm_version": RESEARCH_ALGORITHM_VERSION,
        "dataset_version": task["dataset_version"], "analysis_unit": statistics["analysis_unit"],
        "scope": "all_included_initial", "evidence_ids": [row["evidence_id"] for row in evidence],
        "included_count": statistics["included_segment_count"], "excluded_count": statistics["excluded_segment_count"],
        "group_variable": statistics["group_variable"], "group_count": statistics["group_count"],
        "inference_policy": statistics["inference_policy"], "engine": statistics["engine"],
        "computation_input_hash": fingerprint({"analysis": analysis, "linguistics": linguistics}),
        "rows_hash": fingerprint(rows), "row_count": len(rows),
    }
    return {"summary": f"{method_id}: 固定入力の既存統計エンジンによる{len(rows)}行（{status}）。",
            "claims": [], "method_id": method_id, "method_version": STATISTICAL_TOOL_VERSION,
            "dataset_version": task["dataset_version"], "status": status,
            "datasets": {dataset: {"fields": list(rows[0]) if rows else [], "rows": rows}},
            "manifest": manifest,
            "limitations": ["発話単位の探索的分析です。独立性は確認されておらず、多重比較補正はありません。",
                            "固定された比較軸と全対象を使います。後から採用したラベルや部分範囲は使いません。",
                            "共通統計エンジンで計算し、依頼された手法の結果だけを返します。"]}

LABEL_FIELDS = frozenset({"codes", "code", "theme", "sentiment", "dialogue_act",
                          "importance", "review", "category"})


def run_orchestration_method(method_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    from ..analysis_method_registry import TABLE_PILOT_METHODS
    from ..analysis_method_registry import CONNECTED_METHODS
    if method_id in CONNECTED_METHODS:
        return run_connected_method(method_id, snapshot)
    if method_id in TABLE_PILOT_METHODS:
        return run_table_pilot_method(method_id, snapshot)
    if method_id in STATISTICAL_TOOLS:
        return run_statistical_tool(method_id, snapshot)
    if method_id != "label_frequency":
        return run_analysis_pipeline_method(method_id, snapshot)
    task = snapshot["orchestration_task"]
    labels = snapshot["orchestration_labels"]
    field = task["intent"].get("label_field") or "codes"
    if field not in LABEL_FIELDS:
        raise ValueError("未対応のラベル項目です。")
    selected = task["intent"].get("evidence_ids") or []
    evidence = [row for row in snapshot["evidence"] if not row["excluded"]]
    if selected:
        if not set(selected) <= {row["evidence_id"] for row in evidence}:
            raise ValueError("指定範囲に除外済み・存在しない発話が含まれます。")
        evidence = [row for row in evidence if row["evidence_id"] in selected]
    if not evidence:
        raise ValueError("集計対象の発話がありません。")
    groups: dict[str, list[str]] = defaultdict(list)
    missing = []
    for row in evidence:
        value = labels.get(row["utterance_id"], {}).get(field)
        if value is None or value == "" or value == []:
            missing.append(row["evidence_id"])
            continue
        values = value if isinstance(value, list) else [value]
        categories = set()
        for category in values:
            if isinstance(category, str):
                category = category.strip()
                if category:
                    categories.add(category)
            elif type(category) is bool:
                categories.add("true" if category else "false")
            elif type(category) in {int, float} and math.isfinite(category):
                categories.add(str(category))
            else:
                raise ValueError("ラベル値の型が集計対象外です。")
        if not categories:
            missing.append(row["evidence_id"])
        for category in categories:
            groups[category].append(row["evidence_id"])
    denominator = len(evidence)
    rows = [{"label": category, "count": len(ids), "denominator": denominator,
             "proportion": len(ids) / denominator, "evidence_ids": ids}
            for category, ids in sorted(groups.items(), key=lambda pair: (-len(pair[1]), pair[0]))]
    return {
        "summary": f"固定ラベル版{task['annotation_version']}の{field}を対象{denominator}発話で再集計。欠測{len(missing)}発話。",
        "claims": [], "method_id": "label_frequency", "method_version": "label-frequency-1",
        "research_mode": "exploratory", "dataset_version": task["dataset_version"],
        "annotation_version": task["annotation_version"], "codebook_version": task["codebook_version"],
        "label_field": field, "denominator": denominator, "missing_count": len(missing),
        "missing_evidence_ids": missing, "rows": rows,
        "manifest": {"kind": "deterministic_code", "method_version": "label-frequency-1",
                     "analysis_unit": "utterance", "scope": "selected" if selected else "all_included",
                     "evidence_ids": [row["evidence_id"] for row in evidence],
                     "dataset_version": task["dataset_version"],
                     "annotation_version": task["annotation_version"], "codebook_version": task["codebook_version"]},
        "limitations": ["複数ラベルの度数合計は発話数を超える場合があります。",
                        "欠測を含む対象発話全体を分母に固定しています。",
                        "記述集計であり、人物属性・因果関係や統計的確認を示しません。"],
    }


def _table_population(prepared, method_id):
    request = prepared["request"]
    table = prepared["tables"][0]["table"]
    rows = table["rows"]
    selected = set(request["parameters"].get("row_ids", []))
    if method_id == "table_projection":
        if not selected or not selected <= {r["row_id"] for r in rows}:
            raise AnalysisContractError("projection行が不正です。", code="table_selection")
    else:
        selected = {r["row_id"] for r in rows}
    population = {key: [] for key in ("included_ids", "excluded_ids", "missing_ids",
                                      "unprocessed_ids", "unknown_ids", "observed_zero_ids")}
    parameters = request["parameters"]
    value_columns = [parameters[k] for k in ("value_column", "row_column", "column_column") if k in parameters]
    if method_id in {"table_projection", "table_join"}:
        columns = parameters.get("columns", list(dict.fromkeys(
            k for t in prepared["tables"] for k in t["table"]["fields"])))
        value_columns = [v["variable_id"] for t in prepared["tables"] for v in t["variables"]
                         if v["value_type"] in {"integer", "number"} and v["variable_id"] in columns]
    if method_id == "table_join":
        right = {r["values"]["utterance_id"]: r["values"] for r in prepared["tables"][1]["table"]["rows"]}
        rows = [{**r, "values": {**r["values"], **right.get(r["values"]["utterance_id"], {})}} for r in rows]
    for row in rows:
        v = row["values"]; uid = v["utterance_id"]; status = v["value_status"]
        if row["row_id"] not in selected or status == "excluded":
            population["excluded_ids"].append(uid)
            continue
        population["included_ids"].append(uid)
        if status != "observed":
            population[status + "_ids"].append(uid)
        else:
            if any(c not in v or v[c] is None for c in value_columns):
                raise AnalysisContractError("観測済み値が欠落しています。", code="table_observed_missing")
            if any(type(v.get(c)) in {int, float} and v[c] == 0 for c in value_columns):
                population["observed_zero_ids"].append(uid)
    for key in population: population[key].sort()
    population["denominator"] = len(population["included_ids"])
    return population


def validate_table_pilot_result(raw, task, prepared):
    """Check the real Handler result boundary; structural verification only."""
    from ..analysis_core import canonical, TABLE_PILOT_VERSION, TABLE_PILOT_MAX_BYTES
    from ..analysis_method_registry import CONNECTED_METHODS
    if task["method_id"] in CONNECTED_METHODS:
        expected = run_connected_method(task["method_id"], {"table_pilot":prepared, "orchestration_task":task})
        if canonical(raw) != canonical(expected):
            raise AnalysisContractError("固定計算結果と異なります。",code="connected_result_mismatch")
        return
    if (not isinstance(raw, dict) or raw.get("method_id") != task["method_id"]
            or raw.get("method_version") != TABLE_PILOT_VERSION
            or raw.get("dataset_version") != task["dataset_version"]
            or raw.get("research_mode") != "exploratory" or raw.get("status") != "computed"
            or raw.get("analysis_unit") != "utterance" or raw.get("claims") != []
            or set(raw.get("datasets", {})) != {"table"} or len(canonical(raw)) > TABLE_PILOT_MAX_BYTES):
        raise AnalysisContractError("表結果の契約が不正です。", code="table_result_mismatch")
    table = raw["datasets"]["table"]; fields = table.get("fields"); rows = table.get("rows")
    if (not isinstance(fields, list) or not fields or len(fields) != len(set(fields))
            or any(not isinstance(k, str) or not k for k in fields)
            or "source_utterance_ids" not in fields or not isinstance(rows, list) or not rows
            or set(table) != {"fields", "rows"}):
        raise AnalysisContractError("表の構造が不正です。", code="table_output_shape")
    population = _table_population(prepared, task["method_id"])
    source_ids = set(population["included_ids"]) | set(population["excluded_ids"])
    calculation_ids = sorted(set(population["included_ids"]) - set(population["missing_ids"])
                             - set(population["unprocessed_ids"]) - set(population["unknown_ids"]))
    for row in rows:
        ids = row.get("source_utterance_ids") if isinstance(row, dict) else None
        if (not isinstance(row, dict) or set(row) != set(fields) or not isinstance(ids, list)
                or any(not isinstance(i, str) for i in ids) or len(ids) != len(set(ids))
                or not set(ids) <= source_ids
                or (not ids and (task["method_id"] != "table_crosstab" or type(row.get("count")) is not int or row["count"] != 0))):
            raise AnalysisContractError("結果の発話参照が不正です。", code="table_output_references")
    observed = set(population["included_ids"]) - set(population["missing_ids"]) - set(population["unprocessed_ids"]) - set(population["unknown_ids"])
    originals = {r["values"]["utterance_id"]: r["values"] for r in prepared["tables"][0]["table"]["rows"]}
    method = task["method_id"]
    parameters = prepared["request"]["parameters"]
    if method in {"table_projection", "table_aggregate", "table_join"}:
        actual = {}
        for row in rows:
            uid = row.get("utterance_id")
            if not isinstance(uid, str) or uid not in originals or uid in actual or row["source_utterance_ids"] != [uid]:
                raise AnalysisContractError("表の発話単位が異なります。", code="table_output_identity")
            actual[uid] = row
        if method == "table_projection":
            columns = parameters["columns"]
            selected = set(parameters["row_ids"])
            source_rows = [r for r in prepared["tables"][0]["table"]["rows"] if r["row_id"] in selected]
            expected_rows = {r["values"]["utterance_id"]: {**{k:r["values"].get(k) for k in columns},
                            "source_utterance_ids": [r["values"]["utterance_id"]]} for r in source_rows}
            expected_fields = columns + ["source_utterance_ids"]
        elif method == "table_aggregate":
            expected_fields = ["utterance_id", "conversation_id", "count", "value_status", "source_utterance_ids"]
            expected_rows = {i: {"utterance_id": i, "conversation_id": v["conversation_id"], "value_status": v["value_status"],
                                 "count": 1 if v["value_status"] == "observed" else None, "source_utterance_ids": [i]}
                             for i,v in originals.items()}
        else:
            right = {r["values"]["utterance_id"]: r["values"] for r in prepared["tables"][1]["table"]["rows"]}
            expected_fields = list(dict.fromkeys(k for t in prepared["tables"] for k in t["table"]["fields"])) + ["source_utterance_ids"]
            expected_rows = {i:{**v,**right[i],"source_utterance_ids":[i]} for i,v in originals.items()}
        if fields != expected_fields or canonical(actual) != canonical(expected_rows):
            raise AnalysisContractError("登録操作と表の内容が異なります。", code="table_output_projection")
    if method in {"table_frequency", "table_crosstab"}:
        required_fields = (["category", "count", "source_utterance_ids"] if method == "table_frequency" else
                           ["row_value", "column_value", "count", "source_utterance_ids"])
        if fields != required_fields: raise AnalysisContractError("集計列が異なります。", code="table_output_fields")
        delivered, categories = set(), set()
        for row in rows:
            ids = row["source_utterance_ids"]
            key_fields = ["category"] if method == "table_frequency" else ["row_value", "column_value"]
            key = canonical([row[k] for k in key_fields])
            if (type(row["count"]) is not int or row["count"] != len(ids) or key in categories
                    or not set(ids) <= observed or delivered & set(ids)):
                raise AnalysisContractError("集計の単位・重複・件数が異なります。", code="table_output_count")
            categories.add(key); delivered.update(ids)
            columns = [parameters["value_column"]] if method == "table_frequency" else [parameters["row_column"], parameters["column_column"]]
            for uid in ids:
                if canonical([originals[uid][c] for c in columns]) != canonical([row[k] for k in key_fields]):
                    raise AnalysisContractError("集計セルと元値が異なります。", code="table_output_category")
            if not ids:
                for column, key_field in zip(columns, key_fields):
                    if canonical(row[key_field]) not in {canonical(originals[i][column]) for i in observed}:
                        raise AnalysisContractError("未観測カテゴリのzeroです。", code="table_output_zero_domain")
        if delivered != observed:
            raise AnalysisContractError("計算対象が欠落しています。", code="table_output_population")
        if method == "table_crosstab":
            # Derive the complete typed domains from frozen observed inputs,
            # independently of the delivered cells (including genuine zeros).
            domains = [{canonical(originals[i][column]): originals[i][column] for i in observed}
                       for column in (parameters["row_column"], parameters["column_column"])]
            expected_cells = {canonical([row_value, column_value])
                              for row_value in domains[0].values() for column_value in domains[1].values()}
            if categories != expected_cells:
                raise AnalysisContractError("クロス集計セルが欠落または余分です。", code="table_output_cells")
    manifest = raw.get("manifest", {})
    expected = {"version": TABLE_PILOT_VERSION, "kind": "deterministic_code", "method_id": task["method_id"],
                "method_version": TABLE_PILOT_VERSION, "analysis_unit": "utterance",
                "input_hash": prepared["content_hash"], "parameters_hash": fingerprint(prepared["request"]["parameters"]),
                "rows_hash": fingerprint(rows), "population_hash": fingerprint(population),
                "binding_ids": [b["binding_id"] for b in prepared["receipt"]["bindings"]],
                "included_denominator": population["denominator"], "calculation_ids": calculation_ids,
                "calculation_denominator": len(calculation_ids)}
    if canonical(raw.get("population")) != canonical(population) or canonical(manifest) != canonical(expected):
        raise AnalysisContractError("分母・対象・hashが異なります。", code="table_result_hash")
    return None


def run_table_pilot_method(method_id, snapshot):
    from .. import research_analysis
    from ..analysis_core import TABLE_PILOT_VERSION
    import copy
    prepared = snapshot.get("table_pilot")
    kernel = getattr(research_analysis, "run_table_pilot", None)
    if not isinstance(prepared, dict) or not callable(kernel):
        raise AnalysisContractError("登録表カーネルは未接続です。", code="table_kernel_unavailable")
    result = kernel(method_id, copy.deepcopy(prepared["tables"]), copy.deepcopy(prepared["request"]["parameters"]))
    if not isinstance(result, dict) or set(result) != {"fields", "rows", "population"}:
        raise AnalysisContractError("カーネル結果が不正です。", code="table_kernel_result")
    task = snapshot["orchestration_task"]
    raw = {"summary": "固定表の登録済み記述計算。研究者採否は未回答。",
           "claims": [], "method_id": method_id, "method_version": TABLE_PILOT_VERSION,
           "dataset_version": task["dataset_version"], "research_mode": "exploratory", "status": "computed",
           "analysis_unit": "utterance", "datasets": {"table": {"fields": result["fields"], "rows": result["rows"]}},
           "population": result["population"], "manifest": {
               "version": TABLE_PILOT_VERSION, "kind": "deterministic_code", "method_id": method_id,
               "method_version": TABLE_PILOT_VERSION, "analysis_unit": "utterance",
               "input_hash": prepared["content_hash"], "parameters_hash": fingerprint(prepared["request"]["parameters"]),
               "rows_hash": fingerprint(result["rows"]), "population_hash": fingerprint(result["population"]),
               "binding_ids": [b["binding_id"] for b in prepared["receipt"]["bindings"]]},
           "limitations": ["発話単位の構造・局所記述のみ。意味妥当性と研究者採否は未確認。"]}
    population = result["population"]
    calculation_ids = sorted(set(population["included_ids"]) - set(population["missing_ids"])
                             - set(population["unprocessed_ids"]) - set(population["unknown_ids"]))
    raw["manifest"].update(included_denominator=population["denominator"], calculation_ids=calculation_ids,
                           calculation_denominator=len(calculation_ids))
    validate_table_pilot_result(raw, task, prepared)
    return raw


def run_connected_method(method_id, snapshot):
    from ..research_analysis import run_connected_table
    import copy
    prepared = snapshot["table_pilot"]; task=snapshot["orchestration_task"]
    result = run_connected_table(method_id,copy.deepcopy(prepared["tables"]),copy.deepcopy(prepared["request"]["parameters"]))
    return {"summary":"固定資産の登録計算。探索用・意味妥当性は未評価。","claims":[],"method_id":method_id,
        "method_version":"connected-assets-2","dataset_version":task["dataset_version"],"research_mode":"exploratory",
        "status":"computed","analysis_unit":result["unit_contract"]["unit"],
        "datasets":{"table":{"fields":result["fields"],"rows":result["rows"]}},
        "population":result["population"],"unit_contract":result["unit_contract"],
        "manifest":{"version":"connected-assets-2","input_hash":prepared["content_hash"],
            "parameters_hash":fingerprint(prepared["request"]["parameters"]),"rows_hash":fingerprint(result["rows"]),
            "binding_ids":[b["binding_id"] for b in prepared["receipt"]["bindings"]]},
        "limitations":["採用された質的根拠の構造計算。測定妥当性・独立性・確認的推論を認定しません。"]}
