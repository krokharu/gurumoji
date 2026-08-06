import os
import unittest
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
