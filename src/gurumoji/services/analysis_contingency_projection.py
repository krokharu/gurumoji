"""保存済みのクロス集計結果を、再計算せず図表の原稿へ変換する。"""
from __future__ import annotations

import math


def _number(value, digits=3):
    if value is None:
        return "未計算"
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("有限の保存数値が必要です。")
    return f"{value:.{digits}g}"


def contingency_pages(statistics, policy):
    """固定結果だけを表示する。検定の成立をp値の大小から推測しない。"""
    if not isinstance(statistics, dict) or not isinstance(policy, dict) or not policy.get("crosstab_chi_square"):
        return []
    records = statistics.get("contingency_visualizations", [])
    if not isinstance(records, list):
        return []
    limit = policy.get("max_contingency_tables", 3)
    limit = limit if type(limit) is int and 1 <= limit <= 10 else 3
    pages = []
    for index, item in enumerate(records[:limit]):
        if not isinstance(item, dict) or item.get("schema_version") != "contingency-visual-1":
            continue
        labels, columns, matrix = item.get("row_labels"), item.get("column_labels"), item.get("observed")
        if (not isinstance(labels, list) or not isinstance(columns, list) or not isinstance(matrix, list) or
                len(labels) != len(matrix) or not labels or not columns):
            continue
        try:
            if any(not isinstance(row, list) or len(row) != len(columns) or
                   any(type(v) is not int or v < 0 for v in row) for row in matrix):
                continue
            values = []
            for r, row in enumerate(matrix):
                values.append([labels[r], *[f"{v} ({100*item['row_proportions'][r][c]:.1f}%)" if item['row_proportions'][r][c] is not None else f"{v} (算出不能)" for c, v in enumerate(row)], str(item['row_totals'][r])])
            table_rows = [["行 / 列", *columns, "行合計"], *values]
            footer = f"対象{item['n']} {item['analysis_unit']}。表{index+1}/{len(records)}。割合は行合計が分母。"
            if len(records) > limit:
                footer += f" {limit}表の抜粋。残りは保存結果を参照。"
            common = {"method": "クロス集計。各セルに観測度数（行割合）を表示。" + str(item.get("label", "")),
                      "footer": footer, "source_table_id": item.get("table_id", "")}
            pages.append({**common, "kind": "crosstab", "title": "量的分析：" + str(item['finding']),
                          "grid": table_rows, "reading": item['finding'] + "。観測値の比較であり、母集団の差の証明ではない。"})
            residual_rows = [["行 / 列", *columns], *[[labels[r], *["—" if v is None else f"{v:+.2f}" for v in row]] for r, row in enumerate(item['pearson_residuals'])]]
            reasons = "／".join(item['assumption_reasons']) or "独立性を明示、期待度数の保守的基準を通過"
            title = "量的分析：カイ二乗検定による判断は保留"
            if item['inference_eligible'] is True:
                title = "量的分析：" + item['decision']
            stats = f"χ² = {_number(item['statistic'])}\ndf = {_number(item['degrees_of_freedom'])}\n" + ("p" if item['inference_eligible'] else "参考p") + f" = {_number(item['reference_p_value'])}\nCramér’s V = {_number(item['cramers_v'])}\n期待度数最小 = {_number(item['expected_min'])}"
            pages.append({**common, "kind": "chi_square", "title": title, "grid": residual_rows,
                          "residuals": item['pearson_residuals'], "statistics_text": stats,
                          "method": "Pearsonのカイ二乗（連続性補正なし）。色はPearson残差の符号と大きさ。",
                          "reading": item['decision'] + "。" + reasons,
                          "footer": "正：期待より多い／負：期待より少ない。色をセル別の有意性と解釈しない。"})
        except (KeyError, TypeError, IndexError, ValueError, ZeroDivisionError):
            continue
    return pages
