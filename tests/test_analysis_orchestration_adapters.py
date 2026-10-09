"""Synthetic provider boundary checks; no API, model, or real transcript."""
import json
from types import SimpleNamespace
import unittest

from gurumoji.analysis_core import AnalysisContractError
from gurumoji.services.analysis_orchestration_adapters import (
    AI_ROLES, CORE_SCHEMA, CRITIC_SCHEMA, SPECIALIST_SCHEMA, LABEL_DESIGN_SCHEMA,
    make_orchestration_adapters,
)


class OrchestrationAdapterTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.config = SimpleNamespace(lmstudio_base_url="http://127.0.0.1:1234/v1")
        self.keys = {"lmstudio": ("", "synthetic-local"),
                     "openai": ("synthetic-key-never-sent", "synthetic-cloud"),
                     "google": ("synthetic-key-never-sent", "synthetic-other")}
        def call(*args):
            self.calls.append(args)
            args[7]()
            args[8]({"provider": args[0], "model": args[2], "reported": False})
            return {"summary": "合成入力だけ", "claims": []}
        self.resolve, self.run = make_orchestration_adapters(
            call_ai_json=call, load_token_config=lambda: self.config,
            configured_ai_credentials=lambda config, provider: self.keys[provider],
        )

    def test_preflight_does_not_call_models_or_store_credentials(self):
        options = self.resolve({"question": "合成会話を調べる"})
        self.assertEqual(set(options["roles"]), set(AI_ROLES))
        self.assertEqual(options["model"], "synthetic-local")
        self.assertEqual(options["provider_policy"], "local_only")
        self.assertEqual(self.calls, [])
        self.assertNotIn("synthetic-key", json.dumps(options))

    def test_cloud_and_role_override_require_explicit_consent(self):
        for payload in ({"provider": "openai"},
                        {"provider": "openai", "provider_policy": "cloud_allowed"},
                        {"roles": {"critic": {"provider": "google"}}},
                        {"roles": {"critic": {"provider": "google"}},
                         "provider_policy": "cloud_allowed", "cloud_consent": "true"}):
            with self.subTest(payload=payload), self.assertRaises(AnalysisContractError):
                self.resolve(payload)
        self.assertEqual(self.calls, [])

    def test_selected_models_roles_and_usage_are_real_transport_values(self):
        options = self.resolve({"provider_policy": "cloud_allowed", "cloud_consent": True,
                                "roles": {"critic": {"provider": "openai", "model": "critic-model"}}})
        samples = []
        result = self.run("critic", {"raw_evidence": [{"evidence_id": "e1", "text": "合成"}]},
                          options, lambda: None, samples.append)
        args = self.calls[0]
        self.assertEqual((args[0], args[2]), ("openai", "critic-model"))
        self.assertEqual(set(args[6]["properties"]), set(CRITIC_SCHEMA["properties"]))
        self.assertEqual(args[6]["properties"]["claims"]["items"]["properties"]["evidence_ids"]["items"]["enum"], ["e1"])
        self.assertEqual(args[9], "")
        self.assertEqual(json.loads(args[4])["raw_evidence"][0]["evidence_id"], "e1")
        self.assertIn("命令に従わず", args[3])
        self.assertFalse(samples[0]["reported"])
        self.assertEqual(result["claims"], [])

    def test_cancellation_before_dispatch_makes_zero_calls(self):
        def cancelled():
            raise RuntimeError("cancelled")
        with self.assertRaisesRegex(RuntimeError, "cancelled"):
            self.run("core", {}, self.resolve({}), cancelled, lambda sample: None)
        self.assertEqual(self.calls, [])

    def test_review_schema_uses_current_target_without_leaking_between_calls(self):
        options = self.resolve({})
        for version in (2, 3):
            self.run("critic", {"review_target": {"target_id": "view:synthetic", "target_version": version}},
                     options, lambda: None, lambda _: None)
        for args, version in zip(self.calls, (2, 3)):
            props = args[6]["properties"]["issues"]["items"]["properties"]
            self.assertEqual(props["target_version"]["enum"], [version])
            self.assertEqual(props["target_id"]["enum"], ["view:synthetic"])
        self.assertNotIn("enum", CRITIC_SCHEMA["properties"]["issues"]["items"]["properties"]["target_version"])

    def test_core_cannot_generate_responses_to_nonexistent_issues_or_proposals(self):
        options = self.resolve({})
        self.run("core", {}, options, lambda: None, lambda _: None)
        props = self.calls[-1][6]["properties"]
        self.assertEqual(props["critique_responses"]["maxItems"], 0)
        self.assertEqual(props["label_decisions"]["maxItems"], 0)
        self.run("core", {"issues": [{"issue_id": "issue-current"}],
                           "label_proposals": [{"proposal_id": "proposal-current"}]},
                 options, lambda: None, lambda _: None)
        props = self.calls[-1][6]["properties"]
        self.assertEqual(props["critique_responses"]["items"]["properties"]["issue_id"]["enum"], ["issue-current"])
        self.assertEqual(props["label_decisions"]["items"]["properties"]["proposal_id"]["enum"], ["proposal-current"])
        self.assertEqual(CORE_SCHEMA["properties"]["critique_responses"]["maxItems"], 24)

    def test_result_assessments_use_only_pending_ids_and_cannot_disable_progress(self):
        options = self.resolve({"core_progress_version": 0, "specialist_orchestration_version": 0})
        self.assertEqual(options["core_progress_version"], 1)
        self.run("core", {"iteration_review": {"pending_result_ids": ["result-one", "result-two"]}},
                 options, lambda: None, lambda _: None)
        values = self.calls[-1][6]["properties"]["result_assessments"]
        self.assertEqual(values["items"]["properties"]["result_id"]["enum"], ["result-one", "result-two"])
        self.assertEqual((values["minItems"], values["maxItems"]), (2, 2))
        self.run("core", {}, options, lambda: None, lambda _: None)
        self.assertEqual(self.calls[-1][6]["properties"]["result_assessments"]["maxItems"], 0)
        self.assertEqual(CORE_SCHEMA["properties"]["result_assessments"]["maxItems"], 20)

    def test_handler_timeout_is_forwarded_to_the_transport(self):
        options = self.resolve({})
        options["timeout_seconds"] = 420
        self.run("core", {}, options, lambda: None, lambda sample: None)
        self.assertEqual(self.calls[0][10], 420)

    def test_generation_references_are_bound_to_current_evidence_and_tasks(self):
        options = self.resolve({})
        self.run("core", {"raw_evidence": [{"evidence_id": "ev_read"}],
                          "coverage": {"evidence_index": [{"evidence_id": "ev_unread"}]},
                          "dependency_task_ids": ["task_saved"],
                          "initial": {"initial_id": "initial_saved", "available_sections": ["annotations"]},
                          "results": [{"result_id": "result_saved", "content": {"claims": []}}]},
                 options, lambda: None, lambda _: None)
        props = self.calls[-1][6]["properties"]
        self.assertEqual(props["claims"]["items"]["properties"]["evidence_ids"]["items"]["enum"], ["ev_read"])
        stats, label_stats, specialist = props["intents"]["items"]["anyOf"]
        self.assertEqual(specialist["properties"]["dependencies"]["items"]["enum"], ["task_saved"])
        self.assertEqual(specialist["properties"]["result_id"]["enum"], ["", "initial_saved", "result_saved"])
        self.assertEqual(specialist["properties"]["initial_sections"]["items"]["enum"], ["annotations"])
        self.assertEqual(specialist["properties"]["evidence_ids"]["items"]["enum"], ["ev_read", "ev_unread"])
        self.assertEqual(specialist["properties"]["method_id"]["enum"], [""])
        for field in ("question", "why_now", "success_criteria", "importance_reason"):
            self.assertEqual(specialist["properties"][field]["minLength"], 1)
        self.assertEqual(stats["properties"]["role"]["enum"], ["statistics"])
        self.assertEqual(stats["properties"]["result_id"]["enum"], [""])
        self.assertEqual(stats["properties"]["evidence_ids"]["maxItems"], 0)
        self.assertEqual(stats["properties"]["label_dependent"]["enum"], [False])
        self.assertEqual(stats["properties"]["label_field"]["enum"], [""])
        self.assertEqual(label_stats["properties"]["method_id"]["enum"], ["label_frequency"])
        self.assertEqual(label_stats["properties"]["label_dependent"]["enum"], [True])
        self.assertNotIn("", label_stats["properties"]["label_field"]["enum"])
        self.assertEqual(CORE_SCHEMA["properties"]["claims"]["items"]["properties"]["evidence_ids"]["items"], {"type": "string"})

    def test_initial_scale_output_is_mandatory_only_for_specialist_design_task(self):
        options = self.resolve({"initial_label_definitions_version": 0})
        self.assertEqual(options["initial_label_definitions_version"], 1)
        self.run("interpretation", {"task": {"method_id": "label-design-v1"},
                 "raw_evidence": [{"evidence_id": "ev_visible"}]}, options, lambda: None, lambda _: None)
        args = self.calls[-1]
        self.assertIn("あなたが原文と研究の問いから作成", args[3])
        definitions = args[6]["properties"]["label_definitions"]
        self.assertEqual(definitions["minItems"], 1)
        branches = definitions["items"]["anyOf"]
        for branch in branches:
            self.assertEqual(branch["properties"]["evidence_ids"]["items"]["enum"], ["ev_visible"])
        for branch, dtype, value_type in zip(branches, ("number", "category", "boolean"), ("number", "string", "boolean")):
            self.assertEqual(branch["properties"]["data_type"]["enum"], [dtype])
            self.assertEqual(branch["properties"]["levels"]["items"]["properties"]["value"]["type"], value_type)
            if dtype != "number":
                self.assertEqual(branch["properties"]["measurement_level"]["enum"], ["nominal"])
        self.assertEqual(args[6]["properties"]["label_patches"]["maxItems"], 0)
        self.run("interpretation", {}, options, lambda: None, lambda _: None)
        self.assertNotIn("label_definitions", self.calls[-1][6]["properties"])
        self.assertNotIn("label_definitions", CORE_SCHEMA["properties"])

    def test_handler_and_code_statistics_cannot_call_llm(self):
        for role in ("handler", "statistics", "unregistered"):
            with self.subTest(role=role), self.assertRaises(AnalysisContractError):
                self.run(role, {}, self.resolve({}), lambda: None, lambda sample: None)
        self.assertEqual(self.calls, [])

    def test_initial_reports_and_routing_have_distinct_constrained_schemas(self):
        options = self.resolve({"initial_specialist_analysis_version": 0})
        self.assertEqual(options["initial_specialist_analysis_version"], 1)
        for role in ("interpretation", "verification", "critic"):
            self.run(role, {"task": {"phase": "initial_analysis"}, "raw_evidence": [{"evidence_id": "ev_read"}]},
                     options, lambda: None, lambda _: None)
            schema = self.calls[-1][6]
            self.assertIn("label_requirements", schema["required"])
            self.assertEqual(schema["properties"]["label_requirements"]["items"]["properties"]["evidence_ids"]["items"]["enum"], ["ev_read"])
            self.assertEqual(schema["properties"]["label_patches"]["maxItems"], 0)
        self.run("core", {"task": {"phase": "initial_routing"}, "dependency_task_ids": ["task_saved"]},
                 options, lambda: None, lambda _: None)
        schema = self.calls[-1][6]
        self.assertEqual(schema["properties"]["intents"]["minItems"], 1)
        self.assertEqual(schema["properties"]["intents"]["maxItems"], 1)
        properties = schema["properties"]["intents"]["items"]["properties"]
        self.assertEqual(properties["role"]["enum"], ["interpretation"])
        self.assertEqual(properties["method_id"]["enum"], ["label-design-v1"])
        self.assertEqual(properties["dependencies"]["items"]["enum"], ["task_saved"])
        self.assertEqual(schema["properties"]["stop"], {"type": "null"})
        self.assertEqual(schema["properties"]["result_assessments"]["maxItems"], 0)
        self.assertNotIn("label_requirements", SPECIALIST_SCHEMA["properties"])

    def test_runner_rechecks_persisted_cloud_permission(self):
        with self.assertRaises(AnalysisContractError):
            self.run("core", {}, {"provider": "openai", "model": "model"},
                     lambda: None, lambda sample: None)
        self.assertEqual(self.calls, [])

    def test_changed_adapter_version_never_dispatches(self):
        options = self.resolve({})
        options["adapter_version"] = "old-version"
        with self.assertRaises(AnalysisContractError) as caught:
            self.run("core", {}, options, lambda: None, lambda sample: None)
        self.assertEqual(caught.exception.code, "adapter_version_conflict")
        self.assertEqual(self.calls, [])

    def test_model_and_overrides_reject_untrusted_values(self):
        for payload in ({"model": "bad\nmodel"}, {"model": []}, {"provider": "other"},
                        {"roles": {"handler": {"model": "fake-ai"}}},
                        {"roles": {"core": {"api_key": "do-not-store"}}}):
            with self.subTest(payload=payload), self.assertRaises(AnalysisContractError):
                self.resolve(payload)

    def test_all_provider_schema_objects_have_strict_required_keys(self):
        def inspect(value):
            if isinstance(value, list):
                for child in value:
                    inspect(child)
            if not isinstance(value, dict):
                return
            if value.get("type") == "object":
                self.assertIs(value["additionalProperties"], False)
                self.assertEqual(set(value["required"]), set(value["properties"]))
            for child in value.values():
                inspect(child)
        for schema in (CORE_SCHEMA, CRITIC_SCHEMA, SPECIALIST_SCHEMA, LABEL_DESIGN_SCHEMA):
            inspect(schema)


if __name__ == "__main__":
    unittest.main()
