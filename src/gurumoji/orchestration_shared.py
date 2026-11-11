from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from .analysis_core import AnalysisContractError, canonical

SCHEMA_VERSION = 1
ROLES = {"core": "Core", "handler": "Handler", "interpretation": "会話解釈",
         "statistics": "数量・統計", "verification": "独立検証", "critic": "批判者",
         "orchestrator": "専門オーケストレータ"}
AI_ROLES = frozenset({"core", "interpretation", "verification", "critic", "orchestrator"})
INITIAL_SECTIONS = frozenset({"segments", "annotations", "automatic", "manual", "research", "config", "cautions", "classification"})
LABEL_FIELDS = frozenset({"code", "codes", "theme", "sentiment", "dialogue_act", "importance", "review", "category"})
INITIAL_METHODS = frozenset({"participation", "conversation_dynamics", "label_frequency"})
METHODS = INITIAL_METHODS | {"cross_tabulation"}
TERMINAL = frozenset({"completed", "stopped", "cancelled", "failed"})
IMPORTANCE = {"low": 1, "medium": 2, "high": 3}


def _id(prefix: str) -> str:
    return prefix + "_" + uuid.uuid4().hex


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json(value: Any) -> str:
    return canonical(value).decode("utf-8")


def _error(message: str, code: str = "invalid_request", field: str = "") -> AnalysisContractError:
    return AnalysisContractError(message, code=code, field=field)


def _scope(intent):
    value = intent.get("scope")
    return value if isinstance(value, dict) else {}


def _read_events(db, run_id, events_after=None):
    reset = events_after is not None and events_after > 0 and db.execute(
        "SELECT 1 FROM orchestration_events WHERE run_id=? AND seq=?", (run_id, events_after)).fetchone() is None
    if reset:
        events_after = None
    query = "SELECT seq,payload_json FROM orchestration_events WHERE run_id=?"
    params = (run_id,)
    if events_after is not None:
        query += " AND seq>?"
        params += (events_after,)
    return ([{"seq": row[0], **json.loads(row[1])} for row in db.execute(query + " ORDER BY seq", params)], reset)


class ExecutionStopped(Exception):
    """A cooperative cancellation/deadline signal, never an agent result."""
