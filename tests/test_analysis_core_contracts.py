import unittest

from gurumoji.analysis_core import (
    AnalysisContractError,
    CAPABILITIES,
    MILESTONE_STATES,
    PIPELINE_STATES,
    PUBLICATION_STATES,
    STEP_STATES,
    validate_transition,
)


class AnalysisCoreContractTests(unittest.TestCase):
    def test_all_runtime_state_sets_are_closed_and_nonempty(self):
        self.assertEqual(
            PIPELINE_STATES,
            {"accepted", "running", "waiting", "cancelling", "completed", "failed", "cancelled"},
        )
        self.assertIn("persisting", STEP_STATES)
        self.assertIn("not_applicable", STEP_STATES)
        self.assertEqual(MILESTONE_STATES, {"pending", "active", "waiting", "committed", "failed", "cancelled"})
        self.assertIn("not_selected", PUBLICATION_STATES)

    def test_transition_requires_a_guard_and_rejects_skips(self):
        validate_transition("step", "validating", "persisting", "artifact.valid")
        with self.assertRaisesRegex(AnalysisContractError, "guard"):
            validate_transition("step", "validating", "persisting", "")
        with self.assertRaisesRegex(AnalysisContractError, "許可されていない"):
            validate_transition("step", "validating", "committed", "skip.persistence")
        with self.assertRaises(AnalysisContractError):
            validate_transition("pipeline", "completed", "running", "retry.same.pipeline")

    def test_initial_scope_marks_unselected_capabilities_unavailable(self):
        self.assertEqual(CAPABILITIES["methods"]["participation"]["status"], "available")
        self.assertEqual(CAPABILITIES["methods"]["conversation_dynamics"]["status"], "available")
        self.assertEqual(CAPABILITIES["methods"]["interview_evaluation"]["status"], "unavailable")
        self.assertEqual(CAPABILITIES["exports"]["sav"]["status"], "unavailable")
        self.assertFalse(CAPABILITIES["llm_roles"]["manual"]["external"])


if __name__ == "__main__":
    unittest.main()
