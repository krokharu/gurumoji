from __future__ import annotations

import copy
import math
from typing import Any

from .analysis_core import canonical, validate_publication_targets, EFFECTIVE_PUBLICATION_WRITERS
from .analysis_templates import selection_valid
from .services.orchestration_required_methods import validate_required_methods
from .orchestration_shared import AI_ROLES, IMPORTANCE, _error

def validate_orchestration_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise _error("分析設定はオブジェクトで指定してください。")
    if payload.get("research_mode", payload.get("research_protocol", "exploratory")) != "exploratory":
        raise _error("この実装は探索分析専用です。隔離検証データを伴う確認分析には未対応です。", "confirmatory_unavailable")
    question = payload.get("question", payload.get("objective", "会話の特徴と代替説明を根拠付きで分析する"))
    if not isinstance(question, str) or not question.strip() or len(question) > 8000:
        raise _error("分析する問いを指定してください。", field="question")
    mode = payload.get("stop_mode", "auto")
    if mode not in {"time", "iterations", "importance", "auto"}:
        raise _error("終了モードが正しくありません。", field="stop_mode")
    config = {"question": question.strip(), "stop_mode": mode, "research_mode": "exploratory",
              "provider": payload.get("provider", "lmstudio"), "model": payload.get("model", ""),
              "provider_policy": payload.get("provider_policy", "local_only"),
              "cloud_consent": payload.get("cloud_consent") is True,
              "adapter_version": payload.get("adapter_version", "core-handler-prompts-1"),
              "core_progress_version": payload.get("core_progress_version", 0),
               "core_control_version": payload.get("core_control_version", 0),
              "initial_label_definitions_version": payload.get("initial_label_definitions_version", 0),
              "initial_specialist_analysis_version": payload.get("initial_specialist_analysis_version", 0),
              "model_context_version": payload.get("model_context_version", 0),
              "context_reference_version": payload.get("context_reference_version", 0),
              "specialist_orchestration_version": payload.get("specialist_orchestration_version", 0),
              "metric_codec_version": payload.get("metric_codec_version", 0),
              "label_repair_limit": payload.get("label_repair_limit", 0),
              "local_reasoning": payload.get("local_reasoning", "auto"),
              'evidence_mode': payload.get('evidence_mode', 'sql'),
              "expert_step_ids": payload.get("expert_step_ids"),
              "template_version": payload.get("template_version", "existing-analysis-v1"),
              "template_config": payload.get("template_config", {}), "roles": payload.get("roles", {}),
              "importance_threshold": payload.get("importance_threshold", "medium"),
              "min_iterations": 3 if mode == "auto" and not payload.get("specialist_orchestration_version") else 0,
              "max_iterations": payload.get("max_iterations", None if mode == "auto" else 5),
              "time_limit_seconds": payload.get("time_limit_seconds", None if mode == "auto" else 300),
              "max_calls": payload.get("max_calls", 24), "max_tasks": payload.get("max_tasks", 40),
              "concurrency": payload.get("concurrency", 2),
              "call_timeout_seconds": payload.get("call_timeout_seconds", 120),
              "max_result_bytes": payload.get("max_result_bytes", 2_000_000),
              "max_cost": payload.get("max_cost"),
              "context_index_limit": payload.get("context_index_limit", 0),
              "context_evidence_limit": payload.get("context_evidence_limit", 120),
              "context_text_limit": payload.get("context_text_limit", 60000)}
    config["analysis_interval_version"] = payload.get("analysis_interval_version", 0)
    config["artifact_review_version"] = payload.get("artifact_review_version", 0)
    if "required_methods" in payload:
        config["required_methods"] = validate_required_methods(payload["required_methods"])
        if config["required_methods"] and not (config["specialist_orchestration_version"] and config["core_progress_version"]):
            raise _error("必須分析には専門担当の評価を有効にしてください。", field="required_methods")
    source_id, human_prompt = payload.get("source_analysis_id"), payload.get("human_prompt")
    if source_id is not None or human_prompt is not None:
        if not isinstance(source_id, str) or not source_id.strip():
            raise _error("参照する分析IDを指定してください。", field="source_analysis_id")
        if not isinstance(human_prompt, str) or not human_prompt.strip() or len(human_prompt) > 8000:
            raise _error("追加プロンプトを8000文字以内で入力してください。", field="human_prompt")
        config.update(source_analysis_id=source_id.strip(), human_prompt=human_prompt.strip())
        for key in ("expected_source_result_id", "expected_source_raw_hash"):
            if key in payload:
                if not isinstance(payload[key], str) or not payload[key] or len(payload[key]) > 250:
                    raise _error("確認した参照結果のIDまたはhashが正しくありません。", field=key)
                config[key] = payload[key]
    if config["artifact_review_version"] and not (config["analysis_interval_version"] == 1
            and config["specialist_orchestration_version"] == 1):
        raise _error("先行所見の点検には固定区間と専門側の判断が必要です。", "artifact_input_invalid")
    if config["artifact_review_version"]:
        from .method_experts import counterexample_review_procedure
        procedure = counterexample_review_procedure()
        config["artifact_procedure"] = {k: procedure[k] for k in ("procedure_id", "version", "sha256")}
    config["analysis_interval_seconds"] = payload.get("analysis_interval_seconds", 300)
    for key, low, high in (("max_calls", 1, 10000), ("max_tasks", 1, 20000), ("concurrency", 1, 4),
                           ("core_progress_version", 0, 1),
                            ("core_control_version", 0, 1),
                           ("analysis_interval_version", 0, 1), ("analysis_interval_seconds", 1, 86400),
                           ("artifact_review_version", 0, 1),
                           ("label_repair_limit", 0, 1),
                           ("initial_label_definitions_version", 0, 1),
                            ("initial_specialist_analysis_version", 0, 1),
                            ("model_context_version", 0, 1),
                            ("context_reference_version", 0, 1),
                            ("specialist_orchestration_version", 0, 1),
                            ("metric_codec_version", 0, 1),
                           ("call_timeout_seconds", 1, 3600), ("max_result_bytes", 1000, 20_000_000),
                           ("context_evidence_limit", 1, 120), ("context_text_limit", 1, 60000)):
        if type(config[key]) is not int or not low <= config[key] <= high:
            raise _error(f"{key}は{low}〜{high}の整数です。", field=key)
    steps = config["expert_step_ids"]
    if steps is not None and (not isinstance(steps, list) or not 0 < len(steps) <= 30 or any(not isinstance(step, str) or not step for step in steps) or len(set(steps)) != len(steps)):
        raise _error("専門家の手順IDを重複のない配列で指定してください。", field="expert_step_ids")
    if type(config["context_index_limit"]) is not int or not 0 <= config["context_index_limit"] <= 120:
        raise _error("context_index_limitは0〜120の整数です。0は索引の省略なしです。", field="context_index_limit")
    for key in ("max_iterations", "time_limit_seconds"):
        value = config[key]
        if value is not None and (type(value) is not int or value < 1 or value > 864000):
            raise _error(f"{key}は正の整数またはnullです。", field=key)
    if mode == "time" and config["time_limit_seconds"] is None:
        raise _error("時間モードには時間上限が必要です。", field="time_limit_seconds")
    if mode == "iterations" and config["max_iterations"] is None:
        raise _error("回数モードには回数上限が必要です。", field="max_iterations")
    if mode == "auto" and config["max_iterations"] is not None and config["max_iterations"] < config["min_iterations"]:
        raise _error("AIお任せの回数上限は最低3回以上にしてください。", field="max_iterations")
    if config["importance_threshold"] not in IMPORTANCE:
        raise _error("重要度閾値が正しくありません。", field="importance_threshold")
    if not isinstance(config["template_version"], str) or not config["template_version"]:
        raise _error("テンプレート版を指定してください。", field="template_version")
    if not isinstance(config["template_config"], dict) or not isinstance(config["roles"], dict):
        raise _error("テンプレート設定と役割設定はオブジェクトで指定してください。")
    if not selection_valid(config["template_version"], config["template_config"]):
        raise _error("分析テンプレートのIDまたは版が正しくありません。", field="template_config")
    if config["max_cost"] is not None and (type(config["max_cost"]) not in {int, float}
            or not math.isfinite(config["max_cost"]) or config["max_cost"] <= 0):
        raise _error("費用上限は正の数です。", field="max_cost")
    if config["max_cost"] is not None:
        raise _error("実費用を確実に取得できないため金額上限には未対応です。呼出し数・タスク数上限を指定してください。", "cost_budget_unavailable")
    if config["provider_policy"] not in {"local_only", "cloud_allowed"}:
        raise _error("送信方針が正しくありません。", "provider_unavailable")
    if not isinstance(config["local_reasoning"], str) or config["local_reasoning"] not in {"auto", "off"}:
        raise _error("ローカルAIの追加推論はautoまたはoffを指定してください。", field="local_reasoning")
    from .services.evidence_retrieval import validate_mode
    validate_mode(config['evidence_mode'])
    for role in AI_ROLES:
        options = config["roles"].get(role, {})
        if not isinstance(options, dict):
            raise _error("役割設定が正しくありません。", field="roles")
        provider = options.get("provider", config["provider"])
        model = options.get("model", config["model"])
        if provider not in {"lmstudio", "openai", "google"}:
            raise _error("対応するLLMを選択してください。", "provider_unavailable")
        if provider != "lmstudio" and (config["provider_policy"] != "cloud_allowed" or not config["cloud_consent"]):
            raise _error("外部LLMの利用にはcloud_allowedが必要です。", "provider_unavailable")
        if not isinstance(model, str) or not model.strip() or len(model) > 200 or "\n" in model or "\r" in model:
            raise _error("実際に利用するモデル名を指定してください。", "provider_unavailable")
        config["roles"][role] = {"provider": provider, "model": model.strip()}
    config["publication_targets"] = validate_publication_targets(payload.get("publication_targets", []))
    config["effective_publication_writers"] = list(EFFECTIVE_PUBLICATION_WRITERS) if config["publication_targets"] else []
    canonical(config)
    if config["initial_specialist_analysis_version"] and not (config["initial_label_definitions_version"] and config["core_progress_version"]):
        raise _error("初回の全専門家分析には尺度出力と結果評価の契約が必要です。", "invalid_initial_contract")
    return copy.deepcopy(config)
