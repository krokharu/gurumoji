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


class ConnectionCapabilityContractTests(unittest.TestCase):
    def test_opt_in_metadata_uses_the_22_method_registry_without_default_change(self):
        from gurumoji.analysis_core import capability_catalog, CONNECTION_VERSION
        from gurumoji.analysis_method_registry import METHODS
        before = capability_catalog()
        self.assertEqual(set(before), {"version", "capabilities"})
        value = capability_catalog(connections=True)["connections"]
        self.assertEqual(value["version"], CONNECTION_VERSION)
        self.assertEqual({row["method_id"] for row in value["methods"]}, {key for key, _, _ in METHODS})
        self.assertEqual(len(value["methods"]), 22)
        self.assertEqual(len(value["kinds"]), 5); self.assertEqual(len(value["roles"]), 4)
        self.assertTrue(all(not row["typed_asset_adapter_supported"] for row in value["methods"]))
        self.assertEqual(capability_catalog(), before)

    def test_native_tools_remain_the_existing_allowlist_and_unknown_is_not_registered(self):
        from gurumoji.analysis_method_registry import connection_method_descriptor
        from gurumoji.services.analysis_orchestration_methods import STATISTICAL_TOOLS, STATISTICAL_TOOL_VERSION
        for method_id, (output, _, _) in STATISTICAL_TOOLS.items():
            row = connection_method_descriptor(method_id)
            self.assertEqual(row["method_version"], STATISTICAL_TOOL_VERSION)
            self.assertEqual(row["output_names"], [output])
            self.assertEqual(row["scope_policy"], "all_included_initial")
            self.assertEqual(row["units"], ["utterance"])
            self.assertFalse(row["typed_asset_adapter_supported"])
        for name in ("welch", "paired", "nested", "python_expression", "unknown"):
            self.assertIsNone(connection_method_descriptor(name))


if __name__ == "__main__":
    unittest.main()
