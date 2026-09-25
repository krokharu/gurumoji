"""Adapters between the fixed analysis pipeline and the existing analyses.

The pipeline runs on an immutable snapshot of one conversation; these
functions build that snapshot, adapt existing methods to pipeline steps and
ask the O01 planning adviser (Transformer or an LLM) for a plan candidate."""

from __future__ import annotations

import sqlite3
from typing import Any, Callable

from .. import analysis_plan_advisor
from ..analysis_core import AnalysisContractError
from ..analysis_method_registry import method_results
from .group_analysis import analysis_csv_rows


PIPELINE_METHOD_DATASETS = {
    "participation": ("speakers", "groups", "summary", "observations"),
    "conversation_dynamics": ("transitions", "gaps", "overlaps", "timeline"),
}


def run_analysis_pipeline_method(step_id: str, snapshot: dict[str, Any]) -> dict[str, Any]:
    """Adapt one existing method to the fixed pipeline snapshot."""
    if step_id not in PIPELINE_METHOD_DATASETS:
        raise ValueError("未対応の分析stepです。")
    analysis = snapshot["analysis"]
    datasets = {
        name: analysis_csv_rows(analysis, name)
        for name in PIPELINE_METHOD_DATASETS[step_id]
    }
    methods = method_results(analysis, datasets)
    method = next((value for value in methods if value["method_id"] == step_id), None)
    if method is None:
        raise ValueError(f"{step_id}の既存分析結果を構築できません。")
    return {
        "method": method,
        "datasets": {
            name: {"fields": fields, "rows": rows}
            for name, (fields, rows) in datasets.items()
        },
    }


def make_analysis_pipeline_adapters(
    *,
    archive_snapshot: Any,
    archive_source_stamp: Any,
    call_ai_json: Any,
    configured_ai_credentials: Any,
    encode_transformer_texts: Any,
    group_analysis_for_row: Any,
    load_token_config: Any,
) -> tuple[Callable[..., Any], ...]:
    def build_analysis_pipeline_snapshot(row: sqlite3.Row) -> dict[str, Any]:
        """Capture one immutable input and its existing-analysis adapter view."""
        analysis = group_analysis_for_row(row, include_research_rows=True)
        return {
            "schema_version": 1,
            "input_hash": archive_source_stamp(row),
            "source_revision": int(row["revision_count"] or 0),
            "analysis_revision": int(row["analysis_revision"] or 0),
            "analysis": analysis,
            "archive_snapshot": archive_snapshot(row, analysis),
        }

    def advise_analysis_plan(snapshot: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
        """Run the selected O01 adviser on a small, nonverbatim context packet."""
        context = analysis_plan_advisor.planning_context(
            snapshot["analysis"], payload.get("objective", "")
        )
        if context["included_segment_count"] < 1:
            raise AnalysisContractError("分析できる発話がありません。", code="no_valid_input")
        engine = payload.get("engine", "transformer")
        policy = payload.get("provider_policy", "local_only")
        if not isinstance(policy, str) or policy not in {"local_only", "cloud_allowed"}:
            raise AnalysisContractError("送信方針が正しくありません。", code="provider_unavailable")
        if engine == "transformer":
            if policy != "local_only":
                raise AnalysisContractError("Transformer計画候補はlocal_onlyで生成してください。", code="provider_unavailable")
            candidate, model_info = analysis_plan_advisor.transformer_candidate(
                context, encode_transformer_texts
            )
            provider, model = "local_transformer", model_info["name"]
        elif engine == "llm":
            provider = payload.get("provider", "lmstudio")
            if not isinstance(provider, str) or provider not in {"lmstudio", "openai", "google"}:
                raise AnalysisContractError("計画担当のLLMを選択してください。", code="provider_unavailable")
            if provider == "lmstudio" and policy != "local_only":
                raise AnalysisContractError("ローカルLLMはlocal_onlyで生成してください。", code="provider_unavailable")
            if provider != "lmstudio" and policy != "cloud_allowed":
                raise AnalysisContractError("クラウドLLMにはcloud_allowedが必要です。", code="provider_unavailable")
            config = load_token_config()
            api_key, configured_model = configured_ai_credentials(config, provider)
            model = payload.get("model") or configured_model
            if not isinstance(model, str) or not model.strip() or len(model) > 200 or "\n" in model or "\r" in model:
                raise AnalysisContractError("計画担当のモデルを指定してください。", code="provider_unavailable")
            model = model.strip()
            if provider != "lmstudio" and not api_key:
                raise AnalysisContractError("選択したLLMのAPIキーが未設定です。", code="provider_unavailable")
            base_url = config.lmstudio_base_url if provider == "lmstudio" else ""
            candidate = analysis_plan_advisor.llm_candidate(
                context,
                lambda system, prompt, schema: call_ai_json(
                    provider, api_key, model, system, prompt, "analysis_plan_o01", schema,
                    base_url=base_url,
                ),
            )
        else:
            raise AnalysisContractError("計画担当のエンジンが正しくありません。", code="method_unavailable")
        return {
            "version": analysis_plan_advisor.ADVISOR_VERSION,
            "source_revision": snapshot["source_revision"],
            "analysis_revision": snapshot["analysis_revision"],
            "input_hash": snapshot["input_hash"],
            "objective": context["objective"],
            "engine": engine, "provider": provider, "model": model,
            **candidate,
        }

    return (build_analysis_pipeline_snapshot, advise_analysis_plan)
