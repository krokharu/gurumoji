import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from gurumoji.services.ai import client


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


if __name__ == "__main__":
    unittest.main()
