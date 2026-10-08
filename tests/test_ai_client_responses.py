import json
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from gurumoji.services.ai import client
from gurumoji.services.ai.request_budget import BudgetHold, payload_hash
from test_ai_request_budget import Clock, PAYLOAD, count_proof, make_budget, receipt, response

# Safe CPU boundary observations only; no request or response bodies.
CPU_ATOMIC_PROOF = []


SCHEMA = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
    "additionalProperties": False,
}
PROVIDERS = frozenset({"openai", "google", "lmstudio"})


def call(provider, response, usage=None):
    return client.call_ai_json(
        provider, "key", "model-x", "system", "user", "test_schema", SCHEMA,
        post=lambda *args, **kwargs: response,
        lmstudio_base=lambda value: "http://127.0.0.1:1234/v1",
        lmstudio_model_id=lambda value: str(value),
        lmstudio_reasoning=lambda *args: {},
        providers=PROVIDERS,
        usage_callback=usage.append if usage is not None else None,
    )


class IncompleteResponseTests(unittest.TestCase):
    def assert_error(self, provider, response, fragment):
        with self.assertRaises(RuntimeError) as raised:
            call(provider, response)
        self.assertIn(fragment, str(raised.exception))
        self.assertNotIn("有効な JSON", str(raised.exception))

    def test_openai_truncation_and_filter_are_reported(self):
        self.assert_error("openai", {
            "status": "incomplete",
            "incomplete_details": {"reason": "max_output_tokens"},
            "output": [{"content": [{"type": "output_text", "text": '{"ok": tr'}]}],
        }, "出力トークン上限")
        self.assert_error("openai", {
            "status": "incomplete", "incomplete_details": {"reason": "content_filter"},
        }, "安全フィルター")

    def test_openai_refusal_is_reported(self):
        self.assert_error("openai", {
            "status": "completed",
            "output": [{"content": [{"type": "refusal", "refusal": "I can't help with that."}]}],
        }, "回答を拒否しました: I can't help with that.")

    def test_google_truncation_block_and_prompt_block_are_reported(self):
        self.assert_error("google", {
            "candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": '{"ok"'}]}}],
        }, "出力トークン上限")
        self.assert_error("google", {
            "candidates": [{"finishReason": "SAFETY", "content": {"parts": []}}],
        }, "安全判定により応答が止められました（SAFETY）")
        self.assert_error("google", {
            "promptFeedback": {"blockReason": "PROHIBITED_CONTENT"},
        }, "入力が Google の安全判定でブロックされました")

    def test_google_missing_candidates_does_not_dump_response(self):
        with self.assertRaises(RuntimeError) as raised:
            call("google", {"candidates": [], "modelVersion": "secret-looking-detail"})
        self.assertNotIn("secret-looking-detail", str(raised.exception))

    def test_lmstudio_length_is_still_reported(self):
        self.assert_error("lmstudio", {
            "choices": [{"finish_reason": "length", "message": {"content": '{"ok"'}}],
        }, "ローカルLLM")

    def test_usage_is_recorded_even_when_reply_is_truncated(self):
        usage = []
        with self.assertRaises(RuntimeError):
            call("openai", {
                "status": "incomplete",
                "incomplete_details": {"reason": "max_output_tokens"},
                "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            }, usage)
        self.assertEqual(usage[-1]["total_tokens"], 15)

    def test_completed_replies_still_parse(self):
        self.assertEqual(call("openai", {"status": "completed", "output_text": '{"ok": true}'}), {"ok": True})
        self.assertEqual(call("google", {
            "candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": '{"ok": true}'}]}}],
        }), {"ok": True})
        self.assertEqual(call("lmstudio", {
            "choices": [{"finish_reason": "stop", "message": {"content": '{"ok": true}'}}],
        }), {"ok": True})


class PostJsonRetryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="gurumoji-ai-client-")
        self.addCleanup(temporary.cleanup)
        self.worker = Path(temporary.name) / "worker.py"
        self.worker.write_text("", encoding="utf-8")
        self.sleeps = []

    def runner(self, replies):
        calls = []

        def run(command, *, input_text, timeout, check_cancelled):
            calls.append(input_text)
            reply = replies[min(len(calls), len(replies)) - 1]
            return subprocess.CompletedProcess(command, 0, json.dumps(reply), "")

        return run, calls

    def post(self, run, check_cancelled=None):
        return client.post_json(
            "https://api.openai.com/v1/responses", {}, {"model": "m"},
            worker_file=self.worker, run_subprocess=run,
            check_cancelled=check_cancelled, retry_delays=(1.0, 2.0),
            sleep=self.sleeps.append,
        )

    def test_rate_limit_is_retried_then_succeeds(self):
        run, calls = self.runner([
            {"ok": False, "kind": "http", "status": 429},
            {"ok": False, "kind": "http", "status": 503},
            {"ok": True, "status": 200, "body": '{"done": true}'},
        ])
        self.assertEqual(self.post(run), {"done": True})
        self.assertEqual(len(calls), 3)
        self.assertAlmostEqual(sum(self.sleeps), 3.0)

    def test_retry_after_extends_the_wait_up_to_a_cap(self):
        run, _ = self.runner([
            {"ok": False, "kind": "http", "status": 429, "retry_after": 5},
            {"ok": False, "kind": "http", "status": 429, "retry_after": 9999},
            {"ok": True, "status": 200, "body": "{}"},
        ])
        self.post(run)
        self.assertAlmostEqual(sum(self.sleeps), 5.0 + client.MAX_RETRY_AFTER_SECONDS)

    def test_retries_stop_after_the_last_delay(self):
        run, calls = self.runner([{"ok": False, "kind": "http", "status": 429}])
        with self.assertRaises(RuntimeError) as raised:
            self.post(run)
        self.assertEqual(len(calls), 3)
        self.assertIn("HTTP 429", str(raised.exception))
        self.assertIn("上限", str(raised.exception))

    def test_client_errors_are_not_retried(self):
        run, calls = self.runner([{"ok": False, "kind": "http", "status": 401}])
        with self.assertRaises(RuntimeError) as raised:
            self.post(run)
        self.assertEqual(len(calls), 1)
        self.assertIn("APIキー", str(raised.exception))
        self.assertEqual(self.sleeps, [])

    def test_network_errors_are_not_retried(self):
        run, calls = self.runner([{"ok": False, "kind": "network"}])
        with self.assertRaises(RuntimeError):
            self.post(run)
        self.assertEqual(len(calls), 1)

    def test_cancellation_interrupts_the_retry_wait(self):
        run, calls = self.runner([{"ok": False, "kind": "http", "status": 503}])
        checks = []

        def cancel():
            checks.append(1)
            if len(checks) > 2:
                raise InterruptedError("cancelled")

        with self.assertRaises(InterruptedError):
            self.post(run, check_cancelled=cancel)
        self.assertEqual(len(calls), 1)
        self.assertLess(sum(self.sleeps), 1.0)


class WorkerRetryAfterTests(unittest.TestCase):
    def test_worker_relays_only_a_numeric_retry_after(self):
        import runpy
        import urllib.error
        from email.message import Message
        from unittest.mock import patch

        worker = runpy.run_path(str(Path(client.__file__).parents[2] / "ai_http_worker.py"))
        emitted = []
        for header, expected in (("7", 7), ("Wed, 21 Oct 2026 07:28:00 GMT", None), ("²", None)):
            headers = Message()
            headers["Retry-After"] = header
            error = urllib.error.HTTPError("https://api.openai.com/v1/responses", 429, "x", headers, None)
            request = {"url": "https://api.openai.com/v1/responses", "headers": {}, "payload": {}}
            opener = unittest.mock.Mock()
            opener.open.side_effect = error
            main = worker["main"]
            with patch.dict(main.__globals__, {
                "read_request": lambda: request,
                "emit": emitted.append,
            }), patch("urllib.request.build_opener", return_value=opener):
                main()
            self.assertEqual(emitted[-1]["status"], 429)
            self.assertEqual(emitted[-1].get("retry_after"), expected)
            self.assertNotIn("body", emitted[-1])


class BudgetedPostTests(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.budget = make_budget(self.clock)
        self.calls = []
        self.worker = Path(client.__file__).parents[2] / "ai_http_worker.py"

    def post(self, runner, **changes):
        values = dict(worker_file=self.worker, run_subprocess=runner,
            request_budget=self.budget, task_id="task", attempt_id="attempt", retry_delays=(0, 0))
        values.update(changes)
        return client.post_json("http://127.0.0.1:23456/v1/chat/completions", {}, PAYLOAD, **values)

    def runner(self, reply=None, *, fault=None, mutate=None):
        def run(command, *, input_text, timeout, check_cancelled):
            request = json.loads(input_text)
            self.calls.append(request)
            self.assertNotIn("request_budget", request["payload"])
            self.assertEqual(request["payload"]["max_tokens"], 4096)
            self.assertLessEqual(timeout, 240)
            if fault is not None: raise fault
            value = {"ok": True, "status": 200, "body": json.dumps(response() if reply is None else reply),
                "budget_receipt": receipt(request["request_budget"], self.clock)}
            if mutate: mutate(value)
            return subprocess.CompletedProcess(command, 0, json.dumps(value), "")
        return run

    def test_success_keeps_normal_response_shape_and_exposes_ledger_separately(self):
        self.assertEqual(self.post(self.runner()), response())
        self.assertEqual(self.budget.ledger()["actual_wire_calls"], 1)
        self.assertNotIn("budget_receipt", response())

    def test_retryable_http_errors_are_reserved_once_then_hold_with_no_hidden_retries(self):
        for status in (400, 429, 500, 503):
            with self.subTest(status=status):
                self.budget = make_budget(self.clock); self.calls = []
                def mutation(value): value.update(ok=False, kind="http", status=status, body="must-not-echo-secret")
                with self.assertRaises(BudgetHold) as raised: self.post(self.runner(mutate=mutation))
                self.assertEqual(len(self.calls), 1)
                self.assertNotIn("must-not-echo-secret", str(raised.exception))
                ledger = self.budget.ledger()
                self.assertEqual(ledger["entries"][0]["http_status"], status)
                self.assertEqual(ledger["charged_or_reserved_tokens"], 4106)
                self.assertIsNone(ledger["entries"][0]["usage"])

    def test_ipc_timeout_crash_invalid_json_and_missing_receipt_hold_reservation(self):
        failures = [self.runner(fault=subprocess.TimeoutExpired("secret-command", 1, output="secret-output")),
            self.runner(fault=RuntimeError("secret-worker-exception"))]
        failures += [lambda *a, **k: subprocess.CompletedProcess([], 1, "secret-stdout", "secret-stderr"),
            lambda *a, **k: subprocess.CompletedProcess([], 0, "secret-not-json", ""),
            lambda *a, **k: subprocess.CompletedProcess([], 0, '{"ok":true,"body":"{}"}', "")]
        for runner in failures:
            with self.subTest(runner=runner):
                self.budget = make_budget(self.clock)
                with self.assertRaises(BudgetHold) as raised: self.post(runner)
                self.assertNotIn("secret", str(raised.exception))
                self.assertNotIn("secret", json.dumps(self.budget.ledger()))
                self.assertEqual(self.budget.ledger()["entry_count"], 1)
                self.assertEqual(self.budget.ledger()["reserved_unknown_calls"], 1)
                self.assertIsNone(self.budget.ledger()["actual_wire_calls"])
                self.assertEqual(self.budget.ledger()["observed_wire_calls"], 0)
                self.assertEqual(self.budget.ledger()["charged_or_reserved_tokens"], 4106)
                with self.assertRaisesRegex(BudgetHold, "batch_held"):
                    self.post(lambda *a, **k: self.fail("post after unknown"), attempt_id="next")

    def test_nonjson_truncation_and_usage_missing_are_not_normalized_to_zero(self):
        mutations = [lambda v: v.update(body="secret-not-json"),
            lambda v: v.update(body=json.dumps(response(usage={}))),
            lambda v: v.update(body=json.dumps(response(choices=[{"finish_reason": "length"}])))]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self.budget = make_budget(self.clock); self.calls = []
                with self.assertRaises(BudgetHold): self.post(self.runner(mutate=mutation))
                self.assertEqual(len(self.calls), 1)
                self.assertEqual(self.budget.ledger()["actual_wire_calls"], 1)
                self.assertEqual(self.budget.ledger()["charged_or_reserved_tokens"], 4106)

    def test_parent_counter_delay_and_remaining_5_999_prevent_subprocess_start(self):
        self.budget = make_budget(self.clock, run_started_at=self.clock() - 234.001)
        with self.assertRaisesRegex(BudgetHold, "deadline_reserve"):
            self.post(lambda *a, **k: self.fail("no child when <6 seconds remain"))
        self.assertEqual(self.budget.ledger()["entry_count"], 0)

    def test_local_only_and_output_cap_hash_are_enforced_before_any_http(self):
        with self.assertRaisesRegex(BudgetHold, "local_endpoint_required"):
            client.post_json("https://api.openai.com/v1/responses", {}, PAYLOAD,
                worker_file=self.worker, run_subprocess=lambda *a, **k: self.fail("no cloud"),
                request_budget=self.budget, task_id="task", attempt_id="attempt")
        self.assertEqual(self.budget.ledger()["entry_count"], 0)
        self.post(self.runner())
        sent = self.calls[0]
        self.assertEqual(payload_hash(sent["payload"]), sent["request_budget"]["payload_hash"])

    def test_receipt_budget_tampering_is_unknown_and_no_retry(self):
        def mutation(value): value["budget_receipt"]["ticket_hash"] = payload_hash("changed")
        with self.assertRaisesRegex(BudgetHold, "receipt_mismatch"): self.post(self.runner(mutate=mutation))
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.budget.ledger()["reserved_unknown_calls"], 1)

    def test_cancellation_before_reservation_does_not_create_an_unknown_send(self):
        for error in (InterruptedError("synthetic-private-cancellation"), BudgetHold("deadline_reserve")):
            with self.subTest(error=type(error).__name__):
                def cancel(): raise error
                before = self.budget.ledger()
                with self.assertRaises(type(error)) as raised:
                    self.post(lambda *a, **k: self.fail("no child before reservation"), check_cancelled=cancel)
                self.assertIs(raised.exception, error)
                self.assertEqual(self.budget.ledger(), before)

    def test_external_budget_hold_after_reservation_holds_full_unknown_without_retry(self):
        error = BudgetHold("deadline_reserve")
        with self.assertRaises(BudgetHold) as raised:
            self.post(self.runner(fault=error))
        self.assertIs(raised.exception, error)
        ledger = self.budget.ledger()
        self.assertEqual(ledger["entries"][0]["state"], "unknown")
        self.assertEqual(ledger["entries"][0]["stop_reason"], "deadline_reserve")
        self.assertEqual(ledger["batch"]["hold_reason"], "deadline_reserve")
        self.assertEqual(ledger["charged_or_reserved_tokens"], 4106)
        self.assertIsNone(ledger["actual_wire_calls"])
        with self.assertRaisesRegex(BudgetHold, "batch_held"):
            self.post(lambda *a, **k: self.fail("no child after unknown"), attempt_id="next")
        self.assertEqual(len(self.calls), 1)

    def test_parent_dispatch_deadline_preserves_its_already_unknown_reason(self):
        clock = self.clock
        class DelayedWorker:
            def is_file(self):
                clock.advance(235)
                return True
        with self.assertRaisesRegex(BudgetHold, "parent_deadline_or_ticket"):
            self.post(lambda *a, **k: self.fail("no late child"), worker_file=DelayedWorker())
        ledger = self.budget.ledger()
        self.assertEqual(ledger["entries"][0]["stop_reason"], "parent_deadline_or_ticket")
        self.assertEqual(ledger["batch"]["hold_reason"], "parent_deadline_or_ticket")
        self.assertEqual(ledger["entries"][0]["state"], "unknown")
        self.assertEqual(ledger["charged_or_reserved_tokens"], 4106)
        self.assertIsNone(ledger["entries"][0]["receipt"])

    def test_finish_usage_hold_preserves_received_metadata_and_reason(self):
        with self.assertRaisesRegex(BudgetHold, "usage_unknown"):
            self.post(self.runner(reply=response(usage={})))
        ledger = self.budget.ledger()
        entry = ledger["entries"][0]
        self.assertEqual((entry["state"], entry["stop_reason"], entry["http_status"]), ("unknown", "usage_unknown", 200))
        self.assertEqual(entry["receipt"]["sent"], True)
        self.assertEqual(ledger["actual_wire_calls"], 1)
        self.assertEqual(ledger["batch"]["hold_reason"], "usage_unknown")
        self.assertEqual(ledger["charged_or_reserved_tokens"], 4106)

    def test_later_exception_does_not_replace_already_unknown_receipt_or_reason(self):
        for error in (BudgetHold("deadline_reserve"), InterruptedError("synthetic-private-cancellation")):
            with self.subTest(error=type(error).__name__):
                self.budget = make_budget(self.clock)
                snapshot = []
                def run(command, *, input_text, **kwargs):
                    ticket = json.loads(input_text)["request_budget"]
                    try:
                        self.budget.finish(ticket, receipt(ticket, self.clock), response(usage={}),
                            transport_ok=True, http_status=200)
                    except BudgetHold:
                        snapshot.append(self.budget.ledger())
                    raise error
                with self.assertRaises(BudgetHold) as raised:
                    self.post(run)
                self.assertEqual(raised.exception.reason, error.reason if isinstance(error, BudgetHold) else "transport_unknown")
                self.assertNotIn("synthetic-private", str(raised.exception))
                self.assertEqual(self.budget.ledger(), snapshot[0])

    def test_later_exception_preserves_known_zero_and_known_usage_without_second_refund(self):
        for input_tokens, output_tokens in ((0, 0), (10, 2)):
            for error in (BudgetHold("deadline_reserve"), InterruptedError("synthetic-private-cancellation")):
                with self.subTest(input_tokens=input_tokens, error=type(error).__name__):
                    self.budget = make_budget(self.clock, token_counter=lambda p: count_proof(p, input_tokens=input_tokens))
                    snapshot = []
                    def run(command, *, input_text, **kwargs):
                        ticket = json.loads(input_text)["request_budget"]
                        usage = {"prompt_tokens": input_tokens, "completion_tokens": output_tokens,
                            "total_tokens": input_tokens + output_tokens}
                        self.budget.finish(ticket, receipt(ticket, self.clock), response(usage=usage),
                            transport_ok=True, http_status=200)
                        snapshot.append(self.budget.ledger())
                        raise error
                    with self.assertRaises(BudgetHold) as raised:
                        self.post(run)
                    self.assertEqual(raised.exception.reason, error.reason if isinstance(error, BudgetHold) else "transport_unknown")
                    self.assertEqual(self.budget.ledger(), snapshot[0])
                    self.assertEqual(snapshot[0]["charged_or_reserved_tokens"], input_tokens + output_tokens)
                    self.assertEqual(snapshot[0]["entries"][0]["state"], "known")

    def check_finish_at_cancellation_boundary(self, label, input_tokens, output_tokens, unknown=False):
        for error in (BudgetHold("deadline_reserve"), InterruptedError("synthetic-private-cancellation")):
            with self.subTest(label=label, error=type(error).__name__):
                self.budget = make_budget(self.clock, token_counter=lambda p: count_proof(p, input_tokens=input_tokens))
                reached, finished = threading.Event(), threading.Event()
                tickets, snapshots, failures, calls = [], [], [], []
                creator_thread = threading.get_ident()
                # On the old client this gate is after its stale ledger check;
                # on the fixed client it is before the atomic operation's lock.
                operation_name = "unknown_if_reserved" if hasattr(self.budget, "unknown_if_reserved") else "unknown"
                operation = getattr(self.budget, operation_name)
                def finish_in_thread():
                    try:
                        if not reached.wait(2): raise AssertionError("cancellation boundary not reached")
                        usage = {} if unknown else {"prompt_tokens": input_tokens,
                            "completion_tokens": output_tokens, "total_tokens": input_tokens + output_tokens}
                        try:
                            self.budget.finish(tickets[0], receipt(tickets[0], self.clock), response(usage=usage),
                                transport_ok=True, http_status=200)
                        except BudgetHold as exc:
                            if not unknown or exc.reason != "usage_unknown": raise
                        snapshots.append(self.budget.ledger())
                    except BaseException as exc:
                        failures.append(exc)
                    finally:
                        finished.set()
                def gated_operation(*args, **kwargs):
                    if threading.get_ident() != creator_thread:
                        return operation(*args, **kwargs)
                    reached.set()
                    self.assertTrue(finished.wait(2))
                    self.assertEqual(failures, [])
                    return operation(*args, **kwargs)
                def runner(command, *, input_text, **kwargs):
                    calls.append(1)
                    tickets.append(json.loads(input_text)["request_budget"])
                    raise error
                thread = threading.Thread(target=finish_in_thread)
                thread.start()
                try:
                    with patch.object(self.budget, operation_name, side_effect=gated_operation):
                        with self.assertRaises(BudgetHold) as raised:
                            self.post(runner)
                    self.assertEqual(raised.exception.reason, error.reason if isinstance(error, BudgetHold) else "transport_unknown")
                    if isinstance(error, BudgetHold): self.assertIs(raised.exception, error)
                    actual, expected = self.budget.ledger(), snapshots[0]
                    CPU_ATOMIC_PROOF.append({"case": label, "exception": type(error).__name__,
                        "expected_snapshot_hash": payload_hash(expected), "actual_snapshot_hash": payload_hash(actual),
                        "snapshot_preserved": actual == expected, "state": actual["entries"][0]["state"],
                        "charged_tokens": actual["charged_or_reserved_tokens"], "usage": actual["entries"][0]["usage"],
                        "expected_hold_reason": expected["batch"]["hold_reason"], "actual_hold_reason": actual["batch"]["hold_reason"],
                        "expected_stop_reason": expected["entries"][0]["stop_reason"], "actual_stop_reason": actual["entries"][0]["stop_reason"],
                        "same_reservation": actual["entries"][0]["ticket"]["reservation_id"] == tickets[0]["reservation_id"],
                        "mock_ipc_calls": len(calls), "actual_child_calls": 0, "actual_http_calls": 0,
                        "real_model_calls": 0, "finish_used_production_validators": True})
                    self.assertEqual(actual, expected)
                finally:
                    reached.set()
                    thread.join(2)
                    self.assertFalse(thread.is_alive())

    def test_concurrent_known_zero_finish_before_catch_transition_is_exact_noop(self):
        self.check_finish_at_cancellation_boundary("concurrent_known_zero", 0, 0)

    def test_concurrent_known_usage_finish_before_catch_transition_is_exact_noop(self):
        self.check_finish_at_cancellation_boundary("concurrent_known_usage", 10, 2)

    def test_concurrent_unknown_finish_before_catch_transition_keeps_receipt_and_reason(self):
        self.check_finish_at_cancellation_boundary("concurrent_unknown", 0, 0, unknown=True)


if __name__ == "__main__":
    unittest.main()
