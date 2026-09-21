import unittest

from gurumoji.analysis_core import (
    AnalysisContractError,
    build_execution_binding,
    build_plan_envelope,
    validate_definition,
)


def definition(**values):
    result = {
        "definition_id": "text_length", "name": "発話文字数",
        "description": "各発話の文字数", "unit_of_analysis": "segment",
        "source_columns": ["text"], "output_column": "text_length",
        "data_type": "number", "measurement_level": "ratio",
        "measurement_rule": "text_length", "method": "descriptive",
    }
    result.update(values)
    return result


class AnalysisPlanBindingTests(unittest.TestCase):
    def plan(self, definitions=None, **payload):
        return build_plan_envelope(
            item_id="item-1", source_revision=2, analysis_revision=3,
            input_fingerprint="sha256:input", payload={"provider_policy": "local_only", **payload},
            definitions=definitions or [], segment_count=3,
        )

    def test_m0_envelope_is_hashed_and_m4_binding_is_separate(self):
        value = validate_definition(definition())
        plan = self.plan([value], mode="manual")
        before = plan.copy()
        binding = build_execution_binding(plan, [value])
        self.assertEqual(plan, before)
        self.assertEqual(binding["plan_hash"], plan["plan_hash"])
        self.assertEqual(binding["resolved"][0]["definition_id"], "text_length")
        self.assertEqual([step["milestone"] for step in plan["steps"]][0], "M0")
        self.assertEqual([step["milestone"] for step in plan["steps"]][-1], "M7")

    def test_unresolved_slot_and_out_of_scope_provider_stop_before_m5(self):
        value = validate_definition(definition())
        plan = self.plan([value])
        with self.assertRaisesRegex(AnalysisContractError, "未解決"):
            build_execution_binding(plan, [])
        with self.assertRaisesRegex(AnalysisContractError, "local_only"):
            self.plan(provider_policy="cloud_allowed")

    def test_manual_definition_does_not_require_llm(self):
        value = validate_definition(definition())
        plan = self.plan([value], mode="manual")
        self.assertEqual(plan["provider_policy"], "local_only")
        self.assertNotIn("provider", value)
        self.assertEqual(plan["eligibility"]["execution"], "allowed")

    def test_incompatible_scale_is_rejected_without_method_substitution(self):
        with self.assertRaisesRegex(AnalysisContractError, "名義"):
            validate_definition(definition(measurement_level="nominal"))

    def test_confirmatory_label_requires_predefinition(self):
        with self.assertRaisesRegex(AnalysisContractError, "事前固定"):
            self.plan(research_protocol={"classification": "confirmatory"})


if __name__ == "__main__":
    unittest.main()
