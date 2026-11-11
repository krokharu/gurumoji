"""Transport of one Core-pipeline request: the Handler built the input; this only sends it.

No projection, retry or repair happens here. The generation schema is the one
the Handler pinned to the task, and the Handler validates the decoded reply.
"""
from __future__ import annotations

import json

from ..analysis_core import AnalysisContractError
from .pipeline_context import VERSION


def call_pipeline(request, *, role, provider, model, api_key, base_url, options, call_ai_json,
                  check_cancelled, record_usage, trace=None, transport_diagnostics=False):
    if not isinstance(request, dict) or request.get("version") != VERSION:
        raise AnalysisContractError("パイプライン入力の版が一致しません。", code="analysis_pipeline_conflict")
    check_cancelled()
    system_prompt = request["system"]
    user_prompt = json.dumps(request["packet"], ensure_ascii=False, separators=(",", ":"))
    private = {}
    if options.get("_request_budget") is not None:
        private = {"request_budget": options["_request_budget"], "task_id": request.get("task_id", ""),
                   "attempt_id": options["_budget_attempt_id"] + ":0",
                   "raw_usage_callback": options.get("_raw_usage_callback")}
    if transport_diagnostics and callable(trace):
        private["diagnostic_callback"] = lambda event: trace({**event, "call": 1})
    if callable(trace):
        trace({"stage": "adapter", "phase": "input_assembled", "call": 1, "pipeline_role": request["role"],
               "messages": [{"role": "system", "characters": len(system_prompt)},
                            {"role": "user", "characters": len(user_prompt)}]})
    try:
        result = call_ai_json(provider, api_key, model, system_prompt, user_prompt, request["schema_name"],
                              request["schema"], check_cancelled, record_usage, base_url,
                              options.get("timeout_seconds", 240), **private)
    except Exception as exc:
        if callable(trace):
            from .analysis_diagnostics import error_metadata
            trace({"stage": "provider_call", "phase": "failed", "call": 1, **error_metadata(exc)})
        raise
    if callable(trace):
        trace({"stage": "adapter", "phase": "response_decoded", "call": 1, "response_observed": True})
    check_cancelled()
    return result
