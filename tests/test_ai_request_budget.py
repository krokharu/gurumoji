"""CPU synthetic counter evidence only; no model, SDK, or external HTTP."""
import copy
from dataclasses import FrozenInstanceError
import traceback
import threading
import unittest
from unittest.mock import patch

from gurumoji.services.ai.request_budget import (
    BatchQuota, BudgetHold, COVERAGE, RequestBudget, payload_hash, wire_timeout, prepare_wire,
    C0ProfileReceipt, profile_limits,
)


class Clock:
    def __init__(self, value=1_000_000_000.0):
        self.value = value

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


CONDITIONS = {"model": "synthetic-model", "context_tokens": 32768,
    "tokenizer": "cpu-fixed-counter", "template": "synthetic-template",
    "source": "synthetic-fixture-only", "acceptance_anchor": "CPU-only-test-anchor",
    "model_conditions_hash": payload_hash("synthetic-conditions"),
    "synthetic_only": True, "usage_policy": "reasoning_disabled"}
PAYLOAD = {"model": CONDITIONS["model"], "messages": [{"role": "system", "content": "Synthetic system"},
    {"role": "user", "content": "Synthetic Japanese 日本語"}],
    "response_format": {"type": "json_schema", "json_schema": {"schema": {"type": "object"}}}, "stream": False}


def count_proof(payload, input_tokens=10, **changes):
    return {**CONDITIONS, "payload_hash": payload_hash(payload), "input_tokens": input_tokens,
        "complete_coverage": True, "covered_fields": sorted(COVERAGE), **changes}


def make_budget(clock=None, batch=None, **changes):
    clock = clock or Clock()
    values = dict(budget_id="test-budget", run_id="test-run", run_started_at=clock(),
        batch=batch or BatchQuota(max_calls=216, max_tokens=6193152),
        trial_call_limit=6, trial_token_limit=172032, token_counter=count_proof, model=CONDITIONS["model"],
        context_tokens=32768, tokenizer_id=CONDITIONS["tokenizer"], template_id=CONDITIONS["template"],
        proof_source=CONDITIONS["source"], acceptance_anchor=CONDITIONS["acceptance_anchor"],
        model_conditions_hash=CONDITIONS["model_conditions_hash"], synthetic_only=True,
        usage_policy=CONDITIONS["usage_policy"], clock=clock)
    values.update(changes)
    budget = RequestBudget(**values)
    budget.register_task("task", values["run_started_at"])
    return budget


def synthetic_m_receipt(conditions=None, **changes):
    """CPU-only external-verifier fixture, never a real C0 approval."""
    values = dict(receipt_ref="CPU-only-NOT-C0-EXECUTION-APPROVAL",
        receipt_hash=payload_hash("synthetic-receipt-bytes"), source_sha="0" * 40,
        profile="M", conditions_hash=payload_hash(CONDITIONS if conditions is None else conditions),
        limits_hash=payload_hash(profile_limits("M")))
    values.update(changes)
    return C0ProfileReceipt(**values)


def make_m_budget(clock=None, batch=None, **changes):
    values = dict(profile="M", trial_call_limit=32, trial_token_limit=917504,
        profile_receipt=synthetic_m_receipt(), verify_profile_receipt=lambda receipt: receipt.receipt_hash)
    values.update(changes)
    return make_budget(clock, batch, **values)


def reserve(budget, attempt="attempt", payload=None):
    return budget.reserve(copy.deepcopy(PAYLOAD if payload is None else payload),
        task_id="task", attempt_id=attempt, timeout=240)


def response(**changes):
    return {"choices": [{"finish_reason": "stop", "message": {"content": '{"ok":true}'}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12}, **changes}


def receipt(ticket, clock, sent=True):
    now = clock()
    value = {k: ticket[k] for k in ("ticket_hash", "reservation_id", "payload_hash")}
    value.update(checked_at=now, send_started_at=now if sent is not False else None,
        response_at=now + .1 if sent is True else None, cleanup_at=now + .2,
        wire_timeout=min(235, ticket["task_deadline"] - now - 5) if sent is not False else None, sent=sent)
    clock.advance(.2)
    return value


def finish(budget, reserved, clock, value=None):
    budget.finish(reserved["ticket"], receipt(reserved["ticket"], clock),
        response() if value is None else value, transport_ok=True, http_status=200)


class RequestBudgetTests(unittest.TestCase):
    def test_full_final_payload_is_counted_after_output_cap_and_metadata_not_returned(self):
        clock, counted = Clock(), []
        def counter(payload):
            counted.append(copy.deepcopy(payload))
            return count_proof(payload)
        budget = make_budget(clock, token_counter=counter)
        original = copy.deepcopy(PAYLOAD)
        original["max_tokens"] = 1
        result = reserve(budget, payload=original)
        self.assertEqual(counted[0]["max_tokens"], 4096)
        self.assertEqual(counted[0]["response_format"], PAYLOAD["response_format"])
        self.assertEqual(original["max_tokens"], 1)
        finish(budget, result, clock)
        ledger = budget.ledger()
        self.assertEqual((ledger["entry_count"], ledger["actual_wire_calls"], ledger["charged_or_reserved_tokens"]), (1, 1, 12))
        self.assertFalse(ledger["measurement_ready"])
        self.assertFalse(ledger["handler_connected"])

    def test_fresh_counter_seam_deadline_cost_and_hashed_evidence(self):
        clock = Clock()
        class Counter:
            def __call__(self, payload):
                return count_proof(payload, fresh_verification_required=True)
            def verify_before_dispatch(self, payload, proof):
                self_seen.append((payload_hash(payload), payload_hash(proof)))
                clock.advance(.5)
        self_seen = []
        budget = make_budget(clock, token_counter=Counter(), run_started_at=clock() - 233.8)
        value = reserve(budget)
        ticket = value["ticket"]
        self.assertEqual(ticket["conditions_hash"], payload_hash(budget._conditions))
        self.assertEqual(ticket["counter_proof_hash"], payload_hash(count_proof(value["payload"], fresh_verification_required=True)))
        with self.assertRaisesRegex(BudgetHold, "parent_deadline_or_ticket"):
            budget.dispatch_timeout(ticket, value["payload"])
        self.assertEqual(self_seen, [(ticket["payload_hash"], ticket["counter_proof_hash"])])
        self.assertEqual(budget.ledger()["charged_or_reserved_tokens"], 4106)
        self.assertEqual(budget.ledger()["entries"][0]["state"], "unknown")

    def test_conditions_and_counter_proof_ticket_changes_rejected_in_common_IPC_validator(self):
        clock = Clock(); budget = make_budget(clock); value = reserve(budget)
        for field in ("conditions_hash", "counter_proof_hash"):
            changed = copy.deepcopy(value["ticket"]); changed[field] = payload_hash("different")
            with self.subTest(field=field), self.assertRaisesRegex(BudgetHold, "ticket_changed"):
                prepare_wire(changed, value["payload"], clock)
        # Even a rehashed peer ticket cannot replace the parent's saved entry.
        changed["ticket_hash"] = payload_hash({k: v for k, v in changed.items() if k != "ticket_hash"})
        with self.assertRaisesRegex(BudgetHold, "ticket_changed"):
            budget.dispatch_timeout(changed, value["payload"])
        self.assertEqual(budget.ledger()["charged_or_reserved_tokens"], 4106)

    def test_strict_constructor_types_and_bounds(self):
        bad = [("run_started_at", v) for v in (True, -1, float("nan"), float("inf"), 10**400)]
        bad += [("trial_call_limit", v) for v in (True, 0, 7, 1.0)]
        bad += [("trial_token_limit", v) for v in (True, 0, 172033)]
        bad += [("context_tokens", v) for v in (True, 4095, 32769, 32768.0)]
        bad += [("synthetic_only", 1), ("model_conditions_hash", "unknown"), ("usage_policy", "assumed")]
        for key, value in bad:
            with self.subTest(key=key, value=str(value)[:20]), self.assertRaises(BudgetHold):
                make_budget(**{key: value})
        for values in ({"max_calls": 217, "max_tokens": 1}, {"max_calls": True, "max_tokens": 1},
                       {"max_calls": 1, "max_tokens": float("inf")}, {"max_calls": 1, "max_tokens": 6193153}):
            with self.subTest(values=values), self.assertRaises(BudgetHold):
                BatchQuota(**values)

    def test_external_run_and_task_origins_are_consumed_not_reset(self):
        clock = Clock()
        budget = make_budget(clock, run_started_at=clock() - 500)
        budget.register_task("later", clock() - 100)
        reserved = budget.reserve(PAYLOAD, task_id="later", attempt_id="a", timeout=240)
        self.assertEqual(reserved["ticket"]["run_deadline"], clock() + 100)
        self.assertEqual(reserved["ticket"]["task_deadline"], clock() + 100)
        self.assertEqual(wire_timeout(reserved["ticket"], reserved["payload"], clock()), 95)
        with self.assertRaisesRegex(BudgetHold, "task_origin_changed"):
            budget.register_task("later", clock())

    def test_large_monotonic_origin_keeps_relative_240_deadline(self):
        clock = Clock(1e12)
        budget = make_budget(clock)
        value = reserve(budget)
        self.assertEqual(value["ticket"]["task_deadline"] - clock(), 240)
        self.assertEqual(wire_timeout(value["ticket"], value["payload"], clock()), 235)

    def test_remaining_5_999_has_no_reservation_or_send_and_six_allows_one_second(self):
        for remaining, passes in ((5.999, False), (6, True)):
            with self.subTest(remaining=remaining):
                clock = Clock()
                budget = make_budget(clock, run_started_at=clock() - 240 + remaining)
                if passes:
                    value = reserve(budget)
                    self.assertEqual(wire_timeout(value["ticket"], value["payload"], clock()), 1)
                else:
                    with self.assertRaises(BudgetHold): reserve(budget)
                    self.assertEqual(budget.ledger()["entry_count"], 0)

    def test_tokenization_time_consumes_original_deadline(self):
        clock = Clock()
        def slow(payload):
            clock.advance(.5)
            return count_proof(payload)
        budget = make_budget(clock, run_started_at=clock() - 233.8, token_counter=slow)
        with self.assertRaisesRegex(BudgetHold, "deadline_reserve"): reserve(budget)
        self.assertEqual(budget.ledger()["entry_count"], 0)

    def test_send_clock_is_sampled_after_final_payload_hash_cost(self):
        clock = Clock(); budget = make_budget(clock, run_started_at=clock() - 233.8)
        value = reserve(budget)
        original_hash = payload_hash
        def slow_hash(item):
            if item == value["payload"]:
                clock.advance(.5)
            return original_hash(item)
        with patch("gurumoji.services.ai.request_budget.payload_hash", side_effect=slow_hash):
            with self.assertRaisesRegex(BudgetHold, "deadline_reserve"):
                prepare_wire(value["ticket"], value["payload"], clock)

    def test_batch_216_actual_wire_receipts_and_217th_reservation_rejected(self):
        clock, batch = Clock(), BatchQuota(max_calls=216, max_tokens=6193152)
        actual_calls = 0
        for run in range(36):
            budget = make_budget(clock, batch, run_id="batch-run-" + str(run))
            for attempt in range(6): finish(budget, reserve(budget, str(attempt)), clock)
            actual_calls += budget.ledger()["actual_wire_calls"]
        self.assertEqual(actual_calls, 216)
        self.assertEqual(batch.snapshot()["reserved_entries"], 216)
        extra = make_budget(clock, batch, run_id="217th-run")
        with self.assertRaisesRegex(BudgetHold, "call_limit"): reserve(extra)
        self.assertEqual(extra.ledger()["entry_count"], 0)

    def test_proof_missing_partial_wrong_hash_or_conditions_holds_before_wire(self):
        mutations = [{"payload_hash": payload_hash("wrong")}, {"model": "other"}, {"template": "other"},
            {"source": "other"}, {"context_tokens": 32768.0}, {"synthetic_only": False},
            {"acceptance_anchor": "different"}, {"model_conditions_hash": payload_hash("different")},
            {"complete_coverage": False}, {"covered_fields": ["model", "messages"]},
            {"input_tokens": None}, {"input_tokens": True}, {"input_tokens": 10.0}, {"input_tokens": 24577}]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                budget = make_budget(token_counter=lambda p: count_proof(p, **mutation))
                with self.assertRaises(BudgetHold): reserve(budget)
                self.assertEqual(budget.ledger()["entry_count"], 0)
                self.assertIsNotNone(budget.ledger()["batch"]["hold_reason"])

    def test_counter_exception_never_exposes_details(self):
        for error in (RuntimeError("secret-payload"), BudgetHold("secret-payload")):
            def counter(_): raise error
            budget = make_budget(token_counter=counter)
            try:
                reserve(budget)
            except BudgetHold as raised:
                self.assertNotIn("secret-payload", "".join(traceback.format_exception(raised)))
            else:
                self.fail("counter exception must hold")
            self.assertNotIn("secret-payload", str(budget.ledger()))

    def test_input_context_and_total_reservation_limits_prevent_first_wire(self):
        for changes in ({"trial_token_limit": 4105}, {"batch": BatchQuota(max_calls=216, max_tokens=4105)},
                        {"context_tokens": 5000, "token_counter": lambda p: count_proof(p, input_tokens=1000, context_tokens=5000)}):
            with self.subTest(changes=changes):
                budget = make_budget(**changes)
                with self.assertRaises(BudgetHold): reserve(budget)
                self.assertEqual(budget.ledger()["entry_count"], 0)
        budget = make_budget(token_counter=lambda p: count_proof(p, input_tokens=24576))
        value = reserve(budget)
        self.assertEqual(budget.ledger()["charged_or_reserved_tokens"], 28672)
        self.assertEqual(value["payload"]["max_tokens"], 4096)

    def test_all_six_wire_reservations_and_seventh_rejected(self):
        clock, budget = Clock(), None
        budget = make_budget(clock)
        for n in range(6): finish(budget, reserve(budget, str(n)), clock)
        with self.assertRaisesRegex(BudgetHold, "call_limit"): reserve(budget, "seventh")
        ledger = budget.ledger()
        self.assertEqual((ledger["entry_count"], ledger["actual_wire_calls"]), (6, 6))
        self.assertEqual(ledger["charged_or_reserved_tokens"], 72)

    def test_batch_cap_shared_across_runs_and_no_reset_by_duplicate_run(self):
        clock, batch = Clock(), BatchQuota(max_calls=1, max_tokens=10000)
        first, second = make_budget(clock, batch, run_id="first"), make_budget(clock, batch, run_id="second")
        finish(first, reserve(first), clock)
        with self.assertRaisesRegex(BudgetHold, "call_limit"): reserve(second)
        self.assertEqual(batch.snapshot()["reserved_entries"], 1)
        with self.assertRaisesRegex(BudgetHold, "duplicate_run_budget"):
            make_budget(clock, batch, run_id="first")

    def test_token_release_only_after_known_usage_still_checks_next_maximum(self):
        clock, batch = Clock(), BatchQuota(max_calls=6, max_tokens=4106)
        budget = make_budget(clock, batch)
        finish(budget, reserve(budget), clock)
        self.assertEqual(batch.snapshot()["charged_or_reserved_tokens"], 12)
        with self.assertRaisesRegex(BudgetHold, "token_limit"): reserve(budget, "next")

    def test_raw_unknown_usage_retains_maximum_and_holds_without_zero_coercion(self):
        invalid = [None, {}, {"prompt_tokens": 10, "completion_tokens": 2},
            {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 13}]
        for field in ("prompt_tokens", "completion_tokens", "total_tokens"):
            for bad in (-1, True, 1.0, float("nan"), float("inf"), "1"):
                invalid.append({"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12, field: bad})
        invalid += [{"prompt_tokens": 10, "completion_tokens": 4097, "total_tokens": 4107},
            {"prompt_tokens": 11, "completion_tokens": 2, "total_tokens": 13},
            {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12, "completion_tokens_details": {"reasoning_tokens": 1}},
            {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12, "prompt_tokens_details": {"cached_tokens": True}},
            {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12, "cached_tokens": -1}]
        for raw in invalid:
            with self.subTest(raw=raw):
                clock = Clock(); budget = make_budget(clock); value = reserve(budget)
                with self.assertRaisesRegex(BudgetHold, "usage_unknown"):
                    finish(budget, value, clock, response(usage=raw))
                ledger = budget.ledger()
                self.assertIsNone(ledger["entries"][0]["usage"])
                self.assertEqual(ledger["charged_or_reserved_tokens"], 4106)
                self.assertEqual(ledger["actual_wire_calls"], 1)
                with self.assertRaisesRegex(BudgetHold, "batch_held"): reserve(budget, "retry")

    def test_proven_included_reasoning_is_not_double_added_unknown_policy_holds(self):
        clock = Clock()
        budget = make_budget(clock, usage_policy="output_includes_reasoning",
            token_counter=lambda p: count_proof(p, usage_policy="output_includes_reasoning"))
        finish(budget, reserve(budget), clock, response(usage={"prompt_tokens": 10,
            "completion_tokens": 2, "total_tokens": 12, "completion_tokens_details": {"reasoning_tokens": 1}}))
        self.assertEqual(budget.ledger()["charged_or_reserved_tokens"], 12)
        budget = make_budget(clock, usage_policy=None, token_counter=lambda p: count_proof(p, usage_policy=None))
        with self.assertRaisesRegex(BudgetHold, "usage_unknown"): finish(budget, reserve(budget), clock)

    def test_unknown_transport_and_truncation_hold_even_with_known_sent(self):
        clock = Clock(); budget = make_budget(clock); value = reserve(budget)
        budget.unknown(value["ticket"]["reservation_id"])
        self.assertEqual(budget.ledger()["reserved_unknown_calls"], 1)
        self.assertEqual(budget.ledger()["charged_or_reserved_tokens"], 4106)
        with self.assertRaises(BudgetHold): reserve(budget, "next")
        budget = make_budget(clock); value = reserve(budget)
        with self.assertRaisesRegex(BudgetHold, "response_truncated"):
            finish(budget, value, clock, response(choices=[{"finish_reason": "length"}]))
        self.assertEqual(budget.ledger()["charged_or_reserved_tokens"], 4106)

    def test_request_hash_budget_id_deadline_and_receipt_tampering_are_rejected(self):
        clock = Clock(); budget = make_budget(clock); value = reserve(budget)
        for key, bad in (("budget_id", payload_hash("changed")), ("payload_hash", payload_hash("changed")),
                         ("run_deadline", True), ("task_deadline", clock() + 500)):
            changed = copy.deepcopy(value["ticket"]); changed[key] = bad
            with self.subTest(key=key), self.assertRaises(BudgetHold): wire_timeout(changed, value["payload"], clock())
        changed = copy.deepcopy(value["payload"]); changed["messages"][0]["content"] = "changed"
        with self.assertRaisesRegex(BudgetHold, "request_changed"): wire_timeout(value["ticket"], changed, clock())
        bad = receipt(value["ticket"], clock); bad["ticket_hash"] = payload_hash("other")
        with self.assertRaisesRegex(BudgetHold, "receipt_mismatch"):
            budget.finish(value["ticket"], bad, response(), transport_ok=True, http_status=200)
        self.assertEqual(budget.ledger()["reserved_unknown_calls"], 1)

    def test_duplicate_request_identity_is_not_a_second_wire(self):
        clock = Clock(); budget = make_budget(clock); value = reserve(budget)
        finish(budget, value, clock)
        with self.assertRaisesRegex(BudgetHold, "duplicate_request"): reserve(budget)
        changed = copy.deepcopy(PAYLOAD); changed["messages"] = []
        with self.assertRaisesRegex(BudgetHold, "request_identity_changed"): reserve(budget, payload=changed)
        self.assertEqual(budget.ledger()["entry_count"], 1)

    def test_replayed_completion_cannot_refund_twice_or_erase_known_usage(self):
        clock = Clock(); budget = make_budget(clock); value = reserve(budget)
        received = receipt(value["ticket"], clock)
        budget.finish(value["ticket"], received, response(), transport_ok=True, http_status=200)
        with self.assertRaisesRegex(BudgetHold, "receipt_mismatch"):
            budget.finish(value["ticket"], received, response(), transport_ok=True, http_status=200)
        self.assertEqual(budget.ledger()["charged_or_reserved_tokens"], 12)
        self.assertEqual(budget.ledger()["entries"][0]["usage"]["total_tokens"], 12)

    def test_altered_reservation_id_holds_without_keyerror_or_refund(self):
        clock = Clock(); budget = make_budget(clock); value = reserve(budget)
        changed = copy.deepcopy(value["ticket"]); changed["reservation_id"] = "secret-altered-id"
        with self.assertRaisesRegex(BudgetHold, "ticket_changed") as raised:
            budget.dispatch_timeout(changed, value["payload"])
        self.assertNotIn("secret-altered-id", str(raised.exception))
        self.assertEqual(budget.ledger()["charged_or_reserved_tokens"], 4106)
        self.assertEqual(budget.ledger()["reserved_unknown_calls"], 1)

    def test_inconsistent_reasoning_detail_is_unknown_even_when_inclusion_proven(self):
        clock = Clock()
        budget = make_budget(clock, usage_policy="output_includes_reasoning",
            token_counter=lambda p: count_proof(p, usage_policy="output_includes_reasoning"))
        with self.assertRaisesRegex(BudgetHold, "usage_unknown"):
            finish(budget, reserve(budget), clock, response(usage={"prompt_tokens": 10,
                "completion_tokens": 2, "total_tokens": 12, "reasoning_tokens": 1,
                "completion_tokens_details": {"reasoning_tokens": 2}}))

    def test_parallel_runs_have_isolated_ledgers_and_shared_batch_lock(self):
        clock = Clock(); first = make_budget(clock); second = make_budget(clock)
        first.unknown(reserve(first)["ticket"]["reservation_id"])
        finish(second, reserve(second), clock)
        self.assertIsNone(second.ledger()["batch"]["hold_reason"])
        batch = BatchQuota(max_calls=1, max_tokens=10000)
        budgets = [make_budget(clock, batch, run_id=str(n)) for n in range(2)]
        barrier, outcomes = threading.Barrier(2), []
        def run(budget):
            barrier.wait()
            try: reserve(budget); outcomes.append("reserved")
            except BudgetHold: outcomes.append("held")
        threads = [threading.Thread(target=run, args=(b,)) for b in budgets]
        for thread in threads: thread.start()
        for thread in threads: thread.join(2)
        self.assertCountEqual(outcomes, ["reserved", "held"])
        self.assertEqual(batch.snapshot()["reserved_entries"], 1)

    def test_atomic_unknown_reserves_maximum_and_leaves_other_entry_untouched(self):
        clock = Clock(); budget = make_budget(clock)
        first, second = reserve(budget), reserve(budget, "second")
        before = budget.ledger()
        budget.unknown_if_reserved(first["ticket"]["reservation_id"], "deadline_reserve")
        after = budget.ledger()
        self.assertEqual(after["entries"][1], before["entries"][1])
        self.assertEqual(after["entries"][0]["state"], "unknown")
        self.assertEqual(after["entries"][0]["stop_reason"], "deadline_reserve")
        self.assertEqual(after["charged_or_reserved_tokens"], 8212)
        self.assertEqual(after["batch"]["hold_reason"], "deadline_reserve")
        self.assertIsNone(after["actual_wire_calls"])
        with self.assertRaisesRegex(BudgetHold, "batch_held"): reserve(budget, "next")
        self.assertEqual(budget.ledger(), after)

    def test_atomic_unknown_is_exact_noop_for_known_zero_known_usage_and_unknown(self):
        for input_tokens, output_tokens, unknown in ((0, 0, False), (10, 2, False), (0, 0, True)):
            with self.subTest(input_tokens=input_tokens, unknown=unknown):
                clock = Clock(); budget = make_budget(clock, token_counter=lambda p: count_proof(p, input_tokens=input_tokens))
                value = reserve(budget)
                usage = {} if unknown else {"prompt_tokens": input_tokens, "completion_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens}
                if unknown:
                    with self.assertRaisesRegex(BudgetHold, "usage_unknown"): finish(budget, value, clock, response(usage=usage))
                else:
                    finish(budget, value, clock, response(usage=usage))
                before = budget.ledger()
                budget.unknown_if_reserved(value["ticket"]["reservation_id"], "deadline_reserve")
                budget.unknown_if_reserved(value["ticket"]["reservation_id"], "transport_unknown")
                self.assertEqual(budget.ledger(), before)

    def test_atomic_unknown_holds_lock_against_same_reservation_finish(self):
        clock = Clock(); budget = make_budget(clock); value = reserve(budget)
        received = receipt(value["ticket"], clock)
        entered, probed = threading.Event(), threading.Event()
        lock_held, outcomes, failures = [], [], []
        original_unknown = budget.unknown
        def concurrent_finish():
            try:
                if not entered.wait(2): raise AssertionError("transition boundary not reached")
                acquired = budget._batch._lock.acquire(blocking=False)
                lock_held.append(not acquired)
                if acquired: budget._batch._lock.release()
                probed.set()
                try:
                    budget.finish(value["ticket"], received, response(), transport_ok=True, http_status=200)
                except BudgetHold as exc:
                    outcomes.append(exc.reason)
            except BaseException as exc:
                failures.append(exc)
                probed.set()
        def observed_unknown(*args, **kwargs):
            entered.set()
            self.assertTrue(probed.wait(2))
            return original_unknown(*args, **kwargs)
        thread = threading.Thread(target=concurrent_finish)
        thread.start()
        try:
            with patch.object(budget, "unknown", side_effect=observed_unknown):
                budget.unknown_if_reserved(value["ticket"]["reservation_id"])
        finally:
            entered.set()
            thread.join(2)
            self.assertFalse(thread.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(lock_held, [True])
        self.assertEqual(outcomes, ["receipt_mismatch"])
        ledger = budget.ledger()
        self.assertEqual(ledger["entries"][0]["state"], "unknown")
        self.assertIsNone(ledger["entries"][0]["usage"])
        self.assertEqual(ledger["charged_or_reserved_tokens"], 4106)
        self.assertEqual(ledger["batch"]["hold_reason"], "transport_unknown")
        with self.assertRaisesRegex(BudgetHold, "batch_held"): reserve(budget, "next")

    def test_atomic_unknown_rejects_unknown_reservation_without_echo_or_refund(self):
        clock = Clock(); budget = make_budget(clock); reserve(budget)
        with self.assertRaisesRegex(BudgetHold, "ticket_changed") as raised:
            budget.unknown_if_reserved("synthetic-private-invalid-id")
        self.assertNotIn("synthetic-private", str(raised.exception))
        self.assertEqual(budget.ledger()["charged_or_reserved_tokens"], 4106)
        self.assertEqual(budget.ledger()["entries"][0]["state"], "unknown")


class MProfileTests(unittest.TestCase):
    def test_explicit_verified_M_seven_then_32_allowed_33_rejected(self):
        clock = Clock(); budget = make_m_budget(clock)
        for n in range(32):
            finish(budget, reserve(budget, str(n)), clock)
            if n == 6:
                self.assertEqual(budget.ledger()["actual_wire_calls"], 7)
        with self.assertRaisesRegex(BudgetHold, "call_limit"): reserve(budget, "33")
        ledger = budget.ledger()
        self.assertEqual(ledger["entry_count"], 32)
        self.assertEqual(ledger["charged_or_reserved_tokens"], 32 * 12)
        self.assertEqual(ledger["profile"], "M")
        self.assertEqual(ledger["run_deadline"] - ledger["run_started_at"], 1800)
        self.assertEqual(ledger["trial_token_limit"], 917504)
        self.assertFalse(ledger["measurement_ready"])

    def test_legacy_six_and_600_are_unchanged_and_no_receipt_needed(self):
        clock = Clock(); budget = make_budget(clock)
        for n in range(6): finish(budget, reserve(budget, str(n)), clock)
        with self.assertRaisesRegex(BudgetHold, "call_limit"): reserve(budget, "7")
        ledger = budget.ledger()
        self.assertEqual(ledger["profile"], "legacy")
        self.assertIsNone(ledger["profile_receipt"])
        self.assertEqual(ledger["run_deadline"] - ledger["run_started_at"], 600)
        self.assertEqual((ledger["trial_call_limit"], ledger["trial_token_limit"]), (6, 172032))

    def test_M_needs_immutable_receipt_and_external_exact_verification(self):
        for changes in ({"profile_receipt": None}, {"verify_profile_receipt": None},
                        {"profile_receipt": True}, {"profile_receipt": {}},
                        {"verify_profile_receipt": lambda _: True},
                        {"verify_profile_receipt": lambda _: payload_hash("other")},
                        {"profile_receipt": synthetic_m_receipt(conditions_hash=payload_hash("other"))},
                        {"profile_receipt": synthetic_m_receipt(limits_hash=payload_hash("other"))},
                        {"profile_receipt": synthetic_m_receipt(profile="legacy")},
                        {"profile_receipt": synthetic_m_receipt(source_sha="unknown")},
                        {"trial_call_limit": 33}, {"trial_token_limit": 917505}):
            with self.subTest(changes=changes), self.assertRaises(BudgetHold): make_m_budget(**changes)
        receipt = synthetic_m_receipt()
        with self.assertRaises(FrozenInstanceError): receipt.profile = "legacy"
        calls = []
        budget = make_m_budget(profile_receipt=receipt,
            verify_profile_receipt=lambda received: calls.append(received) or received.receipt_hash)
        self.assertEqual(calls, [receipt])
        ledger = budget.ledger(); ledger["profile_receipt"]["receipt_hash"] = payload_hash("changed")
        self.assertEqual(budget.ledger()["profile_receipt"]["receipt_hash"], receipt.receipt_hash)
        for profile in (None, True, "m", "unknown"):
            with self.subTest(profile=profile), self.assertRaisesRegex(BudgetHold, "invalid_profile"):
                make_budget(profile=profile)
        with self.assertRaisesRegex(BudgetHold, "profile_receipt_invalid"):
            make_budget(profile_receipt=receipt)

    def test_M_external_verifier_failure_does_not_leak_and_never_consumes_run(self):
        batch = BatchQuota(max_calls=216, max_tokens=6193152)
        def denied(_): raise RuntimeError("private-approval-details")
        try:
            make_m_budget(batch=batch, verify_profile_receipt=denied)
        except BudgetHold as exc:
            self.assertNotIn("private-approval-details", "".join(traceback.format_exception(exc)))
        else: self.fail("receipt verification must fail closed")
        self.assertEqual(batch.snapshot()["reserved_entries"], 0)
        self.assertEqual(make_m_budget(batch=batch).ledger()["entry_count"], 0)

    def test_M_task_wire_cleanup_limits_and_external_origins_are_unchanged(self):
        clock = Clock(); origin = clock(); budget = make_m_budget(clock)
        clock.advance(700); budget.register_task("later", clock())
        value = budget.reserve(PAYLOAD, task_id="later", attempt_id="1", timeout=1000)
        self.assertEqual(value["ticket"]["run_deadline"], origin + 1800)
        self.assertEqual(value["ticket"]["task_deadline"], origin + 940)
        self.assertEqual(wire_timeout(value["ticket"], value["payload"], clock), 235)
        clock.advance(234)
        self.assertEqual(wire_timeout(value["ticket"], value["payload"], clock), 1)
        clock.advance(.001)
        with self.assertRaisesRegex(BudgetHold, "parent_deadline_or_ticket"):
            budget.dispatch_timeout(value["ticket"], value["payload"])

    def test_M_common_worker_validation_rejects_profile_caps_receipt_and_deadline_changes(self):
        clock = Clock(); budget = make_m_budget(clock); value = reserve(budget)
        ticket = value["ticket"]
        fields = {"profile": "legacy", "profile_receipt": None, "trial_call_limit": 33,
            "trial_token_limit": 917505, "batch_call_limit": 217, "batch_token_limit": 6193153,
            "run_deadline": clock() + 1801, "task_deadline": clock() + 241,
            "requested_timeout": 236, "conditions_hash": payload_hash("different")}
        changes = [{key: bad} for key, bad in fields.items()]
        for key in ticket["profile_limits"]:
            changes.append({"profile_limits": {**ticket["profile_limits"], key: "changed"}})
        for key in ("profile", "conditions_hash", "limits_hash", "source_sha"):
            changes.append({"profile_receipt": {**ticket["profile_receipt"], key: "changed"}})
        for patch in changes:
            changed = copy.deepcopy(ticket); changed.update(patch)
            # Even internally rehashed impossible profiles/ceilings are rejected.
            changed["ticket_hash"] = payload_hash({k: v for k, v in changed.items() if k != "ticket_hash"})
            with self.subTest(patch=patch), self.assertRaises(BudgetHold):
                prepare_wire(changed, value["payload"], clock)
        changed = copy.deepcopy(ticket)
        changed["profile_receipt"]["receipt_hash"] = payload_hash("different-approval")
        changed["ticket_hash"] = payload_hash({k: v for k, v in changed.items() if k != "ticket_hash"})
        with self.assertRaisesRegex(BudgetHold, "ticket_changed"):
            budget.dispatch_timeout(changed, value["payload"])
        self.assertEqual(budget.ledger()["charged_or_reserved_tokens"], 4106)

    def test_M_unknown_transport_usage_duplicate_and_same_run_cannot_reset(self):
        for reason in ("transport_unknown", "usage_unknown"):
            clock = Clock(); batch = BatchQuota(max_calls=216, max_tokens=6193152)
            budget = make_m_budget(clock, batch); value = reserve(budget)
            with self.assertRaisesRegex(BudgetHold, "duplicate_request"): reserve(budget)
            if reason == "usage_unknown":
                with self.assertRaisesRegex(BudgetHold, reason):
                    finish(budget, value, clock, response(usage={}))
            else: budget.unknown(value["ticket"]["reservation_id"])
            with self.assertRaisesRegex(BudgetHold, "batch_held"): reserve(budget, "retry")
            with self.assertRaisesRegex(BudgetHold, "duplicate_run_budget"):
                make_m_budget(clock, batch)
            self.assertEqual(budget.ledger()["charged_or_reserved_tokens"], 4106)
            self.assertEqual(budget.ledger()["unknown_usage_entries"], 1)

    def test_M_batch_216_cannot_expand_and_schema_is_full_payload_bound(self):
        clock = Clock(); batch = BatchQuota(max_calls=216, max_tokens=6193152)
        for run in range(7):
            budget = make_m_budget(clock, batch, run_id="M-" + str(run))
            for attempt in range(32 if run < 6 else 24):
                finish(budget, reserve(budget, str(attempt)), clock)
        with self.assertRaisesRegex(BudgetHold, "call_limit"): reserve(budget, "217")
        self.assertEqual(batch.snapshot()["reserved_entries"], 216)
        budget = make_m_budget(clock); value = reserve(budget)
        changed = copy.deepcopy(value["payload"])
        changed["response_format"]["json_schema"]["schema"]["description"] = "changed"
        with self.assertRaisesRegex(BudgetHold, "request_changed"):
            prepare_wire(value["ticket"], changed, clock)


if __name__ == "__main__":
    unittest.main()
