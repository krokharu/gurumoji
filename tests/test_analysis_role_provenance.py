"""Recorded-role measurement tests; synthetic sources, Flask and fixed artifacts only."""
import copy
import csv
import io
import json
from pathlib import Path
import subprocess
import time
import unittest
from unittest.mock import patch

import app
import test_content_analysis as support
from gurumoji.analysis_core import validate_definition
from gurumoji.analysis_pipeline import measure_segments
from gurumoji.services.library_rows import normalize_conversation_speaker_profiles


def role_definition(**extra):
    return validate_definition({
        "definition_id": "recorded_roles", "name": "登録された役割", "description": "未登録は欠測",
        "unit_of_analysis": "segment", "source_columns": ["role"], "output_column": "recorded_role",
        "data_type": "category", "measurement_level": "nominal", "measurement_rule": "identity",
        "method": "frequency", **extra,
    })


class RoleProvenanceUnitTests(unittest.TestCase):
    def test_normalization_records_defaults_and_preserves_provenance_on_round_trip(self):
        cases = [({}, "default"), ({"session_role": "participant"}, "legacy_unknown"),
                 ({"session_role": "moderator"}, "explicit")] + [({"session_role": "participant", "session_role_source": marker}, marker)
                            for marker in ("explicit", "registry", "default", "legacy_unknown")]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                original = copy.deepcopy(raw)
                normalized = normalize_conversation_speaker_profiles({"A": raw}, {"A"}, {})
                self.assertEqual(normalized["A"]["session_role_source"], expected)
                self.assertEqual(normalize_conversation_speaker_profiles(normalized, {"A"}, {}), normalized)
                self.assertEqual(raw, original)

    def test_markerless_legacy_registered_participant_is_ambiguous(self):
        rows = measure_segments({"segments": [{"id": "legacy", "role": "participant", "role_source": "registered"}]}, [role_definition()])
        self.assertIsNone(rows[0]["recorded_role"])
        self.assertEqual(rows[0]["recorded_role__missing_reason"], "role_provenance_unknown")

    def test_original_speaker_editor_marks_selection_and_preserves_round_trip_markers(self):
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(["node", str(root / "tests/test_role_provenance_ui.cjs")], cwd=root,
                                check=True, capture_output=True, text=True, timeout=30)
        self.assertEqual(len(json.loads(result.stdout)["passed"]), 3)

    def test_default_missing_and_unknown_provenance_are_not_observed_roles(self):
        segments = [{"id": "default", "role": "participant", "role_source": "default"},
                    {"id": "legacy", "role": "participant"},
                    {"id": "unknown", "role": "observer", "role_source": "unsupported"}]
        before = copy.deepcopy(segments)
        rows = measure_segments({"segments": segments}, [role_definition()])
        self.assertEqual([row["recorded_role"] for row in rows], [None, None, None])
        self.assertTrue(all(row["recorded_role__missing_reason"] for row in rows))
        self.assertEqual(segments, before)

    def test_registered_and_prepared_values_remain_valid_without_invented_confirmation(self):
        rows = measure_segments({"segments": [
            {"id": "explicit_default", "role": "participant", "role_source": "registered", "role_confirmed": False, "recorded_role": "participant", "recorded_role_source": "explicit"},
            {"id": "prepared", "role": "observer", "role_source": "preparation", "role_confirmed": False},
            {"id": "category", "role": "UNKNOWN", "role_source": "registered"},
        ]}, [role_definition()])
        self.assertEqual([row["recorded_role"] for row in rows], ["participant", "observer", "UNKNOWN"])
        self.assertEqual([row["recorded_role__missing_reason"] for row in rows], ["", "", ""])

    def test_nonempty_cannot_count_an_implicit_role_as_true(self):
        definition = role_definition(measurement_rule="nonempty", data_type="boolean")
        rows = measure_segments({"segments": [
            {"id": "default", "role": "participant", "role_source": "default"},
            {"id": "registered", "role": "participant", "role_source": "registered", "recorded_role": "participant", "recorded_role_source": "explicit"},
        ]}, [definition])
        self.assertEqual([row["recorded_role"] for row in rows], [None, True])

    def test_other_source_measurements_do_not_require_role_provenance(self):
        definition = role_definition(source_columns=["speaker"])
        rows = measure_segments({"segments": [{"id": "s1", "speaker": "C", "role": "participant", "role_source": "default"}]}, [definition])
        self.assertEqual(rows[0]["recorded_role"], "C")


class RoleProvenanceFlaskTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # These are the real UI's generated definition payloads, evaluated with
        # its existing synthetic Node harness. This does not launch a browser.
        root = Path(__file__).resolve().parents[1]
        result = subprocess.run(["node", str(root / "tests/test_analysis_measurement_ui.cjs")],
                                cwd=root, check=True, capture_output=True, text=True, timeout=30)
        cls.preset = json.loads(result.stdout)["presetPayloads"]["role_frequency"]
        role_result = subprocess.run(["node", str(root / "tests/test_role_confirmation_ui.cjs")],
                                     cwd=root, check=True, capture_output=True, text=True, timeout=30)
        cls.explicit_profile = json.loads(role_result.stdout)["explicitProfile"]
        if cls.preset["unit_of_analysis"] != "segment" or "各発話" not in cls.preset["description"]:
            raise AssertionError("Role preset must explicitly count utterances rather than people.")

    def setUp(self):
        self.fixture = support.ContentApiTests("test_generated_result_persists_and_becomes_stale_on_edit")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.client, self.url = self.fixture.client, self.fixture.url
        self.store = app.analysis_archive_store()

    def install_source(self, mixed=False):
        segments = [{"id": "unregistered", "speaker": "C", "text": "Synthetic unregistered role", "start": 0, "end": 1}]
        profiles, annotations = {}, {}
        if mixed:
            segments += [{"id": sid, "speaker": speaker, "text": "Synthetic recorded role", "start": i, "end": i + 1}
                         for i, (sid, speaker) in enumerate((("explicit", "E"), ("moderator", "M"), ("prepared", "P"),
                                                            ("registry", "G"), ("excluded", "X"), ("explicit_again", "E")), 1)]
            app.save_speaker_registry_records([{"id": "role_fixture_person", "pseudonym": "Synthetic registry person",
                                                "default_role": "observer", "active": True}], expected_revision=0)
            profiles = {"E": {"session_role": "participant", "session_role_source": "explicit"}, "M": {"session_role": "moderator"},
                        "G": {"global_speaker_id": "role_fixture_person"}, "X": {"session_role": "observer"}}
            annotations = {"excluded": {"excluded": True}}
        with app.database_connection() as connection:
            connection.execute("UPDATE library_items SET segments_json=?,speaker_names_json='{}',speaker_profiles_json=?,analysis_annotations_json=?,revision_count=revision_count+1 WHERE id='content'",
                               (json.dumps(segments), json.dumps(profiles), json.dumps(annotations)))
        if mixed:
            current = self.client.get(self.url).get_json()["manual"]["preparation"]
            response = self.client.put("/api/library/content/preparation", json={
                "revision": current["revision"], "source_hash": current["source_hash"],
                "records": {"prepared": {"role": "observer", "speaker_verified": False}},
            })
            self.assertEqual(response.status_code, 200, response.get_json())
        return self.client.get(self.url).get_json()

    def draft_trial(self, definition=None):
        definition = definition or self.preset
        base = self.url + "/definitions/" + definition["definition_id"]
        saved = self.client.put(base, json={**definition, "expected_revision": 0})
        self.assertEqual(saved.status_code, 200, saved.get_json())
        response = self.client.post(base + "/trials", json={"limit": 20})
        self.assertEqual(response.status_code, 200, response.get_json())
        return saved.get_json()["definition"], response.get_json()["trial"]

    def run_trial(self, saved, trial):
        adopted = self.client.put(self.url + "/definitions/" + saved["definition_id"], json={
            **saved, "status": "adopted", "expected_revision": saved["revision"], "expected_trial": trial,
        })
        self.assertEqual(adopted.status_code, 200, adopted.get_json())
        item = self.client.get(self.url).get_json()["item"]
        started = self.client.post(self.url + "/pipelines", json={
            "request_id": "role-provenance-pipeline-request-0001", "source_revision": item["revision_count"],
            "analysis_revision": item["analysis_revision"], "mode": "manual", "definition_ids": [saved["definition_id"]],
            "expected_definition_versions": {saved["definition_id"]: adopted.get_json()["definition"]["version"]},
            "expected_input_hash": trial["input_hash"], "publication_targets": [],
        })
        self.assertEqual(started.status_code, 202, started.get_json())
        pipeline_id = started.get_json()["pipeline_id"]
        for _ in range(300):
            state = self.client.get(self.url + "/pipelines/" + pipeline_id).get_json()
            if state["status"] in {"completed", "waiting", "failed"}:
                self.assertEqual(state["status"], "completed", state)
                return state["result_run"]
            time.sleep(.02)
        self.fail(str(state))

    def artifact_bytes(self, run_id):
        return {row["name"]: self.store.read_artifact(row["id"])[1] for row in self.store.artifacts(run_id)}

    def test_real_role_preset_reports_unregistered_role_missing_without_changing_analysis_defaults(self):
        current = self.install_source()
        self.assertEqual((current["segments"][0]["role"], current["segments"][0]["role_source"]), ("participant", "default"))
        before = app.build_analysis_pipeline_snapshot(app.library_row("content"))["archive_snapshot"]
        with patch.object(app, "call_ai_json") as ai:
            saved, trial = self.draft_trial()
            self.assertEqual((trial["valid_count"], trial["missing_count"]), (0, 1))
            self.assertIsNone(trial["rows"][0][saved["output_column"]])
            run = self.run_trial(saved, trial)
            ai.assert_not_called()
        artifacts = self.artifact_bytes(run["id"])
        result = json.loads(artifacts["result.json"])
        method = next(value for value in result["methods"] if value["method_id"] == "descriptive_statistics")
        self.assertEqual(method["summaries"][0]["text"], "有効N=0、度数={}")
        self.assertEqual(method["details"]["role_source_policy"]["value_field"], "recorded_role")
        self.assertEqual(method["details"]["role_source_policy"]["ambiguous_legacy_participant"], "missing")
        row = list(csv.DictReader(io.StringIO(artifacts["tables/measurements.csv"].decode("utf-8-sig"))))[0]
        self.assertEqual(row[saved["output_column"]], "")
        self.assertTrue(row[saved["output_column"] + "__missing_reason"])
        after = app.build_analysis_pipeline_snapshot(app.library_row("content"))["archive_snapshot"]
        self.assertEqual(before, after)
        self.assertEqual(after["segments"][0]["role"], "participant")

    def test_mixed_registered_prepared_and_default_roles_agree_in_trial_full_summary_and_csv(self):
        current = self.install_source(mixed=True)
        provenance = {row["id"]: (row["role"], row["role_source"]) for row in current["segments"]}
        self.assertEqual(provenance["registry"], ("participant", "registered"))  # Automatic behavior is unchanged.
        registry_row = next(row for row in current["segments"] if row["id"] == "registry")
        self.assertEqual((registry_row["recorded_role"], registry_row["recorded_role_source"]), ("observer", "registry"))
        self.assertEqual(provenance["prepared"], ("observer", "preparation"))
        source_before = {key: app.library_row("content")[key] for key in ("segments_json", "speaker_profiles_json", "original_segments_json")}
        snapshot = app.build_analysis_pipeline_snapshot(app.library_row("content"))
        old = self.store.save(item_id="content", kind="text_analysis", snapshot=snapshot["archive_snapshot"],
                              result={"parameters": {"fixture": "legacy-role-result"}, "methods": []},
                              datasets={"measurements": (["segment_id", "recorded_role"], [{"segment_id": "unregistered", "recorded_role": "participant"}])},
                              request_id="legacy-role-result-0001", input_fingerprint=snapshot["input_hash"],
                              source_revision=current["item"]["revision_count"], analysis_revision=current["item"]["analysis_revision"], publish=False)
        old_bytes = self.artifact_bytes(old["id"])
        with patch.object(app, "call_ai_json") as ai:
            saved, trial = self.draft_trial()
            self.assertEqual((trial["total_count"], trial["excluded_count"], trial["sample_size"], trial["valid_count"], trial["missing_count"]), (7, 1, 6, 5, 1))
            run = self.run_trial(saved, trial)
            ai.assert_not_called()
        artifacts = self.artifact_bytes(run["id"])
        result = json.loads(artifacts["result.json"])
        method = next(value for value in result["methods"] if value["method_id"] == "descriptive_statistics")
        self.assertIn('有効N=5、度数={"moderator": 1, "observer": 2, "participant": 2}', method["summaries"][0]["text"])
        csv_rows = list(csv.DictReader(io.StringIO(artifacts["tables/measurements.csv"].decode("utf-8-sig"))))
        column = saved["output_column"]
        self.assertEqual([(row["segment_id"], row[column], row[column + "__missing_reason"]) for row in csv_rows],
                         [(row["segment_id"], "" if row[column] is None else row[column], row[column + "__missing_reason"]) for row in trial["rows"]])
        self.assertEqual(result["parameters"]["definitions"][0], result["parameters"]["binding"]["definition_snapshots"][saved["definition_id"]]["payload"])
        self.assertEqual(self.artifact_bytes(old["id"]), old_bytes)
        self.assertEqual({key: app.library_row("content")[key] for key in source_before}, source_before)
        self.assertEqual(app.build_analysis_pipeline_snapshot(app.library_row("content"))["archive_snapshot"], snapshot["archive_snapshot"])

    def test_new_automatic_profiles_record_inserted_defaults_without_counting_them(self):
        # The fixture's ordinary upsert path inserts participant profiles.
        profiles = json.loads(app.library_row("content")["speaker_profiles_json"])
        self.assertTrue(profiles)
        self.assertTrue(all(value["session_role_source"] == "default" for value in profiles.values()))
        before = app.library_row("content")["speaker_profiles_json"]
        current = self.client.get(self.url).get_json()
        self.assertTrue(all(row["recorded_role"] is None for row in current["segments"]))
        self.assertEqual(app.library_row("content")["speaker_profiles_json"], before)

    def test_legacy_round_trip_stays_ambiguous_until_explicit_override_and_preparation_wins(self):
        self.install_source()
        legacy = {"C": {"session_role": "participant"}}
        with app.database_connection() as connection:
            connection.execute("UPDATE library_items SET speaker_profiles_json=? WHERE id='content'", (json.dumps(legacy),))
        stored_before = app.library_row("content")["speaker_profiles_json"]
        current = self.client.get(self.url).get_json()
        self.assertIsNone(current["segments"][0]["recorded_role"])
        self.assertEqual(current["segments"][0]["recorded_role_source"], "legacy_unknown")
        self.assertEqual(app.library_row("content")["speaker_profiles_json"], stored_before)

        def save_profiles(profiles):
            row = app.library_row("content")
            response = self.client.put("/api/library/content", json={"revision_count": row["revision_count"],
                "segments": json.loads(row["segments_json"]), "speaker_names": json.loads(row["speaker_names_json"]),
                "speaker_profiles": profiles})
            self.assertEqual(response.status_code, 200, response.get_json())
            return self.client.get(self.url).get_json()

        # Opening and saving the normalized editor payload cannot certify legacy defaults.
        loaded = self.client.get("/api/library/content")
        self.assertEqual(loaded.status_code, 200, loaded.get_json())
        normalized = loaded.get_json()["speaker_profiles"]
        self.assertEqual(normalized["C"]["session_role_source"], "legacy_unknown")
        current = save_profiles(normalized)
        self.assertIsNone(current["segments"][0]["recorded_role"])
        # Use the actual same-value button handler's generated role payload.
        for field in ("session_role", "session_role_source"):
            normalized["C"][field] = self.explicit_profile[field]
        current = save_profiles(normalized)
        self.assertEqual((current["segments"][0]["recorded_role"], current["segments"][0]["recorded_role_source"]), ("participant", "explicit"))
        self.assertEqual(json.loads(app.library_row("content")["speaker_profiles_json"])["C"]["session_role_source"], "explicit")
        preparation = current["manual"]["preparation"]
        response = self.client.put("/api/library/content/preparation", json={"revision": preparation["revision"],
            "source_hash": preparation["source_hash"], "records": {"unregistered": {"role": "moderator", "speaker_verified": False}}})
        self.assertEqual(response.status_code, 200, response.get_json())
        current = self.client.get(self.url).get_json()
        self.assertEqual((current["segments"][0]["recorded_role"], current["segments"][0]["recorded_role_source"]), ("moderator", "preparation"))

    def test_explicit_participant_overrides_registry_observer_without_changing_registry(self):
        self.install_source(mixed=True)
        with app.database_connection() as connection:
            profiles = json.loads(connection.execute("SELECT speaker_profiles_json FROM library_items WHERE id='content'").fetchone()[0])
            profiles["G"].update(session_role="participant", session_role_source="explicit")
            connection.execute("UPDATE library_items SET speaker_profiles_json=? WHERE id='content'", (json.dumps(profiles),))
        current = self.client.get(self.url).get_json()
        row = next(value for value in current["segments"] if value["id"] == "registry")
        self.assertEqual((row["role"], row["recorded_role"], row["recorded_role_source"]), ("participant", "participant", "explicit"))
        self.assertEqual(app.list_speaker_registry()[0]["default_role"], "observer")

    def test_nonempty_role_uses_the_same_missingness_boundary_through_flask(self):
        self.install_source(mixed=True)
        value = {**self.preset, "measurement_rule": "nonempty", "data_type": "boolean"}
        saved, trial = self.draft_trial(value)
        self.assertEqual((trial["valid_count"], trial["missing_count"]), (5, 1))
        self.assertEqual(trial["values"], [True] * 5)
        run = self.run_trial(saved, trial)
        result = json.loads(self.artifact_bytes(run["id"])["result.json"])
        method = next(value for value in result["methods"] if value["method_id"] == "descriptive_statistics")
        self.assertEqual(method["summaries"][0]["text"], '有効N=5、度数={"True": 5}')


if __name__ == "__main__":
    unittest.main()
