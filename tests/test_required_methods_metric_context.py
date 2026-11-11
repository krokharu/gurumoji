"""必須手法の状態と統計専用配送を合成データで確認する。"""
import copy
import json
import unittest
from types import SimpleNamespace

from gurumoji.services import model_context
from gurumoji.services.analysis_orchestration_adapters import make_orchestration_adapters
from test_metric_delivery import case


class RequiredMethodsMetricContextTests(unittest.TestCase):
    def test_reduced_statistics_review_keeps_required_progress_and_metric_codec(self):
        context = case()
        progress = [{"id": "participation", "status": "succeeded", "task_id": "t",
                     "result_id": "result-0", "review": None, "complete": False}]
        context["required_methods_progress"] = copy.deepcopy(progress)
        calls, samples = [], []
        def transport(*args, **kwargs):
            calls.append((args, kwargs))
            return {"summary": "合成結果", "claims": []}
        def meter(model, base, system, user, schema, **kwargs):
            pending = json.loads(user)["iteration_review"]["pending_result_ids"]
            return {"fits": len(pending) <= 1, "output_reserve": 2000, "count_method": "synthetic"}
        resolve, run = make_orchestration_adapters(
            call_ai_json=transport, load_token_config=lambda: SimpleNamespace(lmstudio_base_url=""),
            configured_ai_credentials=lambda *_: ("", "synthetic"), context_meter=meter)
        options = resolve({"model_context_version": 1, "context_reference_version": 0,
                           "metric_codec_version": 1, "required_methods": ["participation"]})
        options["_run_id"] = "run-synthetic"
        run("orchestrator", context, options, lambda: None, samples.append)
        args, _ = calls[0]
        packet, schema = json.loads(args[4]), args[6]
        self.assertEqual(packet["required_methods_progress"], progress)
        self.assertEqual(len(packet["iteration_review"]["pending_result_ids"]), 1)
        self.assertIn("metric_context", packet)
        self.assertIn("metric_selections", schema["required"])
        self.assertTrue(samples[-1]["context_manifest"]["metric_contract"])
        self.assertEqual(context["required_methods_progress"], progress)

    def test_initial_routing_pruning_keeps_required_progress(self):
        progress = [{"id": "participation", "status": "not_run", "complete": False}]
        context = {"task": {"role": "core", "phase": "initial_routing"},
                   "required_methods_progress": progress}
        self.assertEqual(model_context.compact_context(context)["required_methods_progress"], progress)


if __name__ == "__main__":
    unittest.main()
