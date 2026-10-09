"""Regression guards for the real saved-interview smoke test's acceptance."""
import importlib.util
from pathlib import Path
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location(
    "saved_autonomous_smoke", Path(__file__).resolve().parents[1] / "scripts/test_saved_autonomous_analysis.py")
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


class AutonomousSmokeAcceptanceTests(unittest.TestCase):
    def test_runtime_initialization_is_fenced_to_the_isolated_database(self):
        copied = Path("synthetic-copy/library.sqlite3")
        initialize = Mock()
        app = SimpleNamespace(DATABASE_FILE=Path("synthetic-original/library.sqlite3"),
                              initialize_library=initialize)
        with self.assertRaises(RuntimeError):
            smoke.initialize_test_runtime(app, copied)
        initialize.assert_not_called()
        app.DATABASE_FILE = copied
        smoke.initialize_test_runtime(app, copied)
        initialize.assert_called_once_with(repair_provenance=False)

    def test_initial_analysis_success_does_not_pass_without_core(self):
        result = smoke.assess_run({"status": "completed", "iteration": 0,
                                   "tasks": [], "usage": {"measured_calls": 0}})
        self.assertFalse(result["passed"])
        self.assertFalse(result["checks"]["core_iteration_recorded"])

    def test_attempted_but_failed_core_does_not_pass(self):
        result = smoke.assess_run({"status": "failed", "iteration": 1,
            "tasks": [{"role": "core", "status": "failed"}], "usage": {"measured_calls": 1}})
        self.assertFalse(result["passed"])
        self.assertEqual(result["core_iterations_succeeded"], 0)

    def test_success_requires_actual_core_result_and_usage(self):
        state = {"status": "completed", "iteration": 2,
            "tasks": [{"role": "core", "status": "succeeded"}] * 2,
            "usage": {"measured_calls": 2}}
        self.assertTrue(smoke.assess_run(state)["passed"])
        state["usage"]["measured_calls"] = 0
        self.assertFalse(smoke.assess_run(state)["passed"])

    def test_single_core_result_is_not_a_repeated_loop(self):
        result = smoke.assess_run({"status": "completed", "iteration": 1,
            "tasks": [{"role": "core", "status": "succeeded"}], "usage": {"measured_calls": 1}})
        self.assertFalse(result["passed"])

    def test_delegated_reviews_require_exact_source_coverage_and_not_dummy_core_rounds(self):
        state = {"status": "completed", "iteration": 1, "completed_core_iterations": 1,
            "config": {"specialist_orchestration_version": 1, "min_iterations": 0},
            "tasks": [{"role": "core", "phase": "core", "status": "succeeded"},
                      {"role": "critic", "phase": "label_review", "status": "succeeded"}],
            "results": [{"role": "interpretation", "result_id": "r1", "validation_status": "valid"}],
            "usage": {"measured_calls": 3}}
        decisions = [{"role": "core", "result_assessments": []},
                     {"role": "orchestrator", "result_assessments": [{"result_id": "r1", "disposition": "defer"}]}]
        self.assertTrue(smoke.assess_run(state, decisions)["passed"])
        decisions[1]["result_assessments"].append({"result_id": "r1"})
        self.assertFalse(smoke.assess_run(state, decisions)["checks"]["specialist_results_reviewed"])
        decisions[1]["result_assessments"] = []
        self.assertFalse(smoke.assess_run(state, decisions)["passed"])

    def test_new_runs_require_specialist_output_saved_before_core(self):
        state = {"status": "completed", "iteration": 3, "config": {"initial_label_definitions_version": 1},
                 "tasks": [{"role": "core", "status": "succeeded", "started_at": "2026-10-05T00:01:00+00:00"}] * 3,
                 "usage": {"measured_calls": 4}}
        self.assertFalse(smoke.assess_run(state)["passed"])
        state["initial_label_catalog"] = {"created_by": "interpretation", "status": "ai_draft", "result_id": "label-result", "definitions": [{"name": "Draft"}]}
        design = {"role": "interpretation", "method_id": "label-design-v1", "status": "succeeded",
                  "result_id": "label-result", "ended_at": "2026-10-05T00:00:59+00:00"}
        state["tasks"].append(design)
        self.assertFalse(smoke.assess_run(state)["passed"])
        state["tasks"].pop(); state["tasks"].insert(0, design)
        result = smoke.assess_run(state)
        self.assertTrue(result["passed"])
        self.assertEqual(result["initial_label_definition_count"], 1)
        design["ended_at"] = "2026-10-05T00:01:01+00:00"
        self.assertFalse(smoke.assess_run(state)["passed"])

    def test_current_minimum_requires_three_successful_core_results(self):
        state = {"status": "completed", "iteration": 3, "config": {"min_iterations": 3},
            "tasks": [{"role": "core", "status": "succeeded"}] * 2,
            "usage": {"measured_calls": 3}}
        self.assertFalse(smoke.assess_run(state)["passed"])
        state["tasks"].append({"role": "core", "status": "succeeded"})
        self.assertTrue(smoke.assess_run(state)["passed"])

    def test_initial_routing_is_excluded_from_rounds_and_order_is_verified(self):
        initial = [{"role": role, "method_id": method, "phase": "initial_analysis", "status": "succeeded",
                    "ended_at": "01"} for role, method in (("interpretation", "agent-v1"), ("verification", "agent-v1"),
                    ("critic", "agent-v1"), ("statistics", "participation"), ("statistics", "conversation_dynamics"),
                    ("statistics", "label_frequency"))]
        routing = {"role": "core", "phase": "initial_routing", "status": "succeeded", "started_at": "02", "ended_at": "03"}
        design = {"role": "interpretation", "phase": "initial_labels", "method_id": "label-design-v1", "status": "succeeded",
                  "result_id": "label-result", "started_at": "04", "ended_at": "05"}
        state = {"status": "completed", "iteration": 3, "completed_core_iterations": 3,
            "config": {"min_iterations": 3, "initial_label_definitions_version": 1, "initial_specialist_analysis_version": 1},
            "tasks": [*initial, routing, design, *[{"role": "core", "phase": "core", "status": "succeeded", "started_at": "06"}] * 3],
            "usage": {"measured_calls": 8}, "initial_analysis_report": {"all_roles_reported": True},
            "initial_label_catalog": {"created_by": "interpretation", "status": "ai_draft", "result_id": "label-result", "definitions": [{"name": "Draft"}]}}
        result = smoke.assess_run(state)
        self.assertTrue(result["passed"])
        self.assertEqual(result["core_iterations_succeeded"], 3)
        state["completed_core_iterations"] = 2
        self.assertFalse(smoke.assess_run(state)["passed"])
        state["completed_core_iterations"] = 3
        initial[0]["ended_at"] = "04"
        self.assertFalse(smoke.assess_run(state)["checks"]["core_routes_after_reports_before_scale_design"])
        initial[0]["status"] = "quarantined"
        self.assertFalse(smoke.assess_run(state)["checks"]["all_initial_specialists_reported"])

    def test_repeated_successful_calls_do_not_replace_adopted_decisions(self):
        state = {"status": "completed", "iteration": 3, "completed_core_iterations": 2,
            "config": {"min_iterations": 3}, "tasks": [{"role": "core", "status": "succeeded"}] * 3,
            "usage": {"measured_calls": 3}}
        result = smoke.assess_run(state)
        self.assertFalse(result["passed"])
        self.assertEqual(result["core_iterations_succeeded"], 3)
        self.assertEqual(result["core_iterations_adopted"], 2)

    def test_review_pause_verifies_repetition_but_is_not_completed_analysis(self):
        result = smoke.assess_run({"status": "stopped", "stop_reason": "human_review_required", "iteration": 2,
            "tasks": [{"role": "core", "status": "succeeded"}] * 2, "usage": {"measured_calls": 2}})
        self.assertTrue(result["loop_execution_verified"])
        self.assertFalse(result["analysis_completed"])
        self.assertFalse(result["passed"])
