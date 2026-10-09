"""Opt-in transport reservations. No model readiness or Handler wiring here.

The owner supplies monotonic origins *before* run/task preparation or queuing,
an explicit batch quota, accepted model conditions and a full-payload counter.
Counter evidence is caller supplied; synthetic evidence never establishes real
tokenizer/template/schema coverage. An unknown delivery or usage holds the batch.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import threading
import time
from dataclasses import asdict, dataclass
from typing import Any, Callable

RUN_SECONDS = 600
TASK_SECONDS = 240
CLEANUP_SECONDS = 5
MAX_WIRE_SECONDS = 235
MAX_INPUT_TOKENS = 24576
OUTPUT_TOKENS = 4096
MAX_CONTEXT_TOKENS = 32768
MAX_TRIAL_CALLS = 6
MAX_BATCH_CALLS = 216
M_RUN_SECONDS = 1800
M_EXTENDED_RUN_SECONDS = 8400
M_MAX_TRIAL_CALLS = 32
COVERAGE = frozenset({"model", "system", "messages", "template", "special_tokens", "schema"})
HASH_PATTERN = re.compile(r"sha256:[0-9a-f]{64}\Z")
SAFE_REASONS = frozenset({"invalid_integer", "invalid_clock", "invalid_identity", "invalid_ticket",
    "ticket_changed", "invalid_deadline", "invalid_timeout", "request_changed", "deadline_reserve",
    "invalid_budget", "invalid_conditions", "duplicate_run_budget", "task_origin_changed", "batch_held",
    "task_origin_missing", "model_changed", "request_identity_changed", "duplicate_request",
    "token_proof_unknown", "context_limit", "call_limit", "token_limit", "parent_deadline_or_ticket",
    "transport_unknown", "receipt_mismatch", "receipt_clock", "receipt_deadline",
    "transport_or_usage_unknown", "usage_unknown", "response_truncated", "deadline_overrun",
    "receipt_or_usage_unknown", "local_endpoint_required", "renderer_payload_not_supported",
    "renderer_messages_not_supported", "renderer_schema_not_supported",
    "renderer_conditions_changed", "renderer_tokenizer_unknown",
    "invalid_profile", "profile_receipt_required", "profile_receipt_invalid"})


class BudgetHold(RuntimeError):
    """A safe reason code, never provider text or exception details."""

    def __init__(self, reason: str):
        self.reason = reason if isinstance(reason, str) and reason in SAFE_REASONS else "transport_unknown"
        super().__init__("AI request budget held: " + self.reason)


def payload_hash(value: Any) -> str:
    return "sha256:" + hashlib.sha256(json.dumps(value, ensure_ascii=False,
        sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _integer(value: Any, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise BudgetHold("invalid_integer")
    return value


def _instant(value: Any) -> float:
    if type(value) not in (int, float):
        raise BudgetHold("invalid_clock")
    try:
        value = float(value)
    except (ValueError, OverflowError):
        raise BudgetHold("invalid_clock") from None
    if not math.isfinite(value) or value < 0:
        raise BudgetHold("invalid_clock")
    return value


def _identity(value: Any) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 512:
        raise BudgetHold("invalid_identity")
    return value


def profile_limits(profile: str = "legacy") -> dict:
    """Fresh immutable-by-value ceilings; selecting a profile never approves execution."""
    if type(profile) is not str or profile not in {"legacy", "M", "M_extended"}:
        raise BudgetHold("invalid_profile")
    calls = MAX_TRIAL_CALLS if profile == "legacy" else M_MAX_TRIAL_CALLS
    run_seconds = {"legacy": RUN_SECONDS, "M": M_RUN_SECONDS, "M_extended": M_EXTENDED_RUN_SECONDS}[profile]
    return {"profile": profile, "run_seconds": run_seconds,
        "trial_calls": calls, "trial_tokens": calls * (MAX_INPUT_TOKENS + OUTPUT_TOKENS),
        "task_seconds": TASK_SECONDS, "wire_seconds": MAX_WIRE_SECONDS, "cleanup_seconds": CLEANUP_SECONDS,
        "context_tokens": MAX_CONTEXT_TOKENS, "input_tokens": MAX_INPUT_TOKENS,
        "output_tokens": OUTPUT_TOKENS, "batch_calls": MAX_BATCH_CALLS,
        "batch_tokens": MAX_BATCH_CALLS * (MAX_INPUT_TOKENS + OUTPUT_TOKENS)}


@dataclass(frozen=True)
class C0ProfileReceipt:
    """Reference/binding to an immutable external C0 execution-approval receipt.

    This object is NOT an approval issuer. A trusted external verifier must read
    the referenced receipt, verify its digest, author/approval, exact source SHA,
    condition and ceiling bindings, then return receipt_hash. Neither a CLI flag
    nor a self-attested 'accepted' boolean suffices. The worker checks structural
    integrity, not authenticity; the parent owns verification and IPC trust.
    All fields are immutable scalar strings, with no mutable nested receipt data.
    """
    receipt_ref: str
    receipt_hash: str
    source_sha: str
    profile: str
    conditions_hash: str
    limits_hash: str


def _validate_profile_receipt(value: Any, profile: str, conditions_hash: str) -> None:
    if profile == "legacy":
        if value is not None:
            raise BudgetHold("profile_receipt_invalid")
        return
    if not isinstance(value, dict) or set(value) != set(C0ProfileReceipt.__dataclass_fields__):
        raise BudgetHold("profile_receipt_required")
    if (type(value["receipt_ref"]) is not str or not value["receipt_ref"].strip()
            or len(value["receipt_ref"]) > 512 or type(value["source_sha"]) is not str
            or not re.fullmatch(r"[0-9a-f]{40}", value["source_sha"])
            or value["profile"] != profile or value["conditions_hash"] != conditions_hash
            or value["limits_hash"] != payload_hash(profile_limits(profile))):
        raise BudgetHold("profile_receipt_invalid")
    for key in ("receipt_hash", "conditions_hash", "limits_hash"):
        if type(value[key]) is not str or not HASH_PATTERN.fullmatch(value[key]):
            raise BudgetHold("profile_receipt_invalid")


TICKET_KEYS = frozenset({"budget_id", "run_id", "task_id", "attempt_id", "reservation_id",
    "payload_hash", "model_hash", "conditions_hash", "counter_proof_hash", "run_started_at", "task_started_at", "run_deadline",
    "task_deadline", "requested_timeout", "ticket_hash", "profile", "profile_limits",
    "profile_receipt", "trial_call_limit", "trial_token_limit", "batch_call_limit", "batch_token_limit"})


def _validate_ticket(ticket: dict, payload: dict) -> None:
    """Validate immutable IPC metadata and recompute just before HTTP dispatch.

    Hashes detect changed metadata, not authenticity against a malicious IPC
    peer. The parent also matches the returned ticket to its own reservation.
    """
    if not isinstance(ticket, dict) or set(ticket) != TICKET_KEYS:
        raise BudgetHold("invalid_ticket")
    for key in ("budget_id", "run_id", "task_id", "attempt_id", "reservation_id", "payload_hash", "model_hash", "conditions_hash", "counter_proof_hash", "ticket_hash"):
        if not isinstance(ticket[key], str) or not HASH_PATTERN.fullmatch(ticket[key]):
            raise BudgetHold("invalid_ticket")
    if ticket["ticket_hash"] != payload_hash({k: v for k, v in ticket.items() if k != "ticket_hash"}):
        raise BudgetHold("ticket_changed")
    if ticket["reservation_id"] != payload_hash([ticket[k] for k in (
            "budget_id", "run_id", "task_id", "attempt_id", "payload_hash")]):
        raise BudgetHold("ticket_changed")
    limits = profile_limits(ticket["profile"])
    if payload_hash(ticket["profile_limits"]) != payload_hash(limits):
        raise BudgetHold("invalid_profile")
    _validate_profile_receipt(ticket["profile_receipt"], ticket["profile"], ticket["conditions_hash"])
    for key, ceiling in (("trial_call_limit", "trial_calls"), ("trial_token_limit", "trial_tokens"),
                         ("batch_call_limit", "batch_calls"), ("batch_token_limit", "batch_tokens")):
        _integer(ticket[key], 1, limits[ceiling])
    run_start, task_start = _instant(ticket["run_started_at"]), _instant(ticket["task_started_at"])
    run_end, task_end = _instant(ticket["run_deadline"]), _instant(ticket["task_deadline"])
    if (run_end != run_start + limits["run_seconds"] or task_end != min(run_end, task_start + TASK_SECONDS)
            or not run_start <= task_start < run_end):
        raise BudgetHold("invalid_deadline")
    requested = _instant(ticket["requested_timeout"])
    if not 0 < requested <= MAX_WIRE_SECONDS:
        raise BudgetHold("invalid_timeout")
    if (not isinstance(payload, dict) or type(payload.get("max_tokens")) is not int
            or payload["max_tokens"] != OUTPUT_TOKENS
            or payload_hash(payload) != ticket["payload_hash"]
            or payload_hash(payload.get("model")) != ticket["model_hash"]):
        raise BudgetHold("request_changed")
def _remaining_timeout(ticket: dict, now: float) -> float:
    now = _instant(now)
    if now < ticket["task_started_at"]:
        raise BudgetHold("invalid_deadline")
    remaining = min(ticket["run_deadline"], ticket["task_deadline"]) - now
    # Never clamp a remaining 5.999 seconds to a one-second send.
    timeout = min(ticket["requested_timeout"], MAX_WIRE_SECONDS, remaining - CLEANUP_SECONDS)
    if timeout < 1:
        raise BudgetHold("deadline_reserve")
    return timeout


def wire_timeout(ticket: dict, payload: dict, now: float | Callable[[], float]) -> float:
    """Production callers supply the clock, sampled after full hash validation."""
    _validate_ticket(ticket, payload)
    return _remaining_timeout(ticket, now() if callable(now) else now)


def prepare_wire(ticket: dict, payload: dict, clock: Callable[[], float]) -> tuple[float, float]:
    """Return the timeout and its clock sample after all expensive validation."""
    _validate_ticket(ticket, payload)
    sending_at = _instant(clock())
    return _remaining_timeout(ticket, sending_at), sending_at


class BatchQuota:
    """Explicit caller-owned batch shared by run budgets; no global state.

    Wave B must pass the same object to runs belonging to the same batch.
    A new object is a distinct batch, not a way to reset an existing budget.
    """

    def __init__(self, *, max_calls: int, max_tokens: int):
        self._max_calls = _integer(max_calls, 1, MAX_BATCH_CALLS)
        self._max_tokens = _integer(max_tokens, 1, MAX_BATCH_CALLS * (MAX_INPUT_TOKENS + OUTPUT_TOKENS))
        self._calls, self._tokens, self._hold_reason = 0, 0, None
        self._lock = threading.RLock()
        self._run_ids: set[str] = set()

    def snapshot(self) -> dict:
        with self._lock:
            return {"call_limit": self._max_calls, "token_limit": self._max_tokens,
                "reserved_entries": self._calls, "charged_or_reserved_tokens": self._tokens,
                "remaining_calls": self._max_calls - self._calls,
                "remaining_tokens": self._max_tokens - self._tokens,
                "hold_reason": self._hold_reason}


def strict_usage(response: dict, *, input_reserved: int, usage_policy: str) -> dict:
    """Inspect raw LM Studio usage before the legacy zero-coercing normalizer."""
    usage = response.get("usage")
    if not isinstance(usage, dict):
        raise BudgetHold("usage_unknown")
    try:
        for key, value in usage.items():
            if key.endswith("tokens") or key.endswith("tokens_count"):
                _integer(value, 0, MAX_INPUT_TOKENS + OUTPUT_TOKENS)
        i, o, total = (_integer(usage.get(k), 0, MAX_INPUT_TOKENS + OUTPUT_TOKENS)
            for k in ("prompt_tokens", "completion_tokens", "total_tokens"))
        if i != input_reserved or o > OUTPUT_TOKENS or i + o != total:
            raise BudgetHold("usage_unknown")
        reasoning = []
        for name in ("reasoning_tokens", "thinking_tokens"):
            if name in usage:
                reasoning.append(_integer(usage[name], 0, OUTPUT_TOKENS))
        for name in ("prompt_tokens_details", "completion_tokens_details"):
            if name in usage:
                details = usage[name]
                if not isinstance(details, dict):
                    raise BudgetHold("usage_unknown")
                for key, value in details.items():
                    # All token counters, including cached/audio/accepted tokens,
                    # must be genuine finite integers, never normalized zeroes.
                    if key.endswith("tokens") or key.endswith("tokens_count"):
                        _integer(value, 0, MAX_INPUT_TOKENS + OUTPUT_TOKENS)
                    if key in {"reasoning_tokens", "thinking_tokens"}:
                        if name == "prompt_tokens_details":
                            raise BudgetHold("usage_unknown")
                        reasoning.append(_integer(value, 0, OUTPUT_TOKENS))
        if (len(set(reasoning)) > 1 or any(n > o for n in reasoning)
                or usage_policy not in {"output_includes_reasoning", "reasoning_disabled"}):
            raise BudgetHold("usage_unknown")
        if usage_policy == "reasoning_disabled" and any(reasoning):
            raise BudgetHold("usage_unknown")
    except BudgetHold:
        raise BudgetHold("usage_unknown") from None
    return {"input_tokens": i, "output_tokens": o, "total_tokens": total,
        "reasoning_tokens": max(reasoning) if reasoning else None,
        "reasoning_accounting": usage_policy}


class RequestBudget:
    """One run/trial, consuming origins supplied before any preparation.

    register_task() likewise consumes the task's pre-context/pre-queue origin.
    Quotas are fixed at construction. Caller proofs are bound to accepted model
    conditions but this wave never labels them actual measurement readiness.
    """

    def __init__(self, *, budget_id: str, run_id: str, run_started_at: float,
            batch: BatchQuota, trial_token_limit: int, token_counter: Callable[[dict], dict],
            model: str, context_tokens: int, tokenizer_id: str, template_id: str,
            proof_source: str, acceptance_anchor: str, model_conditions_hash: str,
            synthetic_only: bool, usage_policy: str | None,
            trial_call_limit: int, clock: Callable[[], float] = time.monotonic,
            profile: str = "legacy", profile_receipt: C0ProfileReceipt | None = None,
            verify_profile_receipt: Callable[[C0ProfileReceipt], str] | None = None):
        if not isinstance(batch, BatchQuota) or not callable(token_counter) or not callable(clock):
            raise BudgetHold("invalid_budget")
        self._batch, self._clock, self._counter = batch, clock, token_counter
        self._limits = profile_limits(profile)
        self._profile = profile
        self._run_seconds = self._limits["run_seconds"]
        self._run_start = _instant(run_started_at)
        if self._run_start > _instant(clock()) or self._run_start + self._run_seconds <= self._run_start:
            raise BudgetHold("invalid_deadline")
        self._budget_id, self._run_id = payload_hash(_identity(budget_id)), payload_hash(_identity(run_id))
        self._call_limit = _integer(trial_call_limit, 1, self._limits["trial_calls"])
        self._token_limit = _integer(trial_token_limit, 1, self._limits["trial_tokens"])
        self._model = _identity(model)
        self._context = _integer(context_tokens, OUTPUT_TOKENS, MAX_CONTEXT_TOKENS)
        if type(synthetic_only) is not bool or (usage_policy is not None and usage_policy not in {"output_includes_reasoning", "reasoning_disabled"}):
            raise BudgetHold("invalid_conditions")
        self._conditions = {"model": self._model, "context_tokens": self._context,
            "tokenizer": _identity(tokenizer_id), "template": _identity(template_id),
            "source": _identity(proof_source), "acceptance_anchor": _identity(acceptance_anchor),
            "model_conditions_hash": _identity(model_conditions_hash), "synthetic_only": synthetic_only,
            "usage_policy": usage_policy}
        if not HASH_PATTERN.fullmatch(model_conditions_hash):
            raise BudgetHold("invalid_conditions")
        if profile_receipt is not None and type(profile_receipt) is not C0ProfileReceipt:
            raise BudgetHold("profile_receipt_invalid")
        self._profile_receipt = asdict(profile_receipt) if profile_receipt is not None else None
        _validate_profile_receipt(self._profile_receipt, profile, payload_hash(self._conditions))
        if profile in {"M", "M_extended"}:
            if not callable(verify_profile_receipt):
                raise BudgetHold("profile_receipt_required")
            try:
                verified_hash = verify_profile_receipt(profile_receipt)
                if type(verified_hash) is not str or verified_hash != profile_receipt.receipt_hash:
                    raise BudgetHold("profile_receipt_invalid")
            except Exception:
                raise BudgetHold("profile_receipt_invalid") from None
        elif verify_profile_receipt is not None:
            raise BudgetHold("profile_receipt_invalid")
        self._proofs: dict[str, dict] = {}
        self._tasks: dict[str, float] = {}
        self._entries: dict[str, dict] = {}
        self._requests: dict[tuple[str, str], str] = {}
        self._charged = 0
        with batch._lock:
            if self._run_id in batch._run_ids:
                raise BudgetHold("duplicate_run_budget")
            batch._run_ids.add(self._run_id)

    def _hold(self, reason: str) -> None:
        reason = BudgetHold(reason).reason
        self._batch._hold_reason = self._batch._hold_reason or reason
        raise BudgetHold(reason) from None

    def _available(self) -> None:
        if self._batch._hold_reason:
            raise BudgetHold("batch_held")

    def register_task(self, task_id: str, task_started_at: float) -> None:
        key, start = payload_hash(_identity(task_id)), _instant(task_started_at)
        with self._batch._lock:
            if not self._run_start <= start < self._run_start + self._run_seconds or start > _instant(self._clock()):
                self._hold("invalid_deadline")
            if key in self._tasks and self._tasks[key] != start:
                self._hold("task_origin_changed")
            self._tasks[key] = start

    def reserve(self, payload: dict, *, task_id: str, attempt_id: str, timeout: float) -> dict:
        """Fix max_tokens, count the entire finalized request, reserve one wire."""
        with self._batch._lock:
            self._available()
            try:
                task, attempt = payload_hash(_identity(task_id)), payload_hash(_identity(attempt_id))
                if task not in self._tasks:
                    raise BudgetHold("task_origin_missing")
                requested = _instant(timeout)
                if requested <= 0:
                    raise BudgetHold("invalid_timeout")
                if not isinstance(payload, dict) or payload.get("model") != self._model:
                    raise BudgetHold("model_changed")
                validator = getattr(self._counter, "validate_payload", None)
                if validator is not None:
                    validator(copy.deepcopy(payload))
                final = copy.deepcopy(payload)
                final["max_tokens"] = OUTPUT_TOKENS
                request_hash = payload_hash(final)
                key = (task, attempt)
                if key in self._requests:
                    if self._requests[key] != request_hash:
                        self._hold("request_identity_changed")
                    raise BudgetHold("duplicate_request")
                ticket = {"budget_id": self._budget_id, "run_id": self._run_id, "task_id": task,
                    "attempt_id": attempt, "payload_hash": request_hash, "model_hash": payload_hash(self._model),
                    "conditions_hash": payload_hash(self._conditions), "counter_proof_hash": payload_hash(None),
                    "profile": self._profile, "profile_limits": copy.deepcopy(self._limits),
                    "profile_receipt": copy.deepcopy(self._profile_receipt),
                    "trial_call_limit": self._call_limit, "trial_token_limit": self._token_limit,
                    "batch_call_limit": self._batch._max_calls, "batch_token_limit": self._batch._max_tokens,
                    "run_started_at": self._run_start, "task_started_at": self._tasks[task],
                    "run_deadline": self._run_start + self._run_seconds,
                    "task_deadline": min(self._run_start + self._run_seconds, self._tasks[task] + TASK_SECONDS),
                    "requested_timeout": min(requested, MAX_WIRE_SECONDS)}
                ticket["reservation_id"] = payload_hash([self._budget_id, self._run_id, task, attempt, request_hash])
                ticket["ticket_hash"] = payload_hash(ticket)
                wire_timeout(ticket, final, self._clock)
                proof = self._counter(copy.deepcopy(final))
                if not isinstance(proof, dict) or any(proof.get(k) != v or type(proof.get(k)) is not type(v) for k, v in self._conditions.items()):
                    raise BudgetHold("token_proof_unknown")
                coverage = proof.get("covered_fields")
                if (proof.get("payload_hash") != request_hash or proof.get("complete_coverage") is not True
                        or not isinstance(coverage, list) or any(not isinstance(k, str) for k in coverage)
                        or len(coverage) != len(COVERAGE) or set(coverage) != COVERAGE):
                    raise BudgetHold("token_proof_unknown")
                if (proof.get("fresh_verification_required") is True
                        and not callable(getattr(self._counter, "verify_before_dispatch", None))):
                    raise BudgetHold("token_proof_unknown")
                ticket["counter_proof_hash"] = payload_hash(proof)
                ticket["ticket_hash"] = payload_hash({k: v for k, v in ticket.items() if k != "ticket_hash"})
                counted = _integer(proof.get("input_tokens"), 0, MAX_INPUT_TOKENS)
                total = counted + OUTPUT_TOKENS
                if total > self._context:
                    raise BudgetHold("context_limit")
                wire_timeout(ticket, final, self._clock)
                if len(self._entries) >= self._call_limit or self._batch._calls >= self._batch._max_calls:
                    raise BudgetHold("call_limit")
                if self._charged + total > self._token_limit or self._batch._tokens + total > self._batch._max_tokens:
                    raise BudgetHold("token_limit")
            except BudgetHold as exc:
                if exc.reason == "duplicate_request":
                    raise
                self._hold(exc.reason)
            except Exception:
                self._hold("token_proof_unknown")
            self._charged += total
            self._batch._tokens += total
            self._batch._calls += 1
            self._requests[key] = request_hash
            self._proofs[ticket["reservation_id"]] = copy.deepcopy(proof)
            self._entries[ticket["reservation_id"]] = {"ticket": copy.deepcopy(ticket),
                "input_reserved": counted, "output_reserved": OUTPUT_TOKENS, "maximum_reserved": total,
                "charged_tokens": total, "reserved_at": _instant(self._clock()), "sent": "unknown",
                "usage": None, "state": "reserved", "stop_reason": None, "receipt": None, "http_status": None}
            return {"payload": final, "ticket": ticket}

    def _ticket_entry(self, ticket: dict) -> dict:
        entry = self._entries.get(ticket.get("reservation_id")) if isinstance(ticket, dict) and isinstance(ticket.get("reservation_id"), str) else None
        if entry is not None and entry["ticket"] == ticket:
            return entry
        # A corrupted reservation identity cannot authorize or refund any
        # pending entry. All remain charged and the batch is held.
        for pending in self._entries.values():
            if pending["state"] == "reserved":
                pending.update(state="unknown", usage=None, stop_reason="ticket_changed")
        self._hold("ticket_changed")

    def dispatch_timeout(self, ticket: dict, payload: dict) -> float:
        with self._batch._lock:
            entry = self._ticket_entry(ticket)
            try:
                self._available()
                if entry["ticket"] != ticket or entry["state"] != "reserved":
                    raise BudgetHold("ticket_changed")
                proof = self._proofs[ticket["reservation_id"]]
                if (ticket["conditions_hash"] != payload_hash(self._conditions)
                        or ticket["counter_proof_hash"] != payload_hash(proof)):
                    raise BudgetHold("token_proof_unknown")
                if proof.get("fresh_verification_required") is True:
                    self._counter.verify_before_dispatch(copy.deepcopy(payload), copy.deepcopy(proof))
                # Sample the clock after fresh condition IO and full hash validation.
                return wire_timeout(ticket, payload, self._clock) + CLEANUP_SECONDS
            except Exception:
                self.unknown(ticket["reservation_id"], "parent_deadline_or_ticket")
                raise BudgetHold("parent_deadline_or_ticket") from None

    def unknown(self, reservation_id: str, reason: str = "transport_unknown") -> None:
        with self._batch._lock:
            reason = BudgetHold(reason).reason
            entry = self._entries.get(reservation_id) if isinstance(reservation_id, str) else None
            if entry is None:
                self._ticket_entry({})  # Hold without echoing an invalid ID.
            # Never refund an uncertain send or token charge.
            if entry["state"] != "known":
                entry.update(state="unknown", usage=None, stop_reason=reason)
            self._batch._hold_reason = self._batch._hold_reason or reason

    def unknown_if_reserved(self, reservation_id: str, reason: str = "transport_unknown") -> None:
        """Atomically settle an uncertain pending send; completed entries are unchanged."""
        with self._batch._lock:
            entry = self._entries.get(reservation_id) if isinstance(reservation_id, str) else None
            if entry is None:
                self._ticket_entry({})  # Same safe invalid-reservation rejection.
            if entry["state"] == "reserved":
                # The shared RLock stays held across the check and update.
                self.unknown(reservation_id, reason)

    def finish(self, ticket: dict, receipt: Any, response: dict | None, *, transport_ok: bool,
            http_status: int | None = None) -> None:
        with self._batch._lock:
            entry = self._ticket_entry(ticket)
            if entry["state"] == "known":
                # A second completion cannot erase the already certain usage
                # or refund the same reservation twice.
                self._hold("receipt_mismatch")
            try:
                if entry["ticket"] != ticket or entry["state"] != "reserved":
                    raise BudgetHold("receipt_mismatch")
                expected_keys = {"ticket_hash", "reservation_id", "payload_hash", "checked_at", "send_started_at", "response_at", "cleanup_at", "wire_timeout", "sent"}
                if (not isinstance(receipt, dict) or set(receipt) != expected_keys
                        or any(receipt[k] != ticket[k] for k in ("ticket_hash", "reservation_id", "payload_hash"))
                        or receipt["sent"] not in (True, False, "unknown") or (receipt["sent"] != "unknown" and type(receipt["sent"]) is not bool)):
                    raise BudgetHold("receipt_mismatch")
                checked, cleanup = _instant(receipt["checked_at"]), _instant(receipt["cleanup_at"])
                if not ticket["task_started_at"] <= checked <= cleanup <= _instant(self._clock()):
                    raise BudgetHold("receipt_clock")
                send, received = receipt["send_started_at"], receipt["response_at"]
                if receipt["sent"] is False:
                    if send is not None or received is not None or receipt["wire_timeout"] is not None:
                        raise BudgetHold("receipt_mismatch")
                else:
                    send = _instant(send)
                    if not checked <= send <= cleanup:
                        raise BudgetHold("receipt_clock")
                    allowed = min(
                        ticket["requested_timeout"], MAX_WIRE_SECONDS,
                        min(ticket["task_deadline"], ticket["run_deadline"]) - send - CLEANUP_SECONDS)
                    actual_timeout = _instant(receipt["wire_timeout"])
                    if not 1 <= actual_timeout <= allowed:
                        raise BudgetHold("receipt_deadline")
                    if receipt["sent"] is True:
                        received = _instant(received)
                        if not send <= received <= cleanup:
                            raise BudgetHold("receipt_clock")
                    elif received is not None:
                        raise BudgetHold("receipt_mismatch")
                entry.update(sent=receipt["sent"], receipt=copy.deepcopy(receipt))
                entry["http_status"] = http_status if type(http_status) is int and 100 <= http_status <= 599 else None
                if transport_ok and (entry["http_status"] is None or not 200 <= http_status <= 299):
                    raise BudgetHold("transport_or_usage_unknown")
                if not transport_ok or receipt["sent"] is not True or not isinstance(response, dict):
                    raise BudgetHold("transport_or_usage_unknown")
                usage = strict_usage(response, input_reserved=entry["input_reserved"], usage_policy=self._conditions["usage_policy"])
                choices = response.get("choices")
                if (response.get("status") == "incomplete" or (isinstance(choices, list) and any(
                        isinstance(c, dict) and c.get("finish_reason") == "length" for c in choices))):
                    raise BudgetHold("response_truncated")
                if _instant(self._clock()) > min(ticket["run_deadline"], ticket["task_deadline"]):
                    raise BudgetHold("deadline_overrun")
            except BudgetHold as exc:
                self.unknown(ticket["reservation_id"], exc.reason)
                raise BudgetHold(exc.reason) from None
            except Exception:
                self.unknown(ticket["reservation_id"], "receipt_or_usage_unknown")
                raise BudgetHold("receipt_or_usage_unknown") from None
            released = entry["maximum_reserved"] - usage["total_tokens"]
            self._charged -= released
            self._batch._tokens -= released
            entry.update(usage=usage, charged_tokens=usage["total_tokens"], state="known", stop_reason=None)

    def ledger(self) -> dict:
        with self._batch._lock:
            entries = list(copy.deepcopy(self._entries).values())
            observed = sum(e["sent"] is True for e in entries)
            uncertain = sum(e["sent"] == "unknown" for e in entries)
            return {"budget_id": self._budget_id, "run_id": self._run_id,
                "run_started_at": self._run_start, "run_deadline": self._run_start + self._run_seconds,
                "profile": self._profile, "profile_limits": copy.deepcopy(self._limits),
                "profile_receipt": copy.deepcopy(self._profile_receipt),
                "trial_call_limit": self._call_limit, "trial_token_limit": self._token_limit,
                "entry_count": len(entries), "actual_wire_calls": None if uncertain else observed,
                "observed_wire_calls": observed, "reserved_unknown_calls": uncertain,
                "unknown_usage_entries": sum(e["state"] == "unknown" and e["usage"] is None for e in entries),
                "not_sent_calls": sum(e["sent"] is False for e in entries),
                "charged_or_reserved_tokens": self._charged, "batch": self._batch.snapshot(),
                "conditions_hash": payload_hash(self._conditions), "synthetic_only": self._conditions["synthetic_only"],
                "measurement_ready": False, "handler_connected": False, "entries": entries}
