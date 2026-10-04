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
