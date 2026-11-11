"""クロス表・カイ二乗の計算値と、推測に使える条件を分けて記録する。"""
from __future__ import annotations

import math


CONTINGENCY_VERSION = "contingency-visual-1"


def analyze_contingency(observed, row_labels, column_labels, *,
                        independent=None, analysis_unit="観測", table_id="", label=""):
    """整数度数から図表用の固定結果を作る。外部通信・保存は行わない。"""
    if independent is not None and type(independent) is not bool:
        raise ValueError("独立性はTrue・False・未確認のいずれかで指定してください。")
    if (not isinstance(observed, list) or not 2 <= len(observed) <= 100 or
            not isinstance(column_labels, list) or not 2 <= len(column_labels) <= 100 or
            not isinstance(row_labels, list) or len(row_labels) != len(observed)):
        raise ValueError("クロス表には2行2列以上の度数表と対応するラベルが必要です。")
    for labels in (row_labels, column_labels):
        if any(not isinstance(x, str) or not x.strip() or len(x) > 120 for x in labels) or len(set(labels)) != len(labels):
            raise ValueError("行列ラベルは空でない重複のない文字列にしてください。")
    if any(not isinstance(row, list) or len(row) != len(column_labels) or
           any(type(v) is not int or v < 0 or v > 10**12 for v in row) for row in observed):
        raise ValueError("観測度数には割合ではなく、0以上の整数を指定してください。")
    rows = [sum(row) for row in observed]
    cols = [sum(row[j] for row in observed) for j in range(len(column_labels))]
    n = sum(rows)
    active_rows = [i for i, v in enumerate(rows) if v]
    active_cols = [j for j, v in enumerate(cols) if v]
    expected = [[r*c/n if n else None for c in cols] for r in rows]
    residuals = [[(observed[i][j]-e)/math.sqrt(e) if e else None for j, e in enumerate(row)]
                 for i, row in enumerate(expected)]
    contributions = [[v*v if v is not None else None for v in row] for row in residuals]
    valid_expected = [expected[i][j] for i in active_rows for j in active_cols]
    low = sum(v < 5 for v in valid_expected)
    dof = (len(active_rows)-1)*(len(active_cols)-1) if len(active_rows) >= 2 and len(active_cols) >= 2 else None
    statistic = sum(v for row in contributions for v in row if v is not None) if dof else None
    reference_p = None
    engine_status = "not_computable"
    if statistic is not None:
        try:
            from scipy.stats import chi2
            reference_p = float(chi2.sf(statistic, dof))
            engine_status = "computed"
        except ImportError:
            engine_status = "unavailable"
    reasons = []
    if independent is not True:
        reasons.append("同一会話内の反復発話で独立性を満たさない" if independent is False else "観測の独立性は未確認")
    if low:
        reasons.append(f"期待度数5未満が{low}/{len(valid_expected)}セル")
    if not dof:
        reasons.append("非ゼロの行・列が2種類ずつ必要")
    if engine_status == "unavailable":
        reasons.append("SciPyが利用できずp値は未計算")
    eligible = independent is True and not low and dof is not None and reference_p is not None
    focus = [row[0]/total if total else None for row, total in zip(observed, rows)]
    nonmissing = [v for v in focus if v is not None]
    if nonmissing and max(nonmissing) != min(nonmissing):
        winners = [row_labels[i] for i, v in enumerate(focus) if v == max(nonmissing)]
        finding = f"「{column_labels[0]}」の観測割合は{winners[0]}で最も高い" if len(winners) == 1 else "行によって観測割合が異なる"
    else:
        finding = "各行の観測割合は同じ" if nonmissing else "観測度数がなく割合を比較できない"
    if eligible:
        decision = "独立性の帰無仮説を棄却（α=0.05）" if reference_p < .05 else "独立性の帰無仮説を棄却できない（α=0.05）"
    else:
        decision = "参考計算。カイ二乗検定による判断は保留"
    return {
        "schema_version": CONTINGENCY_VERSION, "table_id": table_id, "label": label,
        "row_labels": list(row_labels), "column_labels": list(column_labels),
        "observed": [list(row) for row in observed], "row_totals": rows, "column_totals": cols, "n": n,
        "row_proportions": [[v/total if total else None for v in row] for row, total in zip(observed, rows)],
        "expected": expected, "pearson_residuals": residuals, "chi_square_contributions": contributions,
        "statistic": statistic, "degrees_of_freedom": dof,
        "cramers_v": math.sqrt(statistic/(n*min(len(active_rows)-1, len(active_cols)-1))) if statistic is not None else None,
        "reference_p_value": reference_p, "p_value": reference_p if eligible else None,
        "independent": independent, "analysis_unit": analysis_unit,
        "expected_min": min(valid_expected) if valid_expected else None,
        "expected_below_5": low, "expected_cell_count": len(valid_expected),
        "expected_rule": "すべての有効セルの期待度数が5以上（保守的基準）",
        "excluded_zero_rows": [row_labels[i] for i, v in enumerate(rows) if not v],
        "excluded_zero_columns": [column_labels[j] for j, v in enumerate(cols) if not v],
        "inference_eligible": eligible, "inference_status": "eligible" if eligible else "reference_only",
        "assumption_reasons": reasons, "decision": decision, "finding": finding,
        "residual_note": "Pearson残差=(観測度数−期待度数)/√期待度数。セル別の有意性検定ではない。",
        "engine_status": engine_status,
    }
