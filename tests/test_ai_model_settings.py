import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import app


class AiModelSettingsTests(unittest.TestCase):
    def test_google_default_is_flash_latest(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing = Path(temporary_directory) / "missing.json"
            self.assertEqual(
                app.load_token_config(missing).google_model,
                "gemini-flash-latest",
            )

    def test_update_model_preserves_credentials_and_unrelated_values(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            token_file = Path(temporary_directory) / "tokens.json"
            original = {
                "google_api_key": "test-google-secret",
                "google_model": "gemini-old",
                "openai_api_key": "test-openai-secret",
                "openai_model": "gpt-test",
                "custom_setting": {"keep": True},
            }
            token_file.write_text(json.dumps(original), encoding="utf-8")

            config = app.update_token_model(
                "google",
                "gemini-flash-latest",
                token_file,
            )

            stored = json.loads(token_file.read_text(encoding="utf-8"))
            self.assertEqual(stored["google_model"], "gemini-flash-latest")
            self.assertEqual(stored["google_api_key"], "test-google-secret")
            self.assertEqual(stored["openai_api_key"], "test-openai-secret")
            self.assertEqual(stored["custom_setting"], {"keep": True})
            self.assertEqual(config.google_model, "gemini-flash-latest")

    def test_lmstudio_default_is_local_loopback_and_model_ids_may_contain_slashes(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            token_file = Path(temporary_directory) / "tokens.json"
            token_file.write_text(json.dumps({"custom_setting": True}), encoding="utf-8")

            config = app.update_token_model(
                "lmstudio",
                "qwen/qwen3-8b-instruct",
                token_file,
            )

            stored = json.loads(token_file.read_text(encoding="utf-8"))
            self.assertEqual(config.lmstudio_base_url, "http://127.0.0.1:1234/v1")
            self.assertEqual(config.lmstudio_model, "qwen/qwen3-8b-instruct")
            self.assertEqual(stored["lmstudio_model"], "qwen/qwen3-8b-instruct")
            self.assertEqual(stored["custom_setting"], True)

    def test_lmstudio_url_only_accepts_local_loopback(self):
        self.assertEqual(
            app.lmstudio_base_url("http://127.0.0.1:4567/"),
            "http://127.0.0.1:4567/v1",
        )
        self.assertEqual(
            app.lmstudio_base_url("http://[::1]:1234/v1"),
            "http://[::1]:1234/v1",
        )
        with self.assertRaises(ValueError):
            app.lmstudio_base_url("http://192.168.1.10:1234/v1")

    def test_lmstudio_model_list_uses_local_openai_compatible_endpoint(self):
        response = mock.MagicMock()
        response.read.return_value = json.dumps({
            "data": [
                {"id": "qwen/qwen3-8b-instruct", "object": "model"},
                {"id": "", "object": "model"},
            ]
        }).encode("utf-8")
        response.__enter__.return_value = response
        config = app.TokenConfig(lmstudio_model="qwen/qwen3-8b-instruct")
        with mock.patch.object(app.urllib.request, "urlopen", return_value=response) as urlopen:
            models = app.available_ai_models("lmstudio", config)

        self.assertEqual(models[0]["id"], "qwen/qwen3-8b-instruct")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://127.0.0.1:1234/v1/models")

    def test_lmstudio_call_uses_chat_completions_structured_output(self):
        schema = {
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
            "additionalProperties": False,
        }
        response = {
            "choices": [{"message": {"content": '{"ok":true}'}}],
            "usage": {"prompt_tokens": 6, "completion_tokens": 2, "total_tokens": 8},
        }
        collected = []
        with mock.patch.object(app, "post_json", return_value=response) as post_json:
            result = app.call_ai_json(
                "lmstudio", "", "qwen/qwen3-8b-instruct", "system", "user",
                "test_schema", schema, usage_callback=collected.append,
                base_url="http://127.0.0.1:1234/v1",
            )

        self.assertEqual(result, {"ok": True})
        self.assertEqual(post_json.call_args.args[0], "http://127.0.0.1:1234/v1/chat/completions")
        payload = post_json.call_args.args[2]
        self.assertEqual(payload["response_format"]["type"], "json_schema")
        self.assertEqual(collected[-1]["total_tokens"], 8)

    def test_model_api_reads_and_updates_the_patched_tokens_json(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            token_file = Path(temporary_directory) / "tokens.json"
            token_file.write_text(
                json.dumps({
                    "google_api_key": "test-google-secret",
                    "google_model": "gemini-flash-latest",
                }),
                encoding="utf-8",
            )
            models = [{
                "id": "gemini-flash-latest",
                "label": "Gemini Flash Latest",
                "description": "test model",
            }]
            client = app.app.test_client()
            with (
                mock.patch.object(app, "TOKEN_FILE", token_file),
                mock.patch.object(app, "available_ai_models", return_value=models),
            ):
                listed = client.get("/api/ai/models?provider=google")
                self.assertEqual(listed.status_code, 200)
                payload = listed.get_json()
                self.assertEqual(payload["selected_model"], "gemini-flash-latest")
                self.assertEqual(payload["models"], models)
                self.assertNotIn("api_key", json.dumps(payload))

                updated = client.put(
                    "/api/ai/model",
                    json={"provider": "google", "model": "gemini-2.5-flash"},
                    headers={"X-Gurumoji-Request": "1"},
                )
                self.assertEqual(updated.status_code, 200)
                stored = json.loads(token_file.read_text(encoding="utf-8"))
                self.assertEqual(stored["google_model"], "gemini-2.5-flash")
                self.assertEqual(stored["google_api_key"], "test-google-secret")

    def test_page_exposes_clickable_model_picker(self):
        page = app.app.test_client().get("/").data.decode("utf-8")
        script = (Path(app.__file__).resolve().parent / "static" / "app.js").read_text(
            encoding="utf-8"
        )

        self.assertIn('data-model-provider="openai"', page)
        self.assertIn('data-model-provider="google"', page)
        self.assertIn('data-model-provider="lmstudio"', page)
        self.assertIn('value="lmstudio"', page)
        self.assertIn('id="ai-model-dialog"', page)
        self.assertIn("/api/ai/models?provider=", script)
        self.assertIn("/api/ai/model", script)
        self.assertIn("openAiModelDialog", script)


if __name__ == "__main__":
    unittest.main()
