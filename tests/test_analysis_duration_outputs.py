"""Remaining duration outputs distinguish unknown time, true zero and empty sets."""
import copy
import csv
import io
import json
import unittest
from unittest.mock import patch

import app
import test_content_analysis as support
from gurumoji.services.group_analysis import normalize_analysis_config
from gurumoji.services.group_analysis_exports import analysis_csv_rows


def turn(sid, start=None, end=None, **extra):
    return {"id": sid, "speaker": "A", "text": "synthetic duration",
            "start": start, "end": end, "emotions": {"aist": {"label": "neu", "label_ja": "平常"}}, **extra}


class DurationOutputTests(unittest.TestCase):
    def setUp(self):
        self.fixture = support.ContentApiTests("test_generated_result_persists_and_becomes_stale_on_edit")
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.client, self.url = self.fixture.client, self.fixture.url
        manager = patch.object(app, "call_ai_json", side_effect=AssertionError("no external inference"))
        self.ai = manager.start()
        self.addCleanup(manager.stop)

    def install(self, segments, *, excluded=()):
        config = normalize_analysis_config({"codebook": [{"id": "c", "label": "Synthetic code"}]})
        annotations = {row["id"]: {"codes": ["c"], "excluded": row["id"] in excluded} for row in segments}
        with app.database_connection() as connection:
            connection.execute("""UPDATE library_items SET segments_json=?,speaker_names_json='{}',speaker_profiles_json='{}',
                analysis_config_json=?,analysis_annotations_json=?,revision_count=revision_count+1 WHERE id='content'""",
                (json.dumps(segments), json.dumps(config), json.dumps(annotations)))
        self.before = app.library_row("content")["segments_json"]
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.before, app.library_row("content")["segments_json"])
        return response.get_json()

    def test_timeline_span_emotions_and_codes_share_observed_time_coverage(self):
        cases = [
            ("missing", [turn("u", time_unknown=True)], None, None, 0, 1),
            ("partial", [turn("k", 0, 10), turn("u", time_unknown=True)], 10, 10, 1, 1),
            ("zero", [turn("z", 0, 0)], 0, 0, 1, 0),
            ("zero_at_ten", [turn("z", 10, 10)], 10, 0, 1, 0),
            ("empty", [], None, 0, 0, 0),
            ("positive", [turn("k", 0, 10)], 10, 10, 1, 0),
        ]
        for name, segments, span, seconds, timed, missing in cases:
            with self.subTest(name=name):
                data = self.install(segments)
                automatic = data["automatic"]
                self.assertEqual(automatic["overview"]["session_duration"], span)
                self.assertEqual(automatic["overview"]["session_timed_turn_count"], timed)
                self.assertEqual(automatic["overview"]["session_missing_time_turn_count"], missing)
                if not timed:
                    self.assertEqual(automatic["time_bins"], [])
                else:
                    self.assertEqual(sum(row["turn_count"] for row in automatic["time_bins"]), timed)
                    self.assertEqual(automatic["time_bins"][-1]["end"], span)
                    self.assertEqual(sum(row["speaking_seconds"] for row in automatic["time_bins"]), seconds)
                code = data["manual"]["code_metrics"][0]
                self.assertEqual((code["segment_count"], code["timed_turn_count"], code["missing_time_turn_count"]), (len(segments), timed, missing))
                self.assertEqual(code["speaking_seconds"], seconds)
                if segments:
                    emotion = automatic["emotions"][0]
                    self.assertEqual((emotion["count"], emotion["timed_turn_count"], emotion["missing_time_turn_count"]), (len(segments), timed, missing))
                    self.assertEqual(emotion["seconds"], seconds)
                else:
                    self.assertEqual(automatic["emotions"], [])
                self.assertEqual(self.before, app.library_row("content")["segments_json"])
        self.ai.assert_not_called()

    def test_source_span_coverage_remains_separate_from_included_bins(self):
        data = self.install([turn("excluded_known", 0, 10), turn("included_missing")], excluded=("excluded_known",))
        automatic = data["automatic"]
        overview = automatic["overview"]
        self.assertEqual(overview["session_duration"], 10)
        self.assertEqual((overview["session_timed_turn_count"], overview["session_missing_time_turn_count"]), (1, 1))
        self.assertEqual((overview["timed_turn_count"], overview["missing_time_turn_count"]), (0, 1))
        self.assertEqual(automatic["time_bins"], [])
        self.assertIsNone(automatic["emotions"][0]["seconds"])
        self.assertIsNone(data["manual"]["code_metrics"][0]["speaking_seconds"])

    def test_true_zero_at_bin_boundary_keeps_event_without_changing_physical_relations(self):
        base = [turn("a", 0, 1), {**turn("b", 9, 10), "speaker": "B"}]
        before = self.install(base)["automatic"]
        after = self.install([*base, turn("z", 300, 300)])["automatic"]
        for key in ("transitions", "long_gaps", "overlap_candidates"):
            self.assertEqual(after[key], before[key])
        self.assertEqual(after["overview"]["session_duration"], 300)
        self.assertEqual(sum(row["turn_count"] for row in after["time_bins"]), 3)
        self.assertEqual(sum(row["speaking_seconds"] for row in after["time_bins"]), 2)

    def test_live_and_fixed_csv_keep_unknown_blanks_true_zero_and_coverage(self):
        for name, segments in (("missing", [turn("u")]), ("zero", [turn("z", 10, 10)]),
                               ("partial", [turn("k", 0, 10), turn("u")]), ("empty", [])):
            with self.subTest(name=name):
                self.install(segments)
                snapshot = app.build_analysis_pipeline_snapshot(app.library_row("content"))
                self.assertEqual(snapshot["analysis"]["algorithm_version"], "focus-group-local-7")
                datasets = {key: analysis_csv_rows(snapshot["analysis"], key) for key in ("timeline", "emotions", "codes", "summary")}
                store = app.analysis_archive_store()
                run = store.save(item_id="content", kind="text_analysis", snapshot=snapshot["archive_snapshot"],
                    result={"parameters": {}, "algorithms": {"automatic": snapshot["analysis"]["algorithm_version"]}},
                    datasets=datasets, request_id="duration-closure-" + name + "-0001", input_fingerprint=snapshot["input_hash"],
                    source_revision=snapshot["source_revision"], analysis_revision=snapshot["analysis_revision"], publish=False)
                for dataset in ("timeline", "emotions", "codes"):
                    live = self.client.get(self.url + "/export.csv?dataset=" + dataset)
                    artifact = next(row for row in store.artifacts(run["id"]) if row["name"] == "tables/" + dataset + ".csv")
                    fixed = self.client.get('/api/analysis/artifacts/' + artifact["id"])
                    live_rows = list(csv.DictReader(io.StringIO(live.data.decode("utf-8-sig"))))
                    fixed_rows = list(csv.DictReader(io.StringIO(fixed.data.decode("utf-8-sig"))))
                    # The two existing CSV writers encode booleans/nested JSON differently.
                    # Compare the timing contract, not those unrelated legacy encodings.
                    timing_keys = {"index", "start", "end", "turn_count", "speaking_seconds", "count", "seconds",
                                   "segment_count", "timed_turn_count", "missing_time_turn_count", "algorithm_version"}
                    self.assertEqual([{k: v for k, v in row.items() if k in timing_keys} for row in live_rows],
                                     [{k: v for k, v in row.items() if k in timing_keys} for row in fixed_rows])
                    if dataset == "timeline" and name in ("missing", "empty"):
                        self.assertEqual(fixed_rows, [])
                    elif dataset != "timeline" and fixed_rows:
                        key = "seconds" if dataset == "emotions" else "speaking_seconds"
                        self.assertEqual(fixed_rows[0][key], "" if name == "missing" else "10.0" if name == "partial" else "0.0")
                        self.assertIn("missing_time_turn_count", fixed_rows[0])
                self.assertEqual(self.before, app.library_row("content")["segments_json"])

    def test_pre_upgrade_v6_timeline_remains_as_saved_in_adapter(self):
        from gurumoji.services.analysis_pipeline_adapters import run_analysis_pipeline_method
        self.install([turn("u")])
        legacy = copy.deepcopy(app.build_analysis_pipeline_snapshot(app.library_row("content"))["analysis"])
        legacy["algorithm_version"] = "focus-group-local-6"
        legacy["automatic"]["time_bins"] = [{"index": 0, "start": 0, "end": 300, "turn_count": 0, "speaking_seconds": 0, "speakers": []}]
        before = copy.deepcopy(legacy)
        result = run_analysis_pipeline_method("conversation_dynamics", {"analysis": legacy})
        self.assertEqual(len(result["datasets"]["timeline"]["rows"]), 1)
        self.assertEqual(result["datasets"]["timeline"]["rows"][0]["algorithm_version"], "focus-group-local-6")
        self.assertEqual(legacy, before)

    def test_library_read_projection_is_nullable_bounded_and_does_not_poison_list(self):
        cases = [("bad", None), ({"bad": 1}, None), ([], None), (None, None),
                 (10 ** 400, None), (1e308, None), ("10", 10), ("１０", 10), ("١٠", 10), ("1_0", 10), (0, 0)]
        for end, expected in cases:
            with self.subTest(end=str(end)[:40]):
                self.install([turn("s", 0, end)])
                response = self.client.get("/api/library/content")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get_json()["duration"], expected)
                self.assertEqual(response.get_json()["timed_turn_count"], int(expected is not None))
                self.assertEqual(response.get_json()["missing_time_turn_count"], int(expected is None))
                response = self.client.get("/api/library")
                self.assertEqual(response.status_code, 200)
                item = next(row for row in response.get_json()["items"] if row["id"] == "content")
                self.assertEqual(item["duration"], expected)
                self.assertEqual(self.before, app.library_row("content")["segments_json"])
        self.ai.assert_not_called()

    def test_full_library_timing_projection_is_bound_to_raw_values_and_not_persisted(self):
        for start, end in (("0", "10"), ("０", "１０"), ("٠", "١٠"), ("0", "1_0")):
            with self.subTest(start=start, end=end):
                self.install([turn("string-time", start, end)])
                value = self.client.get("/api/library/content").get_json()
                timing = value["segment_timings"][0]
                self.assertEqual(timing, {"segment_id": "string-time", "source_start": start, "source_end": end,
                                          "source_time_unknown": None, "valid": True, "start": 0.0, "end": 10.0})
                self.assertEqual(value["segments"][0]["start"], start)
                self.assertEqual(value["segments"][0]["end"], end)
                listed = next(row for row in self.client.get("/api/library").get_json()["items"] if row["id"] == "content")
                self.assertNotIn("segment_timings", listed)
                self.assertEqual(self.before, app.library_row("content")["segments_json"])

    def test_full_timing_projection_preserves_empty_and_nonempty_json_markers(self):
        for marker, expected in (([], True), ({}, True), (False, True), (None, True),
                                 (0, True), ("", True), ([False], False), ({"known": False}, False), (True, False)):
            for start, end in ((0, 10), (0, 0), ("0", "10")):
                with self.subTest(marker=marker, start=start, end=end):
                    self.install([turn("marker", start, end, time_unknown=marker)])
                    value = self.client.get("/api/library/content").get_json()
                    projected = value["segment_timings"][0]
                    self.assertIs(projected["valid"], expected)
                    self.assertEqual(projected["source_time_unknown"], marker)
                    self.assertEqual(value["segments"][0]["time_unknown"], marker)
                    self.assertEqual(projected["end"], float(end) if expected else None)
                    self.assertEqual(self.before, app.library_row("content")["segments_json"])
        self.ai.assert_not_called()
