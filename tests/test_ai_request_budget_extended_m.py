"""Synthetic CPU/IPC fixtures only, never C0 authorization for model execution.

The real parent/worker validators run with an in-memory JSON transport and a
fake opener. No socket, HTTP request, model, SDK, application DB or Vault is used.
"""
import copy
import json
import socket
import subprocess
import sys
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import Mock, patch

from gurumoji import ai_http_worker as worker
from gurumoji.services.ai import client
from gurumoji.services.ai.request_budget import (
    BatchQuota, BudgetHold, C0ProfileReceipt, payload_hash, prepare_wire, profile_limits,
)
from test_ai_request_budget import (
    Clock, CONDITIONS, PAYLOAD, count_proof, finish, make_budget, make_m_budget,
    reserve, response, synthetic_m_receipt,
)


EXTENDED_LIMITS = {"profile": "M_extended", "run_seconds": 8400,
    "trial_calls": 32, "trial_tokens": 32 * 28672, "task_seconds": 240,
    "wire_seconds": 235, "cleanup_seconds": 5, "context_tokens": 32768,
    "input_tokens": 24576, "output_tokens": 4096, "batch_calls": 216,
    "batch_tokens": 216 * 28672}


def synthetic_extended_receipt(**changes):
    """A fixed synthetic external record; it grants no real execution approval."""
    record = {"synthetic_only": True, "execution_authorized": False,
        "source_sha": "e" * 40, "profile": "M_extended",
        "conditions_hash": payload_hash(CONDITIONS), "limits_hash": payload_hash(EXTENDED_LIMITS)}
    receipt = C0ProfileReceipt(receipt_ref="synthetic://CPU-only-NOT-C0-EXECUTION-APPROVAL",
        receipt_hash=payload_hash(record), **{key: record[key] for key in (
            "source_sha", "profile", "conditions_hash", "limits_hash")})
    return replace(receipt, **changes)


def verify_synthetic_record(receipt):
    """Test-only trusted verifier checks every binding against the fixed record."""
    if receipt != synthetic_extended_receipt():
        raise ValueError("synthetic receipt does not match the external fixture")
    return receipt.receipt_hash


def make_extended_budget(clock=None, batch=None, **changes):
    values = {"profile": "M_extended", "trial_call_limit": 32, "trial_token_limit": 917504,
        "profile_receipt": synthetic_extended_receipt(), "verify_profile_receipt": verify_synthetic_record}
    values.update(changes)
    return make_budget(clock, batch, **values)


class ExtendedMProfileTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.ipc_inputs, self.worker_results, self.parent_timeouts = [], [], []
        self.prepare_delay = 0
        self.mutate_ticket = None
        self.worker_body = response()
        self.open_error = None
        self.cancel_after_open = False
        self.fake_response = Mock(status=200, headers={})
        self.fake_response.__enter__ = Mock(return_value=self.fake_response)
        self.fake_response.__exit__ = Mock(return_value=False)
        self.fake_response.read.side_effect = self.read_response
        self.opener = Mock()
        self.opener.open.side_effect = self.open_response
        for target in ("socket", "create_connection"):
            blocker = patch.object(socket, target, side_effect=AssertionError("socket use forbidden"))
            blocker.start()
            self.addCleanup(blocker.stop)

    def open_response(self, request, timeout):
        if self.open_error is not None:
            raise self.open_error
        return self.fake_response

    def read_response(self, size):
        self.clock.advance(.2)
        return json.dumps(self.worker_body).encode("utf-8")

    def build_opener(self, *handlers):
        self.clock.advance(self.prepare_delay)
        return self.opener

    def run_in_memory_worker(self, command, *, input_text, timeout, check_cancelled):
        wire = json.loads(input_text)
        self.ipc_inputs.append(copy.deepcopy(wire))
        self.parent_timeouts.append(timeout)
        if self.mutate_ticket is not None:
            self.mutate_ticket(wire["request_budget"])
            ticket = wire["request_budget"]
            ticket["ticket_hash"] = payload_hash({k: v for k, v in ticket.items() if k != "ticket_hash"})
        # Preserve actual worker validation/receipt code; replace only clock and I/O.
        with patch.object(worker.time, "monotonic", self.clock), \
                patch.object(worker.urllib.request, "build_opener", side_effect=self.build_opener), \
                patch.object(worker, "emit", side_effect=lambda value: self.worker_results.append(
                    json.loads(json.dumps(value)))), patch.object(sys, "path", list(sys.path)):
            self.assertEqual(worker.guarded_main(wire), 0)
        if self.cancel_after_open:
            raise InterruptedError("synthetic cancellation after uncertain delivery")
        return subprocess.CompletedProcess(command, 0, json.dumps(self.worker_results[-1]), "")

    def post(self, budget, task_id="task", attempt_id="attempt"):
        return client.post_json("http://127.0.0.1:9/v1/chat/completions", {}, PAYLOAD,
            worker_file=Path(worker.__file__), run_subprocess=self.run_in_memory_worker,
            request_budget=budget, task_id=task_id, attempt_id=attempt_id,
            timeout=1000, retry_delays=(0, 0))

    def assert_unknown_cost(self, budget, expected=4106):
        ledger = budget.ledger()
        self.assertEqual(ledger["entry_count"], 1)
        self.assertEqual(ledger["entries"][0]["state"], "unknown")
        self.assertIsNone(ledger["entries"][0]["usage"])
        self.assertEqual(ledger["charged_or_reserved_tokens"], expected)
        self.assertEqual(ledger["batch"]["charged_or_reserved_tokens"], expected)
        with self.assertRaisesRegex(BudgetHold, "batch_held"):
            self.post(budget, attempt_id="no-retry")
        self.assertEqual(budget.ledger(), ledger)

    def test_exact_limits_and_legacy_M_serialized_hashes_are_unchanged(self):
        self.assertEqual(profile_limits("M_extended"), EXTENDED_LIMITS)
        self.assertEqual(profile_limits("M_extended"), {**profile_limits("M"),
            "profile": "M_extended", "run_seconds": 8400})
        for profile, expected in (("legacy", "2ec9aa9e3344dcdce6a2fa8b59722175e388407a46744bfedc66fbaa3204355f"),
                ("M", "ef34d6161a0009a8d18eb5a39272281561bc5ec0e0403615994e54abfdad200d")):
            with self.subTest(profile=profile):
                self.assertEqual(payload_hash(profile_limits(profile)), "sha256:" + expected)
        changed = profile_limits("M_extended")
        changed["run_seconds"] = 9000
        self.assertEqual(profile_limits("M_extended"), EXTENDED_LIMITS)

    def test_verified_reservation_IPC_worker_and_known_usage_after_old_M_deadline(self):
        origin = self.clock()
        verifier = Mock(side_effect=verify_synthetic_record)
        budget = make_extended_budget(self.clock, verify_profile_receipt=verifier)
        verifier.assert_called_once_with(synthetic_extended_receipt())
        self.clock.advance(2000)
        budget.register_task("later", self.clock())
        self.prepare_delay = 17
        self.assertEqual(self.post(budget, "later"), response())
        ticket = self.ipc_inputs[0]["request_budget"]
        self.assertEqual(ticket["run_started_at"], origin)
        self.assertEqual(ticket["run_deadline"], origin + 8400)
        self.assertEqual(ticket["task_deadline"], origin + 2240)
        self.assertEqual(ticket["requested_timeout"], 235)
        self.assertEqual(ticket["profile_limits"], EXTENDED_LIMITS)
        self.assertEqual(ticket["profile_receipt"], asdict(synthetic_extended_receipt()))
        self.assertEqual(self.parent_timeouts, [240])
        self.assertEqual(self.opener.open.call_args.kwargs["timeout"], 218)
        ledger = budget.ledger()
        self.assertEqual(ledger["entries"][0]["ticket"], ticket)
        self.assertEqual(ledger["entries"][0]["receipt"], self.worker_results[0]["budget_receipt"])
        self.assertEqual(ledger["entries"][0]["state"], "known")
        self.assertEqual(ledger["entries"][0]["usage"]["total_tokens"], 12)
        self.assertEqual((ledger["actual_wire_calls"], ledger["charged_or_reserved_tokens"]), (1, 12))
        self.assertTrue(ledger["synthetic_only"])
        self.assertFalse(ledger["measurement_ready"])
        self.assertFalse(ledger["handler_connected"])
        history = copy.deepcopy(ledger)
        ledger["profile_receipt"]["source_sha"] = "f" * 40
        ledger["entries"][0]["ticket"]["run_deadline"] += 1
        self.assertEqual(budget.ledger(), history)

    def test_legacy_and_old_M_receipt_keep_original_deadlines_and_no_fallback(self):
        for factory, seconds in ((make_budget, 600), (make_m_budget, 1800)):
            with self.subTest(seconds=seconds):
                clock = Clock()
                budget = factory(clock)
                finish(budget, reserve(budget), clock)
                self.assertEqual(budget.ledger()["run_deadline"], 1_000_000_000 + seconds)
                clock.value = 1_000_000_000 + seconds
                with self.assertRaisesRegex(BudgetHold, "invalid_deadline"):
                    budget.register_task("expired", clock())
                self.assertEqual(budget.ledger()["charged_or_reserved_tokens"], 12)
        self.assertEqual(make_m_budget().ledger()["profile_receipt"], asdict(synthetic_m_receipt()))

    def test_missing_self_attested_old_or_mismatched_receipts_fail_closed(self):
        changes = [{"profile_receipt": value} for value in (None, True, {}, synthetic_m_receipt())]
        changes += [{"verify_profile_receipt": value} for value in (
            None, True, lambda _: True, lambda _: payload_hash("other"))]
        changes += [{"profile_receipt": synthetic_extended_receipt(**{key: value})} for key, value in (
            ("profile", "M"), ("conditions_hash", payload_hash("other")),
            ("limits_hash", payload_hash(profile_limits("M"))), ("source_sha", "unknown"),
            ("source_sha", "f" * 40), ("receipt_hash", payload_hash("changed-record")),
            ("receipt_ref", "synthetic://wrong-external-record"))]
        for change in changes:
            with self.subTest(change=change):
                batch = BatchQuota(max_calls=216, max_tokens=6193152)
                with self.assertRaises(BudgetHold):
                    make_extended_budget(self.clock, batch, **change)
                self.assertEqual(batch.snapshot()["reserved_entries"], 0)
                self.assertEqual(make_extended_budget(self.clock, batch).ledger()["entry_count"], 0)

    def test_unknown_profiles_and_arbitrary_ceiling_overrides_are_rejected(self):
        for profile in (None, True, "m_extended", "M_extended_8401", "unknown", {"run_seconds": 8400}):
            with self.subTest(profile=profile), self.assertRaisesRegex(BudgetHold, "invalid_profile"):
                make_extended_budget(profile=profile)
        for change in ({"trial_call_limit": 33}, {"trial_token_limit": 917505},
                {"context_tokens": 32769}, {"trial_call_limit": True}, {"trial_token_limit": 917504.0}):
            with self.subTest(change=change), self.assertRaises(BudgetHold):
                make_extended_budget(**change)
        with self.assertRaises(TypeError):
            make_extended_budget(run_seconds=8401)

    def test_32_call_ceiling_and_full_input_output_reservation_are_unchanged(self):
        budget = make_extended_budget(self.clock, token_counter=lambda p: count_proof(p, input_tokens=24576))
        for n in range(32):
            value = reserve(budget, str(n))
            self.assertEqual(value["payload"]["max_tokens"], 4096)
        ledger = budget.ledger()
        self.assertEqual((ledger["entry_count"], ledger["charged_or_reserved_tokens"]), (32, 917504))
        with self.assertRaisesRegex(BudgetHold, "call_limit"):
            reserve(budget, "33")
        self.assertEqual(budget.ledger()["charged_or_reserved_tokens"], 917504)

    def test_shared_batch_costs_and_unique_run_reservations_cannot_reset(self):
        batch = BatchQuota(max_calls=216, max_tokens=6193152)
        legacy, old_M = make_budget(self.clock, batch, run_id="legacy"), make_m_budget(self.clock, batch, run_id="M")
        finish(legacy, reserve(legacy), self.clock)
        finish(old_M, reserve(old_M), self.clock)
        history = [legacy.ledger()["entries"], old_M.ledger()["entries"]]
        budget = make_extended_budget(self.clock, batch)
        value = reserve(budget)
        with self.assertRaisesRegex(BudgetHold, "duplicate_request"):
            reserve(budget)
        with self.assertRaisesRegex(BudgetHold, "duplicate_run_budget"):
            make_extended_budget(self.clock, batch)
        budget.unknown(value["ticket"]["reservation_id"])
        self.assertEqual(batch.snapshot()["charged_or_reserved_tokens"], 24 + 4106)
        self.assertEqual(batch.snapshot()["reserved_entries"], 3)
        with self.assertRaisesRegex(BudgetHold, "batch_held"):
            reserve(make_extended_budget(self.clock, batch, run_id="cannot-reset"))
        self.assertEqual([legacy.ledger()["entries"], old_M.ledger()["entries"]], history)

    def test_worker_rejects_rehashed_profiles_limits_receipts_and_deadlines(self):
        changes = [{key: value} for key, value in (
            ("profile", "M"), ("profile", "unknown"), ("profile_receipt", None),
            ("profile_receipt", asdict(synthetic_m_receipt())),
            ("trial_call_limit", 33), ("trial_token_limit", 917505),
            ("batch_call_limit", 217), ("batch_token_limit", 6193153),
            ("run_deadline", self.clock() + 8401), ("run_deadline", self.clock() + 1800),
            ("task_deadline", self.clock() + 241), ("requested_timeout", 236))]
        changes += [{"profile_limits": {**EXTENDED_LIMITS, key: "changed"}} for key in EXTENDED_LIMITS]
        changes += [{"profile_receipt": asdict(synthetic_extended_receipt(**{key: value}))}
            for key, value in (("conditions_hash", payload_hash("wrong")),
                ("limits_hash", payload_hash("wrong")), ("source_sha", "invalid"))]
        for change in changes:
            with self.subTest(change=change):
                budget = make_extended_budget(self.clock)
                self.mutate_ticket = lambda ticket: ticket.update(copy.deepcopy(change))
                with self.assertRaises(BudgetHold):
                    self.post(budget)
                self.assertEqual(self.worker_results[-1]["kind"], "guard")
                self.assertIs(self.worker_results[-1]["budget_receipt"]["sent"], False)
                self.assert_unknown_cost(budget)
        self.opener.open.assert_not_called()

    def test_parent_rejects_rehashed_valid_source_or_origin_change_without_refund(self):
        for mutate in (lambda t: t["profile_receipt"].update(source_sha="f" * 40),
                lambda t: t.update(run_started_at=t["run_started_at"] - 1, run_deadline=t["run_deadline"] - 1)):
            with self.subTest(mutate=mutate):
                budget = make_extended_budget(self.clock)
                value = reserve(budget)
                ticket = copy.deepcopy(value["ticket"])
                mutate(ticket)
                ticket["ticket_hash"] = payload_hash({k: v for k, v in ticket.items() if k != "ticket_hash"})
                # Worker integrity is not external receipt authenticity; parent owns IPC trust.
                self.assertEqual(prepare_wire(ticket, value["payload"], self.clock)[0], 235)
                with self.assertRaisesRegex(BudgetHold, "ticket_changed"):
                    budget.dispatch_timeout(ticket, value["payload"])
                self.assert_unknown_cost(budget)

    def test_run_and_task_deadline_six_second_boundary_and_expiry(self):
        for run_boundary in (False, True):
            for remaining in (6, 5.999):
                with self.subTest(run_boundary=run_boundary, remaining=remaining):
                    clock = Clock()
                    budget = make_extended_budget(clock)
                    if run_boundary:
                        clock.advance(8400 - remaining)
                        budget.register_task("near-end", clock())
                        task = "near-end"
                    else:
                        clock.advance(240 - remaining)
                        task = "task"
                    if remaining == 6:
                        value = budget.reserve(PAYLOAD, task_id=task, attempt_id="boundary", timeout=240)
                        self.assertEqual(value["ticket"]["task_deadline"], clock() + 6)
                        self.assertEqual(prepare_wire(value["ticket"], value["payload"], clock)[0], 1)
                        clock.advance(.001)
                        with self.assertRaisesRegex(BudgetHold, "parent_deadline_or_ticket"):
                            budget.dispatch_timeout(value["ticket"], value["payload"])
                        self.assertEqual(budget.ledger()["charged_or_reserved_tokens"], 4106)
                    else:
                        with self.assertRaisesRegex(BudgetHold, "deadline_reserve"):
                            budget.reserve(PAYLOAD, task_id=task, attempt_id="boundary", timeout=240)
                        self.assertEqual(budget.ledger()["entry_count"], 0)
        budget = make_extended_budget(self.clock)
        self.clock.advance(8400)
        with self.assertRaisesRegex(BudgetHold, "invalid_deadline"):
            budget.register_task("expired", self.clock())

    def test_worker_preparation_expiry_preserves_original_run_deadline_and_cost(self):
        budget = make_extended_budget(self.clock)
        self.clock.advance(8400 - 6.2)
        budget.register_task("last", self.clock())
        self.prepare_delay = .5
        with self.assertRaises(BudgetHold):
            self.post(budget, "last")
        self.opener.open.assert_not_called()
        self.assertEqual(self.worker_results[0]["kind"], "guard")
        self.assertIs(self.worker_results[0]["budget_receipt"]["sent"], False)
        self.assert_unknown_cost(budget)

    def test_unknown_usage_transport_and_cancellation_keep_cost_and_never_retry(self):
        for mode in ("usage", "transport", "cancel"):
            with self.subTest(mode=mode):
                self.worker_body = response(usage={}) if mode == "usage" else response()
                self.open_error = OSError("synthetic transport uncertainty") if mode == "transport" else None
                self.cancel_after_open = mode == "cancel"
                budget = make_extended_budget(self.clock)
                before = len(self.ipc_inputs)
                with self.assertRaises(BudgetHold):
                    self.post(budget)
                self.assert_unknown_cost(budget)
                self.assertEqual(len(self.ipc_inputs) - before, 1)


if __name__ == "__main__":
    unittest.main()
