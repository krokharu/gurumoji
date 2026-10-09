"""Descriptive comparison across interview sessions."""

from __future__ import annotations

import sqlite3
from collections import Counter
from typing import Any, Callable


def comparison_rate(count: int | float, denominator: int | float) -> float:
    return round(1000 * float(count) / float(denominator), 2) if denominator else 0.0


def _emotion_model_id(entry: Any) -> str | None:
    """Accept only the current projection's actual model key and valid label."""
    if not isinstance(entry, dict):
        return None
    model_id = entry.get("model")
    if (not isinstance(model_id, str) or not model_id.strip()
            or model_id != model_id.strip() or model_id.casefold() == "unknown"):
        return None
    labels = [entry.get(key) for key in ("label", "label_ja")]
    if any(value is not None and not isinstance(value, str) for value in labels):
        return None
    if not any(isinstance(value, str) and value.strip() for value in labels):
        return None
    name = entry.get("model_name")
    if name is not None and not isinstance(name, str):
        return None
    return model_id


def _emotion_observations(
    projections: list[tuple[list[dict[str, Any]], dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Describe observable predictions, never inference execution or emotion absence.

    Catalog identity comes only from actual model keys in included turn details.
    Empty arrays are valid current projections; missing/legacy/malformed details
    cannot establish counts. Conflicting display names leave a model unresolved,
    rather than choosing a name or merging different IDs with the same name.
    """
    model_names: dict[str, set[str]] = {}
    for included, _quality in projections:
        for segment in included:
            details = segment.get("emotion_details")
            if not isinstance(details, list):
                continue
            for entry in details:
                model_id = _emotion_model_id(entry)
                if model_id is not None:
                    names = model_names.setdefault(model_id, set())
                    name = entry.get("model_name")
                    if isinstance(name, str) and name.strip():
                        names.add(name.strip())
    catalog = {
        model_id: next(iter(names)) if names else None
        for model_id, names in sorted(model_names.items()) if len(names) <= 1
    }
    results = []
    for included, quality in projections:
        seen_ids: set[str] = set()
        observed: Counter[str] = Counter()
        any_observed = 0
        known = True
        for segment in included:
            turn_id = segment.get("id")
            if (not isinstance(turn_id, str) or not turn_id.strip()
                    or turn_id != turn_id.strip() or turn_id in seen_ids):
                known = False
            else:
                seen_ids.add(turn_id)
            details = segment.get("emotion_details")
            if not isinstance(details, list):
                known = False
                continue
            models = set()
            for entry in details:
                model_id = _emotion_model_id(entry)
                if model_id is None or model_id not in catalog:
                    known = False
                else:
                    models.add(model_id)
            # Multiple labels or repeated details on one turn count only once.
            observed.update(models)
            any_observed += bool(models)

        def counts(count: int) -> dict[str, Any]:
            return {
                "observed_count": count if known else None,
                "missing_prediction_count": len(included) - count if known else None,
                # An empty target is inapplicable, not evidence of a model result.
                "status": ("not_applicable" if not included else "known" if known else "unknown"),
                "source": "analysis.segments[].emotion_details" if known else "unknown",
            }

        percent = quality.get("emotion_coverage_percent")
        valid_percent = (type(percent) in (int, float) and 0 <= percent <= 100)
        results.append({
            "version": 1,
            "target_scope": "included_nonempty_segments",
            "target_count": len(included),
            "any_model": counts(any_observed),
            "models": [
                {"model_id": model_id, "model_name": name, **counts(observed[model_id])}
                for model_id, name in catalog.items()
            ],
            "legacy_any_model_coverage": {
                "percent": percent if valid_percent else None,
                "scope": "all_timeline_segments",
                "source": ("analysis.automatic.data_quality.emotion_coverage_percent"
                           if valid_percent else "unknown"),
            },
        })
    return results


def build_interview_comparison(
    rows: list[sqlite3.Row], *, allow_different_content: bool,
    row_session_profile: Callable[[sqlite3.Row], dict[str, str]],
    interview_comparison_identity: Callable[[dict[str, Any]], tuple[str, str, str]],
    group_analysis_for_row: Callable[[sqlite3.Row], dict[str, Any]],
    text_mining_counter: Callable[..., Counter[str]],
) -> dict[str, Any]:
    """Build a descriptive, evidence-preserving comparison across sessions.

    The calculation intentionally compares normalised descriptive measures, not
    participant-level hypothesis tests: turns within a group interview are not
    independent samples.  This keeps the result useful without overstating
    what a cross-session transcript comparison can establish.
    """
    profiles = [row_session_profile(row) for row in rows]
    identities = [interview_comparison_identity(profile) for profile in profiles]
    keys = [identity[0] for identity in identities]
    same_content = bool(keys and keys[0]) and all(key == keys[0] for key in keys)
    if not allow_different_content and not same_content:
        raise ValueError(
            "通常比較では、全インタビューに同じ「比較グループ」を設定してください。"
            "既存データは質問ガイドが完全一致する場合のみ自動照合されます。"
            "異なる内容を比較する場合は、画面のチェックを入れてください。"
        )

    interviews: list[dict[str, Any]] = []
    term_counters: dict[str, Counter[str]] = {}
    term_totals: dict[str, int] = {}
    code_counts: dict[str, dict[str, int]] = {}
    emotion_counts: dict[str, dict[str, int]] = {}
    emotion_projections: list[tuple[list[dict[str, Any]], dict[str, Any]]] = []

    for row, profile, identity in zip(rows, profiles, identities):
        analysis = group_analysis_for_row(row)
        item_id = str(row["id"])
        included = [
            segment for segment in analysis["segments"]
            if not segment.get("excluded") and str(segment.get("text") or "").strip()
        ]
        emotion_projections.append((included, analysis["automatic"]["data_quality"]))
        counter = text_mining_counter(
            included, set(analysis["config"].get("stop_words") or [])
        )
        term_counters[item_id] = counter
        term_totals[item_id] = sum(counter.values())
        overview = analysis["automatic"]["overview"]
        interviews.append({
            "item_id": item_id,
            "source_name": str(row["source_name"]),
            "comparison_label": identity[1],
            "comparison_source": identity[2],
            "session_type": profile.get("session_type", "focus_group"),
            "session_date": profile.get("session_date", ""),
            "objective": profile.get("objective", ""),
            "included_segment_count": len(included),
            "speaker_count": int(overview.get("speaker_count") or 0),
            "participant_count": overview.get("participant_count"),
            "observed_participant_count": overview.get("observed_participant_count"),
            "session_duration": overview.get("session_duration"),
            "session_timed_turn_count": overview.get("session_timed_turn_count"),
            "session_missing_time_turn_count": overview.get("session_missing_time_turn_count"),
            "total_speaking_seconds": overview.get("total_speaking_seconds"),
            "timed_turn_count": overview.get("timed_turn_count"),
            "missing_time_turn_count": overview.get("missing_time_turn_count"),
            "term_count": term_totals[item_id],
            "excluded_segment_count": int(
                analysis["automatic"]["data_quality"].get("excluded_segments") or 0
            ),
        })
        code_counts[item_id] = {
            str(code.get("label") or code.get("id") or "未設定"):
            int(code.get("segment_count") or 0)
            for code in analysis["manual"].get("code_metrics", [])
            if int(code.get("segment_count") or 0) > 0
        }
        emotions: Counter[str] = Counter()
        for emotion in analysis["automatic"].get("emotions", []):
            model = str(emotion.get("model_name") or emotion.get("model") or "感情モデル")
            label = str(emotion.get("emotion") or emotion.get("label") or "未設定")
            emotions[f"{model}: {label}"] += int(emotion.get("count") or 0)
        emotion_counts[item_id] = dict(emotions)

    for item, observation in zip(interviews, _emotion_observations(emotion_projections)):
        item["emotion_observation"] = observation

    item_ids = [item["item_id"] for item in interviews]
    common_terms: list[dict[str, Any]] = []
    if term_counters:
        shared = set.intersection(*(set(counter) for counter in term_counters.values()))
        for term in shared:
            counts = [term_counters[item_id][term] for item_id in item_ids]
            if min(counts) < 2:
                continue
            common_terms.append({
                "term": term,
                "minimum_count": min(counts),
                "interviews": [
                    {
                        "item_id": item_id,
                        "count": term_counters[item_id][term],
                        "rate_per_1000_terms": comparison_rate(
                            term_counters[item_id][term], term_totals[item_id]
                        ),
                    }
                    for item_id in item_ids
                ],
            })
    common_terms.sort(key=lambda value: (-value["minimum_count"], value["term"]))

    characteristic_terms: list[dict[str, Any]] = []
    all_terms = set().union(*(set(counter) for counter in term_counters.values()))
    for item in interviews:
        item_id = item["item_id"]
        other_ids = [candidate for candidate in item_ids if candidate != item_id]
        # Keep the per-term calculation explicit: the other-session denominator
        # is the sum of every selected transcript, not the number of sessions.
        other_total = sum(term_totals[candidate] for candidate in other_ids)
        for term in all_terms:
            count = term_counters[item_id][term]
            if count < 2:
                continue
            other_count = sum(term_counters[candidate][term] for candidate in other_ids)
            own_rate = comparison_rate(count, term_totals[item_id])
            other_rate = comparison_rate(other_count, other_total)
            characteristic_terms.append({
                "item_id": item_id,
                "source_name": item["source_name"],
                "term": term,
                "count": count,
                "rate_per_1000_terms": own_rate,
                "other_count": other_count,
                "other_rate_per_1000_terms": other_rate,
                "difference_per_1000_terms": round(own_rate - other_rate, 2),
            })
    characteristic_terms.sort(
        key=lambda value: (-abs(value["difference_per_1000_terms"]), -value["count"], value["term"])
    )

    def categorical_rows(
        values_by_item: dict[str, dict[str, int]], *, key: str,
    ) -> list[dict[str, Any]]:
        labels = set().union(*(set(values) for values in values_by_item.values()))
        result = []
        for label in labels:
            counts = [int(values_by_item[item_id].get(label, 0)) for item_id in item_ids]
            if not any(counts):
                continue
            result.append({
                key: label,
                "interviews": [
                    {
                        "item_id": item_id,
                        "count": int(values_by_item[item_id].get(label, 0)),
                        "rate_per_100_segments": comparison_rate(
                            values_by_item[item_id].get(label, 0),
                            next(item["included_segment_count"] for item in interviews if item["item_id"] == item_id),
                        ) / 10,
                    }
                    for item_id in item_ids
                ],
                "max_count": max(counts),
            })
        return sorted(result, key=lambda value: (-value["max_count"], value[key]))[:20]

    mode = "same_content" if same_content else "different_content"
    cautions = [
        "発話・語・コードの割合は記述的な比較です。個々の発話を独立した標本として検定していません。",
        "発話時間や頻度の差だけで、重要性・原因・参加者全体への一般化を判断しないでください。",
    ]
    if mode == "different_content":
        cautions.insert(
            0,
            "内容が異なる比較です。共通語・特徴語は探索の手がかりであり、質問や対象者条件の差を統制した結論ではありません。",
        )
    return {
        "schema_version": 1,
        "mode": mode,
        "allow_different_content": allow_different_content,
        "same_content": same_content,
        "comparison_key": keys[0] if same_content else "",
        "interviews": interviews,
        "common_terms": common_terms[:20],
        "characteristic_terms": characteristic_terms[:30],
        "code_comparison": categorical_rows(code_counts, key="code"),
        "emotion_comparison": categorical_rows(emotion_counts, key="emotion"),
        "cautions": cautions,
    }
