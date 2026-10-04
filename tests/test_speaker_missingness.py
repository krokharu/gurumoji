"""Synthetic API/export regressions for nullable participation timing metrics."""
import csv
import io
import json
import unittest
from unittest.mock import patch

import app
import test_content_analysis as support
from gurumoji.analysis_pipeline import AnalysisPipelineService


def turn(speaker, start=None, end=None, **extra):
    return {"speaker": speaker, "text": "synthetic timing", "start": start, "end": end, **extra}


class SpeakerMissingnessTests(unittest.TestCase):
    def setUp(self):
        self.fixture = support.ContentApiTests("test_generated_result_persists_and_becomes_stale_on_edit")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.client, self.url = self.fixture.client, self.fixture.url
        self.ai = patch.object(app, "call_ai_json", side_effect=AssertionError("external AI forbidden"))
        self.spy = self.ai.start()
        self.addCleanup(self.ai.stop)

    def install(self, turns, roles=None, *, group_by="role", exclude_moderator=True):
        segments = [{"id": f"t{i}", **value} for i, value in enumerate(turns)]
        profiles = {row["speaker"]: {"session_role": (roles or {}).get(row["speaker"], "participant"),
                                     "session_role_source": "explicit"} for row in segments}
        with app.database_connection() as connection:
            connection.execute("""UPDATE library_items SET segments_json=?,speaker_names_json='{}',
                speaker_profiles_json=?,analysis_annotations_json='{}',analysis_config_json=?,
                revision_count=revision_count+1 WHERE id='content'""",
                (json.dumps(segments), json.dumps(profiles), json.dumps({"group_by": group_by, "exclude_moderator": exclude_moderator})))
        self.original = app.library_row("content")["segments_json"]
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True)[:500])
        self.assertEqual(self.original, app.library_row("content")["segments_json"])
        self.spy.assert_not_called()
        return response.get_json()

    def metrics(self, data):
        return {row["speaker"]: row for row in data["automatic"]["speaker_metrics"]}

    def assert_no_ratio_observations(self, data):
        labels = {row["label"] for row in data["automatic"]["observations"]}
        self.assertFalse(labels & {"発話時間の集中候補", "発言機会の確認候補", "司会発話比率の確認"})

    def test_missing_and_partial_speakers_invalidate_complete_population_ratios(self):
        for turns in ([turn("A", 0, 10), turn("B", time_unknown=True)],
                      [turn("A", 0, 10), turn("B", 10, 12), turn("B", time_unknown=True)]):
            with self.subTest(turns=len(turns)):
                data = self.install(turns)
                metrics = self.metrics(data)
                self.assertEqual(metrics["B"]["speaking_seconds"], None if len(turns) == 2 else 2)
                self.assertEqual(metrics["B"]["missing_time_turn_count"], 1)
                for metric in metrics.values():
                    self.assertIsNone(metric["speaking_percent"])
                    self.assertIsNone(metric["participant_percent"])
                for key in ("gini", "hhi", "normalized_evenness", "max_participant_percent"):
                    self.assertIsNone(data["automatic"]["balance"][key])
                self.assertEqual(data["automatic"]["balance"]["metric_status"], "not_computable")
                self.assertEqual(data["automatic"]["balance"]["balance_missing_time_turn_count"], 1)
                self.assert_no_ratio_observations(data)

    def test_all_missing_group_moderator_overview_are_unknown_with_coverage(self):
        data = self.install([turn("A"), turn("B", time_unknown=True)], {"A": "participant", "B": "moderator"})
        for metric in self.metrics(data).values():
            self.assertIsNone(metric["speaking_seconds"])
            self.assertIsNone(metric["speaking_percent"])
        automatic = data["automatic"]
        for row in [*automatic["groups"], automatic["moderator"]]:
            self.assertIsNone(row["speaking_seconds"])
            self.assertIsNone(row["speaking_percent"])
            self.assertEqual(row["timed_turn_count"], 0)
            self.assertEqual(row["missing_time_turn_count"], 1)
        self.assertIsNone(automatic["overview"]["total_speaking_seconds"])
        self.assertEqual(automatic["overview"]["timed_turn_count"], 0)
        self.assertEqual(automatic["overview"]["missing_time_turn_count"], 2)
        self.assert_no_ratio_observations(data)

    def test_observer_missingness_does_not_invalidate_complete_participant_subset(self):
        data = self.install([turn("A", 0, 10), turn("B")], {"A": "participant", "B": "observer"})
        metrics = self.metrics(data)
        self.assertIsNone(metrics["A"]["speaking_percent"])
        self.assertEqual(metrics["A"]["participant_percent"], 100)
        self.assertEqual(data["automatic"]["balance"]["balance_missing_time_turn_count"], 0)
        self.assertEqual(data["automatic"]["balance"]["metric_status"], "computed")
        included = self.install([turn("A", 0, 10), turn("B")], {"A": "participant", "B": "observer"}, exclude_moderator=False)
        self.assertIsNone(self.metrics(included)["A"]["participant_percent"])

    def test_true_zero_numeric_string_and_complete_timing_keep_observed_values(self):
        data = self.install([turn("A", 0, 0), turn("B", "0", "10")])
        metrics = self.metrics(data)
        self.assertEqual((metrics["A"]["speaking_seconds"], metrics["A"]["speaking_percent"], metrics["A"]["participant_percent"]), (0, 0, 0))
        self.assertEqual(metrics["B"]["participant_percent"], 100)
        data = self.install([turn("A", 0, 0), turn("B", 1, 1)])
        for metric in self.metrics(data).values():
            self.assertEqual(metric["speaking_seconds"], 0)
            self.assertIsNone(metric["speaking_percent"])
            self.assertIsNone(metric["participant_percent"])
        self.assert_no_ratio_observations(data)

    def test_live_and_fixed_csv_keep_blanks_zeros_coverage_and_algorithm_version(self):
        data = self.install([turn("A", 0, 10), turn("B"), turn("Z", 1, 1)])
        self.assertEqual(data["algorithm_version"], "focus-group-local-7")
        response = self.client.get(self.url + "/export.csv?dataset=speakers")
        self.assertEqual(response.status_code, 200)
        live = {row["speaker"]: row for row in csv.DictReader(io.StringIO(response.data.decode("utf-8-sig")))}
        self.assertEqual(live["B"]["speaking_seconds"], "")
        self.assertEqual(live["A"]["participant_percent"], "")
        payload = self.fixture.payload("missing-timing-fixed-0001")
        payload.update(source_revision=data["item"]["revision_count"], analysis_revision=data["item"]["analysis_revision"],
                       mode="automatic", definition_ids=[], publication_targets=[])
        with patch.object(AnalysisPipelineService, "_schedule", return_value=None):
            response = self.client.post(self.url + "/pipelines", json=payload)
            self.assertEqual(response.status_code, 202, response.get_json())
            pipeline_id = response.get_json()["pipeline_id"]
            app.analysis_pipeline_service()._run(pipeline_id, "http://synthetic.invalid")
            state = app.analysis_pipeline_service().status("content", pipeline_id, ensure_running=False)
        self.assertEqual(state["status"], "completed", state)
        artifact = next(row for row in state["result_run"]["artifacts"] if row["name"] == "tables/speakers.csv")
        fixed = {row["speaker"]: row for row in csv.DictReader(io.StringIO(self.client.get(artifact["url"]).data.decode("utf-8-sig")))}
        for key in ("speaking_seconds", "speaking_percent", "participant_percent", "timed_turn_count", "missing_time_turn_count", "algorithm_version"):
            self.assertEqual({speaker: row[key] for speaker, row in fixed.items()}, {speaker: row[key] for speaker, row in live.items()})
        self.assertEqual(float(fixed["Z"]["speaking_seconds"]), 0)
        result_artifact = next(row for row in state["result_run"]["artifacts"] if row["name"] == "result.json")
        saved = self.client.get(result_artifact["url"]).get_json()
        self.assertEqual(saved["algorithms"]["automatic"], "focus-group-local-7")
        participation = next(method for method in saved["methods"] if method["method_id"] == "participation")
        self.assertEqual(participation["engine"]["version"], "focus-group-local-7")
        self.assertIn("時刻不明1発話", participation["summaries"][0]["text"])
        self.assertEqual(self.original, app.library_row("content")["segments_json"])
        self.spy.assert_not_called()

    def test_huge_integer_times_are_missing_without_mutating_source(self):
        from gurumoji.transcript_preparation import valid_time
        from gurumoji.services.group_analysis import analysis_segment_bounds
        for value in (10 ** 400, -(10 ** 400)):
            for field in ("start", "end"):
                segment = turn("A", 0, 10, **{})
                segment[field] = value
                with self.subTest(field=field, negative=value < 0):
                    self.assertFalse(valid_time(segment))
                    self.assertFalse(analysis_segment_bounds(segment)[2])
                    data = self.install([segment])
                    self.assertIsNone(self.metrics(data)["A"]["speaking_seconds"])
                    self.assertEqual(data["automatic"]["data_quality"]["invalid_time_segments"], 1)

    def test_report_and_interview_comparison_preserve_unknown_time(self):
        from collections import Counter
        from gurumoji.services.group_analysis_exports import focus_group_analysis_report_markdown
        from gurumoji.services.interview_comparison import build_interview_comparison
        data = self.install([turn("A")])
        report = focus_group_analysis_report_markdown(data)
        self.assertIn("時刻あり発話の合計 不明", report)
        self.assertIn("時刻不明 1 発話", report)
        result = build_interview_comparison(
            [{"id": "content", "source_name": "synthetic"}], allow_different_content=False,
            row_session_profile=lambda _row: {},
            interview_comparison_identity=lambda _profile: ("same", "same", "fixture"),
            group_analysis_for_row=lambda _row: data,
            text_mining_counter=lambda _segments, _stop: Counter(),
        )
        self.assertIsNone(result["interviews"][0]["total_speaking_seconds"])
        self.assertEqual(result["interviews"][0]["missing_time_turn_count"], 1)

    def test_pre_upgrade_snapshot_is_not_recalculated_or_relabelled(self):
        import copy
        from gurumoji.services.analysis_pipeline_adapters import run_analysis_pipeline_method
        self.install([turn("A")])
        legacy = copy.deepcopy(app.build_analysis_pipeline_snapshot(app.library_row("content"))["analysis"])
        legacy["algorithm_version"] = "focus-group-local-4"
        legacy["automatic"]["speaker_metrics"][0].update(speaking_seconds=0, speaking_percent=0, participant_percent=0)
        for key in ("timed_turn_count", "missing_time_turn_count"):
            legacy["automatic"]["overview"].pop(key, None)
        before = copy.deepcopy(legacy)
        value = run_analysis_pipeline_method("participation", {"analysis": legacy})
        self.assertEqual(value["datasets"]["speakers"]["rows"][0]["speaking_seconds"], 0)
        self.assertEqual(value["datasets"]["speakers"]["rows"][0]["algorithm_version"], "focus-group-local-4")
        self.assertEqual(value["method"]["engine"]["version"], "focus-group-local-4")
        self.assertEqual(value["method"]["summaries"], [])
        self.assertEqual(legacy, before)
