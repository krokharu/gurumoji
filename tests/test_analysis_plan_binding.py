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


class ConnectionSelectionTests(unittest.TestCase):
    def test_optional_omission_is_explicit_selected_optional_waits(self):
        from test_expert_skill_bindings import selection
        from gurumoji.analysis_core import assess_connection_inputs
        slot, refs, descriptor = selection()
        slot.update(required=False, min_items=0)
        del refs[0]["candidate"]
        self.assertEqual(assess_connection_inputs(slot, refs, descriptor)["decision"], "needs_input")
        refs[0].update(selection="omitted", omission_reason="TEST fixed new-plan omission")
        value = assess_connection_inputs(slot, refs, descriptor)
        self.assertEqual(value["decision"], "eligible")
        self.assertFalse(value["execution_enabled"])
        slot["required"] = True; slot["min_items"] = 1
        self.assertEqual(assess_connection_inputs(slot, refs, descriptor)["decision"], "rejected")

    def test_descriptor_schema_scope_and_adapter_cannot_be_widened_by_a_slot(self):
        from test_expert_skill_bindings import selection
        from gurumoji.analysis_core import assess_connection_inputs
        for field, value in (("unit", "participant"), ("scope_mode", "section"), ("scope_policy", "selected_subset"),
                             ("adapter", {"adapter_id": "arbitrary-expression", "version": "1"})):
            slot, refs, descriptor = selection(); refs[0]["candidate"][field] = value
            if field == "unit": slot["accept_units"] = [value]
            if field == "scope_mode": slot["scope_modes"] = [value]
            if field == "adapter": slot["adapter"] = value
            self.assertEqual(assess_connection_inputs(slot, refs, descriptor)["decision"], "unsupported")


if __name__ == "__main__":
    unittest.main()
