import threading
import time
import unittest
from unittest.mock import patch

import app
import test_content_analysis as support


class AnalysisMilestoneTests(unittest.TestCase):
    def setUp(self):
        self.fixture = support.ContentApiTests(
            "test_generated_result_persists_and_becomes_stale_on_edit"
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.client = self.fixture.client
        self.url = self.fixture.url

    def payload(self, request_id):
        data = self.client.get(self.url).get_json()
        return {
            "request_id": request_id,
            "source_revision": data["item"]["revision_count"],
            "analysis_revision": data["item"]["analysis_revision"],
            "mode": "automatic", "definition_ids": [],
            "provider_policy": "local_only", "publication_targets": [],
        }

    def status(self, pipeline_id):
        return self.client.get(f"{self.url}/pipelines/{pipeline_id}").get_json()

    def wait(self, pipeline_id, wanted):
        body = None
        for _ in range(250):
            body = self.status(pipeline_id)
            if body["status"] in wanted:
                return body
            time.sleep(0.02)
        self.fail(f"pipeline timeout: {body}")

    def test_independent_m2_tasks_overlap_and_m3_never_starts_early(self):
        both_started = threading.Event()
        release = threading.Event()
        active = set()
        lock = threading.Lock()
        original = app.run_analysis_pipeline_method

        def delayed(step_id, snapshot):
            with lock:
                active.add(step_id)
                if active == {"participation", "conversation_dynamics"}:
                    both_started.set()
            release.wait(2)
            return original(step_id, snapshot)

        with patch.object(app, "run_analysis_pipeline_method", side_effect=delayed):
            response = self.client.post(
                self.url + "/pipelines", json=self.payload("parallel-milestone-request-0001")
            )
            pipeline_id = response.get_json()["pipeline_id"]
            self.assertTrue(both_started.wait(2), self.status(pipeline_id))
            during = self.status(pipeline_id)
            m2 = next(value for value in during["milestones"] if value["id"] == "M2")
            m3 = next(value for value in during["milestones"] if value["id"] == "M3")
            self.assertEqual({value["status"] for value in m2["steps"]}, {"running"})
            self.assertEqual(m3["steps"][0]["status"], "planned")
            self.assertFalse(any(event["type"] == "milestone_started" and event["payload"]["milestone"] == "M3"
                                 for event in during["events"]))
            release.set()
            result = self.wait(pipeline_id, {"completed", "failed", "waiting"})
        self.assertEqual(result["status"], "completed", result)

    def test_retry_only_failed_step_and_keep_committed_sibling(self):
        calls = {"participation": 0, "conversation_dynamics": 0}
        original = app.run_analysis_pipeline_method

        def fail_once(step_id, snapshot):
            calls[step_id] += 1
            if step_id == "conversation_dynamics" and calls[step_id] == 1:
                raise OSError("temporary fixture failure")
            return original(step_id, snapshot)

        with patch.object(app, "run_analysis_pipeline_method", side_effect=fail_once):
            response = self.client.post(
                self.url + "/pipelines", json=self.payload("retry-milestone-request-0001")
            )
            pipeline_id = response.get_json()["pipeline_id"]
            failed = self.wait(pipeline_id, {"waiting", "failed"})
            self.assertEqual(failed["wait_reason"], "retry")
            m2 = next(value for value in failed["milestones"] if value["id"] == "M2")
            self.assertEqual({value["step_id"]: value["status"] for value in m2["steps"]}, {
                "conversation_dynamics": "failed", "participation": "committed",
            })
            retried = self.client.post(
                f"{self.url}/pipelines/{pipeline_id}/retry", json={"step_id": "conversation_dynamics"}
            )
            self.assertEqual(retried.status_code, 200, retried.get_json())
            result = self.wait(pipeline_id, {"completed", "failed", "waiting"})
        self.assertEqual(result["status"], "completed", result)
        self.assertEqual(calls, {"participation": 1, "conversation_dynamics": 2})
        m2 = next(value for value in result["milestones"] if value["id"] == "M2")
        self.assertEqual(next(value for value in m2["steps"] if value["step_id"] == "conversation_dynamics")["attempt"], 2)

    def test_retry_limit_is_enforced_without_rerunning_committed_sibling(self):
        original = app.run_analysis_pipeline_method

        def always_fail(step_id, snapshot):
            if step_id == "conversation_dynamics":
                raise OSError("persistent fixture failure")
            return original(step_id, snapshot)

        with patch.object(app, "run_analysis_pipeline_method", side_effect=always_fail):
            response = self.client.post(
                self.url + "/pipelines", json=self.payload("retry-limit-request-0001")
            )
            pipeline_id = response.get_json()["pipeline_id"]
            for expected_attempt in (1, 2, 3):
                state = self.wait(pipeline_id, {"waiting", "failed"})
                failed = next(
                    value for milestone in state["milestones"] for value in milestone["steps"]
                    if value["step_id"] == "conversation_dynamics"
                )
                self.assertEqual(failed["attempt"], expected_attempt)
                response = self.client.post(
                    f"{self.url}/pipelines/{pipeline_id}/retry",
                    json={"step_id": "conversation_dynamics"},
                )
                if expected_attempt < 3:
                    self.assertEqual(response.status_code, 200, response.get_json())
                else:
                    self.assertEqual(response.status_code, 409)
                    self.assertEqual(response.get_json()["reason_code"], "retry_limit_reached")


if __name__ == "__main__":
    unittest.main()
