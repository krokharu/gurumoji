"""Allowlisted deterministic computations for Handler-issued statistics tasks."""
from __future__ import annotations

from collections import defaultdict
import math
from typing import Any

from .analysis_pipeline_adapters import run_analysis_pipeline_method
from .orchestration_required_methods import LABEL_METHODS

LABEL_FIELDS = frozenset({"codes", "code", "theme", "sentiment", "dialogue_act",
                          "importance", "review", "category"})


def run_orchestration_method(method_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    if method_id not in LABEL_METHODS:
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
    if method_id == "cross_tabulation":
        return _cross_tabulation(evidence, labels, field, task, selected)
    groups: dict[str, list[str]] = defaultdict(list)
    missing = []
    for row in evidence:
        value = labels.get(row["utterance_id"], {}).get(field)
        categories = _categories(value)
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


def _categories(value):
    if value is None or value == "" or value == []:
        return set()
    categories = set()
    for category in value if isinstance(value, list) else [value]:
        if isinstance(category, str):
            if category.strip():
                categories.add(category.strip())
        elif type(category) is bool:
            categories.add("true" if category else "false")
        elif type(category) in {int, float} and math.isfinite(category):
            categories.add(str(category))
        else:
            raise ValueError("ラベル値の型が集計対象外です。")
    return categories


def _cross_tabulation(evidence, labels, field, task, selected):
    """話者×ラベルを発話単位で集計し、欠測と複数回答を区別する。"""
    cells, speakers, columns = defaultdict(list), {}, defaultdict(list)
    missing, missing_speaker, missing_label = [], [], []
    for row in evidence:
        eid, speaker = row["evidence_id"], row.get("speaker")
        categories = _categories(labels.get(row["utterance_id"], {}).get(field))
        known_speaker = isinstance(speaker, str) and speaker.strip() and speaker.strip().upper() != "UNKNOWN"
        if not known_speaker:
            missing_speaker.append(eid)
        if not categories:
            missing_label.append(eid)
        if not known_speaker or not categories:
            missing.append(eid)
        if not known_speaker:
            continue
        group = speakers.setdefault(speaker, {"speaker": speaker, "denominator": 0, "observed_count": 0,
                                               "missing_count": 0, "evidence_ids": []})
        group["denominator"] += 1
        group["observed_count" if categories else "missing_count"] += 1
        group["evidence_ids"].append(eid)
        for category in sorted(categories):
            cells[speaker, category].append(eid)
            columns[category].append(eid)
    denominator, observed = len(evidence), len(evidence) - len(missing)
    availability = "unavailable" if not observed else ("partial" if missing else "computed")
    rows = []
    for speaker, group in sorted(speakers.items()):
        for category, column_ids in sorted(columns.items()):
            ids = cells[speaker, category]
            rows.append({"speaker": speaker, "label": category, "count": len(ids),
                         "denominator": denominator, "row_denominator": group["denominator"],
                         "column_denominator": len(column_ids), "row_proportion": len(ids) / group["denominator"]
                         if group["observed_count"] else None,
                         "column_proportion": len(ids) / len(column_ids), "proportion": len(ids) / denominator,
                         "evidence_ids": ids})
    version = "speaker-label-crosstab-1"
    return {"summary": f"話者×{field}のクロス集計。対象{denominator}発話、有効{observed}発話、欠測{len(missing)}発話。"
                       + ("有効な組がないため集計不可。" if not observed else ""),
            "claims": [], "method_id": "cross_tabulation", "method_version": version,
            "research_mode": "exploratory", "dataset_version": task["dataset_version"],
            "annotation_version": task["annotation_version"], "codebook_version": task["codebook_version"],
            "row_field": "speaker", "label_field": field, "availability": availability,
            "denominator": denominator, "observed_count": observed, "missing_count": len(missing),
            "missing_speaker_count": len(missing_speaker), "missing_label_count": len(missing_label),
            "missing_evidence_ids": missing, "missing_speaker_evidence_ids": missing_speaker,
            "missing_label_evidence_ids": missing_label, "total_assignments": sum(map(len, columns.values())),
            "row_totals": [group for _, group in sorted(speakers.items())],
            "column_totals": [{"label": category, "count": len(ids), "evidence_ids": ids}
                              for category, ids in sorted(columns.items())], "rows": rows,
            "manifest": {"kind": "deterministic_code", "method_version": version, "analysis_unit": "utterance",
                         "scope": "selected" if selected else "all_included", "row_field": "speaker",
                         "label_field": field, "evidence_ids": [row["evidence_id"] for row in evidence],
                         "dataset_version": task["dataset_version"], "annotation_version": task["annotation_version"],
                         "codebook_version": task["codebook_version"]},
            "limitations": ["既存の話者ID×指定ラベルだけを集計します。人物属性やラベルを推定しません。",
                            "話者またはラベルの欠測がある発話は組の度数から除外し、欠測数を別に示します。",
                            "行内割合の分母はラベル欠測を含む当該話者の対象発話数です。全件欠測の行は割合を算出しません。",
                            "列内割合の分母は当該ラベルを持つ話者既知の発話数です。全体割合の分母は対象全発話数です。",
                            "複数ラベルは各ラベルへ1発話1回計上するため、行の度数・割合の合計は行の発話数・100%を超える場合があります。",
                            "記述集計です。有意差検定、人物単位の独立性、因果関係は示しません。"]}
