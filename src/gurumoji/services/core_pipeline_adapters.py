"""Coreパイプラインのprovider境界。同意・版・予算を確認して1回だけ送信する。"""
from __future__ import annotations

import copy
from typing import Any, Callable

from ..analysis_core import AnalysisContractError
from .pipeline_context import VERSION as ADAPTER_VERSION

AI_ROLES = ("core", "interpretation", "verification", "critic")
PROVIDERS = {"lmstudio", "openai", "google"}


def make_orchestration_adapters(*, call_ai_json: Callable[..., Any],
                                load_token_config: Callable[..., Any],
                                configured_ai_credentials: Callable[..., Any], transport_diagnostics: bool = False):
    def resolve(payload: dict[str, Any]) -> dict[str, Any]:
        """Preflight without calling models or persisting secrets."""
        if not isinstance(payload, dict):
            raise AnalysisContractError("実行条件をJSONオブジェクトで指定してください。")
        value = copy.deepcopy(payload)
        provider = value.get("provider", "lmstudio")
        policy = value.get("provider_policy", "local_only")
        if not isinstance(policy, str) or policy not in {"local_only", "cloud_allowed"}:
            raise AnalysisContractError("送信方針が正しくありません。", code="provider_unavailable")
        if "model" in value and not isinstance(value["model"], str):
            raise AnalysisContractError("モデルIDは文字列で指定してください。")
        overrides = value.get("roles", {})
        if not isinstance(overrides, dict) or any(role not in AI_ROLES for role in overrides):
            raise AnalysisContractError("モデル上書きはCore・会話解釈・独立検証・批判者だけに指定できます。")
        config = load_token_config()
        roles: dict[str, Any] = {}
        for role in AI_ROLES:
            override = overrides.get(role, {})
            if not isinstance(override, dict) or set(override) - {"provider", "model"}:
                raise AnalysisContractError("役割別のモデル設定が正しくありません。")
            if any(key in override and not isinstance(override[key], str) for key in ("provider", "model")):
                raise AnalysisContractError("役割別のモデル設定は文字列で指定してください。")
            selected = override.get("provider") or provider
            if not isinstance(selected, str) or selected not in PROVIDERS:
                raise AnalysisContractError("未対応のAIプロバイダーです。", code="provider_unavailable")
            if selected != "lmstudio" and (policy != "cloud_allowed" or value.get("cloud_consent") is not True):
                raise AnalysisContractError("会話原文・分析結果を選択したクラウドAIへ送信する同意が必要です。", code="provider_unavailable")
            key, configured_model = configured_ai_credentials(config, selected)
            model = override.get("model") or (value.get("model") if selected == provider else "") or configured_model
            if not isinstance(model, str) or not model.strip() or len(model) > 200 or any(ord(c) < 33 or ord(c) == 127 for c in model.strip()):
                raise AnalysisContractError("実際に使用するモデルIDを指定してください。", code="provider_unavailable")
            if selected != "lmstudio" and not key:
                raise AnalysisContractError("選択したAIのAPIキーが未設定です。", code="provider_unavailable")
            roles[role] = {"provider": selected, "model": model.strip()}
        value.update(provider=roles["core"]["provider"], model=roles["core"]["model"],
                     provider_policy=policy, roles=roles)
        return value

    def runner(role: str, context: dict[str, Any], options: dict[str, Any],
               check_cancelled: Callable[[], None], record_usage: Callable[[dict], None]) -> dict[str, Any]:
        if role not in AI_ROLES:
            raise AnalysisContractError("この役割はAI呼出しを許可されていません。")
        if options.get("adapter_version") != ADAPTER_VERSION:
            raise AnalysisContractError("保存時とAI実行契約の版が異なります。履歴を残して新しいrunを開始してください。", code="adapter_version_conflict")
        selected = options.get("roles", {}).get(role, options)
        provider, model = selected.get("provider"), selected.get("model")
        # Defense in depth for resumed runs and direct runner use.
        if provider not in PROVIDERS or not model:
            raise AnalysisContractError("保存されたモデル設定が不正です。", code="provider_unavailable")
        if provider != "lmstudio" and (options.get("provider_policy") != "cloud_allowed" or options.get("cloud_consent") is not True):
            raise AnalysisContractError("クラウドAIへの送信は許可されていません。", code="provider_unavailable")
        check_cancelled()
        config = load_token_config()
        api_key, _ = configured_ai_credentials(config, provider)
        if provider != "lmstudio" and not api_key:
            raise AnalysisContractError("選択したAIのAPIキーが未設定です。", code="provider_unavailable")
        from .analysis_diagnostics import emit
        from .pipeline_adapter import call_pipeline
        diagnostic = options.get("_agent_diagnostic")
        return call_pipeline(context, role=role, provider=provider, model=model, api_key=api_key,
            base_url=config.lmstudio_base_url if provider == "lmstudio" else "", options=options,
            call_ai_json=call_ai_json, check_cancelled=check_cancelled, record_usage=record_usage,
            transport_diagnostics=transport_diagnostics,
            trace=(lambda event: emit(diagnostic, {"adapter_version": ADAPTER_VERSION, "provider": provider,
                                                   "role": role, **event})) if callable(diagnostic) else None)

    return resolve, runner


def make_asset_binding_adapters(*, store, expert_registry):
    """Private opt-in, read-only seam; no model, scheduler or adoption callback.

    The existing registry owns expert/actor/capability checks, the existing store
    owns immutable content and current permissions. Default AI adapters are intact.
    """
    def resolve(*, expert_id, method_id, step_id, actor, slot, inputs, context):
        return store.bind_asset_inputs(slot=slot, inputs=inputs, context=context, method_id=method_id,
            assess=lambda envelopes: expert_registry.assess_inputs(
                expert_id, method_id, step_id, actor, slot, envelopes))

    def revalidate(previous, **request):
        authority = (request["expert_id"], request["method_id"], request["step_id"], request["actor"])
        return store.revalidate_asset_inputs(previous, slot=request["slot"], inputs=request["inputs"],
            context=request["context"], method_id=request["method_id"],
            assess=lambda envelopes: expert_registry.assess_inputs(*authority, request["slot"], envelopes))

    return resolve, revalidate


def resolve_table_pilot(store, method_id, request, snapshot):
    """Explicit local opt-in seam; no model, latest lookup, or automatic adoption."""
    prepared = store.prepare_table_pilot(method_id, request, expected_snapshot=snapshot)
    prepared["method_id"] = method_id
    return prepared
