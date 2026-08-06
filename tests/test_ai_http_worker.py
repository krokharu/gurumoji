import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class AiHttpWorkerTests(unittest.TestCase):
    def test_ai_usage_is_persisted_and_returned_with_library_item(self):
        original_database = app.DATABASE_FILE
        try:
            with tempfile.TemporaryDirectory(prefix="gurumoji-ai-usage-") as temporary:
                root = Path(temporary)
                app.DATABASE_FILE = root / "library.sqlite3"
                app.initialize_library()
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
        finally:
            app.DATABASE_FILE = original_database

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


if __name__ == "__main__":
    unittest.main()
