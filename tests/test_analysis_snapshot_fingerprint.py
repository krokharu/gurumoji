"""Input source-stamp boundary tests; every database and source is synthetic."""
import copy
import unittest
from unittest.mock import patch

import app
import test_content_analysis as support
from gurumoji.analysis_core import AnalysisContractError
from gurumoji.services.analysis_pipeline_adapters import make_analysis_pipeline_adapters


class SnapshotFingerprintUnitTests(unittest.TestCase):
    def builder(self, *, change=None, archive_change=False):
        state = {"preparation": 1, "registry": 1}
        row = {"revision_count": 1, "analysis_revision": 1}
        def stamp(_):
            return f"prep:{state['preparation']}:registry:{state['registry']}"
        def analyze(_, **kwargs):
            analysis = {"segments": [{"id": "s1", "text": "synthetic"}], "observed_versions": copy.deepcopy(state)}
            if change:
                state[change] += 1
            return analysis
        def archive(_, analysis):
            result = copy.deepcopy(analysis)
            if archive_change:
                state["preparation"] += 1
            return result
        build, _ = make_analysis_pipeline_adapters(
            archive_snapshot=archive, archive_source_stamp=stamp, group_analysis_for_row=analyze,
            call_ai_json=lambda *_: None, configured_ai_credentials=lambda *_: None,
            encode_transformer_texts=lambda *_: None, load_token_config=lambda: None,
        )
        return build, row, state

    def test_normal_snapshot_retains_one_coherent_read_only_source_version(self):
        build, row, state = self.builder()
        before = copy.deepcopy((row, state))
        snapshot = build(row)
        self.assertEqual(snapshot["input_hash"], "prep:1:registry:1")
        self.assertEqual(snapshot["analysis"]["observed_versions"], {"preparation": 1, "registry": 1})
        self.assertEqual((row, state), before)

    def test_preparation_change_during_analysis_rejects_old_result_with_new_hash(self):
        build, row, _ = self.builder(change="preparation")
        with self.assertRaises(AnalysisContractError) as caught:
            build(row)
        self.assertEqual(caught.exception.code, "revision_conflict")

    def test_registry_change_during_analysis_rejects_old_result_with_new_hash(self):
        build, row, _ = self.builder(change="registry")
        with self.assertRaises(AnalysisContractError) as caught:
            build(row)
        self.assertEqual(caught.exception.code, "revision_conflict")

    def test_archive_construction_is_inside_the_same_stamp_boundary(self):
        build, row, _ = self.builder(archive_change=True)
        with self.assertRaises(AnalysisContractError):
            build(row)


class SnapshotFingerprintIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = support.ContentApiTests("test_generated_result_persists_and_becomes_stale_on_edit")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.row = app.library_row("content")

    def test_normal_real_snapshot_leaves_the_temporary_database_unchanged(self):
        with app.database_connection() as connection:
            before = list(connection.iterdump())
        snapshot = app.build_analysis_pipeline_snapshot(self.row)
        self.assertEqual(snapshot["input_hash"], app.archive_source_stamp(self.row))
        with app.database_connection() as connection:
            self.assertEqual(list(connection.iterdump()), before)

    def changed_snapshot(self, target):
        original = app.group_analysis_for_row
        def change_after_analysis(*args, **kwargs):
            analysis = original(*args, **kwargs)
            with app.database_connection() as connection:
                if target == "preparation":
                    connection.execute("INSERT INTO transcript_preparations(item_id,revision,state_json) VALUES ('content',1,'{}') ON CONFLICT(item_id) DO UPDATE SET revision=revision+1")
                else:
                    connection.execute("UPDATE application_metadata SET value=CAST(value AS INTEGER)+1 WHERE key='speaker_registry_revision'")
            return analysis
        before_hash = app.archive_source_stamp(self.row)
        with patch.object(app, "group_analysis_for_row", side_effect=change_after_analysis), patch.object(app, "call_ai_json") as ai:
            with self.assertRaises(AnalysisContractError) as caught:
                app.build_analysis_pipeline_snapshot(self.row)
            self.assertEqual(caught.exception.code, "revision_conflict")
            ai.assert_not_called()
        self.assertNotEqual(before_hash, app.archive_source_stamp(self.row))
        with app.database_connection() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM analysis_pipeline_requests").fetchone()[0], 0)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM analysis_runs").fetchone()[0], 0)

    def test_http_start_returns_conflict_before_accepting_a_registry_race(self):
        original = app.group_analysis_for_row
        def change(*args, **kwargs):
            result = original(*args, **kwargs)
            with app.database_connection() as connection:
                connection.execute("UPDATE application_metadata SET value=CAST(value AS INTEGER)+1 WHERE key='speaker_registry_revision'")
            return result
        payload = {"request_id": "snapshot-registry-race-0001", "source_revision": self.row["revision_count"],
                   "analysis_revision": self.row["analysis_revision"], "definition_ids": [], "publication_targets": []}
        with patch.object(app, "group_analysis_for_row", side_effect=change):
            response = self.fixture.client.post(self.fixture.url + "/pipelines", json=payload)
        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(response.get_json()["reason_code"], "revision_conflict")
        with app.database_connection() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM analysis_pipeline_requests").fetchone()[0], 0)

    def test_preparation_revision_race_is_rejected_with_temporary_database(self):
        self.changed_snapshot("preparation")

    def test_registry_revision_race_is_rejected_with_temporary_database(self):
        self.changed_snapshot("registry")


if __name__ == "__main__":
    unittest.main()
