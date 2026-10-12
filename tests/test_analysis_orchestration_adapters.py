"""Synthetic provider boundary checks; no API, model, or real transcript."""
import json
from types import SimpleNamespace
import unittest

from gurumoji.analysis_core import AnalysisContractError
from gurumoji.services.analysis_orchestration_adapters import (
    AI_ROLES, CORE_SCHEMA, CRITIC_SCHEMA, SPECIALIST_SCHEMA,
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
        self.assertEqual(args[6], CRITIC_SCHEMA)
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

    def test_private_guard_seam_preserves_identity_and_checks_after_payload_work(self):
        guard, observed, checks = object(), [], []
        def call(*args, **kwargs):
            observed.append(kwargs)
            return {"summary": "TEST", "claims": []}
        resolve, run = make_orchestration_adapters(call_ai_json=call,
            load_token_config=lambda: self.config, configured_ai_credentials=lambda *_: ("", "synthetic-local"))
        options = resolve({})
        options.update(_request_budget=guard, _budget_attempt_id="TEST-attempt")
        run("core", {"task": {"task_id": "TEST-task"}}, options, lambda: checks.append(True), lambda _: None)
        self.assertIs(observed[0]["request_budget"], guard)
        self.assertEqual((observed[0]["task_id"], observed[0]["attempt_id"]), ("TEST-task", "TEST-attempt:0"))
        self.assertGreaterEqual(len(checks), 3)

    def test_late_adapter_result_is_not_returned_to_consumer(self):
        called = []
        def call(*args):
            called.append(True)
            return {"summary": "TEST", "claims": []}
        _, run = make_orchestration_adapters(call_ai_json=call, load_token_config=lambda: self.config,
            configured_ai_credentials=lambda *_: ("", "synthetic-local"))
        def check():
            if called: raise RuntimeError("deadline")
        with self.assertRaisesRegex(RuntimeError, "deadline"):
            run("core", {}, self.resolve({}), check, lambda _: None)

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

    def test_handler_timeout_is_forwarded_to_the_transport(self):
        options = self.resolve({})
        options["timeout_seconds"] = 420
        self.run("core", {}, options, lambda: None, lambda sample: None)
        self.assertEqual(self.calls[0][10], 420)

    def test_verification_references_are_bound_to_its_supplied_evidence_per_call(self):
        options = self.resolve({})
        for ids in (["e2", "e1"], ["e3"], []):
            self.run("verification", {"raw_evidence": [{"evidence_id": eid, "text": "synthetic"} for eid in ids]},
                     options, lambda: None, lambda _: None)
            refs = self.calls[-1][6]["properties"]["claims"]["items"]["properties"]["evidence_ids"]
            if ids:
                self.assertEqual(refs["items"]["enum"], sorted(ids))
            else:
                self.assertEqual(refs["maxItems"], 0)
        self.assertNotIn("enum", SPECIALIST_SCHEMA["properties"]["claims"]["items"]["properties"]["evidence_ids"]["items"])

    def test_roles_keep_complete_compact_index_and_delivered_utterance_ids(self):
        context = {"raw_evidence": [{"evidence_id": "e0", "utterance_id": "u0", "text": "synthetic"}],
                   "coverage": {"evidence_index": [{"evidence_id": f"e{i}", "utterance_id": f"u{i}"} for i in range(323)]}}
        for role in ("core", "verification", "critic"):
            self.run(role, context, self.resolve({}), lambda: None, lambda _: None)
            sent = json.loads(self.calls[-1][4])
            index = sent["coverage"]["evidence_index"]
            if role in {"core", "critic"}:
                self.assertEqual(index, {"columns": ["evidence_id"], "rows": [[f"e{i}"] for i in range(323)]})
                self.assertIn("columns_rows_v1", sent["coverage"]["evidence_index_format"])
                index = [dict(zip(index["columns"], row)) for row in index["rows"]]
            else:
                self.assertIsInstance(index, list)
                self.assertNotIn("columns_rows_v1", sent["coverage"]["evidence_index_format"])
            self.assertEqual(index, [{"evidence_id": f"e{i}"} for i in range(323)])
            self.assertEqual(sent["raw_evidence"][0]["utterance_id"], "u0")
        self.assertEqual(context["coverage"]["evidence_index"][-1]["utterance_id"], "u322")

    def test_handler_and_code_statistics_cannot_call_llm(self):
        for role in ("handler", "statistics", "unregistered"):
            with self.subTest(role=role), self.assertRaises(AnalysisContractError):
                self.run(role, {}, self.resolve({}), lambda: None, lambda sample: None)
        self.assertEqual(self.calls, [])

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

    def test_handler_pending_gate_constrains_core_without_leaking_to_next_call(self):
        options = self.resolve({})
        self.run("core", {"statistical_review_gate": {"status": "human_pending", "result_ids": ["saved-draft"]}},
                 options, lambda: None, lambda _: None)
        self.assertEqual(self.calls[-1][6]["properties"]["claims"]["maxItems"], 0)
        self.run("core", {}, options, lambda: None, lambda _: None)
        self.assertEqual(self.calls[-1][6]["properties"]["claims"]["maxItems"], 24)
        self.assertEqual(CORE_SCHEMA["properties"]["claims"]["maxItems"], 24)

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
        for schema in (CORE_SCHEMA, CRITIC_SCHEMA, SPECIALIST_SCHEMA):
            inspect(schema)


if __name__ == "__main__":
    unittest.main()


class AssetBindingAdapterBoundaryTests(unittest.TestCase):
    def test_private_binding_passes_actual_registry_authority_and_never_enables_execution(self):
        from test_analysis_asset_bindings import SyntheticStore
        from gurumoji.method_experts import ExpertCatalog
        from gurumoji.services.expert_agents import ExpertAgentRegistry
        from gurumoji.services.analysis_orchestration_adapters import make_asset_binding_adapters
        from pathlib import Path
        fixture = SyntheticStore()
        self.addCleanup(fixture.close)
        original, state = fixture.descriptors(fixture.run(), original=True)
        fixture.register(originals=[original], states=[state])
        registry = ExpertAgentRegistry(ExpertCatalog(root=Path(__file__).resolve().parents[1]/"docs/program-vault",
                                                     local_root=Path(fixture.temp.name)/"empty"))
        resolve, revalidate = make_asset_binding_adapters(store=fixture.store, expert_registry=registry)
        request = fixture.request(original, original=True)
        request.update(expert_id="exp-correlation", step_id="cor-p2",
                       actor={"kind":"code","actor_id":"TEST-code","step_ids":["cor-p2"]})
        result = resolve(**request)
        self.assertEqual(result["decision"], "eligible")
        self.assertFalse(result["execution_enabled"])
        request["expert_id"] = "exp-TEST-unknown"
        self.assertEqual(resolve(**request)["decision"], "rejected")
        self.assertEqual(revalidate(result, **request)["decision"], "blocked")

    def test_selected_optional_stops_without_implicit_omission_or_model_call(self):
        from test_analysis_asset_bindings import SyntheticStore
        from gurumoji.services.analysis_orchestration_adapters import make_asset_binding_adapters
        from unittest.mock import Mock
        fixture = SyntheticStore()
        self.addCleanup(fixture.close)
        asset, state = fixture.descriptors(fixture.run())
        fixture.register([asset], states=[state])
        registry = Mock()
        resolve, _ = make_asset_binding_adapters(store=fixture.store, expert_registry=registry)
        request = fixture.request(asset)
        request["slot"].update(required=False, min_items=0)
        request["inputs"][0].pop("source")
        request.update(expert_id="exp-correlation", step_id="cor-p2",
                       actor={"kind":"code","actor_id":"TEST-code","step_ids":["cor-p2"]})
        self.assertEqual(resolve(**request)["decision"], "needs_input")
        registry.assess_inputs.assert_not_called()
