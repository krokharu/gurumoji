import time
import unittest
from unittest.mock import patch

import app
import test_content_analysis as support
from gurumoji.vault_registry import VaultRegistry


class AnalysisPipelinePublicationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = support.ContentApiTests(
            "test_generated_result_persists_and_becomes_stale_on_edit"
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.client = self.fixture.client
        self.url = self.fixture.url

    def payload(self):
        item = self.client.get(self.url).get_json()["item"]
        return {
            "request_id": "pipeline-publication-request-0001",
            "source_revision": item["revision_count"],
            "analysis_revision": item["analysis_revision"],
            "mode": "automatic", "definition_ids": [], "provider_policy": "local_only",
            "publication_targets": ["input", "orchestrator", "visualization"],
        }

    def wait(self, pipeline_id, statuses):
        body = None
        for _ in range(300):
            body = self.client.get(f"{self.url}/pipelines/{pipeline_id}").get_json()
            if body["status"] in statuses:
                return body
            time.sleep(0.02)
        self.fail(f"pipeline timeout: {body}")

    def test_per_target_failure_keeps_result_and_publication_only_retry_calls_no_ai(self):
        original = VaultRegistry._write

        def conflict_visual(registry, data, kind, relative, note_id, properties, body):
            if kind == "visualization" and note_id.startswith("visual-"):
                return "conflict"
            return original(registry, data, kind, relative, note_id, properties, body)

        with patch.object(VaultRegistry, "_write", new=conflict_visual), \
             patch.object(app, "call_ai_json") as ai, patch.object(app, "post_json") as http:
            response = self.client.post(self.url + "/pipelines", json=self.payload())
            self.assertEqual(response.status_code, 202, response.get_json())
            pipeline_id = response.get_json()["pipeline_id"]
            failed = self.wait(pipeline_id, {"waiting", "failed"})
            self.assertEqual(failed["status"], "waiting", failed)
            self.assertEqual(failed["wait_reason"], "publication")
            self.assertEqual(failed["result_run"]["status"], "completed")
            self.assertEqual(failed["result_run"]["vault_status"], "completed")
            outcomes = {value["target_role"]: value["status"] for value in failed["publications"]}
            self.assertEqual(outcomes["input"], "published")
            self.assertEqual(outcomes["orchestrator"], "published")
            self.assertEqual(outcomes["visualization"], "conflict")
            ai.assert_not_called()
            http.assert_not_called()

        with patch.object(app, "call_ai_json") as ai, patch.object(app, "post_json") as http:
            retried = self.client.post(
                f"{self.url}/pipelines/{pipeline_id}/retry", json={"step_id": "publish_result"}
            )
            self.assertEqual(retried.status_code, 200, retried.get_json())
            completed = self.wait(pipeline_id, {"completed", "waiting", "failed"})
            self.assertEqual(completed["status"], "completed", completed)
            self.assertTrue(all(value["status"] == "published" for value in completed["publications"]))
            self.assertEqual(completed["result_run"]["id"], failed["result_run"]["id"])
            ai.assert_not_called()
            http.assert_not_called()


if __name__ == "__main__":
    unittest.main()
