import threading
import time
import unittest
import json
from types import SimpleNamespace
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

    def test_local_transformer_proposal_is_validated_and_recorded_in_plan(self):
        class Vector:
            def __init__(self, value):
                self.value = value

            def __matmul__(self, other):
                return self.value * other.value

        def encode(values, *, kind):
            if kind == "query":
                return [Vector(1)], {"name": "test-local-transformer"}
            return [Vector(0.9), Vector(0.2)], {"name": "test-local-transformer"}

        payload = self.payload("proposal-transformer-request-0001")
        with patch.object(app, "encode_transformer_texts", side_effect=encode):
            response = self.client.post(self.url + "/plans/proposals", json={
                **payload, "engine": "transformer", "objective": "参加の偏りを確認したい",
            })
        self.assertEqual(response.status_code, 200, response.get_json())
        proposal = response.get_json()["proposal"]
        self.assertEqual(proposal["primary_method"], "participation")
        self.assertEqual(proposal["provider"], "local_transformer")
        recorded = {key: value for key, value in proposal.items() if key != "advice_token"}
        preview = self.client.post(self.url + "/plans/preview", json={
            **payload, "planning_proposal": proposal,
        })
        self.assertEqual(preview.status_code, 200, preview.get_json())
        self.assertEqual(preview.get_json()["plan"]["planning_proposal"], recorded)
        started = self.client.post(self.url + "/pipelines", json={
            **payload, "planning_proposal": proposal,
        })
        self.assertEqual(started.status_code, 202, started.get_json())
        self.assertEqual(started.get_json()["planning"], {
            "objective": proposal["objective"], "provider": "local_transformer",
            "model": "test-local-transformer", "primary_method": "participation",
        })
        completed = self.wait(started.get_json()["pipeline_id"], {"completed", "failed", "waiting"})
        self.assertEqual(completed["status"], "completed", completed)
        run = completed["result_run"]
        artifact = next(value for value in run["artifacts"] if value["name"] == "result.json")
        package = json.loads(self.client.get(artifact["url"]).data)
        self.assertEqual(package["parameters"]["planning_proposal"], recorded)
        proposal["input_hash"] = "old-input"
        tampered = self.client.post(self.url + "/plans/preview", json={
            **payload, "planning_proposal": proposal,
        })
        self.assertEqual(tampered.status_code, 400, tampered.get_json())

    def test_selected_local_llm_proposes_only_supported_plan_fields(self):
        payload = self.payload("proposal-local-llm-request-0001")
        with patch.object(app, "load_token_config", return_value=SimpleNamespace(
            lmstudio_base_url="http://127.0.0.1:1234/v1"
        )), patch.object(app, "configured_ai_credentials", return_value=("", "test-local-model")), patch.object(
            app, "call_ai_json", return_value={
                "primary_method": "conversation_dynamics", "rationale": "話者交替を先に確認する。",
                "checks": [{"id": "timing_quality", "message": "発話時刻を確認する。"}],
            }
        ) as call:
            response = self.client.post(self.url + "/plans/proposals", json={
                **payload, "engine": "llm", "provider": "lmstudio",
                "objective": "発話の時間構造を確認したい",
            })
        self.assertEqual(response.status_code, 200, response.get_json())
        proposal = response.get_json()["proposal"]
        self.assertEqual(proposal["provider"], "lmstudio")
        self.assertEqual(proposal["model"], "test-local-model")
        self.assertEqual(proposal["review_order"][0], "conversation_dynamics")
        self.assertIn("interpretation_limit", {check["id"] for check in proposal["checks"]})
        self.assertIn("available_methods", call.call_args.args[4])
        self.assertNotIn("segments", json.loads(call.call_args.args[4]))

    def test_cloud_llm_requires_explicit_cloud_policy(self):
        payload = self.payload("proposal-cloud-policy-request-0001")
        with patch.object(app, "call_ai_json") as call:
            response = self.client.post(self.url + "/plans/proposals", json={
                **payload, "engine": "llm", "provider": "openai",
                "objective": "参加の偏りを確認したい",
            })
        self.assertEqual(response.status_code, 409, response.get_json())
        call.assert_not_called()

    def test_selected_cloud_llm_receives_only_planning_context(self):
        payload = self.payload("proposal-cloud-allowed-request-0001")
        with patch.object(app, "load_token_config", return_value=SimpleNamespace()), patch.object(
            app, "configured_ai_credentials", return_value=("test-key", "test-cloud-model")
        ), patch.object(app, "call_ai_json", return_value={
            "primary_method": "participation", "rationale": "参加の偏りを先に確認する。",
            "checks": [],
        }) as call:
            response = self.client.post(self.url + "/plans/proposals", json={
                **payload, "engine": "llm", "provider": "openai",
                "provider_policy": "cloud_allowed", "objective": "参加の偏りを確認したい",
            })
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(call.call_args.args[0], "openai")
        context = json.loads(call.call_args.args[4])
        self.assertEqual(context["objective"], "参加の偏りを確認したい")
        self.assertEqual(set(context), {
            "objective", "included_segment_count", "speaker_count", "invalid_time_segments", "available_methods",
        })
        proposal = response.get_json()["proposal"]
        preview = self.client.post(self.url + "/plans/preview", json={
            **payload, "provider_policy": "cloud_allowed", "planning_proposal": proposal,
        })
        self.assertEqual(preview.status_code, 200, preview.get_json())

    def test_llm_cannot_add_an_unimplemented_method(self):
        payload = self.payload("proposal-invalid-method-request-0001")
        with patch.object(app, "load_token_config", return_value=SimpleNamespace(
            lmstudio_base_url="http://127.0.0.1:1234/v1"
        )), patch.object(app, "configured_ai_credentials", return_value=("", "test-local-model")), patch.object(
            app, "call_ai_json", return_value={
                "primary_method": "inferential_statistics", "rationale": "実装されていない手法を使う。",
                "checks": [],
            }
        ):
            response = self.client.post(self.url + "/plans/proposals", json={
                **payload, "engine": "llm", "provider": "lmstudio",
                "objective": "参加の偏りを確認したい",
            })
        self.assertEqual(response.status_code, 400, response.get_json())
        self.assertEqual(response.get_json()["reason_code"], "invalid_proposal")

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
