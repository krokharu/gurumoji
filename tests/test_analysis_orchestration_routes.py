"""HTTP tests with an in-memory fake service and no external actions."""
from types import SimpleNamespace
from unittest.mock import Mock
import unittest

from flask import Flask
from gurumoji.analysis_core import AnalysisContractError
from gurumoji.web.analysis_orchestration_routes import register_orchestration_routes


class OrchestrationRouteTests(unittest.TestCase):
    def setUp(self):
        self.run = {"run_id": "run-1", "status": "running"}
        self.service = SimpleNamespace(**{name: Mock(return_value=self.run) for name in
                                        ("start", "status", "cancel", "resume", "result")})
        self.service.history = Mock(return_value=[self.run])
        self.prepare = Mock(side_effect=lambda value: value)
        flask = Flask(__name__)
        register_orchestration_routes(flask, lambda: self.service, self.prepare)
        self.client = flask.test_client()
        self.url = "/api/library/synthetic/analysis/orchestration"

    def test_polling_and_history_only_read(self):
        self.assertEqual(self.client.get(self.url).get_json(), {"runs": [self.run]})
        for _ in range(5):
            self.assertEqual(self.client.get(self.url + "/run-1").get_json(), {"run": self.run})
        self.prepare.assert_not_called()
        self.service.start.assert_not_called()
        self.service.resume.assert_not_called()

    def test_start_preflights_and_returns_run(self):
        response = self.client.post(self.url, json={"question": "合成の問い"})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.get_json(), {"run": self.run})
        self.prepare.assert_called_once_with({"question": "合成の問い"})
        self.service.start.assert_called_once()

    def test_non_object_or_large_payload_never_starts(self):
        for value in ([], "text", 1, None, {"question": "x" * 65536}):
            response = self.client.post(self.url, json=value)
            self.assertEqual(response.status_code, 400)
        self.prepare.assert_not_called()
        self.service.start.assert_not_called()

    def test_model_permission_failure_is_actionable(self):
        self.prepare.side_effect = AnalysisContractError("クラウド送信への同意が必要", code="provider_unavailable")
        response = self.client.post(self.url, json={})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["reason_code"], "provider_unavailable")
        self.service.start.assert_not_called()

    def test_result_scope_is_forwarded_and_download_is_attachment(self):
        self.client.get(self.url + "/run-1/results/result-1")
        self.service.result.assert_called_with("synthetic", "run-1", "result-1")
        response = self.client.get(self.url + "/run-1/export.json")
        self.assertEqual(response.status_code, 200)
        self.assertIn("attachment", response.headers["Content-Disposition"])
        self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_cancel_and_resume_use_exact_scope(self):
        self.assertEqual(self.client.post(self.url + "/run-1/cancel", json={}).status_code, 200)
        self.service.cancel.assert_called_once_with("synthetic", "run-1")
        self.assertEqual(self.client.post(self.url + "/run-1/resume", json={}).status_code, 202)
        self.service.resume.assert_called_once_with("synthetic", "run-1", {})

    def test_researcher_route_retains_original_wire_body_without_model_preparation(self):
        self.service.submit_human_record = Mock(return_value={"duplicate": False, "state": {"status": "candidate"}})
        raw = b'{ "TEST_fixture_only": true }'
        response = self.client.post(self.url + "/run-1/human-records", data=raw, content_type="application/json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        self.service.submit_human_record.assert_called_once_with("synthetic", "run-1", {"TEST_fixture_only": True}, request_bytes=raw)
        self.prepare.assert_not_called()
        self.service.start.assert_not_called()

    def test_storage_errors_do_not_expose_filesystem_or_data(self):
        self.service.status.side_effect = OSError("private-path-and-data")
        response = self.client.get(self.url + "/run-1")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private-path", response.get_data(as_text=True))

    def publication_client(self):
        self.publication = SimpleNamespace(status=Mock(return_value={"save_status": "saved", "publication_status": "not_selected"}),
                                           retry=Mock(), finalize=Mock())
        flask = Flask(__name__ + "-publication")
        register_orchestration_routes(flask, lambda: self.service, self.prepare,
                                      lambda: self.publication)
        return flask.test_client()

    def test_publication_polling_is_read_only_and_separate(self):
        client = self.publication_client()
        result = client.get(self.url + "/run-1").get_json()["run"]
        self.assertEqual(result["publication"]["publication_status"], "not_selected")
        self.assertEqual(result["status"], "running")
        self.publication.finalize.assert_not_called()
        self.publication.retry.assert_not_called()
        self.service.start.assert_not_called()

    def test_publication_retry_rejects_scope_changes_and_never_resumes_analysis(self):
        client = self.publication_client()
        endpoint = self.url + "/run-1/publication/retry"
        for value in ({"publication_targets": ["input", "orchestrator", "visualization"]},
                      {"force": True}, {"source_revision": 99}):
            self.assertEqual(client.post(endpoint, json=value).status_code, 400)
        self.publication.retry.assert_not_called()
        response = client.post(endpoint, json={})
        self.assertEqual(response.status_code, 200)
        self.publication.retry.assert_called_once_with("synthetic", "run-1")
        self.service.resume.assert_not_called()
        self.service.start.assert_not_called()

    def test_publication_conflict_has_a_specific_non_success_response(self):
        from gurumoji.analysis_store import StoreConflict
        client = self.publication_client()
        self.publication.retry.side_effect = StoreConflict("保存済みの公開範囲と不一致")
        response = client.post(self.url + "/run-1/publication/retry", json={})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["reason_code"], "publication_conflict")


if __name__ == "__main__":
    unittest.main()
