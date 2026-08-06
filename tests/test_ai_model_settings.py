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
        self.assertIn('id="ai-model-dialog"', page)
        self.assertIn("/api/ai/models?provider=", script)
        self.assertIn("/api/ai/model", script)
        self.assertIn("openAiModelDialog", script)


if __name__ == "__main__":
    unittest.main()
