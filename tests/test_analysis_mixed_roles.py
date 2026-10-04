"""Per-turn role mixtures must not become a first-turn speaker assignment."""
import copy
import csv
import io
import itertools
import json
import unittest
from unittest.mock import patch

import app
import test_content_analysis as support
from gurumoji.analysis_pipeline import measure_segments
from test_analysis_role_provenance import role_definition


class MixedRoleTests(unittest.TestCase):
    def setUp(self):
        self.fixture = support.ContentApiTests("test_generated_result_persists_and_becomes_stale_on_edit")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.client, self.url = self.fixture.client, self.fixture.url
        manager = patch.object(app, "call_ai_json", side_effect=AssertionError("no external inference"))
        self.ai = manager.start()
        self.addCleanup(manager.stop)

    def install(self, order=("a1", "a2", "b"), *, roles=None, excluded=(), exclude_moderator=True):
        values = {"a1": {"speaker": "A", "start": 0, "end": 1},
                  "a2": {"speaker": "A", "start": 1, "end": 10},
                  "b": {"speaker": "B", "start": 10, "end": 20}}
        segments = [{"id": sid, "text": "synthetic role fixture", **values[sid]} for sid in order]
        roles = roles or {"a1": "moderator", "a2": "participant", "b": "participant"}
        with app.database_connection() as connection:
            connection.execute("""UPDATE library_items SET segments_json=?,speaker_names_json='{}',speaker_profiles_json='{}',
                analysis_annotations_json=?,analysis_config_json=?,revision_count=revision_count+1 WHERE id='content'""",
                (json.dumps(segments), json.dumps({sid: {"excluded": True} for sid in excluded}),
                 json.dumps({"group_by": "role", "exclude_moderator": exclude_moderator})))
        data = self.client.get(self.url).get_json()
        preparation = data["manual"]["preparation"]
        response = self.client.put("/api/library/content/preparation", json={
            "revision": preparation["revision"], "source_hash": preparation["source_hash"],
            "participant_count": 6, "metadata_sources": "synthetic roster fixture", "records": {sid: {"role": role} for sid, role in roles.items()},
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        before = app.library_row("content")["segments_json"]
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True)[:400])
        data = response.get_json()
        self.assertEqual(app.library_row("content")["segments_json"], before)
        self.assertEqual({row["id"]: row["role"] for row in data["segments"]}, roles)
        measured = {row["segment_id"]: row["recorded_role"] for row in measure_segments(data, [role_definition()])}
        self.assertEqual(measured, {sid: role for sid, role in roles.items() if sid not in excluded})
        self.ai.assert_not_called()
        return data

    def metrics(self, data):
        return {row["speaker"]: row for row in data["automatic"]["speaker_metrics"]}

    def test_mixture_preserves_global_amounts_but_suspends_role_dependent_aggregates(self):
        data = self.install()
        automatic, metrics = data["automatic"], self.metrics(data)
        self.assertEqual((metrics["A"]["speaking_seconds"], metrics["B"]["speaking_seconds"]), (10, 10))
        self.assertEqual((metrics["A"]["speaking_percent"], metrics["B"]["speaking_percent"]), (50, 50))
        self.assertEqual(metrics["A"]["role"], "mixed")
        self.assertEqual(metrics["A"]["observed_roles"], ["moderator", "participant"])
        self.assertEqual(metrics["A"]["role_status"], "mixed")
        self.assertEqual(metrics["B"]["role"], "participant")
        self.assertTrue(all(row["participant_percent"] is None for row in metrics.values()))
        for key in ("max_participant_percent", "gini", "hhi", "normalized_evenness", "participant_speaking_seconds"):
            self.assertIsNone(automatic["balance"][key])
        self.assertEqual(automatic["balance"]["unavailable_reason"], "mixed_roles")
        self.assertIsNone(automatic["overview"]["observed_participant_count"])
        self.assertEqual(automatic["overview"]["participant_count"], 6)
        self.assertIsNone(automatic["moderator"]["speaking_seconds"])
        self.assertIsNone(automatic["moderator"]["speaking_percent"])
        self.assertIsNone(automatic["moderator"]["question_candidates"])
        self.assertTrue(all(row["speaking_seconds"] is None and row["speaking_percent"] is None for row in automatic["groups"]))
        self.assertTrue(all(row["role_aggregation_status"] == "mixed" for row in automatic["groups"]))
        self.assertFalse(any(row["label"] in {"発話時間の集中候補", "発言機会の確認候補", "司会発話比率の確認"} for row in automatic["observations"]))

    def test_every_saved_order_has_same_role_and_population_aggregates(self):
        signatures = []
        for order in itertools.permutations(("a1", "a2", "b")):
            data = self.install(order)
            automatic = data["automatic"]
            signatures.append({"metrics": self.metrics(data), "balance": automatic["balance"],
                               "groups": sorted(automatic["groups"], key=lambda row: row["group"]),
                               "moderator": automatic["moderator"], "observations": automatic["observations"]})
        self.assertTrue(all(value == signatures[0] for value in signatures[1:]))

    def test_all_speaker_denominator_is_not_invalidated_by_role_mixture(self):
        data = self.install(exclude_moderator=False)
        automatic, metrics = data["automatic"], self.metrics(data)
        self.assertEqual((metrics["A"]["participant_percent"], metrics["B"]["participant_percent"]), (50, 50))
        self.assertEqual(automatic["balance"]["denominator"], "observed_speakers")
        self.assertEqual(automatic["balance"]["gini"], 0)
        self.assertEqual(automatic["balance"]["normalized_evenness"], 1)
        self.assertEqual(automatic["balance"]["hhi"], .5)
        self.assertIsNone(automatic["moderator"]["speaking_seconds"])
        self.assertTrue(all(row["speaking_seconds"] is None for row in automatic["groups"]))
        concentration = next(row for row in automatic["observations"] if row["label"] == "発話時間の集中候補")
        self.assertIn("観測話者内", concentration["message"])
        self.assertNotIn("参加者内", concentration["message"])

    def test_excluded_cause_and_uniform_roles_keep_existing_results(self):
        data = self.install(excluded=("a1",))
        metrics = self.metrics(data)
        self.assertEqual(metrics["A"]["role"], "participant")
        self.assertAlmostEqual(metrics["A"]["participant_percent"], 47.37, places=2)
        self.assertAlmostEqual(metrics["B"]["participant_percent"], 52.63, places=2)
        data = self.install(roles={"a1": "moderator", "a2": "moderator", "b": "participant"})
        self.assertEqual(self.metrics(data)["B"]["participant_percent"], 100)
        self.assertEqual(data["automatic"]["moderator"]["speaking_seconds"], 10)

    def test_exports_include_derived_mixture_and_original_v5_snapshot_stays_fixed(self):
        from gurumoji.services.analysis_pipeline_adapters import run_analysis_pipeline_method
        self.install()
        analysis = app.build_analysis_pipeline_snapshot(app.library_row("content"))["analysis"]
        result = run_analysis_pipeline_method("participation", {"analysis": analysis})
        self.assertEqual(analysis["algorithm_version"], "focus-group-local-7")
        self.assertEqual(result["datasets"]["speakers"]["rows"][0]["role_status"], "mixed")
        self.assertIn("役割混在", " ".join(row["text"] for row in result["method"]["summaries"]))
        response = self.client.get(self.url + "/export.csv?dataset=groups")
        self.assertEqual(response.status_code, 200)
        rows = list(csv.DictReader(io.StringIO(response.data.decode("utf-8-sig"))))
        self.assertTrue(all(row["speaking_seconds"] == "" and row["role_aggregation_status"] == "mixed" for row in rows))
        legacy = copy.deepcopy(analysis)
        legacy["algorithm_version"] = "focus-group-local-5"
        legacy["automatic"]["speaker_metrics"][0].update(role="moderator", participant_percent=0)
        legacy["automatic"]["speaker_metrics"][1]["participant_percent"] = 100
        for row in legacy["automatic"]["speaker_metrics"]:
            for key in ("role_status", "observed_roles"):
                row.pop(key, None)
        legacy["automatic"]["overview"].pop("mixed_role_speaker_count", None)
        before = copy.deepcopy(legacy)
        old = run_analysis_pipeline_method("participation", {"analysis": legacy})
        self.assertEqual(old["method"]["engine"]["version"], "focus-group-local-5")
        self.assertEqual(old["datasets"]["speakers"]["rows"][0]["role"], "moderator")
        self.assertEqual(old["datasets"]["speakers"]["rows"][1]["participant_percent"], 100)
        self.assertEqual(legacy, before)
