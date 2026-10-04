"""Real app composition, staged statistics and temporary publication only."""
import json
import unittest
from unittest.mock import patch

import app
import gurumoji.research_analysis as research
import test_analysis_orchestration_integration as support


class DurableOutputIntegrationTests(unittest.TestCase):
    setUp = support.OrchestrationIntegrationTests.setUp
    payload = support.OrchestrationIntegrationTests.payload
    response = support.OrchestrationIntegrationTests.response
    start = support.OrchestrationIntegrationTests.start

    def state(self, rid):
        return self.client.get(self.url + "/" + rid).get_json()["run"]

    def test_default_fixed_save_has_no_vault_writers_and_polling_has_no_ai(self):
        with patch.object(app, "call_orchestration_ai_json", side_effect=self.response), \
             patch.object(app.AnalysisStore, "_publish_generated_vaults") as generated, \
             patch.object(app.AnalysisStore, "_publish_research") as owned:
            rid = self.start()
            self.assertEqual(self.state(rid)["phase"], "initial")
            self.service.run(rid)
            state = self.state(rid)
            self.assertEqual(state["status"], "completed", state)
            self.assertEqual(state["publication"]["save_status"], "saved", state["publication"])
            self.assertEqual(state["publication"]["publication_status"], "not_selected")
            count = len(self.calls)
            for _ in range(3):
                self.state(rid)
            self.assertEqual(len(self.calls), count)
            generated.assert_not_called(); owned.assert_not_called()
        saved = state["publication"]["result_run"]
        self.assertEqual(saved["kind"], "autonomous_analysis")
        artifact = next(a for a in saved["artifacts"] if a["name"] == "result.json")
        package = self.client.get(artifact["url"]).get_json()
        self.assertEqual(package["orchestration"]["run"]["run_id"], rid)
        self.assertTrue(package["orchestration"]["raw_results"])

    def test_completed_statistics_are_not_repeated_after_later_initial_failure(self):
        original = self.service.initial_builder.run_stage
        visits = []
        fail = [True]
        def stage(name, row, outputs):
            visits.append(name)
            if name == "content" and fail[0]:
                fail[0] = False
                raise OSError("Synthetic interruption after completed statistics")
            return original(name, row, outputs)
        with patch.object(self.service.initial_builder, "run_stage", side_effect=stage), \
             patch.object(research, "_statistics_analysis", wraps=research._statistics_analysis) as statistics, \
             patch.object(app, "call_orchestration_ai_json", side_effect=self.response):
            rid = self.start()
            self.service.run(rid)
            state = self.state(rid)
            self.assertEqual(state["status"], "recovery_required", state)
            self.assertEqual(statistics.call_count, 1)
            self.assertEqual(len(self.calls), 0)
            response = self.client.post(self.url + "/" + rid + "/resume", json={})
            self.assertEqual(response.status_code, 202, response.get_json())
            self.service.run(rid)
            final = self.state(rid)
            self.assertEqual(final["status"], "completed", final)
            self.assertEqual(statistics.call_count, 1)
            self.assertEqual(visits.count("statistics"), 1)
            self.assertEqual(visits.count("base"), 1)
            self.assertEqual(visits.count("content"), 2)
            self.assertEqual(final["publication"]["save_status"], "saved")

    def test_explicit_four_writer_set_and_retry_never_recompute_analysis(self):
        payload = self.payload()
        payload["publication_targets"] = ["input", "orchestrator", "visualization"]
        with patch.object(app, "call_orchestration_ai_json", side_effect=self.response):
            rid = self.start(payload)
            self.service.run(rid)
        state = self.state(rid)
        self.assertEqual(state["status"], "completed", state)
        self.assertEqual(state["publication"]["publication_status"], "published", state["publication"])
        self.assertEqual(set(state["publication"]["effective_writers"]), {"input", "orchestrator", "visualization", "research"})
        self.assertTrue(all(v["status"] == "published" for v in state["publication"]["outcomes"].values()))
        with patch.object(app, "call_orchestration_ai_json") as model, \
             patch.object(app, "run_orchestration_method") as method, \
             patch.object(self.service.initial_builder, "run_stage") as initial:
            response = self.client.post(self.url + "/" + rid + "/publication/retry", json={})
            self.assertEqual(response.status_code, 200, response.get_json())
            model.assert_not_called(); method.assert_not_called(); initial.assert_not_called()

    def test_publication_guard_reads_uncommitted_revision_in_same_connection(self):
        item = app.library_row("content")
        original = app.archive_source_stamp(item)
        with app.database_connection() as connection:
            connection.execute("INSERT OR REPLACE INTO application_metadata(key,value) VALUES('speaker_registry_revision','synthetic-new')")
            with self.assertRaises(app.AnalysisContractError) as caught:
                app.orchestration_source_guard(connection, "content", original)
        self.assertEqual(caught.exception.code, "revision_conflict")


if __name__ == "__main__":
    unittest.main()
