import copy
import csv
import hashlib
import io
import json
import tempfile
from collections import Counter
import unittest
from pathlib import Path
from unittest.mock import patch

import app
from gurumoji import research_analysis
from gurumoji.services.interview_comparison import build_interview_comparison


class InterviewComparisonApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gurumoji-interview-comparison-")
        self.addCleanup(self.temp.cleanup)
        self.database_patch = patch.object(app, "DATABASE_FILE", Path(self.temp.name) / "library.sqlite3")
        self.database_patch.start()
        self.addCleanup(self.database_patch.stop)
        for name, value in {
            "DATA_DIRECTORY": Path(self.temp.name),
            "MEDIA_DIRECTORY": Path(self.temp.name) / "media",
            "THUMBNAIL_DIRECTORY": Path(self.temp.name) / "thumbnails",
            "TRAINING_AUDIO_DIRECTORY": Path(self.temp.name) / "training",
        }.items():
            setting = patch.object(app, name, value)
            setting.start()
            self.addCleanup(setting.stop)
        # Synthetic text only; do not load a language or emotion model.
        for name in ("_load_ginza", "_load_sudachi"):
            loader = patch.object(research_analysis, name, return_value=(None, "test fallback"))
            loader.start()
            self.addCleanup(loader.stop)
        research_analysis._RESEARCH_CACHE.clear()
        self.addCleanup(research_analysis._RESEARCH_CACHE.clear)
        app.initialize_library()
        self.client = app.app.test_client()
        self.add_item("same_a", "同内容 A", "製品評価", ["使いやすい製品", "価格を改善してほしい"])
        self.add_item("same_b", "同内容 B", "製品評価", ["製品は使いやすい", "価格より機能を重視する"])
        self.add_item("different", "別内容", "採用面接", ["採用の面接方法", "候補者の評価方法"])

    def add_item(self, item_id, name, comparison_group, texts, predictions=None):
        segments = [
            {"id": f"{item_id}_{index}", "speaker": "P1", "start": index * 2,
             "end": index * 2 + 1, "text": text}
            for index, text in enumerate(texts)
        ]
        if predictions is not None:
            for segment, emotions in zip(segments, predictions):
                segment["emotions"] = emotions
        app.upsert_library_item(
            item_id=item_id, source_name=name, output_dir=Path(self.temp.name) / item_id,
            media_path=None, language="ja", segments=segments, speaker_names={"P1": "参加者"},
            outline=None, emotion_analysis=None, files=[], write_srt=False, write_json=True,
            session_profile={
                "session_type": "focus_group", "comparison_group": comparison_group,
                "objective": "比較テスト", "moderator_guide": "質問ガイド",
            },
        )

    def test_same_content_comparison_is_allowed_by_default(self):
        response = self.client.post("/api/library/interview-comparison", json={
            "item_ids": ["same_a", "same_b"], "allow_different_content": False,
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        data = response.get_json()
        self.assertTrue(data["same_content"])
        self.assertEqual(data["mode"], "same_content")
        self.assertEqual([item["item_id"] for item in data["interviews"]], ["same_a", "same_b"])
        self.assertIn("term_count", data["interviews"][0])

    def test_unknown_actual_participant_count_stays_null_and_observed_count_is_separate(self):
        data = self.client.post("/api/library/interview-comparison", json={
            "item_ids": ["same_a", "same_b"], "allow_different_content": False,
        }).get_json()
        for row in data["interviews"]:
            self.assertIsNone(row["participant_count"])
            self.assertEqual(row["observed_participant_count"], 1)

    def test_different_content_requires_explicit_override(self):
        payload = {"item_ids": ["same_a", "different"], "allow_different_content": False}
        blocked = self.client.post("/api/library/interview-comparison", json=payload)
        self.assertEqual(blocked.status_code, 409)
        self.assertIn("異なる内容", blocked.get_json()["error"])

        payload["allow_different_content"] = True
        allowed = self.client.post("/api/library/interview-comparison", json=payload)
        self.assertEqual(allowed.status_code, 200, allowed.get_json())
        data = allowed.get_json()
        self.assertEqual(data["mode"], "different_content")
        self.assertTrue(any("内容が異なる" in caution for caution in data["cautions"]))

    def test_catalog_exposes_safe_comparison_metadata(self):
        items = self.client.get("/api/library").get_json()["items"]
        same = next(item for item in items if item["id"] == "same_a")
        self.assertEqual(same["comparison_label"], "製品評価")
        self.assertTrue(same["comparison_key"].startswith("group:"))
        self.assertEqual(same["comparison_source"], "comparison_group")

    def test_comparison_group_is_editable_and_comparison_ui_is_loaded(self):
        template = self.client.get("/").get_data(as_text=True)
        script = (app.APP_DIRECTORY / "static" / "app.js").read_text(encoding="utf-8")
        comparison_script = (app.APP_DIRECTORY / "static" / "interview-comparison.js").read_text(encoding="utf-8")
        self.assertIn('id="session-comparison-group"', template)
        self.assertIn("'comparison_group'", script)
        self.assertIn("#session-comparison-group", script)
        self.assertIn("/api/library/interview-comparison", comparison_script)
        self.assertIn('id="interview-comparison-history-list"', template)
        self.assertIn("/api/analysis/runs/${encodeURIComponent(runId)}/vault", comparison_script)
        self.assertIn("loadComparisonHistory()", comparison_script)

    def test_browser_requests_require_csrf_and_save_the_displayed_input_version(self):
        headers = {'Origin': 'http://localhost', 'Sec-Fetch-Site': 'same-origin'}
        selection = {'item_ids': ['same_a', 'same_b'], 'allow_different_content': False}
        url = '/api/library/interview-comparison'
        self.assertEqual(self.client.post(url, json=selection, headers=headers).status_code, 403)
        self.assertEqual(self.client.post(url + '/runs', json=selection, headers=headers).status_code, 403)
        headers['X-Gurumoji-Request'] = '1'
        compared = self.client.post(url, json=selection, headers=headers)
        self.assertEqual(compared.status_code, 200)
        payload = {**selection, 'request_id': 'versioned-comparison-0001',
                   'input_fingerprints': compared.get_json()['input_fingerprints']}
        missing = {key: value for key, value in payload.items() if key != 'input_fingerprints'}
        self.assertEqual(self.client.post(url + '/runs', json=missing, headers=headers).status_code, 400)
        with app.database_connection() as connection:
            connection.execute("UPDATE library_items SET source_name='changed',revision_count=revision_count+1 WHERE id='same_a'")
        stale = self.client.post(url + '/runs', json=payload, headers=headers)
        self.assertEqual(stale.status_code, 409, stale.get_json())
        self.assertTrue(stale.get_json()['conflict'])
        self.assertEqual(app.analysis_archive_store().list_comparisons(), [])
        payload['input_fingerprints'] = self.client.post(url, json=selection, headers=headers).get_json()['input_fingerprints']
        saved = self.client.post(url + '/runs', json=payload, headers=headers)
        self.assertEqual(saved.status_code, 200, saved.get_json())
        repeated = self.client.post(url + '/runs', json=payload, headers=headers)
        self.assertEqual(repeated.get_json()['run']['id'], saved.get_json()['run']['id'])


    def test_real_projection_api_service_save_fresh_and_exports_preserve_old_values(self):
        for item_id, observed, sad in (("observed_a", 100, 20), ("observed_b", 5, 1)):
            predictions = [
                {"ser-id": {"model_name": "Synthetic SER", "label": "sad" if n < sad else "neutral",
                            "label_ja": "悲しみ" if n < sad else "中立"}} if n < observed else {}
                for n in range(100)
            ]
            self.add_item(item_id, item_id, "合成比較", ["合成の発話"] * 100, predictions)
        selection = {"item_ids": ["observed_a", "observed_b"], "allow_different_content": False}
        url = "/api/library/interview-comparison"

        def files():
            return {str(path.relative_to(self.temp.name)): hashlib.sha256(path.read_bytes()).hexdigest()
                    for path in Path(self.temp.name).rglob("*") if path.is_file()}

        before = files()
        with patch.object(app, "call_ai_json", side_effect=AssertionError("No AI allowed")):
            response = self.client.post(url, json=selection)
            self.assertEqual(response.status_code, 200, response.get_json())
            data = response.get_json()
            rows, allow_different = app.interview_comparison_request(selection)
            service = app.build_interview_comparison(rows, allow_different_content=allow_different)
            self.assertEqual({k: v for k, v in data.items() if k != "input_fingerprints"}, service)
            self.assertEqual(files(), before, "Comparison API and service must remain read-only")
            self.assertEqual(data["schema_version"], 1)
            sad = next(row for row in data["emotion_comparison"] if row["emotion"] == "Synthetic SER: 悲しみ")
            self.assertEqual([(v["count"], v["rate_per_100_segments"]) for v in sad["interviews"]],
                             [(20, 20.0), (1, 1.0)])
            for item, observed in zip(data["interviews"], (100, 5)):
                observation = item["emotion_observation"]
                self.assertEqual(observation["target_count"], 100)
                self.assertEqual(observation["any_model"]["observed_count"], observed)
                self.assertEqual(observation["any_model"]["missing_prediction_count"], 100 - observed)
                self.assertEqual(observation["models"][0]["model_id"], "ser-id")
                self.assertEqual(observation["models"][0]["observed_count"], observed)
            saved = self.client.post(url + "/runs", json={
                **selection, "request_id": "emotion-observation-0001",
                "input_fingerprints": data["input_fingerprints"],
            })
            self.assertEqual(saved.status_code, 200, saved.get_json())
            run = saved.get_json()["run"]
            # Reopen through the existing store/getters; do not use a cached result.
            store = app.analysis_archive_store()
            before = files()
            self.assertEqual(store.get(run["id"])["status"], "completed")
            snapshot, result, manifest, content = store.verified_package(run["id"])
            self.assertEqual(result["comparison"], service)
            self.assertEqual(result["schema_version"], 1)
            self.assertEqual(result["algorithms"]["interview_comparison"], 1)
            self.assertEqual([m["conversation_id"] for m in snapshot["members"]], selection["item_ids"])
            self.assertEqual(json.loads(content["result.json"])["comparison"], service)
            exported = list(csv.DictReader(io.StringIO(
                content["tables/comparison_emotions.csv"].decode("utf-8-sig"))))
            exported_sad = [row for row in exported if row["emotion"] == "Synthetic SER: 悲しみ"]
            self.assertEqual([(int(r["count"]), float(r["rate_per_100_segments"])) for r in exported_sad],
                             [(20, 20.0), (1, 1.0)])
            self.assertEqual(list(exported[0]), ["emotion", "max_count", "item_id", "count", "rate_per_100_segments"])
            interview_csv = content["tables/comparison_interviews.csv"].decode("utf-8-sig")
            self.assertNotIn("emotion_observation", next(csv.reader(io.StringIO(interview_csv))))
            for artifact in store.artifacts(run["id"]):
                metadata, exported_bytes = store.read_artifact(artifact["id"])
                self.assertEqual(exported_bytes, content[metadata["name"]])
            self.assertEqual(files(), before, "Fresh getters and existing artifact exports must not write")


    def test_unknown_projection_survives_save_fresh_json_and_typed_table_export(self):
        self.add_item("same_b", "同内容 B", "製品評価", ["合成の発話"],
                      [{"ser-id": {"model_name": "Synthetic SER", "label": "sad"}}])
        original_projection = app.group_analysis_for_row

        def legacy_projection(row):
            analysis = original_projection(row)
            if row["id"] == "same_a":
                for segment in analysis["segments"]:
                    segment.pop("emotion_details")
            return analysis

        selection = {"item_ids": ["same_a", "same_b"], "allow_different_content": False}
        url = "/api/library/interview-comparison"
        with patch.object(app, "group_analysis_for_row", side_effect=legacy_projection):
            compared = self.client.post(url, json=selection)
            self.assertEqual(compared.status_code, 200, compared.get_json())
            data = compared.get_json()
            saved = self.client.post(url + "/runs", json={
                **selection, "request_id": "emotion-observation-unknown-0001",
                "input_fingerprints": data["input_fingerprints"],
            })
        self.assertEqual(saved.status_code, 200, saved.get_json())
        store = app.analysis_archive_store()
        _snapshot, result, _manifest, content = store.verified_package(saved.get_json()["run"]["id"])
        observation = result["comparison"]["interviews"][0]["emotion_observation"]
        self.assertEqual(observation, data["interviews"][0]["emotion_observation"])
        for value in [observation["any_model"], *observation["models"]]:
            self.assertIsNone(value["observed_count"])
            self.assertIsNone(value["missing_prediction_count"])
            self.assertEqual(value["status"], "unknown")
        table = json.loads(content["tables/comparison_interviews.json"])
        self.assertEqual(table["rows"][0]["values"]["emotion_observation"], observation)
        self.assertEqual(result["comparison"]["emotion_comparison"], data["emotion_comparison"])


    def test_zero_target_not_applicable_survives_save_fresh_exports(self):
        self.add_item("empty_target", "対象発話なし", "合成比較", [])
        self.add_item("observed_target", "対象発話あり", "合成比較", ["合成の発話"], [{
            "ser-a": {"model_name": "Same display", "label": "sad"},
            "ser-b": {"model_name": "Same display", "label": "sad"},
        }])
        selection = {"item_ids": ["empty_target", "observed_target"], "allow_different_content": False}
        url = "/api/library/interview-comparison"
        compared = self.client.post(url, json=selection)
        self.assertEqual(compared.status_code, 200, compared.get_json())
        data = compared.get_json()
        observation = data["interviews"][0]["emotion_observation"]
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(data["interviews"][0]["included_segment_count"], 0)
        self.assertEqual(observation["target_count"], 0)
        self.assertEqual([model["model_id"] for model in observation["models"]], ["ser-a", "ser-b"])
        expected = {"observed_count": 0, "missing_prediction_count": 0,
                    "status": "not_applicable", "source": "analysis.segments[].emotion_details"}
        self.assertEqual(observation["any_model"], expected)
        for model in observation["models"]:
            self.assertEqual({key: model[key] for key in expected}, expected)
        self.assertEqual(observation["legacy_any_model_coverage"], {
            "percent": 0.0, "scope": "all_timeline_segments",
            "source": "analysis.automatic.data_quality.emotion_coverage_percent",
        })
        saved = self.client.post(url + "/runs", json={
            **selection, "request_id": "emotion-observation-zero-0001",
            "input_fingerprints": data["input_fingerprints"],
        })
        self.assertEqual(saved.status_code, 200, saved.get_json())
        store = app.analysis_archive_store()
        _snapshot, result, _manifest, content = store.verified_package(saved.get_json()["run"]["id"])
        self.assertEqual(result["comparison"]["interviews"], data["interviews"])
        self.assertEqual(result["comparison"]["emotion_comparison"], data["emotion_comparison"])
        self.assertEqual(json.loads(content["result.json"])["comparison"]["interviews"], data["interviews"])
        table = json.loads(content["tables/comparison_interviews.json"])
        self.assertEqual(table["rows"][0]["values"]["emotion_observation"], observation)
        csv_rows = list(csv.DictReader(io.StringIO(content["tables/comparison_interviews.csv"].decode("utf-8-sig"))))
        self.assertEqual(csv_rows[0]["included_segment_count"], "0")
        self.assertNotIn("emotion_observation", csv_rows[0])
        emotion_rows = list(csv.DictReader(io.StringIO(content["tables/comparison_emotions.csv"].decode("utf-8-sig"))))
        for row in emotion_rows:
            if row["item_id"] == "empty_target":
                self.assertEqual((int(row["count"]), float(row["rate_per_100_segments"])), (0, 0.0))


class EmotionObservationTests(unittest.TestCase):
    @staticmethod
    def detail(model="ser-a", name="Synthetic SER", label="sad", **extra):
        return {"model": model, "model_name": name, "label": label, "label_ja": label, **extra}

    @staticmethod
    def segment(turn_id="turn-1", details=None, **extra):
        return {"id": turn_id, "text": "synthetic text", "excluded": False,
                "emotion_details": [] if details is None else details, **extra}

    @staticmethod
    def projection(segments, *, coverage=50.0, emotions=None):
        return {"segments": segments, "config": {}, "manual": {"code_metrics": []},
                "automatic": {"overview": {}, "emotions": emotions or [],
                              "data_quality": {"emotion_coverage_percent": coverage}}}

    def compare(self, *projections):
        original = copy.deepcopy(projections)
        rows = [{"id": str(n), "source_name": f"Synthetic {n}"} for n in range(len(projections))]
        result = build_interview_comparison(
            rows, allow_different_content=False,
            row_session_profile=lambda row: {},
            interview_comparison_identity=lambda profile: ("synthetic", "Synthetic", "comparison_group"),
            group_analysis_for_row=lambda row: projections[int(row["id"])],
            text_mining_counter=lambda segments, stop_words: Counter(),
        )
        self.assertEqual(projections, original, "The service must not mutate its inputs")
        return result

    def observation(self, projection):
        # A known second interview supplies the shared actual-model catalog.
        data = self.compare(projection, self.projection([self.segment(details=[self.detail()])]))
        return data["interviews"][0]["emotion_observation"]

    def assert_unknown(self, observation):
        for value in [observation["any_model"], *observation["models"]]:
            self.assertIsNone(value["observed_count"])
            self.assertIsNone(value["missing_prediction_count"])
            self.assertEqual(value["status"], "unknown")
            self.assertEqual(value["source"], "unknown")

    def test_valid_empty_arrays_mean_unobserved_in_this_projection_only(self):
        observation = self.observation(self.projection([self.segment("one"), self.segment("two")]))
        self.assertEqual(set(observation), {"version", "target_scope", "target_count", "any_model", "models",
                                            "legacy_any_model_coverage"})
        self.assertEqual((observation["version"], observation["target_scope"], observation["target_count"]),
                         (1, "included_nonempty_segments", 2))
        expected = {"observed_count": 0, "missing_prediction_count": 2, "status": "known",
                    "source": "analysis.segments[].emotion_details"}
        self.assertEqual(observation["any_model"], expected)
        self.assertEqual(observation["models"], [{"model_id": "ser-a", "model_name": "Synthetic SER", **expected}])
        empty = self.compare(self.projection([self.segment()]))["interviews"][0]["emotion_observation"]
        self.assertEqual(empty["models"], [])
        self.assertEqual(empty["any_model"]["observed_count"], 0)

    def test_unique_turns_not_labels_and_shared_catalog_not_display_names(self):
        a = self.detail("id-a", "Same display")
        b = self.detail("id-b", "Same display")
        data = self.compare(
            self.projection([self.segment("one", [a, a, {**a, "label": "happy"}, b]),
                             self.segment("two", [a]), self.segment("three")]),
            self.projection([self.segment("one", [b])]),
        )
        first, second = [item["emotion_observation"] for item in data["interviews"]]
        self.assertEqual(first["any_model"]["observed_count"], 2)
        self.assertEqual([(m["model_id"], m["observed_count"], m["missing_prediction_count"]) for m in first["models"]],
                         [("id-a", 2, 1), ("id-b", 1, 2)])
        self.assertEqual([(m["model_id"], m["observed_count"], m["missing_prediction_count"]) for m in second["models"]],
                         [("id-a", 0, 1), ("id-b", 1, 0)])

    def test_excluded_and_blank_rows_are_outside_target_and_legacy_scope_is_retained(self):
        rows = [self.segment("one", [self.detail()]), self.segment("two"),
                self.segment(None, excluded=True, emotion_details=None),
                self.segment(None, text="  ", emotion_details=None)]
        observation = self.observation(self.projection(rows, coverage=75.25))
        self.assertEqual(observation["target_count"], 2)
        self.assertEqual(observation["any_model"]["observed_count"], 1)
        self.assertEqual(observation["any_model"]["missing_prediction_count"], 1)
        self.assertEqual(observation["legacy_any_model_coverage"], {
            "percent": 75.25, "scope": "all_timeline_segments",
            "source": "analysis.automatic.data_quality.emotion_coverage_percent",
        })

    def test_missing_or_legacy_details_cannot_be_reconstructed_from_aggregates(self):
        row = self.segment()
        del row["emotion_details"]
        row["emotions"] = ["sad"]
        projection = self.projection([row], coverage=100.0,
                                     emotions=[{"model": "summary-only-id", "model_name": "Synthetic SER",
                                                "emotion": "sad", "count": 1}])
        observation = self.observation(projection)
        self.assert_unknown(observation)
        self.assertEqual([m["model_id"] for m in observation["models"]], ["ser-a"])
        self.assertEqual(observation["legacy_any_model_coverage"]["percent"], 100.0)

    def test_malformed_arrays_or_entries_make_counts_unknown(self):
        cases = [None, {}, "sad", 1, [None], ["sad"], [{}],
                 [{"model": "ser-a", "label": ""}], [{"model": "ser-a", "label": 1}],
                 [{"model": "ser-a", "label": "sad", "label_ja": []}],
                 [{"model": "ser-a", "label": "sad", "model_name": []}]]
        for details in cases:
            with self.subTest(details=details):
                self.assert_unknown(self.observation(self.projection([
                    self.segment("valid", [self.detail()]), self.segment("bad", emotion_details=details)])))

    def test_missing_or_invalid_turn_ids_make_counts_unknown(self):
        for turn_id in (None, "", "  ", " padded ", 0, 1, True, [], {}):
            with self.subTest(turn_id=turn_id):
                self.assert_unknown(self.observation(self.projection([self.segment(turn_id, [self.detail()])])))
        row = self.segment(details=[self.detail()])
        del row["id"]
        self.assert_unknown(self.observation(self.projection([row])))

    def test_duplicate_turn_ids_do_not_create_observation_counts(self):
        observation = self.observation(self.projection([
            self.segment("duplicate", [self.detail()]), self.segment("duplicate")]))
        self.assertEqual(observation["target_count"], 2)
        self.assert_unknown(observation)

    def test_unknown_model_keys_never_become_display_name_identities(self):
        for model_id in (None, "", " ", "unknown", "UNKNOWN", " padded ", 7, True, []):
            with self.subTest(model_id=model_id):
                observation = self.observation(self.projection([
                    self.segment(details=[self.detail(model=model_id)])]))
                self.assert_unknown(observation)
                self.assertEqual([m["model_id"] for m in observation["models"]], ["ser-a"])
        entry = self.detail()
        del entry["model"]
        self.assert_unknown(self.observation(self.projection([self.segment(details=[entry])])))

    def test_conflicting_names_are_unresolved_across_the_shared_catalog(self):
        data = self.compare(
            self.projection([self.segment(details=[self.detail(name="First"), self.detail("stable", "Stable")])]),
            self.projection([self.segment(details=[self.detail(name="Second")])]),
        )
        for item in data["interviews"]:
            observation = item["emotion_observation"]
            self.assert_unknown(observation)
            self.assertEqual([m["model_id"] for m in observation["models"]], ["stable"])

    def test_missing_display_name_keeps_actual_model_id_without_inventing_a_name(self):
        entry = self.detail()
        del entry["model_name"]
        observation = self.compare(self.projection([self.segment(details=[entry])]))["interviews"][0]["emotion_observation"]
        self.assertEqual(observation["models"][0]["model_id"], "ser-a")
        self.assertIsNone(observation["models"][0]["model_name"])
        self.assertEqual(observation["models"][0]["observed_count"], 1)

    def test_zero_target_has_zero_counts_without_a_new_rate_or_legacy_denominator(self):
        for rows, coverage in (([], 0.0), ([self.segment(excluded=True)], 100.0),
                               ([self.segment(text="")], 50.0)):
            with self.subTest(rows=rows):
                other = self.projection([self.segment(details=[
                    self.detail("ser-a", "Same display"), self.detail("ser-b", "Same display")])])
                data = self.compare(self.projection(rows, coverage=coverage), other)
                observation = data["interviews"][0]["emotion_observation"]
                self.assertEqual(observation["target_count"], 0)
                self.assertEqual([model["model_id"] for model in observation["models"]], ["ser-a", "ser-b"])
                expected = {"observed_count": 0, "missing_prediction_count": 0,
                            "status": "not_applicable", "source": "analysis.segments[].emotion_details"}
                self.assertEqual(observation["any_model"], expected)
                for counts in observation["models"]:
                    self.assertEqual({key: value for key, value in counts.items()
                                      if key not in {"model_id", "model_name"}}, expected)
                self.assertEqual(observation["legacy_any_model_coverage"], {
                    "percent": coverage, "scope": "all_timeline_segments",
                    "source": "analysis.automatic.data_quality.emotion_coverage_percent",
                })
                self.assertEqual(data["interviews"][1]["emotion_observation"]["any_model"]["status"], "known")

    def test_zero_target_without_model_catalog_is_not_applicable(self):
        observation = self.compare(self.projection([]))["interviews"][0]["emotion_observation"]
        self.assertEqual(observation["target_count"], 0)
        self.assertEqual(observation["models"], [])
        self.assertEqual(observation["any_model"], {
            "observed_count": 0, "missing_prediction_count": 0,
            "status": "not_applicable", "source": "analysis.segments[].emotion_details",
        })

    def test_missing_or_invalid_legacy_coverage_stays_unknown_without_back_calculation(self):
        for coverage in (None, "50", True, -1, 101, 10 ** 400, float("inf"), float("nan"), {}):
            with self.subTest(coverage=coverage):
                observation = self.observation(self.projection([self.segment(details=[self.detail()])], coverage=coverage))
                self.assertEqual(observation["legacy_any_model_coverage"], {
                    "percent": None, "scope": "all_timeline_segments", "source": "unknown"})
                self.assertEqual(observation["any_model"]["observed_count"], 1)
        projection = self.projection([self.segment(details=[self.detail()])])
        del projection["automatic"]["data_quality"]["emotion_coverage_percent"]
        self.assertIsNone(self.observation(projection)["legacy_any_model_coverage"]["percent"])


if __name__ == "__main__":
    unittest.main()
