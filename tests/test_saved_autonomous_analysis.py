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

    def test_current_minimum_requires_three_successful_core_results(self):
        state = {"status": "completed", "iteration": 3, "config": {"min_iterations": 3},
            "tasks": [{"role": "core", "status": "succeeded"}] * 2,
            "usage": {"measured_calls": 3}}
        self.assertFalse(smoke.assess_run(state)["passed"])
        state["tasks"].append({"role": "core", "status": "succeeded"})
        self.assertTrue(smoke.assess_run(state)["passed"])

    def test_review_pause_verifies_repetition_but_is_not_completed_analysis(self):
        result = smoke.assess_run({"status": "stopped", "stop_reason": "human_review_required", "iteration": 2,
            "tasks": [{"role": "core", "status": "succeeded"}] * 2, "usage": {"measured_calls": 2}})
        self.assertTrue(result["loop_execution_verified"])
        self.assertFalse(result["analysis_completed"])
        self.assertFalse(result["passed"])
