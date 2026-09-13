import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class ColabRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def test_detects_colab_and_disables_native_dialog(self):
        with patch.dict(os.environ, {"MOJIOKOSI_RUNTIME": "colab"}, clear=False):
            runtime = app.runtime_info()

        self.assertEqual(runtime["kind"], "colab")
        self.assertTrue(runtime["browser_upload"])
        self.assertFalse(runtime["native_file_dialog"])

    def test_colab_page_uses_browser_file_picker(self):
        with patch.dict(os.environ, {"MOJIOKOSI_RUNTIME": "colab"}, clear=False):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'data-picker-mode="browser"', response.data)
        self.assertIn("端末からアップロード".encode(), response.data)
        self.assertIn("Ollama（ColabローカルLLM）".encode(), response.data)

    def test_colab_config_identifies_ollama_local_provider(self):
        with (
            patch.dict(os.environ, {"MOJIOKOSI_RUNTIME": "colab"}, clear=False),
            patch.object(app, "lmstudio_connection_status", return_value={
                "reachable": True,
                "model_count": 1,
                "message": "接続済み",
            }),
        ):
            response = self.client.get("/api/config")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["local_llm_short_label"], "Ollama")
        self.assertEqual(payload["local_llm_label"], "Ollama（ColabローカルLLM）")

    def test_notebook_can_select_and_start_a_colab_local_llm(self):
        notebook_path = Path(app.PROJECT_DIRECTORY) / "notebooks" / "Gurumoji_Colab.ipynb"
        notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
        source = "\n".join(
            "".join(cell.get("source", []))
            for cell in notebook.get("cells", [])
        )

        self.assertIn('LOCAL_LLM_MODEL = "qwen3:4b-instruct"', source)
        self.assertIn('["ollama", "serve"]', source)
        self.assertIn('["ollama", "pull", LOCAL_LLM_MODEL]', source)
        self.assertIn('"http://127.0.0.1:11434/v1"', source)

    def test_native_dialog_endpoint_directs_colab_to_upload(self):
        with patch.dict(os.environ, {"MOJIOKOSI_RUNTIME": "colab"}, clear=False):
            response = self.client.post("/api/select-input")

        self.assertEqual(response.status_code, 409)
        self.assertTrue(response.get_json()["browser_upload_only"])

    def test_colab_page_allows_only_colab_frame_ancestors(self):
        with patch.dict(os.environ, {"MOJIOKOSI_RUNTIME": "colab"}, clear=False):
            response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertNotIn("X-Frame-Options", response.headers)
        policy = response.headers["Content-Security-Policy"]
        self.assertIn("frame-ancestors https://colab.research.google.com", policy)
        self.assertIn("https://*.research.google.com", policy)

    def test_colab_loopback_proxy_may_rewrite_host_but_not_bypass_cross_site_guard(self):
        headers = {"Host": "random-tunnel.example"}
        environ = {"REMOTE_ADDR": "127.0.0.1"}
        with patch.dict(os.environ, {"MOJIOKOSI_RUNTIME": "colab"}, clear=False):
            page = self.client.get("/", headers=headers, environ_overrides=environ)
            cross_site = self.client.get(
                "/api/config",
                headers={**headers, "Sec-Fetch-Site": "cross-site"},
                environ_overrides=environ,
            )

        self.assertEqual(page.status_code, 200)
        self.assertEqual(cross_site.status_code, 403)


if __name__ == "__main__":
    unittest.main()
