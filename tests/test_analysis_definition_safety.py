"""Synthetic fixed-definition/CAS regression tests; no models or real Vaults."""
import copy
from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from gurumoji.analysis_core import AnalysisContractError, fingerprint, validate_definition
from gurumoji.analysis_pipeline import AnalysisPipelineService, initialize_pipeline_store, measure_segments, _manual_method


def definition(**extra):
    return {
        "definition_id": "text_size", "name": "文字数", "description": "発話の文字数",
        "unit_of_analysis": "segment", "source_columns": ["text"], "output_column": "measured_size",
        "data_type": "number", "measurement_level": "ratio", "measurement_rule": "text_length",
        "method": "descriptive", "status": "adopted", **extra,
    }


class DefinitionSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "synthetic.sqlite"
        with self.connect() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            initialize_pipeline_store(connection)
        self.item = {"id": "synthetic", "revision_count": 1, "analysis_revision": 1}
        segments = [{"id": "e1", "text": "abc", "speaker": "A", "speaker_name": "A",
                     "duration": 60, "start": 0, "end": 60, "valid_time": True}]
        self.snapshot = {"analysis": {"segments": segments}, "archive_snapshot": {"segments": segments},
                         "input_hash": "sha256:synthetic", "source_revision": 1, "analysis_revision": 1}
        self.saved = []
        self.service = AnalysisPipelineService(
            connect=self.connect, find_item=lambda _: self.item,
            source_fingerprint=lambda _: self.snapshot["input_hash"],
            snapshot_builder=lambda _: copy.deepcopy(self.snapshot),
            method_runner=lambda method, _: {"method": {"method_id": method}, "datasets": {}},
            save_result=self.save_result, publish_result=lambda _: {}, publication_outcomes=lambda _: {},
            public_run=lambda _: {}, runtime_key=self.temp.name,
        )
        self.service._schedule = lambda *_: None

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.db, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def save_result(self, **kwargs):
        self.saved.append(copy.deepcopy(kwargs))
        return {"id": "synthetic-result", "status": "completed", "fingerprint": fingerprint(kwargs["result"])}

    def save(self, **extra):
        return self.service.save_definition("synthetic", "text_size", definition(**extra))

    def payload(self, **extra):
        return {"request_id": "definition-safety-request-0001", "source_revision": 1, "analysis_revision": 1,
                "mode": "manual", "definition_ids": ["text_size"], "publication_targets": [], **extra}

    def start(self, **extra):
        body, status = self.service.start("synthetic", self.payload(**extra), app_url="http://synthetic.invalid")
        self.assertEqual(status, 202)
        return body["pipeline_id"]

    def test_accepted_binding_uses_v1_after_mutable_definition_becomes_v2(self):
        self.save()
        pipeline_id = self.start()
        self.save(expected_revision=1, source_columns=["duration"], measurement_rule="duration")
        self.service._run(pipeline_id, "http://synthetic.invalid")
        state = self.service.status("synthetic", pipeline_id, ensure_running=False)
        self.assertEqual(state["status"], "completed", state)
        package = self.saved[0]
        self.assertEqual(package["datasets"]["measurements"][1][0]["measured_size"], 3)
        parameters = package["result"]["parameters"]
        self.assertEqual(parameters["definitions"][0]["version"], 1)
        self.assertEqual(parameters["binding"]["resolved"][0]["definition_version"], 1)
        self.assertEqual(parameters["definitions"][0], parameters["binding"]["definition_snapshots"]["text_size"]["payload"])

    def test_definition_changed_between_preview_and_acceptance_is_rejected(self):
        self.save()
        original = self.service.preview
        def preview(*args):
            result = original(*args)
            self.save(expected_revision=1, source_columns=["duration"], measurement_rule="duration")
            return result
        with patch.object(self.service, "preview", side_effect=preview):
            with self.assertRaises(AnalysisContractError) as caught:
                self.start()
        self.assertEqual(caught.exception.code, "revision_conflict")
        with self.connect() as connection:
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM analysis_pipeline_requests").fetchone()[0], 0)

    def test_status_aba_between_preview_and_acceptance_is_rejected(self):
        self.save()
        original = self.service.preview
        def preview(*args):
            result = original(*args)
            self.save(expected_revision=1, status="draft")
            current = self.save(expected_revision=2)
            self.assertEqual((current["version"], current["revision"]), (1, 3))
            return result
        with patch.object(self.service, "preview", side_effect=preview):
            with self.assertRaises(AnalysisContractError):
                self.start()

    def test_reusing_request_id_for_another_definition_version_is_conflict(self):
        self.save()
        self.start()
        self.save(expected_revision=1, source_columns=["duration"], measurement_rule="duration")
        with self.assertRaises(AnalysisContractError) as caught:
            self.start()
        self.assertEqual(caught.exception.code, "request_conflict")

    def test_get_trial_confirm_adopt_preserves_content_version_and_increments_revision(self):
        saved = self.save(status="draft")
        trial = self.service.trial_definition("synthetic", "text_size")
        self.assertEqual(self.service.get_definition("synthetic", "text_size")["last_trial"], trial)
        adopted = self.save(expected_revision=saved["revision"], expected_trial=trial)
        self.assertEqual((adopted["version"], adopted["revision"], adopted["status"]), (1, 2, "adopted"))
        self.start(expected_definition_versions={"text_size": 1}, expected_input_hash=trial["input_hash"])
        self.assertEqual(trial["rows"][0]["segment_id"], "e1")

    def test_newer_trial_invalidates_older_trial_token(self):
        self.save(status="draft")
        old = self.service.trial_definition("synthetic", "text_size")
        self.service.trial_definition("synthetic", "text_size")
        with self.assertRaises(AnalysisContractError) as caught:
            self.save(expected_revision=1, expected_trial=old)
        self.assertEqual(caught.exception.code, "trial_conflict")

    def test_changed_input_rejects_trial_adoption_and_start_expected_hash(self):
        self.save(status="draft")
        trial = self.service.trial_definition("synthetic", "text_size")
        self.snapshot["input_hash"] = "sha256:changed"
        with self.assertRaises(AnalysisContractError):
            self.save(expected_revision=1, expected_trial=trial)
        self.save(expected_revision=1)
        with self.assertRaises(AnalysisContractError):
            self.start(expected_input_hash=trial["input_hash"])

    def test_trial_race_cannot_attach_old_measurements_to_new_definition(self):
        self.save(status="draft")
        original = measure_segments
        def measure(*args, **kwargs):
            rows = original(*args, **kwargs)
            self.save(expected_revision=1, status="draft", source_columns=["duration"], measurement_rule="duration")
            return rows
        with patch("gurumoji.analysis_pipeline.measure_segments", side_effect=measure):
            with self.assertRaises(AnalysisContractError) as caught:
                self.service.trial_definition("synthetic", "text_size")
        self.assertEqual(caught.exception.code, "trial_conflict")
        self.assertEqual(self.service.get_definition("synthetic", "text_size")["last_trial"], {})

    def test_edit_clears_trial_and_does_not_persist_transport_metadata(self):
        self.save(status="draft")
        self.service.trial_definition("synthetic", "text_size")
        self.save(expected_revision=1, status="draft", description="changed")
        current = self.service.get_definition("synthetic", "text_size")
        self.assertEqual(current["last_trial"], {})
        with self.connect() as connection:
            payload = json.loads(connection.execute("SELECT payload_json FROM analysis_definitions").fetchone()[0])
        self.assertNotIn("expected_revision", payload)
        self.assertNotIn("status", payload)

    def test_invalid_stored_version_never_defaults_to_one(self):
        self.save()
        for version in (None, True, False, 1.0, "1", 0, -1):
            with self.subTest(version=version):
                value = definition(version=version)
                if version is None:
                    value.pop("version")
                with self.connect() as connection:
                    connection.execute("UPDATE analysis_definitions SET payload_json=?", (json.dumps(value),))
                with self.assertRaises(AnalysisContractError):
                    self.start()

    def test_wrong_stored_definition_id_and_retired_status_are_rejected(self):
        self.save()
        with self.connect() as connection:
            value = definition(definition_id="wrong_id", version=1)
            connection.execute("UPDATE analysis_definitions SET payload_json=?", (json.dumps(value),))
        with self.assertRaises(AnalysisContractError):
            self.start()
        with self.connect() as connection:
            connection.execute("UPDATE analysis_definitions SET payload_json=?,status='retired'", (json.dumps(definition(version=1)),))
        with self.assertRaises(AnalysisContractError):
            self.start()

    def test_boolean_revision_and_expected_versions_are_rejected(self):
        self.save()
        with self.assertRaises(AnalysisContractError):
            self.save(expected_revision=True)
        for versions in ({"text_size": True}, {"text_size": 1.0}, {"text_size": "1"}, {}, {"other_id": 1}):
            with self.subTest(versions=versions), self.assertRaises(AnalysisContractError):
                self.start(expected_definition_versions=versions)

    def test_legacy_manual_binding_stops_without_rewriting_artifacts(self):
        self.save()
        pipeline_id = self.start()
        with self.connect() as connection:
            row = connection.execute("SELECT binding_json FROM analysis_pipeline_requests").fetchone()
            binding = json.loads(row[0]); binding.pop("definition_snapshots")
            connection.execute("UPDATE analysis_pipeline_requests SET binding_json=?", (json.dumps(binding),))
        with self.assertRaises(AnalysisContractError) as caught:
            self.service._run(pipeline_id, "http://synthetic.invalid")
        self.assertEqual(caught.exception.code, "definition_snapshot_missing")
        self.assertEqual(self.saved, [])

    def test_legacy_automatic_binding_still_runs(self):
        pipeline_id = self.start(definition_ids=[], mode="automatic")
        with self.connect() as connection:
            binding = json.loads(connection.execute("SELECT binding_json FROM analysis_pipeline_requests").fetchone()[0])
            binding.pop("definition_snapshots")
            connection.execute("UPDATE analysis_pipeline_requests SET binding_json=?", (json.dumps(binding),))
        self.service._run(pipeline_id, "http://synthetic.invalid")
        self.assertEqual(len(self.saved), 1)

    def test_tampered_binding_or_input_stops_before_any_method(self):
        self.save()
        pipeline_id = self.start()
        with self.connect() as connection:
            binding = json.loads(connection.execute("SELECT binding_json FROM analysis_pipeline_requests").fetchone()[0])
            binding["definition_snapshots"]["text_size"]["payload"]["measurement_rule"] = "duration"
            connection.execute("UPDATE analysis_pipeline_requests SET binding_json=?", (json.dumps(binding),))
        with self.assertRaises(AnalysisContractError):
            self.service._run(pipeline_id, "http://synthetic.invalid")
        self.assertEqual(self.saved, [])

    def test_reserved_and_generated_output_columns_are_rejected(self):
        for column in ("segment_id", "speaker", "speaker_name", "score__missing_reason", "score__missing_reason_extra"):
            with self.subTest(column=column), self.assertRaises(AnalysisContractError):
                self.save(output_column=column)

    def test_unsupported_behavioral_contracts_are_explicitly_rejected(self):
        for field, value in (("unit_of_analysis", "speaker"), ("aggregation", "sum"),
                             ("denominator", "confirmed_participants"), ("missing_rule", "zero_impute")):
            with self.subTest(field=field), self.assertRaises(AnalysisContractError) as caught:
                self.save(**{field: value})
            self.assertEqual(caught.exception.code, "definition_behavior_unsupported")

    def test_boolean_rules_cannot_be_declared_numeric(self):
        for rule in ("nonempty", "boolean_true"):
            with self.subTest(rule=rule), self.assertRaises(AnalysisContractError):
                self.save(measurement_rule=rule)

    def test_identity_boolean_rejects_arbitrary_strings_and_keeps_true_false(self):
        value = validate_definition(definition(measurement_rule="identity", data_type="boolean", measurement_level="nominal", method="frequency"))
        rows = measure_segments({"segments": [{"text": item} for item in ("true", "false", None, True, False)]}, [value])
        self.assertEqual([row["measured_size"] for row in rows], [None, None, None, True, False])
        method, _ = _manual_method([value], rows)
        self.assertIn("有効N=2", method["summaries"][0]["text"])

    def test_numeric_identity_trial_and_full_counts_match_summary(self):
        self.save(measurement_rule="identity")
        self.snapshot["analysis"]["segments"] = [{"id": str(index), "text": value} for index, value in enumerate(("3", "bad", "false", 0, 3.5, True))]
        trial = self.service.trial_definition("synthetic", "text_size")
        self.assertEqual((trial["valid_count"], trial["missing_count"]), (2, 4))
        pipeline_id = self.start()
        self.service._run(pipeline_id, "http://synthetic.invalid")
        method = next(value for value in self.saved[0]["result"]["methods"] if value["method_id"] == "descriptive_statistics")
        self.assertIn("有効N=2", method["summaries"][0]["text"])

    def test_category_identity_keeps_json_scalars_but_rejects_objects(self):
        value = validate_definition(definition(measurement_rule="identity", data_type="category", measurement_level="nominal", method="frequency"))
        source = ["", "UNKNOWN", 0, 2.5, False, None, [], {}, float("inf")]
        rows = measure_segments({"segments": [{"text": item} for item in source]}, [value])
        self.assertEqual([row["measured_size"] for row in rows], ["", "UNKNOWN", 0, 2.5, False, None, None, None, None])
        self.assertTrue(all(row["measured_size__missing_reason"] for row in rows[5:]))

    def test_text_rules_keep_real_empty_text_but_reject_absent_or_object_source(self):
        for rule, dtype, level, method in (("text_length", "number", "ratio", "descriptive"), ("nonempty", "boolean", "nominal", "frequency")):
            value = validate_definition(definition(measurement_rule=rule, data_type=dtype, measurement_level=level, method=method))
            rows = measure_segments({"segments": [{"text": item} for item in ("", None, ["x"], "abc")]}, [value])
            self.assertEqual([row["measured_size"] for row in rows], [0 if rule == "text_length" else False, None, None, 3 if rule == "text_length" else True])

    def test_boolean_true_has_no_string_truthiness_coercion(self):
        value = validate_definition(definition(source_columns=["question_candidate"], measurement_rule="boolean_true", data_type="boolean", measurement_level="nominal", method="frequency"))
        rows = measure_segments({"segments": [{"question_candidate": item} for item in (True, False, "false", 0, None)]}, [value])
        self.assertEqual([row["measured_size"] for row in rows], [True, False, None, None, None])

    def test_numeric_identity_never_counts_boolean_or_nonfinite_as_valid(self):
        value = validate_definition(definition(source_columns=["question_candidate"], measurement_rule="identity"))
        for source in (True, False, None, "3", float("nan"), float("inf")):
            with self.subTest(source=source):
                row = measure_segments({"segments": [{"id": "e1", "question_candidate": source}]}, [value])[0]
                self.assertIsNone(row["measured_size"])
                self.assertEqual(row["measured_size__missing_reason"], "invalid_source_value")

    def test_multiple_distinct_sources_are_rejected_but_duplicates_normalize(self):
        for sources in (["text", "duration"], ["duration", "text"]):
            with self.subTest(sources=sources), self.assertRaises(AnalysisContractError):
                self.save(source_columns=sources)
        saved = self.save(source_columns=["text", "text"])
        self.assertEqual(saved["source_columns"], ["text"])

    def test_legacy_source_named_output_remains_valid(self):
        value = self.save(output_column="duration")
        self.assertEqual(value["output_column"], "duration")
        self.start()

    def test_unsupported_legacy_definition_can_be_read_and_explicitly_repaired(self):
        self.save()
        with self.connect() as connection:
            connection.execute("UPDATE analysis_definitions SET payload_json=?", (json.dumps(definition(version=1, source_columns=["text", "duration"])),))
        current = self.service.get_definition("synthetic", "text_size")
        self.assertEqual(current["validation_error"]["reason_code"], "source_columns_unsupported")
        with self.assertRaises(AnalysisContractError):
            self.start()
        repaired = self.save(expected_revision=1)
        self.assertEqual((repaired["version"], repaired["revision"]), (2, 2))

    def test_identity_duration_preserves_unknown_time_and_real_zero(self):
        value = validate_definition(definition(source_columns=["duration"], measurement_rule="identity"))
        rows = measure_segments({"segments": [
            {"id": "known", "start": 0, "end": 10, "duration": 10},
            {"id": "unknown", "start": 0, "end": 0, "duration": 0, "time_unknown": True},
            {"id": "zero", "start": 0, "end": 0, "duration": 0},
        ]}, [value])
        self.assertEqual([row["measured_size"] for row in rows], [10.0, None, 0.0])
        self.assertEqual(rows[1]["measured_size__missing_reason"], "invalid_source_value")

    def test_duplicate_definition_output_columns_stop_before_pipeline(self):
        self.save()
        self.service.save_definition("synthetic", "other_size", definition(definition_id="other_size"))
        with self.assertRaises(AnalysisContractError) as caught:
            self.start(definition_ids=["text_size", "other_size"])
        self.assertEqual(caught.exception.code, "output_column_conflict")
        with self.assertRaises(AnalysisContractError):
            self.start(definition_ids=["text_size", "text_size"])

    def test_measurement_boundary_also_rejects_colliding_legacy_payloads(self):
        values = [validate_definition(definition()), validate_definition(definition(definition_id="other_size"))]
        with self.assertRaises(AnalysisContractError):
            measure_segments(self.snapshot["analysis"], values)


if __name__ == "__main__":
    unittest.main()
