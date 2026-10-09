"""Composition acceptance: export POST retains the shared request guards."""

import unittest
from unittest.mock import patch

import app


class AIDataExportRouteSecurityTests(unittest.TestCase):
    path = "/api/library/synthetic-item/ai-export.zip"
    token = "synthetic-export-test-token-12345"

    def setUp(self):
        self.database = self.enterContext(patch.object(app, "database_connection"))
        self.enterContext(patch.object(app, "REMOTE_ACCESS_ENABLED", False))
        self.enterContext(patch.object(app, "is_colab_runtime", return_value=False))
        self.client = app.create_app().test_client()

    def tearDown(self):
        self.database.assert_not_called()

    def test_untrusted_host_is_rejected_before_export(self):
        response = self.client.post(self.path, json={}, headers={"Host": "evil.example"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "Untrusted Host header.")

    def test_cross_site_is_rejected_before_export(self):
        response = self.client.post(self.path, json={}, headers={
            "Sec-Fetch-Site": "cross-site", "X-Gurumoji-Request": "1",
        })
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "Cross-origin request rejected.")

    def test_same_origin_browser_requires_csrf_header(self):
        response = self.client.post(self.path, json={}, headers={
            "Sec-Fetch-Site": "same-origin", "Origin": "http://localhost",
        })
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "Missing CSRF request header.")

    def test_remote_mode_requires_authentication(self):
        with patch.object(app, "REMOTE_ACCESS_ENABLED", True), \
                patch.object(app, "REMOTE_ACCESS_TOKEN", self.token):
            response = self.client.post(self.path, json={})
        self.assertEqual(response.status_code, 401)
        self.assertIn("Basic", response.headers["WWW-Authenticate"])

    def test_authenticated_remote_download_reaches_request_validation(self):
        # A local attachment download is also supported by the established
        # authenticated remote UI. Invalid JSON stops before any DB read.
        with patch.object(app, "REMOTE_ACCESS_ENABLED", True), \
                patch.object(app, "REMOTE_ACCESS_TOKEN", self.token), \
                patch.object(app, "REMOTE_LOCAL_PATHS_ENABLED", False):
            response = self.client.post(self.path, data="null", content_type="application/json",
                headers={"Authorization": f"Bearer {self.token}", "X-Gurumoji-Request": "1"},
                environ_overrides={"REMOTE_ADDR": "192.0.2.20"})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_request")
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_oversized_json_is_rejected_before_export(self):
        with patch.object(app, "MAX_JSON_REQUEST_BYTES", 16):
            response = self.client.post(self.path, json={"include_names": False})
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.get_json()["error"], "Request body exceeds the configured size limit.")


if __name__ == "__main__":
    unittest.main()
