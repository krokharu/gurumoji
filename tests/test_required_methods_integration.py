"""合成入力と一時DBによる必須分析の実行契約。"""
import unittest

import test_analysis_orchestration as fixture
from gurumoji.analysis_core import AnalysisContractError
from gurumoji.analysis_orchestration import validate_orchestration_payload


class RequiredMethodsIntegrationTests(unittest.TestCase):
    connect = fixture.RuntimeTests.connect
    build = fixture.RuntimeTests.build
    run_agent = fixture.RuntimeTests.run_agent
    method = fixture.RuntimeTests.method
    make_service = fixture.RuntimeTests.make_service
    start = fixture.RuntimeTests.start
    drive = fixture.RuntimeTests.drive

    def setUp(self):
        fixture.RuntimeTests.setUp(self)
        self.agent = self.agent_response

    def agent_response(self, role, context, *_):
        task = context["task"]
        if role == "orchestrator":
            return fixture.core("統計と限界を確認", stop=None,
                                result_assessments=fixture.assess_pending_results(context),
                                alternatives=[], unresolved=[])
        if role == "core" and task["phase"] == "core":
            return fixture.core("人による判断が必要", intents=[], alternatives=[], unresolved=[],
                                result_assessments=[], stop={"reason": "human_review_required",
                                                            "summary": "人の確認待ち", "unresolved": []})
        return fixture.InitialSpecialistTests.valid_agent(self, role, context)

    def test_invalid_required_methods_rejected(self):
        base = {"model": "synthetic-model"}
        for value in (["unknown"], ["participation", "participation"], "participation", None):
            with self.subTest(value=value), self.assertRaises(AnalysisContractError):
                validate_orchestration_payload({**base, "required_methods": value})

    def test_stop_requires_all_methods_review_and_core_integration(self):
        methods = ["participation", "conversation_dynamics", "label_frequency"]
        run = self.drive(self.start(required_methods=methods, specialist_orchestration_version=1,
                                    core_progress_version=1, initial_label_definitions_version=1,
                                    initial_specialist_analysis_version=1, max_calls=150, max_tasks=200))
        self.assertEqual(run["config"]["required_methods"], methods)
        self.assertEqual(run["status"], "stopped", run.get("error"))
        self.assertEqual(run["stop_reason"], "human_review_required")
        self.assertTrue(run["analysis_processing_complete"])
        progress = run["required_methods_progress"]
        self.assertEqual({p["id"] for p in progress}, set(methods))
        for item in progress:
            self.assertEqual(item["status"], "succeeded", item)
            self.assertEqual(item["review"]["disposition"], "adopt", item)
            self.assertTrue(item["review"]["reason"], item)
            self.assertTrue(item["core_integrated"], item)
            self.assertTrue(item["complete"], item)
        self.item["revision"] = "input-v2"
        stale = self.service.status("conversation", run["run_id"])
        self.assertTrue(stale["stale"])
        self.assertTrue(all(not item["complete"] for item in stale["required_methods_progress"]))

    def test_required_methods_run_without_initial_label_workflow(self):
        run = self.drive(self.start(required_methods=["participation", "label_frequency"],
                                    specialist_orchestration_version=1, core_progress_version=1,
                                    max_calls=100, max_tasks=100))
        self.assertEqual(run["status"], "stopped", run.get("error"))
        self.assertEqual(run["stop_reason"], "human_review_required")
        self.assertTrue(run["analysis_processing_complete"])
        self.assertTrue(all(item["complete"] for item in run["required_methods_progress"]))
        self.assertTrue(any(t["phase"] == "required_methods" for t in run["tasks"]))

    def test_failed_required_calculation_cannot_be_marked_complete(self):
        def failed_method(name, snapshot):
            raise ValueError("合成データの計算不能")
        self.method = failed_method
        self.service = self.make_service()
        run = self.drive(self.start(required_methods=["participation"],
                                    specialist_orchestration_version=1, core_progress_version=1,
                                    max_calls=50, max_tasks=60))
        self.assertFalse(run.get("analysis_processing_complete", False), run)
        self.assertNotEqual(run["status"], "completed")
        self.assertFalse(run["required_methods_progress"][0]["complete"])

    def test_deferred_review_cannot_be_marked_complete(self):
        original = self.agent
        def defer_statistics(role, context, *args):
            response = original(role, context, *args)
            if role == "orchestrator" and context["review_domain"] == "statistics":
                for assessment in response["result_assessments"]:
                    assessment["disposition"] = "defer"
            return response
        self.agent = defer_statistics
        run = self.drive(self.start(required_methods=["participation"],
                                    specialist_orchestration_version=1, core_progress_version=1,
                                    max_calls=50, max_tasks=60))
        self.assertNotEqual(run["status"], "completed")
        self.assertEqual(run["stop_reason"], "required_methods_incomplete")
        self.assertFalse(run.get("analysis_processing_complete", False))
        progress = run["required_methods_progress"][0]
        self.assertEqual(progress["review"]["disposition"], "defer")
        self.assertFalse(progress["complete"])


if __name__ == "__main__":
    unittest.main()
