"""Save analysis results as immutable runs in the AnalysisStore.

Each archive_* function turns one kind of result (text analysis, segment
classification, AI finishing, meeting minutes, interview comparison) into
the store's snapshot/result/datasets contract."""

from __future__ import annotations

import hashlib
import os
import sqlite3
from collections import Counter
from typing import Any, Callable

from .. import method_experts, transcript_preparation as preparation
from ..ai_finishing import FINISHING_VERSION, finishing_changes
from ..analysis_insights import INSIGHT_VERSION, KWIC_FIELDS
from ..analysis_method_registry import method_results
from ..analysis_store import AnalysisStore, digest as archive_digest
from ..jev_review import (
    JEV_DEFAULT_MODEL,
    JEV_REVIEW_VERSION,
    comparison_rows as jev_comparison_rows,
)
from ..segment_classification import (
    DIALOGUE_ACTS,
    SEGMENT_CLASSIFICATION_VERSION,
    summary as segment_classification_summary,
    topic_candidates as segment_classification_topic_candidates,
)
from ..text_utils import json_load
from .group_analysis import (
    ANALYSIS_CSV_FIELDS,
    analysis_csv_rows,
    row_analysis_annotations,
    row_analysis_config,
)
from .library_rows import row_meeting_minutes
from .meeting_minutes import MEETING_MINUTES_VERSION


def make_analysis_archive(
    *,
    analysis_archive_store: Any,
    database_connection: Any,
    row_segments: Any,
    row_session_profile: Any,
) -> tuple[Callable[..., Any], ...]:
    def archive_source_stamp(row) -> str:
        with database_connection() as connection:
            registry = connection.execute("SELECT value FROM application_metadata WHERE key='speaker_registry_revision'").fetchone()
            prep_revision, _ = preparation.load_state(connection, row["id"])
        keys = ("id", "source_name", "segments_json", "speaker_names_json", "speaker_profiles_json",
                "session_profile_json", "outline_json", "emotion_analysis_json", "revision_count",
                "analysis_revision", "analysis_config_json", "analysis_annotations_json")
        return archive_digest({"source": {key: row[key] for key in keys},
                               "preparation_revision": prep_revision,
                               "registry_revision": registry[0] if registry else "0"})

    def archive_snapshot(row, analysis: dict) -> dict:
        return {"title": str(row["source_name"]), "conversation_id": str(row["id"]),
                "source_revision": int(row["revision_count"]), "analysis_revision": int(row["analysis_revision"]),
                "segments": analysis["segments"], "config": analysis.get("config", {}),
                "annotations": analysis.get("annotations", {}),
                "preparation": analysis.get("manual", {}).get("preparation", {}),
                "speakers": analysis.get("automatic", {}).get("speaker_metrics", []),
                "original_source": {"segments": row_segments(row),
                                    "speaker_names": json_load(row["speaker_names_json"], {}),
                                    "speaker_profiles": json_load(row["speaker_profiles_json"], {}),
                                    "session_profile": row_session_profile(row)}}

    def archive_group_analysis(row, analysis: dict, request_id: str, *, kind: str = "text_analysis",
                               kwic: dict | None = None, app_url: str = "http://127.0.0.1:7860",
                               check_cancelled: Callable[[], None] = lambda: None,
                               store: AnalysisStore | None = None) -> dict:
        datasets = {name: analysis_csv_rows(analysis, name) for name in ANALYSIS_CSV_FIELDS}
        if kwic is not None:
            datasets = {"kwic": (KWIC_FIELDS, kwic["hits"])}
        outline = json_load(row["outline_json"], None)
        ai = analysis.get("insights", {}).get("ai") or {}
        methods = method_results(analysis, datasets, outline=outline, kwic=kwic)
        if kwic is not None: methods = [m for m in methods if m["method_id"] == "kwic"]
        expert_hashes = method_experts.attach_method_reviews(methods, analysis)
        expert_hashes.update(method_experts.knowledge_hashes(analysis.get("experts")))
        parameters: dict[str, Any] = ({key: kwic[key] for key in ("query", "mode", "speaker")}
                                      if kwic is not None else analysis["config"])
        algorithms = {"automatic": analysis.get("algorithm_version"),
                      "insights": INSIGHT_VERSION, "finishing": FINISHING_VERSION,
                      "research": analysis.get("research", {}).get("algorithm_version"),
                      "engine": analysis.get("research", {}).get("linguistics", {}).get("engine", {}),
                      "experts": dict(sorted(expert_hashes.items()))}
        if kind == "transformer_topics":
            transformer_result = analysis.get("transformer", {}).get("result") or {}
            parameters = {"analysis": analysis["config"],
                          "transformer": transformer_result.get("parameters", {})}
            algorithms["transformer"] = transformer_result.get("algorithm_version", "")
        result = {"schema_version": 1, "parameters": parameters,
                  "algorithms": algorithms,
                  "ai_request_id": ai.get("request_id", ""), "methods": methods,
                  "analysis": analysis if kwic is None else {"kwic": kwic}}
        return (store or analysis_archive_store()).save(item_id=str(row["id"]), kind=kind,
            snapshot=archive_snapshot(row, analysis), result=result, datasets=datasets,
            request_id=request_id, input_fingerprint=archive_source_stamp(row),
            source_revision=int(row["revision_count"]), analysis_revision=int(row["analysis_revision"]),
            app_url=app_url, provider=ai.get("provider", "") if kind == "ai_insights" else "",
            model=ai.get("model", "") if kind == "ai_insights" else "", check_cancelled=check_cancelled)

    def archive_segment_classification(
        row: sqlite3.Row, analysis: dict[str, Any], classification: dict[str, Any],
        request_id: str, *, app_url: str = "http://127.0.0.1:7860",
    ) -> dict[str, Any]:
        """Persist one immutable proposal run without changing manual annotations."""
        analysis_with_result = dict(analysis)
        analysis_with_result["segment_classification"] = {
            "result": classification,
            "stale": False,
            "summary": segment_classification_summary(classification),
            "dialogue_acts": DIALOGUE_ACTS,
        }
        datasets = {
            name: analysis_csv_rows(analysis_with_result, name)
            for name in ("segment_classifications", "segment_classification_crosstabs")
        }
        classification_state = analysis_with_result["segment_classification"]
        methods = method_results(
            analysis_with_result, datasets, classification=classification_state
        )
        methods = [value for value in methods if value["method_id"] == "segment_classification"]
        llm_source = (classification.get("sources") or {}).get("llm") or {}
        usage = llm_source.get("usage") or {}
        result = {
            "schema_version": 1,
            "parameters": {
                "use_jev": bool(llm_source.get("available")),
                "topic_candidate_count": len(segment_classification_topic_candidates(
                    analysis.get("config", {}).get("codebook", [])
                )),
                "classification_fingerprint": str(classification.get("fingerprint") or ""),
            },
            "algorithms": {
                "segment_classification": SEGMENT_CLASSIFICATION_VERSION,
                "template": SEGMENT_CLASSIFICATION_VERSION,
                "transformer": ((classification.get("sources") or {}).get("transformer") or {}).get("algorithm_version", ""),
            },
            "methods": methods,
            "classification": classification,
            "usage": usage,
        }
        return analysis_archive_store().save(
            item_id=str(row["id"]), kind="segment_classification",
            snapshot=archive_snapshot(row, analysis_with_result), result=result,
            datasets=datasets, request_id=request_id,
            input_fingerprint=archive_source_stamp(row),
            source_revision=int(row["revision_count"]),
            analysis_revision=int(row["analysis_revision"]), app_url=app_url,
            provider="typesafe" if llm_source.get("available") else "",
            model=str(usage.get("model") or ""),
        )

    def archive_ai_finishing(row, original_segments: list[dict], stages: dict, provider: str,
                             model: str, usage: dict, context_outline: dict | None = None,
                             jev_usage: dict | None = None,
                             request_id: str | None = None) -> dict:
        segments = row_segments(row)
        names = json_load(row["speaker_names_json"], {})
        display = [{**s, "speaker_name": names.get(s.get("speaker"), s.get("speaker", "UNKNOWN"))} for s in segments]
        jev_rows = jev_comparison_rows(segments)
        agreement_counts = Counter(str(row.get("agreement") or "") for row in jev_rows)
        jev_details = ({
            "review_version": JEV_REVIEW_VERSION,
            "model": str(jev_rows[0].get("jev_model") or JEV_DEFAULT_MODEL),
            "usage": jev_usage or {},
            "decision_labels": ["correction_needed", "no_correction_needed"],
            "reviewed_segment_count": len(jev_rows),
            "agreement_counts": dict(agreement_counts),
        } if jev_rows else {})
        details = {"prompt_version": FINISHING_VERSION, "provider": provider, "model": model,
                   "usage": usage, "stages": stages, "original_segments": original_segments,
                   "changes": finishing_changes(original_segments, segments),
                   "context_outline": context_outline, "jev_comparison": jev_details}
        datasets = {"ai_changes": (["segment_id", "start", "end", "before_text", "after_text",
                                     "before_speaker", "after_speaker", "noise_candidate", "review_reason"], details["changes"])}
        if jev_rows:
            datasets["ai_jev_comparison"] = ([
                "segment_id", "start", "end", "speaker", "original_text", "current_text",
                "current_ai_flagged", "jev_flagged", "agreement", "jev_decision",
                "correction_needed_probability", "jev_confidence", "jev_model",
            ], jev_rows)
        cautions = ["AI仕上げは自動処理です。修正前の原文と比較して確認してください。"]
        if jev_rows:
            cautions.append(
                "Jevは音声ではなく文字起こしと会話文脈だけで修正要否を二択判定します。候補は原音で確認してください。"
            )
        analysis = {"segments": display, "config": row_analysis_config(row),
                    "annotations": row_analysis_annotations(row, segments, row_analysis_config(row)),
                    "cautions": cautions}
        outline = json_load(row["outline_json"], None)
        methods = [m for m in method_results(analysis, datasets, outline=outline, finishing=details)
                   if m["method_id"] in {"ai_finishing", "outline"}]
        algorithms = {"finishing": FINISHING_VERSION}
        if jev_rows:
            algorithms["jev_review"] = JEV_REVIEW_VERSION
        result = {"schema_version": 1, "methods": methods, "parameters": {"stages": stages},
                  "algorithms": algorithms, "finishing": details, "outline": outline}
        port = os.environ.get("MOJIOKOSI_PORT", "7860")
        if not port.isdigit() or not 1 <= int(port) <= 65535: port = "7860"
        return analysis_archive_store().save(item_id=str(row["id"]), kind="ai_finishing",
            snapshot=archive_snapshot(row, analysis), result=result, datasets=datasets,
            request_id=request_id or "finishing-" + str(row["id"]), input_fingerprint=archive_source_stamp(row),
            source_revision=int(row["revision_count"]), analysis_revision=int(row["analysis_revision"]),
            provider=provider, model=model, app_url=f"http://127.0.0.1:{port}")

    def archive_app_url() -> str:
        port = os.environ.get("MOJIOKOSI_PORT", "7860")
        return f"http://127.0.0.1:{port if port.isdigit() and 1 <= int(port) <= 65535 else '7860'}"

    def archive_meeting_minutes(row) -> dict | None:
        """Save meeting minutes as their own run, never inside the conversation's text analysis."""
        minutes = row_meeting_minutes(row)
        if row_session_profile(row).get("session_type") != "meeting" or not (
                minutes["tasks"] or minutes["decisions"] or minutes["summary"]
                or minutes["analysis"]["speaker_activity"]):
            return None
        segments = row_segments(row)
        names = json_load(row["speaker_names_json"], {})
        config = row_analysis_config(row)
        analysis = {"segments": [{**s, "speaker_name": names.get(s.get("speaker"), s.get("speaker", "UNKNOWN"))}
                                 for s in segments],
                    "config": config, "annotations": row_analysis_annotations(row, segments, config)}
        datasets = {
            "meeting_tasks": (["task_id", "title", "owner", "priority", "due_date", "due_text", "status", "confidence",
                               "evidence_segment_id", "evidence_start", "evidence_end", "source_text"], minutes["tasks"]),
            "meeting_decisions": (["decision_id", "text", "speaker", "evidence_segment_id", "evidence_start",
                                   "evidence_end"], minutes["decisions"]),
            "meeting_speaker_activity": (["speaker", "turns", "seconds"], minutes["analysis"]["speaker_activity"]),
        }
        methods = [m for m in method_results(analysis, datasets, meeting=minutes) if m["method_id"] == "meeting_minutes"]
        result = {"schema_version": 1, "methods": methods,
                  "parameters": {"method": minutes.get("method", ""), "version": minutes.get("version", "")},
                  "algorithms": {"meeting_minutes": MEETING_MINUTES_VERSION}, "meeting_minutes": minutes}
        stamp = archive_source_stamp(row)
        return analysis_archive_store().save(item_id=str(row["id"]), kind="meeting_minutes",
            snapshot=archive_snapshot(row, analysis), result=result, datasets=datasets,
            request_id="meeting-" + archive_digest({"source": stamp, "minutes": minutes})[:40],
            input_fingerprint=stamp, source_revision=int(row["revision_count"]),
            analysis_revision=int(row["analysis_revision"]), app_url=archive_app_url())

    def interview_comparison_datasets(comparison: dict[str, Any]) -> dict[str, tuple[list[str], list[dict]]]:
        """Long-format tables: one row per interview, so every value keeps its conversation ID."""
        def spread(rows: list[dict], label: str, summary: str) -> list[dict]:
            return [{label: row.get(label), summary: row.get(summary), **value}
                    for row in rows for value in row.get("interviews", [])]
        return {
            "comparison_interviews": (["item_id", "source_name", "comparison_label", "comparison_source", "session_type",
                                       "session_date", "objective", "included_segment_count", "speaker_count",
                                       "participant_count", "session_duration", "total_speaking_seconds", "term_count",
                                       "excluded_segment_count"], comparison.get("interviews", [])),
            "comparison_common_terms": (["term", "minimum_count", "item_id", "count", "rate_per_1000_terms"],
                                        spread(comparison.get("common_terms", []), "term", "minimum_count")),
            "comparison_characteristic_terms": (["item_id", "source_name", "term", "count", "rate_per_1000_terms",
                                                 "other_count", "other_rate_per_1000_terms", "difference_per_1000_terms"],
                                                comparison.get("characteristic_terms", [])),
            "comparison_codes": (["code", "max_count", "item_id", "count", "rate_per_100_segments"],
                                 spread(comparison.get("code_comparison", []), "code", "max_count")),
            "comparison_emotions": (["emotion", "max_count", "item_id", "count", "rate_per_100_segments"],
                                    spread(comparison.get("emotion_comparison", []), "emotion", "max_count")),
        }

    def archive_interview_comparison(rows: list, comparison: dict[str, Any], request_id: str, *,
                                     app_url: str, store: AnalysisStore | None = None) -> dict:
        """Save a group-interview comparison as one multi-conversation run, apart from each interview's runs."""
        item_ids = [str(row["id"]) for row in rows]
        group_id = "comparison-" + hashlib.sha256("\n".join(sorted(item_ids)).encode("utf-8")).hexdigest()[:24]
        members = [{"conversation_id": str(row["id"]), "title": str(row["source_name"]),
                    "source_revision": int(row["revision_count"] or 0),
                    "analysis_revision": int(row["analysis_revision"] or 0),
                    "input_fingerprint": archive_source_stamp(row)} for row in rows]
        datasets = interview_comparison_datasets(comparison)
        methods = [m for m in method_results({"segments": [], "config": {}}, datasets, comparison=comparison)
                   if m["method_id"] == "interview_comparison"]
        expert_hashes = method_experts.attach_method_reviews(
            methods, {"segments": [], "config": {}}, context={"session_count": len(comparison.get("interviews", []))})
        allow_different = bool(comparison.get("allow_different_content"))
        snapshot = {"title": "グループインタビュー比較：" + " / ".join(member["title"] for member in members),
                    "conversation_id": group_id, "kind": "interview_comparison", "members": members,
                    "allow_different_content": allow_different,
                    "comparison_key": comparison.get("comparison_key", ""), "segments": []}
        result = {"schema_version": 1, "methods": methods,
                  "parameters": {"item_ids": item_ids, "allow_different_content": allow_different},
                  "algorithms": {"interview_comparison": comparison.get("schema_version", 1), "experts": expert_hashes},
                  "comparison": comparison}
        return (store or analysis_archive_store()).save(item_id=group_id, kind="interview_comparison", snapshot=snapshot,
            result=result, datasets=datasets, request_id=request_id,
            input_fingerprint=archive_digest([member["input_fingerprint"] for member in members]),
            source_revision=0, analysis_revision=0, app_url=app_url, member_ids=item_ids)

    def refresh_archive_index(item_id: str) -> None:
        # Vault failure must not undo a successful transcript/configuration edit.
        try:
            analysis_archive_store().publish_index(item_id)
        except (OSError, ValueError, LookupError, sqlite3.Error):
            with database_connection() as connection:
                connection.execute("UPDATE analysis_runs SET vault_status='conflict',error='原文は保存済みですが、Vaultの更新確認が必要です。' WHERE item_id=? AND status='completed'", (item_id,))

    return (
        archive_source_stamp,
        archive_snapshot,
        archive_group_analysis,
        archive_segment_classification,
        archive_ai_finishing,
        archive_app_url,
        archive_meeting_minutes,
        interview_comparison_datasets,
        archive_interview_comparison,
        refresh_archive_index,
    )
