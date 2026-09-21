import time
import unittest
from unittest.mock import patch

import app
import test_content_analysis as support


class AnalysisLlmBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.fixture = support.ContentApiTests(
            "test_generated_result_persists_and_becomes_stale_on_edit"
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.client = self.fixture.client
        self.url = self.fixture.url

    def base(self, request_id):
        item = self.client.get(self.url).get_json()["item"]
        return {
            "request_id": request_id,
            "source_revision": item["revision_count"],
            "analysis_revision": item["analysis_revision"],
            "mode": "manual", "definition_ids": [],
            "provider_policy": "local_only", "publication_targets": [],
        }

    def test_pipeline_declares_llm_roles_unavailable_and_rejects_cloud_policy(self):
        catalog = self.client.get("/api/analysis/pipeline-capabilities")
        self.assertEqual(catalog.status_code, 200)
        self.assertEqual(catalog.get_json()["capabilities"]["llm_roles"]["all"]["status"], "unavailable")
        rejected = self.client.post(
            self.url + "/plans/preview",
            json={**self.base("cloud-policy-preview-0001"), "provider_policy": "cloud_allowed"},
        )
        self.assertEqual(rejected.status_code, 409)
        self.assertEqual(rejected.get_json()["reason_code"], "provider_unavailable")

    def test_manual_pipeline_and_publication_make_zero_ai_calls(self):
        with patch.object(app, "call_ai_json") as ai, patch.object(app, "post_json") as worker:
            response = self.client.post(
                self.url + "/pipelines", json=self.base("manual-local-only-request-0001")
            )
            self.assertEqual(response.status_code, 202, response.get_json())
            pipeline_id = response.get_json()["pipeline_id"]
            body = None
            for _ in range(250):
                body = self.client.get(f"{self.url}/pipelines/{pipeline_id}").get_json()
                if body["status"] in {"completed", "waiting", "failed", "cancelled"}:
                    break
                time.sleep(0.02)
            self.assertEqual(body["status"], "completed", body)
            ai.assert_not_called()
            worker.assert_not_called()


if __name__ == "__main__":
    unittest.main()
