import json
import copy
import http.server
import subprocess
import sys
import tempfile
import time
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import app
from support import use_temporary_library
from gurumoji.services.ai import client
from gurumoji.services.ai.request_budget import BudgetHold, payload_hash
from gurumoji.services.subprocesses import run_cancellable_subprocess
from test_ai_request_budget import PAYLOAD, count_proof, make_budget, response

# Safe metadata only, consumed by the CPU proof collector; no bodies/headers.
CPU_TRANSPORT_PROOF = []


class AiHttpWorkerTests(unittest.TestCase):
    def test_ai_usage_is_persisted_and_returned_with_library_item(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-ai-usage-") as temporary:
            root = Path(temporary)
            use_temporary_library(self, root)
            row = app.upsert_library_item(
                item_id="ai-usage-item",
                source_name="sample.wav",
                output_dir=root / "output",
                media_path=None,
                language="ja",
                segments=[],
                speaker_names={},
                outline=None,
                emotion_analysis=None,
                files=[],
                write_srt=False,
                write_json=True,
                ai_usage={
                    "provider": "google", "model": "gemini-test", "request_count": 3,
                    "input_tokens": 300, "output_tokens": 60, "total_tokens": 360,
                    "cached_tokens": 20, "reasoning_tokens": 12, "reported": True,
                },
            )
            usage = app.library_public(row)["ai_usage"]
            self.assertEqual(usage["provider"], "google")
            self.assertEqual(usage["request_count"], 3)
            self.assertEqual(usage["total_tokens"], 360)

    def test_openai_and_gemini_token_usage_is_normalized(self):
        schema = {
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
            "additionalProperties": False,
        }
        collected = []
        openai_response = {
            "output_text": '{"ok": true}',
            "usage": {
                "input_tokens": 120,
                "output_tokens": 30,
                "total_tokens": 150,
                "input_tokens_details": {"cached_tokens": 20},
                "output_tokens_details": {"reasoning_tokens": 8},
            },
        }
        with patch.object(app, "post_json", return_value=openai_response):
            result = app.call_ai_json(
                "openai", "secret", "gpt-test", "system", "user",
                "test_schema", schema, usage_callback=collected.append,
            )
        self.assertEqual(result, {"ok": True})
        self.assertEqual(collected[-1]["input_tokens"], 120)
        self.assertEqual(collected[-1]["output_tokens"], 30)
        self.assertEqual(collected[-1]["total_tokens"], 150)
        self.assertEqual(collected[-1]["cached_tokens"], 20)
        self.assertEqual(collected[-1]["reasoning_tokens"], 8)

        gemini_response = {
            "candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}],
            "usageMetadata": {
                "promptTokenCount": 200,
                "candidatesTokenCount": 40,
                "totalTokenCount": 252,
                "cachedContentTokenCount": 10,
                "thoughtsTokenCount": 12,
            },
        }
        with patch.object(app, "post_json", return_value=gemini_response):
            result = app.call_ai_json(
                "google", "secret", "gemini-test", "system", "user",
                "test_schema", schema, usage_callback=collected.append,
            )
        self.assertEqual(result, {"ok": True})
        self.assertEqual(collected[-1]["provider"], "google")
        self.assertEqual(collected[-1]["input_tokens"], 200)
        self.assertEqual(collected[-1]["output_tokens"], 40)
        self.assertEqual(collected[-1]["total_tokens"], 252)
        self.assertEqual(collected[-1]["reasoning_tokens"], 12)

    def test_parent_passes_api_secret_only_through_stdin(self):
        secret = "sentinel-api-secret"
        worker_reply = json.dumps({
            "ok": True,
            "status": 200,
            "body": json.dumps({"result": "ok"}),
        })
        completed = subprocess.CompletedProcess(["worker"], 0, worker_reply, "")
        with patch.object(app, "run_cancellable_subprocess", return_value=completed) as run:
            result = app.post_json(
                "https://api.openai.com/v1/responses",
                {"Authorization": f"Bearer {secret}", "Content-Type": "application/json"},
                {"model": "test"},
                check_cancelled=lambda: None,
            )

        self.assertEqual(result, {"result": "ok"})
        command = run.call_args.args[0]
        kwargs = run.call_args.kwargs
        self.assertNotIn(secret, " ".join(command))
        self.assertNotIn(secret, json.dumps(kwargs.get("env") or {}))
        self.assertIn(secret, kwargs["input_text"])
        self.assertIsNotNone(kwargs["check_cancelled"])

    def test_worker_rejects_unapproved_hosts_without_echoing_secret(self):
        secret = "never-echo-this-secret"
        request_data = json.dumps({
            "url": "https://example.com/collect",
            "headers": {"Authorization": secret},
            "payload": {"secret": secret},
            "timeout": 2,
        })
        completed = subprocess.run(
            [sys.executable, "-I", str(Path(app.__file__).with_name("ai_http_worker.py"))],
            input=request_data,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
            check=False,
        )
        self.assertEqual(completed.returncode, 0)
        self.assertFalse(json.loads(completed.stdout)["ok"])
        self.assertNotIn(secret, completed.stdout)
        self.assertNotIn(secret, completed.stderr)

    def test_worker_allows_only_loopback_for_lmstudio_requests(self):
        worker_path = Path(app.__file__).with_name("ai_http_worker.py")
        probe = (
            "import runpy,sys; worker=runpy.run_path(sys.argv[1]); "
            "print(worker['validate_url']('http://127.0.0.1:1234/v1/chat/completions')); "
            "\ntry: worker['validate_url']('http://192.168.1.10:1234/v1/chat/completions') "
            "\nexcept ValueError: print('rejected')"
        )
        completed = subprocess.run(
            [sys.executable, "-I", "-c", probe, str(worker_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("http://127.0.0.1:1234/v1/chat/completions", completed.stdout)
        self.assertIn("rejected", completed.stdout)

    def test_worker_allows_typesafe_system_one_endpoint(self):
        worker_path = Path(app.__file__).with_name("ai_http_worker.py")
        probe = (
            "import runpy,sys; worker=runpy.run_path(sys.argv[1]); "
            "print(worker['validate_url']('https://api.typesafe.ai/v1/systemone'))"
        )
        completed = subprocess.run(
            [sys.executable, "-I", "-c", probe, str(worker_path)],
            capture_output=True, text=True, encoding="utf-8", timeout=5, check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn("https://api.typesafe.ai/v1/systemone", completed.stdout)

    def test_worker_uses_utf8_stdio_in_isolated_real_process(self):
        worker_path = Path(app.__file__).with_name("ai_http_worker.py")
        probe = (
            "import runpy,sys; "
            "worker=runpy.run_path(sys.argv[1]); "
            "worker['emit']({'text':'日本語😀','stdin_encoding':sys.stdin.encoding,"
            "'stdout_encoding':sys.stdout.encoding})"
        )
        completed = subprocess.run(
            [sys.executable, "-I", "-c", probe, str(worker_path)],
            capture_output=True,
            timeout=5,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, completed.stderr.decode("utf-8", "replace"))
        payload = json.loads(completed.stdout.decode("utf-8"))
        self.assertEqual(payload["text"], "日本語😀")
        self.assertEqual(payload["stdin_encoding"].replace("-", "").lower(), "utf8")
        self.assertEqual(payload["stdout_encoding"].replace("-", "").lower(), "utf8")

    def test_cancellable_subprocess_with_stdin_stops_promptly(self):
        checks = 0

        def cancel() -> None:
            nonlocal checks
            checks += 1
            if checks >= 3:
                raise InterruptedError("cancelled")

        started = time.monotonic()
        with self.assertRaises(InterruptedError):
            app.run_cancellable_subprocess(
                [
                    sys.executable,
                    "-c",
                    "import sys,time; sys.stdin.read(); time.sleep(30)",
                ],
                input_text="private-input",
                timeout=35,
                check_cancelled=cancel,
            )
        self.assertLess(time.monotonic() - started, 3.0)


class BudgetedRealWorkerTests(unittest.TestCase):
    def setUp(self):
        class SyntheticHandler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                self.server.received_hashes.append(payload_hash(payload))
                mode = self.server.mode
                if mode == "wait_for_cancel":
                    self.server.post_observed.set()
                    self.server.release_response.wait(5)
                if mode == "http_error":
                    status, body = 429, b"synthetic-secret-must-not-echo"
                elif mode == "nonjson":
                    status, body = 200, b"synthetic-nonjson-private-detail"
                else:
                    status = 200
                    value = response()
                    value["usage"]["prompt_tokens"] = self.server.input_tokens
                    value["usage"]["total_tokens"] = self.server.input_tokens + 2
                    if mode == "usage_missing": value.pop("usage")
                    if mode == "truncated": value["choices"][0]["finish_reason"] = "length"
                    body = json.dumps(value).encode("utf-8")
                try:
                    self.send_response(status)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                    if mode != "wait_for_cancel": raise
                finally:
                    if mode == "wait_for_cancel": self.server.handler_finished.set()
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), SyntheticHandler)
        self.server.mode, self.server.received_hashes = "success", []
        self.server.input_tokens = 10
        self.server.post_observed = threading.Event()
        self.server.release_response = threading.Event()
        self.server.handler_finished = threading.Event()
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)
        self.worker = Path(client.__file__).parents[2] / "ai_http_worker.py"
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/v1/chat/completions"
        self.assertNotEqual(self.server.server_address[1], 1234)
        self.children, self.child_outputs = [], []
        self.recorded_posts, self.recorded_children = 0, 0

    def close_server(self):
        self.server.release_response.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        self.assertFalse(self.thread.is_alive())

    def runner(self, prepare_delay=0):
        def run(command, *, input_text, timeout, check_cancelled):
            if check_cancelled: check_cancelled()
            if prepare_delay:
                # Exercise the real worker with delayed child opener setup;
                # the production deadline validator is never patched.
                probe = ("import runpy,sys,time,urllib.request\n"
                    "original=urllib.request.build_opener\n"
                    f"def delayed(*a,**k): time.sleep({prepare_delay!r}); return original(*a,**k)\n"
                    "urllib.request.build_opener=delayed\n"
                    "runpy.run_path(sys.argv[1],run_name='__main__')")
                command = [sys.executable, "-I", "-c", probe, str(self.worker)]
            completed = subprocess.run(command, input=input_text, capture_output=True,
                text=True, encoding="utf-8", timeout=timeout, check=False)
            self.children.append(completed.returncode)
            self.assertNotIn("synthetic-secret-must-not-echo", completed.stdout + completed.stderr)
            self.assertNotIn("synthetic-header-secret", completed.stdout + completed.stderr)
            # Successful protocol bodies are parsed only in memory; do not
            # persist them in the proof. Receipt fields are safe metadata.
            protocol = json.loads(completed.stdout)
            self.child_outputs.append({"ok": protocol.get("ok"), "kind": protocol.get("kind"),
                "receipt": protocol.get("budget_receipt")})
            return completed
        return run

    def post(self, budget, runner=None, attempt="attempt", check_cancelled=None):
        return client.post_json(self.url, {"Authorization": "synthetic-header-secret"},
            copy.deepcopy(PAYLOAD), worker_file=self.worker, run_subprocess=runner or self.runner(),
            request_budget=budget, task_id="task", attempt_id=attempt,
            retry_delays=(0, 0), timeout=240, check_cancelled=check_cancelled)

    def keep_proof(self, label, budget):
        ledger = budget.ledger()
        self.assertNotIn("synthetic-header-secret", json.dumps(ledger))
        CPU_TRANSPORT_PROOF.append({"case": label, "server_post_count": len(self.server.received_hashes) - self.recorded_posts,
            "server_payload_hashes": self.server.received_hashes[self.recorded_posts:], "worker_exit_codes": self.children[self.recorded_children:],
            "ledger": ledger, "real_model_calls": 0, "external_http_calls": 0,
            "sdk_load_gpu_calls": 0, "synthetic_counter_only": True})
        self.recorded_posts, self.recorded_children = len(self.server.received_hashes), len(self.children)

    def test_real_worker_known_usage_and_same_absolute_parent_child_clock(self):
        budget = make_budget(time.monotonic, run_started_at=time.monotonic())
        result = self.post(budget)
        self.assertEqual(result, response())
        self.assertEqual(self.children, [0])
        self.assertEqual(len(self.server.received_hashes), 1)
        ledger = budget.ledger(); entry = ledger["entries"][0]
        self.assertEqual(entry["ticket"]["payload_hash"], self.server.received_hashes[0])
        self.assertLessEqual(entry["receipt"]["wire_timeout"], 235)
        self.assertEqual(entry["usage"]["total_tokens"], 12)
        self.assertEqual(ledger["charged_or_reserved_tokens"], 12)
        self.keep_proof("localhost_real_worker_known", budget)

    def test_production_subprocess_budget_hold_after_post_holds_unknown_and_blocks_next_child(self):
        self.server.mode, self.server.input_tokens = "wait_for_cancel", 7
        budget = make_budget(time.monotonic, run_started_at=time.monotonic(),
            token_counter=lambda p: count_proof(p, input_tokens=7))
        error = BudgetHold("deadline_reserve")
        processes = []
        original_popen = subprocess.Popen
        def observed_popen(*args, **kwargs):
            process = original_popen(*args, **kwargs)
            processes.append(process)
            return process
        def cancel_after_post():
            if self.server.post_observed.is_set(): raise error
        second_error = None
        try:
            # Observe actual children without replacing the production runner,
            # worker, deadlines, receipts or validators.
            with patch("gurumoji.services.subprocesses.subprocess.Popen", side_effect=observed_popen):
                with self.assertRaises(BudgetHold) as raised:
                    self.post(budget, run_cancellable_subprocess, check_cancelled=cancel_after_post)
                self.assertIs(raised.exception, error)
                first_ledger = budget.ledger()
                first_posts, first_children = len(self.server.received_hashes), len(processes)
                self.server.release_response.set()
                self.assertTrue(self.server.handler_finished.wait(2))
                self.server.mode = "success"
                try:
                    self.post(budget, run_cancellable_subprocess, attempt="next")
                except BudgetHold as exc:
                    second_error = exc
            self.assertEqual((first_posts, first_children), (1, 1))
            self.assertEqual(len(self.server.received_hashes) - first_posts, 0)
            self.assertEqual(len(processes) - first_children, 0)
            self.assertIsNotNone(second_error)
            self.assertEqual(second_error.reason, "batch_held")
            self.assertTrue(all(p.poll() is not None for p in processes))
            self.assertTrue(all(p.stdin.closed and p.stdout.closed and p.stderr.closed for p in processes))
            entry = first_ledger["entries"][0]
            self.assertEqual((entry["state"], entry["sent"], entry["stop_reason"]), ("unknown", "unknown", "deadline_reserve"))
            self.assertIsNone(entry["receipt"])
            self.assertIsNone(entry["usage"])
            self.assertIsNone(first_ledger["actual_wire_calls"])
            self.assertEqual(first_ledger["batch"]["hold_reason"], "deadline_reserve")
            self.assertEqual(first_ledger["charged_or_reserved_tokens"], 4103)
            self.assertEqual(budget.ledger(), first_ledger)
            self.children.extend(p.returncode for p in processes)
            self.keep_proof("localhost_production_cancel_after_post_unknown_hold_next_post0", budget)
            CPU_TRANSPORT_PROOF[-1].update(first_observed_posts=first_posts,
                next_observed_posts=len(self.server.received_hashes) - first_posts,
                next_child_count=len(processes) - first_children, original_cancel_reason=error.reason,
                production_cancellable_subprocess=True, children_stopped=True, streams_closed=True,
                handler_finished=True)
        finally:
            self.server.release_response.set()
            for process in processes:
                if process.poll() is None:
                    process.kill()
                    process.communicate()

    def test_real_child_preparation_delay_rechecks_deadline_and_sends_nothing(self):
        origin = time.monotonic() - 233.8  # 6.2 seconds left at parent setup.
        budget = make_budget(time.monotonic, run_started_at=origin)
        with self.assertRaises(BudgetHold): self.post(budget, self.runner(prepare_delay=.5))
        ledger = budget.ledger()
        self.assertEqual(len(self.server.received_hashes), 0)
        self.assertEqual(self.children, [0])
        self.assertEqual((ledger["entry_count"], ledger["actual_wire_calls"], ledger["not_sent_calls"]), (1, 0, 1))
        self.assertIsNone(ledger["entries"][0]["receipt"]["send_started_at"])
        self.assertEqual(ledger["charged_or_reserved_tokens"], 4106)
        with self.assertRaises(BudgetHold):
            self.post(budget, lambda *a, **k: self.fail("no later worker"), "next")
        self.keep_proof("localhost_real_child_delay_no_post", budget)

    def test_real_http_error_body_is_suppressed_and_usage_unknown_holds_no_retry(self):
        self.server.mode = "http_error"
        budget = make_budget(time.monotonic, run_started_at=time.monotonic())
        with self.assertRaises(BudgetHold) as raised: self.post(budget)
        self.assertNotIn("synthetic-secret-must-not-echo", str(raised.exception))
        self.assertEqual(len(self.server.received_hashes), 1)
        self.assertEqual(budget.ledger()["entries"][0]["http_status"], 429)
        with self.assertRaises(BudgetHold): self.post(budget, attempt="next")
        self.assertEqual(len(self.server.received_hashes), 1)
        self.keep_proof("localhost_real_http429_hold", budget)

    def test_real_usage_missing_holds_full_reservation(self):
        self.server.mode = "usage_missing"
        budget = make_budget(time.monotonic, run_started_at=time.monotonic())
        with self.assertRaisesRegex(BudgetHold, "usage_unknown"): self.post(budget)
        self.assertEqual(budget.ledger()["charged_or_reserved_tokens"], 4106)
        self.assertIsNone(budget.ledger()["entries"][0]["usage"])
        self.keep_proof("localhost_real_missing_usage_hold", budget)

    def test_real_nonjson_and_truncated_responses_never_become_success(self):
        for mode in ("nonjson", "truncated"):
            with self.subTest(mode=mode):
                self.server.mode = mode
                budget = make_budget(time.monotonic, run_started_at=time.monotonic())
                with self.assertRaises(BudgetHold): self.post(budget)
                self.assertEqual(budget.ledger()["charged_or_reserved_tokens"], 4106)
                self.assertEqual(budget.ledger()["actual_wire_calls"], 1)
                self.keep_proof("localhost_real_" + mode + "_hold", budget)


if __name__ == "__main__":
    unittest.main()
