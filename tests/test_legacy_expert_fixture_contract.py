"""Keep the old omitted expert selection as a real Handler rejection."""
import unittest
from unittest.mock import patch

import app
import test_analysis_orchestration_integration as support


class LegacyExpertFixtureContractTests(unittest.TestCase):
    setUp = support.OrchestrationIntegrationTests.setUp
    payload = support.OrchestrationIntegrationTests.payload
    response = support.OrchestrationIntegrationTests.response
    start = support.OrchestrationIntegrationTests.start

    def test_omitted_expert_id_rejects_before_any_core_adoption(self):
        def omitted(*args):
            raw = self.response(*args)
            for intent in raw.get("intents", []):
                intent.pop("expert_id")
            return raw

        with patch.object(app, "call_orchestration_ai_json", side_effect=omitted), \
             patch.object(app, "run_orchestration_method") as method:
            rid = self.start()
            self.service.run(rid)
        exported = self.service.result("content", rid)
        run = exported["run"]
        self.assertEqual(run["stop_reason"], "execution_failure")
        self.assertEqual(run["tasks"][0]["error"], "expert_selection_invalid")
        self.assertEqual(run["tasks"][0]["validation_status"], "quarantined")
        self.assertEqual(exported["decisions"], [])
        self.assertEqual(run["current_view"], {})
        self.assertEqual(len(exported["raw_results"]), 1)
        self.assertEqual(exported["raw_results"][0]["validation_status"], "quarantined")
        self.assertTrue(all("expert_id" not in intent
                            for intent in exported["raw_results"][0]["raw"]["intents"]))
        self.assertEqual([role for role, *_ in self.calls], ["core"])
        self.assertFalse(any(task["role"] != "core" for task in run["tasks"]))
        method.assert_not_called()

    def test_general_agent_without_expert_provider_remains_compatible(self):
        # Historical general-agent mode is still supported; it does not test
        # the selected-expert path covered by the five integration regressions.
        self.service.expert_provider = None
        payload = self.payload()
        payload.pop("expert_ids")
        payload.pop("expert_inputs")

        def general(*args):
            raw = self.response(*args)
            for intent in raw.get("intents", []):
                intent.pop("expert_id")
            return raw

        with patch.object(app, "call_orchestration_ai_json", side_effect=general):
            rid = self.start(payload)
            self.service.run(rid)
        exported = self.service.result("content", rid)
        self.assertEqual(exported["run"]["status"], "completed", exported["run"])
        self.assertTrue(exported["decisions"])
        self.assertFalse(any("expert_agent" in task for task in exported["run"]["tasks"]))


if __name__ == "__main__":
    unittest.main()
