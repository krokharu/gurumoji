"""Bounded execution metadata: no credentials, prompt text or provider error text."""
from __future__ import annotations

import hashlib
import json
import math
import re
import traceback
from functools import wraps, lru_cache
from pathlib import Path

VERSION = "analysis-diagnostics-1"
_IDENTIFIER = re.compile(r"[A-Za-z0-9_./:@+-]{1,200}\Z")
_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_SECRET_PREFIXES = ("sk-", "sk_", "AIza", "Bearer", "ghp_", "github_pat_")
_TEXT_KEYS = frozenset({"version", "event", "stage", "phase", "status", "code", "cause", "reason",
    "exception_type", "module", "function", "model", "provider", "role", "name", "scope", "mode", "error_code", "budget_reason", "budget_cause",
    "reasoning_effort", "response_format_type", "format", "adapter_version", "kind", "analysis_scope_task_id",
    "evidence_id", "result_id", "table_id", "outline_section", "task_id", "attempt_id", "run_id"})
_HASH_KEYS = frozenset({"payload_hash", "budget_payload_hash", "ticket_hash", "reservation_id",
    "schema_hash", "response_hash", "content_hash", "text_hash", "request_hash", "wire_hash", "projection_hash", "scope_hash",
    "system_hash", "user_hash", "run_question_hash", "expert_question_hash", "input_version", "data_version", "source_hash", "packet_hash", "response_schema_hash",
    "handler_hash", "adapter_hash", "client_hash", "pipeline_hash", "diagnostic_hash", "app_hash", "expert_hash", "binding_hash", "map_hash"})
_NUMBER_KEYS = frozenset({"round", "current_round", "call", "max_read_rounds", "max_requests_per_round", "remaining_read_rounds", "remaining_requests", "required_read_requests",
    "read_requests_executed", "request_index", "offset", "limit", "characters", "total_characters",
    "new_characters", "new_evidence_count", "before_characters", "after_characters", "before_rows", "after_rows",
    "prefix_before", "prefix_after", "union_before", "union_after", "line", "http_status", "input_tokens",
    "output_tokens", "total_tokens", "prompt_tokens", "completion_tokens", "temperature", "top_p", "top_k",
    "min_p", "max_tokens", "schema_characters", "response_characters", "raw_rows", "raw_characters",
    "available_count", "provided_count", "omitted_count", "index_available_count", "index_provided_count",
    "index_omitted_count", "hook_index_count", "outline_count", "hook_outline_count", "count", "generation",
    "elapsed_ms", "claim_count", "intent_count", "analysis_request_count", "retry_count", "returned_rows", "lost_characters",
    "contiguous_before_characters", "contiguous_after_characters", "missing_input_count", "input_limit", "excess_tokens",
    "before_input_tokens", "input_token_target", "hash_reference_count"})
_BOOL_KEYS = frozenset({"stream", "complete", "input_complete", "fits_remaining_requests", "response_observed", "no_progress", "schema_valid", "inverse_matches",
    "truncated", "budgeted", "same_question", "api_specified", "is_zero_progress", "provider_response_received", "strict_preworker_not_sent", "projected"})
_CONTAINER_KEYS = frozenset({"settings", "messages", "usage", "locations", "coverage", "request", "expanded_request",
    "fragments", "before_fragments", "after_fragments", "outline", "hook_outline", "validation", "diagnostic",
    "input", "output", "progress", "read_progress", "next_requests", "before", "after", "response", "requests", "code_identity", "returned_fragments", "intents", "analysis_requests", "expert_report"})
_ID_LIST_KEYS = frozenset({"evidence_ids", "pending_outputs", "finish_reasons", "warnings", "input_fields", "output_fields",
    "provided_ids", "scope_ids", "already_supplied_ids", "new_ids", "dependencies", "outline_sections", "pending_nonempty_outputs"})


def identifier(value):
    if (isinstance(value, str) and _IDENTIFIER.fullmatch(value)
            and not value.startswith(_SECRET_PREFIXES)):
        return value
    return None


def digest(value):
    try:
        return "sha256:" + hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    except (ValueError, TypeError, OverflowError, RecursionError):
        return None


def sanitize(value, depth=0):
    """Drop unknown fields and arbitrary text, even from a malformed callback."""
    if depth > 9 or not isinstance(value, dict):
        return {}
    out = {}
    for key, item in value.items():
        if key in _HASH_KEYS and isinstance(item, str) and _HASH.fullmatch(item):
            out[key] = item
        elif key in _TEXT_KEYS:
            safe = identifier(item)
            if safe is not None:
                out[key] = safe
            elif key == "evidence_id" and type(item) is int and item >= 0:
                out[key] = item
        elif key in _NUMBER_KEYS and type(item) in (int, float) and math.isfinite(item):
            out[key] = item
        elif key in _BOOL_KEYS and type(item) is bool:
            out[key] = item
        elif key in _ID_LIST_KEYS and isinstance(item, list):
            out[key] = [safe for v in item[:2000] if (safe := identifier(v)) is not None]
            if len(item) > 2000:
                out["truncated"] = True
        elif key in _CONTAINER_KEYS:
            if isinstance(item, dict):
                out[key] = sanitize(item, depth + 1)
            elif isinstance(item, list):
                out[key] = [sanitize(v, depth + 1) for v in item[:2000] if isinstance(v, dict)]
                if len(item) > 2000:
                    out["truncated"] = True
    return out


def emit(callback, event):
    if not callable(callback):
        return False
    try:
        callback(sanitize({"version": VERSION, **event}))
        return True
    except Exception:
        # Diagnostic IO must not turn a known response into another dispatch.
        return False


def _safe_metadata(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except Exception:
            return {"warnings": ["metadata_unavailable"]}
    return wrapped


@lru_cache(maxsize=1)
@_safe_metadata
def code_identity():
    """Source-file hashes sampled once per process; never infer a Git commit."""
    base = Path(__file__).resolve().parents[1]
    files = {"handler_hash": "analysis_orchestration.py", "adapter_hash": "services/analysis_orchestration_adapters.py",
        "client_hash": "services/ai/client.py", "pipeline_hash": "services/pipeline_run.py",
        "diagnostic_hash": "services/analysis_diagnostics.py", "app_hash": "app.py", "expert_hash": "services/expert_agents.py"}
    return {key: "sha256:" + hashlib.sha256((base / name).read_bytes()).hexdigest() for key, name in files.items()}


@_safe_metadata
def request_metadata(payload):
    schema = payload.get("response_format", {}).get("json_schema", {}).get("schema")
    if schema is None:
        schema = payload.get("text", {}).get("format", {}).get("schema")
    if schema is None:
        schema = payload.get("generationConfig", {}).get("responseJsonSchema")
    settings = {k: payload[k] for k in ("temperature", "top_p", "top_k", "min_p", "max_tokens", "reasoning_effort", "stream") if k in payload}
    messages = payload.get("messages", payload.get("input", []))
    out = {"payload_hash": digest(payload), "model": payload.get("model"), "settings": settings,
        "messages": [{"role": m.get("role"), "characters": len(m["content"]), "content_hash": digest(m["content"])}
            for m in messages if isinstance(m, dict) and isinstance(m.get("content"), str)],
        "response_format_type": payload.get("response_format", {}).get("type")}
    if schema is not None:
        out.update(schema_hash=digest(schema), schema_characters=len(json.dumps(schema, ensure_ascii=False, separators=(",", ":"))))
    return sanitize(out)


@_safe_metadata
def response_metadata(response):
    if not isinstance(response, dict):
        return {"response_hash": digest(response)}
    choices = response.get("choices", [])
    usage = response.get("usage", {})
    return sanitize({"response_hash": digest(response), "response_characters": len(json.dumps(response, ensure_ascii=False)),
        "finish_reasons": [c.get("finish_reason") for c in choices if isinstance(c, dict)],
        "usage": usage if isinstance(usage, dict) else {}, "response_observed": True})


@_safe_metadata
def decision_metadata(reply, *, context=None):
    """生成本文を残さず、採用検査に必要な操作名と件数だけを記録する。"""
    if not isinstance(reply, dict):
        return {}
    action = reply.get("action", {})
    return sanitize({"name": action.get("op") if isinstance(action, dict) else None,
                     "count": len(reply.get("state_ops", [])),
                     "raw_rows": len(reply.get("observations", []))})


@_safe_metadata
def error_metadata(exc):
    from ..analysis_core import AnalysisContractError
    from .ai.request_budget import BudgetHold
    frames = list(traceback.walk_tb(exc.__traceback__))[-8:]
    code = exc.code if isinstance(exc, AnalysisContractError) else exc.reason if isinstance(exc, BudgetHold) else None
    return sanitize({"exception_type": type(exc).__name__, "code": code,
        **(exc.details if isinstance(exc, BudgetHold) else {}),
        **({"strict_preworker_not_sent": exc.strict_preworker_not_sent} if isinstance(exc, BudgetHold) else {}),
        "cause": exc.cause if isinstance(exc, BudgetHold) else None, "locations": [{"module": frame.f_globals.get("__name__"),
            "function": frame.f_code.co_name, "line": line} for frame, line in frames]})


@_safe_metadata
def context_metadata(context):
    """実際に送るpacketの件数・文字数・hashだけを返す。"""
    packet = context.get("packet", context)
    if "coverage" in packet and not isinstance(packet["coverage"], dict):
        raise ValueError("invalid_coverage")
    rows = packet.get("raw_evidence", [])
    if "utterances" in packet:
        columns = packet["utterances"]["columns"]
        rows = [dict(zip(columns, row)) for row in packet["utterances"]["rows"]]
    version = packet.get("data_version")
    if isinstance(version, str) and re.fullmatch(r"[0-9a-f]{64}", version):
        version = "sha256:" + version
    return sanitize({"input_version": version, "input_fields": list(packet),
        "coverage": packet.get("coverage", {}), "raw_rows": len(rows),
        "raw_characters": sum(len(row.get("text", "")) for row in rows)})
