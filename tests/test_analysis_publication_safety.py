"""Temporary-vault publication scope, evidence, and immutable-package regressions."""
import json
import time
import unittest
from unittest.mock import patch

import app
import test_content_analysis as support
from gurumoji.analysis_store import AnalysisStore, StoreConflict, initialize_store
from gurumoji.vault_registry import VaultRegistry


class PublicationSafetyTests(unittest.TestCase):
    def setUp(self):
        self.fixture = support.ContentApiTests("test_generated_result_persists_and_becomes_stale_on_edit")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.client, self.url = self.fixture.client, self.fixture.url
        self.store = app.analysis_archive_store()

    def payload(self, targets=None):
        item = self.client.get(self.url).get_json()["item"]
        return {"request_id": "publication-safety-request-0001", "source_revision": item["revision_count"],
                "analysis_revision": item["analysis_revision"], "mode": "automatic", "definition_ids": [],
                "publication_targets": ["input", "orchestrator", "visualization"] if targets is None else targets}

    def start(self, targets=None):
        response = self.client.post(self.url + "/pipelines", json=self.payload(targets))
        self.assertEqual(response.status_code, 202, response.get_json())
        return response.get_json()["pipeline_id"]

    def wait(self, pipeline_id):
        for _ in range(300):
            value = self.client.get(f"{self.url}/pipelines/{pipeline_id}").get_json()
            if value["status"] in {"completed", "waiting", "failed"}:
                return value
            time.sleep(.02)
        self.fail(str(value))

    def retry(self, pipeline_id):
        response = self.client.post(f"{self.url}/pipelines/{pipeline_id}/retry", json={"step_id": "publish_result"})
        self.assertEqual(response.status_code, 200, response.get_json())
        return self.wait(pipeline_id)

    def test_partial_duplicate_unknown_or_malformed_targets_never_dispatch_writers(self):
        with patch.object(AnalysisStore, "publish") as publish:
            for targets in (["input"], ["input", "visualization"], ["input"] * 3, ["research"], [None], "input", {}):
                with self.subTest(targets=targets):
                    response = self.client.post(self.url + "/pipelines", json=self.payload(targets))
                    self.assertEqual(response.status_code, 400, response.get_json())
            publish.assert_not_called()

    def test_empty_scope_never_writes_even_via_direct_retry_or_refresh(self):
        with patch.object(VaultRegistry, "publish_analysis") as generated, patch.object(AnalysisStore, "source_notes") as research:
            state = self.wait(self.start([]))
            self.assertEqual(state["status"], "completed", state)
            self.assertEqual({value["status"] for value in state["publications"]}, {"not_selected"})
            run_id = state["result_run"]["id"]
            self.store.publish(run_id)
            self.store.refresh_vaults("content")
            generated.assert_not_called(); research.assert_not_called()
        for attempt in self.store.publication_attempts(run_id):
            self.assertEqual((attempt["requested"], attempt["effective"], attempt["executed"]), ([], [], []))
            self.assertEqual(attempt["status"], "not_selected")
        with self.assertRaises(StoreConflict):
            self.store.publish(run_id, targets=["input", "orchestrator", "visualization"])

    def test_research_conflict_prevents_completed_and_keeps_four_writer_attempt(self):
        with patch.object(AnalysisStore, "source_notes", side_effect=StoreConflict("synthetic research conflict")):
            state = self.wait(self.start())
        self.assertEqual((state["status"], state["wait_reason"]), ("waiting", "publication"), state)
        outputs = {value["target_role"]: value["status"] for value in state["publications"]}
        self.assertEqual(outputs, {"research": "conflict", "input": "published", "orchestrator": "published", "visualization": "published"})
        run = state["result_run"]
        self.assertEqual(run["status"], "completed")
        self.assertFalse(run["vault_outputs_complete"])
        first = self.store.publication_attempts(run["id"])[0]
        self.assertEqual(first["requested"], ["input", "orchestrator", "visualization"])
        self.assertEqual(set(first["effective"]), {"research", "input", "orchestrator", "visualization"})
        self.assertEqual(set(first["executed"]), set(first["effective"]))
        self.assertEqual(first["status"], "incomplete")
        with patch.object(app, "call_ai_json") as ai, patch.object(app, "run_analysis_pipeline_method") as methods:
            final = self.retry(state["pipeline_id"])
            self.assertEqual(final["status"], "completed", final)
            self.assertEqual(final["result_run"]["id"], run["id"])
            methods.assert_not_called(); ai.assert_not_called()
        attempts = self.store.publication_attempts(run["id"])
        self.assertEqual(len(attempts), 2)
        self.assertEqual(attempts[0], first)
        self.assertEqual(attempts[0]["package_hash"], attempts[1]["package_hash"])
        self.assertEqual(attempts[1]["status"], "completed")

    def test_missing_or_corrupt_fixed_package_blocks_retry_without_analysis_or_writers(self):
        with patch.object(AnalysisStore, "source_notes", side_effect=StoreConflict("synthetic conflict")):
            state = self.wait(self.start())
        run_id = state["result_run"]["id"]
        artifact = next(value for value in self.store.artifacts(run_id) if value["name"].startswith("tables/"))
        (self.store.root / artifact["path"]).write_bytes(b"synthetic corruption")
        with patch.object(app, "run_analysis_pipeline_method") as methods, patch.object(VaultRegistry, "publish_analysis") as generated, patch.object(AnalysisStore, "source_notes") as research:
            final = self.retry(state["pipeline_id"])
            self.assertEqual((final["status"], final["wait_reason"]), ("waiting", "publication"), final)
            self.assertEqual(final["result_run"]["id"], run_id)
            methods.assert_not_called(); generated.assert_not_called(); research.assert_not_called()
        self.assertEqual((self.store.root / artifact["path"]).read_bytes(), b"synthetic corruption")
        self.assertEqual(self.store.get(run_id)["status"], "completed")
        attempt = self.store.publication_attempts(run_id)[-1]
        self.assertEqual((attempt["status"], attempt["executed"]), ("blocked", []))
        self.assertFalse(self.store.public(self.store.get(run_id))["vault_outputs_complete"])

    def test_missing_manifest_is_never_rebuilt_on_publication_retry(self):
        state = self.wait(self.start())
        run_id = state["result_run"]["id"]
        artifact = next(value for value in self.store.artifacts(run_id) if value["name"] == "manifest.json")
        path = self.store.root / artifact["path"]
        path.unlink()
        with patch.object(VaultRegistry, "publish_analysis") as generated, patch.object(AnalysisStore, "source_notes") as research:
            with self.assertRaises(OSError):
                self.store.retry(run_id)
            generated.assert_not_called(); research.assert_not_called()
        self.assertFalse(path.exists())

    def test_legacy_no_attempt_is_unknown_even_when_generated_notes_exist(self):
        state = self.wait(self.start())
        run_id = state["result_run"]["id"]
        with self.store.connect() as connection:
            connection.execute("DELETE FROM analysis_publication_attempts WHERE run_id=?", (run_id,))
        outcomes = self.store.publication_outcomes(run_id)
        self.assertEqual({value["status"] for value in outcomes.values()}, {"unknown"})
        self.assertFalse(self.store.public(self.store.get(run_id))["vault_outputs_complete"])

    def test_restart_preserves_incomplete_attempt_and_allows_same_package_retry(self):
        state = self.wait(self.start())
        run_id = state["result_run"]["id"]
        with self.store.connect() as connection:
            connection.execute("UPDATE analysis_publication_attempts SET status='publishing',outcomes_json=? WHERE run_id=?",
                               (json.dumps({kind: {"status": "pending", "error": ""} for kind in ("research", "input", "orchestrator", "visualization")}), run_id))
            initialize_store(connection)
        first = self.store.publication_attempts(run_id)[0]
        self.assertEqual(first["status"], "incomplete")
        self.assertEqual({value["status"] for value in first["outcomes"].values()}, {"unknown"})
        self.store.retry(run_id)
        self.assertEqual(self.store.publication_attempts(run_id)[-1]["status"], "completed")

    def test_active_publication_and_scope_changes_are_rejected(self):
        state = self.wait(self.start())
        run_id = state["result_run"]["id"]
        with self.assertRaises(StoreConflict):
            self.store.publish(run_id, targets=[])
        with self.store.connect() as connection:
            connection.execute("UPDATE analysis_publication_attempts SET status='publishing' WHERE run_id=?", (run_id,))
        with patch.object(VaultRegistry, "publish_analysis") as generated:
            with self.assertRaises(StoreConflict):
                self.store.retry(run_id)
            generated.assert_not_called()


if __name__ == "__main__":
    unittest.main()
