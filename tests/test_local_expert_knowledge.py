"""Production knowledge delivery and evaluator checks; no local inference."""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

from gurumoji.analysis_core import AnalysisContractError
from gurumoji.services import model_context
from gurumoji.services.analysis_orchestration_adapters import ADAPTER_VERSION, make_orchestration_adapters
import test_analysis_orchestration as fixtures

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
# The script shares this test's filename: load it under an unambiguous name.
import importlib.util
spec = importlib.util.spec_from_file_location("local_expert_probe", Path(__file__).resolve().parents[1] / "scripts/test_local_expert_knowledge.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class KnowledgeDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.cases, self.read_log = probe.make_cases()

    def test_actual_notes_and_permitted_brief_reach_transport_as_resources(self):
        calls, measured, manifests = [], [], []
        def meter(*args, **kwargs):
            measured.append(model_context.restored_reference_context(args[3], kwargs.get("data_messages")))
            return {"fits": True, "output_reserve": 1600}
        resolve, run = make_orchestration_adapters(
            call_ai_json=lambda *a, **kw: calls.append((a, kw)) or {"summary": "synthetic"},
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url="http://127.0.0.1:1234/v1"),
            configured_ai_credentials=lambda *_: ("", "synthetic"), context_meter=meter)
        for case in self.cases:
            context = copy.deepcopy(case["context"])
            run("interpretation", context, resolve({"model_context_version": 1, "context_reference_version": 1}),
                lambda: None, manifests.append)
            args, keywords = calls[-1]
            restored = model_context.restored_reference_context(args[4], keywords["data_messages"])
            self.assertEqual(restored["expert_knowledge"], case["context"]["expert_knowledge"])
            self.assertEqual(measured[-1]["expert_knowledge"], restored["expert_knowledge"])
            self.assertEqual(manifests[-1]["context_manifest"]["expert_knowledge"], restored["expert_knowledge"])
            self.assertNotIn("expert_knowledge", json.loads(args[4]))
            self.assertEqual(context, case["context"])
        brief = measured[-1]["expert_knowledge"]["brief"]
        for field in ("steps", "prohibited_conclusions", "required_inputs", "applicability_checks", "out_of_scope"):
            self.assertTrue(brief[field])

    def test_mandatory_knowledge_is_not_silently_cut_to_fit(self):
        calls, manifests = [], []
        resolve, run = make_orchestration_adapters(
            call_ai_json=lambda *a, **kw: calls.append(a),
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url=""),
            configured_ai_credentials=lambda *_: ("", "synthetic"),
            context_meter=lambda *a, **kw: {"fits": False})
        case = self.cases[1]
        with self.assertRaises(AnalysisContractError) as caught:
            run("interpretation", case["context"], resolve({"model_context_version": 1, "context_reference_version": 1}),
                lambda: None, manifests.append)
        self.assertEqual(caught.exception.code, "context_budget_exceeded")
        self.assertEqual(calls, [])
        self.assertEqual(manifests[-1]["context_manifest"]["expert_knowledge"], case["context"]["expert_knowledge"])

    def test_expected_decisions_never_appear_in_task_data(self):
        for case in self.cases:
            instruction = json.loads(case["user"])
            self.assertNotIn("expected", instruction)
            for question in instruction["questions"]:
                self.assertEqual(set(question), {"question_id", "question"})
        self.assertNotIn("literature_full_text", self.cases[1]["context"]["expert_knowledge"]["read_scope"])

    def test_handler_supplies_common_rules_to_core_and_each_initial_ai_role(self):
        runtime = fixtures.InitialSpecialistTests()
        runtime.setUp()
        self.addCleanup(runtime.doCleanups)
        def reply(*args, **keywords):
            context = model_context.restored_reference_context(args[4], keywords.get("data_messages"))
            return fixtures.InitialSpecialistTests.valid_agent(runtime, args[5].removeprefix("analysis_orchestration_"), context)
        resolve, runtime.agent = make_orchestration_adapters(call_ai_json=reply,
            load_token_config=lambda: SimpleNamespace(lmstudio_base_url=""),
            configured_ai_credentials=lambda *_: ("", "synthetic"),
            context_meter=lambda *a, **kw: {"fits": True, "output_reserve": 3200})
        runtime.service = runtime.make_service(adapter_version=ADAPTER_VERSION)
        run = runtime.drive(fixtures.RuntimeTests.start(runtime, **resolve({"context_reference_version": 1,
            "model_context_version": 1, "specialist_orchestration_version": 0, "max_calls": 80, "max_tasks": 80})))
        self.assertIn(run["status"], {"completed", "stopped"}, run.get("error"))
        roles = set()
        for role, context, _ in runtime.calls:
            roles.add(role)
            knowledge = context["expert_knowledge"]
            self.assertEqual(knowledge["version"], 2)
            self.assertEqual(knowledge["status"], "common_rules_only")
            self.assertEqual({source["note_id"] for source in knowledge["sources"]},
                             {"analysis-common-evidence-and-claims", "analysis-common-ai-assistance-boundaries"})
            self.assertTrue(all(source["source_sha256"] for source in knowledge["sources"]))
            if role == "verification":
                self.assertNotIn("current_view", context)
                self.assertNotIn("results", context)
        self.assertTrue({"core", "interpretation", "verification", "critic"}.issubset(roles),
                        (roles, run.get("stop_reason"), [(task["role"], task["status"], task.get("error")) for task in run["tasks"]]))

    def test_wrong_answers_fake_quotes_duplicates_and_truncation_do_not_pass(self):
        case = self.cases[0]
        response = {"choices": [{"finish_reason": "length", "message": {"content": json.dumps({"answers": [
            {"question_id": "statistics", "decision": "allowed", "source_id": "analysis-common-evidence-and-claims", "quote": "存在しない専門家の引用を作って答えを正しく見せる"}]*6}, ensure_ascii=False)}}]}
        score = probe.score(case, response)
        self.assertFalse(score["passed"])
        self.assertFalse(any(score["checks"].values()))


if __name__ == "__main__":
    unittest.main()
