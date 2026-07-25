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


if __name__ == "__main__":
    unittest.main()
