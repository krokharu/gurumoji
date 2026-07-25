import csv
import io
import json
import re
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

import app


ANALYSIS_DATASETS = {
    "speakers": {
        "speaker", "speaker_name", "role", "turn_count", "speaking_seconds",
        "speaking_percent", "participant_percent",
    },
    "transitions": {
        "from_speaker", "to_speaker", "count", "average_gap_seconds",
    },
    "gaps": {"start", "end", "seconds"},
    "overlaps": {"start", "end", "seconds"},
    "keywords": {"term", "count"},
    "emotions": {"speaker", "model", "emotion", "count", "seconds"},
    "timeline": {"index", "start", "end", "speaking_seconds", "turn_count"},
    "codes": {"id", "label", "segment_count", "speaking_seconds"},
    "groups": {
        "group", "speaker_count", "turn_count", "speaking_seconds",
        "speaking_percent",
    },
    "coded_segments": {
        "segment_id", "speaker", "text", "code_ids", "interaction_tags",
        "memo", "important", "excluded",
    },
    "interactions": {"tag", "label", "count"},
    "case_matrix": {"speaker", "speaker_name", "role", "codes"},
    "context": {"id", "label", "ready", "kind"},
    "summary": {"section", "metric", "value"},
    "observations": {"level", "label", "message"},
    "important_quotes": {
        "segment_id", "speaker", "speaker_name", "text", "code_labels", "memo",
    },
}


class AnalysisApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="gurumoji-analysis-")
        self.original_database = app.DATABASE_FILE
        app.DATABASE_FILE = Path(self.temporary.name) / "library.sqlite3"
        app.initialize_library()
        self.client = app.app.test_client()
        self.item_id = "analysis_fixture"
        app.upsert_library_item(
            item_id=self.item_id,
            source_name="group_interview.wav",
            output_dir=Path(self.temporary.name) / "output",
            media_path=None,
            language="ja",
            segments=[
                {
                    "id": "m_intro",
                    "start": 0.0,
                    "end": 2.0,
                    "speaker": "MODERATOR",
                    "text": "製品についてどう思いますか？",
                    "emotions": {"aist": {"label_ja": "平常"}},
                },
                {
                    "id": "p1_first",
                    "start": 2.5,
                    "end": 7.5,
                    "speaker": "PARTICIPANT_A",
                    "text": '=HYPERLINK("https://example.test","改善")',
                },
                {
                    "id": "p2_overlap",
                    "start": 7.0,
                    "end": 10.0,
                    "speaker": "PARTICIPANT_B",
                    "text": "改善提案に賛成です",
                    "emotions": {"aist": {"label_ja": "喜び"}},
                },
                {
                    "id": "p1_after_gap",
                    "start": 15.0,
                    "end": 19.0,
                    "speaker": "PARTICIPANT_A",
                    "text": "操作方法を改善したい",
                },
                {
                    "id": "m_followup",
                    "start": 19.5,
                    "end": 21.0,
                    "speaker": "MODERATOR",
                    "text": "理由を教えてください？",
                },
                {
                    "id": "p2_last",
                    "start": 21.1,
                    "end": 24.1,
                    "speaker": "PARTICIPANT_B",
                    "text": "時間を短くしたい",
                },
            ],
            speaker_names={
                "MODERATOR": "司会",
                "PARTICIPANT_A": "=2+3",
                "PARTICIPANT_B": "参加者B",
            },
            outline=None,
            emotion_analysis=None,
            files=[],
            write_srt=False,
            write_json=True,
            session_profile={
                "session_type": "focus_group",
                "objective": "製品の改善点を明らかにする",
                "moderator_guide": "利用体験、改善点",
                "group_conditions": "既存利用者",
                "field_notes": "重なり発話あり",
            },
            speaker_profiles={
                "MODERATOR": {
                    "display_name": "司会",
                    "session_role": "moderator",
                    "organization": "研究所",
                },
                "PARTICIPANT_A": {
                    "display_name": "=2+3",
                    "session_role": "participant",
                    "organization": "-危険組織",
                },
                "PARTICIPANT_B": {
                    "display_name": "参加者B",
                    "session_role": "participant",
                    "organization": "安全組織",
                },
            },
        )

    def tearDown(self):
        app.DATABASE_FILE = self.original_database
        self.temporary.cleanup()

    def create_analysis_item(
        self,
        item_id,
        segments,
        speaker_names=None,
        speaker_profiles=None,
    ):
        app.upsert_library_item(
            item_id=item_id,
            source_name=f"{item_id}.wav",
            output_dir=Path(self.temporary.name) / f"{item_id}-output",
            media_path=None,
            language="ja",
            segments=segments,
            speaker_names=speaker_names or {},
            outline=None,
            emotion_analysis=None,
            files=[],
            write_srt=False,
            write_json=True,
            speaker_profiles=speaker_profiles,
        )
        return item_id

    def put_analysis(self, item_id, *, config=None, annotations=None):
        current = self.client.get(f"/api/library/{item_id}/analysis").get_json()
        payload = {
            "source_revision": current["item"]["revision_count"],
            "analysis_revision": current["item"]["analysis_revision"],
        }
        if config is not None:
            payload["config"] = config
        if annotations is not None:
            payload["annotations"] = annotations
        return self.client.put(f"/api/library/{item_id}/analysis", json=payload)

    def put_manual_analysis(self):
        return self.client.put(
            f"/api/library/{self.item_id}/analysis",
            json={
                "source_revision": 0,
                "analysis_revision": 0,
                "config": {
                    "research_question": "参加者は製品改善をどのように捉えているか",
                    "analysis_unit": "turn",
                    "exclude_moderator": True,
                    "group_by": "organization",
                    "long_gap_seconds": 3.0,
                    "overlap_seconds": 0.2,
                    "low_participation_percent": 10.0,
                    "time_bin_seconds": 30,
                    "codebook": [
                        {
                            "id": "code_improvement",
                            "label": "改善要望",
                            "description": "製品の変更を求める発話",
                            "include_example": "操作方法を改善したい",
                            "exclude_example": "現状への単純な賛同",
                            "color": "#123456",
                        },
                        {
                            "id": "code_formula",
                            "label": "+FORMULA",
                            "description": "CSV式注入対策用fixture",
                            "color": "#654321",
                        },
                    ],
                    "analyst_memo": "反例も確認する",
                    "interpretation_status": "reviewed",
                },
                "annotations": {
                    "p1_first": {
                        "codes": ["code_improvement", "code_formula"],
                        "interaction_tags": ["engagement"],
                        "memo": "改善案を初めて提示",
                        "important": True,
                    },
                    "p2_overlap": {
                        "codes": ["code_improvement"],
                        "interaction_tags": ["agreement"],
                        "memo": "重なりながら賛同",
                    },
                    "missing_segment": {
                        "codes": ["code_improvement"],
                        "important": True,
                    },
                },
            },
        )

    def test_get_analysis_computes_fixed_metrics_and_candidates(self):
        response = self.client.get(f"/api/library/{self.item_id}/analysis")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(
            set(data),
            {
                "schema_version", "algorithm_version", "generated_at", "item",
                "config", "annotations", "classification", "cautions",
                "automatic", "manual", "segments", "exports",
            },
        )
        self.assertEqual(
            set(data["classification"]),
            {"automatic", "configured", "manual"},
        )
        overview = data["automatic"]["overview"]
        self.assertEqual(overview["session_duration"], 24.1)
        self.assertEqual(overview["segment_count"], 6)
        self.assertEqual(overview["included_segment_count"], 6)
        self.assertEqual(overview["total_speaking_seconds"], 18.5)

        metrics = {
            item["speaker"]: item
            for item in data["automatic"]["speaker_metrics"]
        }
        self.assertEqual(metrics["MODERATOR"]["speaking_seconds"], 3.5)
        self.assertEqual(metrics["PARTICIPANT_A"]["speaking_seconds"], 9.0)
        self.assertEqual(metrics["PARTICIPANT_B"]["speaking_seconds"], 6.0)
        self.assertFalse(metrics["MODERATOR"]["included_in_balance"])
        self.assertEqual(metrics["MODERATOR"]["participant_percent"], 0.0)
        self.assertEqual(metrics["PARTICIPANT_A"]["participant_percent"], 60.0)
        self.assertEqual(metrics["PARTICIPANT_B"]["participant_percent"], 40.0)

        balance = data["automatic"]["balance"]
        self.assertEqual(balance["participant_count"], 2)
        self.assertEqual(balance["participant_speaking_seconds"], 15.0)
        self.assertEqual(balance["denominator"], "participant_only")

        transitions = {
            (item["from_speaker"], item["to_speaker"]): item
            for item in data["automatic"]["transitions"]
        }
        self.assertEqual(len(transitions), 5)
        self.assertEqual(
            transitions[("PARTICIPANT_A", "PARTICIPANT_B")]["average_gap_seconds"],
            -0.5,
        )
        self.assertEqual(
            transitions[("PARTICIPANT_A", "PARTICIPANT_B")]["overlap_candidates"],
            1,
        )

        self.assertEqual(
            data["automatic"]["long_gaps"],
            [{
                "start": 10.0,
                "end": 15.0,
                "seconds": 5.0,
                "previous_name": "参加者B",
                "next_name": "=2+3",
            }],
        )
        self.assertEqual(len(data["automatic"]["overlap_candidates"]), 1)
        overlap = data["automatic"]["overlap_candidates"][0]
        self.assertEqual(overlap["seconds"], 0.5)
        self.assertEqual(overlap["from_speaker"], "PARTICIPANT_A")
        self.assertEqual(overlap["to_speaker"], "PARTICIPANT_B")

        moderator = data["automatic"]["moderator"]
        self.assertTrue(moderator["assigned"])
        self.assertEqual(moderator["question_candidates"], 2)
        self.assertEqual(moderator["participant_responses"], 2)
        self.assertEqual(moderator["participant_to_participant_transitions"], 2)
        self.assertEqual(moderator["cross_speaker_transitions"], 5)
        self.assertIn("json", data["exports"])
        self.assertEqual(set(ANALYSIS_DATASETS), set(data["exports"]) - {"json"})

    def test_put_persists_codebook_annotations_and_manual_metrics(self):
        before_item = self.client.get(
            f"/api/library/{self.item_id}/analysis"
        ).get_json()["item"]

        response = self.put_manual_analysis()

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(
            data["config"]["research_question"],
            "参加者は製品改善をどのように捉えているか",
        )
        self.assertEqual(data["config"]["group_by"], "organization")
        self.assertEqual(data["config"]["interpretation_status"], "reviewed")
        self.assertEqual(len(data["manual"]["codebook"]), 2)
        self.assertNotIn("missing_segment", data["annotations"])
        self.assertEqual(
            data["annotations"]["p1_first"]["codes"],
            ["code_improvement", "code_formula"],
        )
        self.assertEqual(
            data["annotations"]["p2_overlap"]["interaction_tags"],
            ["agreement"],
        )
        self.assertEqual(data["manual"]["coded_segment_count"], 2)
        self.assertEqual(data["manual"]["important_quote_count"], 1)

        code_metrics = {
            item["id"]: item for item in data["manual"]["code_metrics"]
        }
        improvement = code_metrics["code_improvement"]
        self.assertEqual(improvement["segment_count"], 2)
        self.assertEqual(improvement["speaking_seconds"], 8.0)
        self.assertEqual(improvement["speaker_count"], 2)
        self.assertEqual(improvement["important_count"], 1)
        self.assertEqual(
            data["item"]["revision_count"],
            before_item["revision_count"],
        )
        self.assertEqual(
            data["item"]["analysis_revision"],
            before_item["analysis_revision"] + 1,
        )
        self.assertEqual(data["item"]["updated_at"], before_item["updated_at"])
        self.assertIsNotNone(data["item"]["analysis_updated_at"])

        groups = {item["group"]: item for item in data["automatic"]["groups"]}
        self.assertEqual(groups["-危険組織"]["speaker_count"], 1)
        self.assertEqual(groups["-危険組織"]["speaking_seconds"], 9.0)
        self.assertEqual(groups["安全組織"]["speaking_seconds"], 6.0)

        loaded = self.client.get(
            f"/api/library/{self.item_id}/analysis"
        ).get_json()
        self.assertEqual(loaded["config"], data["config"])
        self.assertEqual(loaded["annotations"], data["annotations"])

    def test_json_and_all_csv_exports_follow_contract(self):
        self.assertEqual(self.put_manual_analysis().status_code, 200)

        exported_json = self.client.get(
            f"/api/library/{self.item_id}/analysis/export.json"
        )
        self.assertEqual(exported_json.status_code, 200)
        self.assertIn("attachment", exported_json.headers["Content-Disposition"])
        exported_data = json.loads(exported_json.data.decode("utf-8"))
        self.assertEqual(exported_data["schema_version"], 1)
        self.assertEqual(exported_data["item"]["id"], self.item_id)
        self.assertEqual(
            exported_data["annotations"]["p1_first"]["memo"],
            "改善案を初めて提示",
        )

        exported_rows = {}
        for dataset, expected_headers in ANALYSIS_DATASETS.items():
            with self.subTest(dataset=dataset):
                response = self.client.get(
                    f"/api/library/{self.item_id}/analysis/export.csv"
                    f"?dataset={dataset}"
                )
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.data.startswith(b"\xef\xbb\xbf"))
                self.assertIn(
                    "attachment",
                    response.headers["Content-Disposition"],
                )
                body = response.data.decode("utf-8-sig")
                reader = csv.DictReader(io.StringIO(body))
                self.assertIsNotNone(reader.fieldnames)
                self.assertTrue(expected_headers.issubset(set(reader.fieldnames)))
                self.assertTrue(
                    {"revision_count", "analysis_revision"}.issubset(
                        set(reader.fieldnames)
                    )
                )
                rows = list(reader)
                exported_rows[dataset] = rows
                for row in rows:
                    for cell in row.values():
                        if not cell:
                            continue
                        stripped = cell.lstrip()
                        self.assertFalse(
                            stripped.startswith(("=", "+", "@")),
                            f"{dataset} contains an unsafe spreadsheet cell: {cell!r}",
                        )
                        if stripped.startswith("-") and not re.fullmatch(
                            r"-?(?:\d+(?:\.\d*)?|\.\d+)", stripped
                        ):
                            self.fail(
                                f"{dataset} contains an unsafe spreadsheet cell: {cell!r}"
                            )

        speaker_a = next(
            row for row in exported_rows["speakers"]
            if row["speaker"] == "PARTICIPANT_A"
        )
        self.assertEqual(speaker_a["speaker_name"], "'=2+3")
        formula_code = next(
            row for row in exported_rows["codes"]
            if row["id"] == "code_formula"
        )
        self.assertEqual(formula_code["label"], "'+FORMULA")
        unsafe_group = next(
            row for row in exported_rows["groups"]
            if row["group"].endswith("危険組織")
        )
        self.assertEqual(unsafe_group["group"], "'-危険組織")
        emotion = next(
            row for row in exported_rows["emotions"]
            if row["speaker"] == "MODERATOR"
        )
        self.assertEqual(emotion["model"], "aist")
        coded = next(
            row for row in exported_rows["coded_segments"]
            if row["segment_id"] == "p1_first"
        )
        self.assertEqual(
            json.loads(coded["code_ids"]),
            ["code_improvement", "code_formula"],
        )
        self.assertEqual(json.loads(coded["interaction_tags"]), ["engagement"])
        self.assertEqual(coded["memo"], "改善案を初めて提示")
        self.assertEqual(coded["important"], "1")

        invalid = self.client.get(
            f"/api/library/{self.item_id}/analysis/export.csv?dataset=unknown"
        )
        self.assertEqual(invalid.status_code, 400)

    def test_empty_analysis_has_no_nan_or_infinity_and_exports_headers(self):
        empty_id = "empty_analysis"
        app.upsert_library_item(
            item_id=empty_id,
            source_name="empty.wav",
            output_dir=Path(self.temporary.name) / "empty-output",
            media_path=None,
            language="ja",
            segments=[],
            speaker_names={},
            outline=None,
            emotion_analysis=None,
            files=[],
            write_srt=False,
            write_json=True,
        )

        response = self.client.get(f"/api/library/{empty_id}/analysis")

        self.assertEqual(response.status_code, 200)
        raw = response.data.decode("utf-8")
        self.assertIsNone(
            re.search(r"(?<![A-Za-z])(?:NaN|Infinity|-Infinity)(?![A-Za-z])", raw)
        )
        data = response.get_json()
        json.dumps(data, ensure_ascii=False, allow_nan=False)
        overview = data["automatic"]["overview"]
        self.assertEqual(overview["segment_count"], 0)
        self.assertEqual(overview["speaker_count"], 0)
        self.assertEqual(overview["total_speaking_seconds"], 0.0)
        self.assertEqual(data["automatic"]["balance"]["gini"], 0.0)
        self.assertEqual(data["automatic"]["balance"]["normalized_evenness"], 0.0)

        for dataset, expected_headers in ANALYSIS_DATASETS.items():
            with self.subTest(dataset=dataset):
                exported = self.client.get(
                    f"/api/library/{empty_id}/analysis/export.csv?dataset={dataset}"
                )
                self.assertEqual(exported.status_code, 200)
                self.assertTrue(exported.data.startswith(b"\xef\xbb\xbf"))
                reader = csv.DictReader(
                    io.StringIO(exported.data.decode("utf-8-sig"))
                )
                self.assertTrue(expected_headers.issubset(set(reader.fieldnames or [])))
                self.assertTrue(
                    {"revision_count", "analysis_revision"}.issubset(
                        set(reader.fieldnames or [])
                    )
                )

        exported_json = self.client.get(
            f"/api/library/{empty_id}/analysis/export.json"
        )
        self.assertEqual(exported_json.status_code, 200)
        json.dumps(
            json.loads(exported_json.data.decode("utf-8")),
            ensure_ascii=False,
            allow_nan=False,
        )

    def test_missing_records_and_invalid_payloads_return_client_errors(self):
        self.assertEqual(
            self.client.get("/api/library/missing/analysis").status_code,
            404,
        )
        self.assertEqual(
            self.client.put(
                "/api/library/missing/analysis",
                json={"config": {}, "annotations": {}},
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                "/api/library/missing/analysis/export.json"
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.put(
                f"/api/library/{self.item_id}/analysis",
                data="not-json",
                content_type="text/plain",
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.put(
                f"/api/library/{self.item_id}/analysis",
                json={"config": {}, "annotations": {}},
            ).status_code,
            400,
        )

    def test_put_rejects_string_values_for_boolean_fields(self):
        current = self.client.get(
            f"/api/library/{self.item_id}/analysis"
        ).get_json()
        revisions = {
            "source_revision": current["item"]["revision_count"],
            "analysis_revision": current["item"]["analysis_revision"],
        }
        invalid_payloads = [
            {
                **revisions,
                "config": {"exclude_moderator": "false"},
                "annotations": {},
            },
            {
                **revisions,
                "config": {"exclude_moderator": True},
                "annotations": {
                    "p1_first": {
                        "memo": "文字列booleanは受け付けない",
                        "important": "false",
                    }
                },
            },
            {
                **revisions,
                "config": {"exclude_moderator": True},
                "annotations": {
                    "p1_first": {
                        "memo": "文字列booleanは受け付けない",
                        "excluded": "false",
                    }
                },
            },
        ]
        for payload in invalid_payloads:
            with self.subTest(payload=payload):
                response = self.client.put(
                    f"/api/library/{self.item_id}/analysis",
                    json=payload,
                )
                self.assertEqual(response.status_code, 400)

        loaded = self.client.get(
            f"/api/library/{self.item_id}/analysis"
        ).get_json()
        self.assertEqual(loaded["item"]["analysis_revision"], 0)
        self.assertEqual(loaded["annotations"], {})

    def test_generated_code_ids_are_deterministic(self):
        config = {
            "codebook": [
                {"label": "IDなしコード", "description": "決定的に補う"},
                {"label": "二つ目", "description": "別IDになる"},
            ]
        }
        first = self.put_analysis(
            self.item_id,
            config=config,
            annotations={},
        )
        self.assertEqual(first.status_code, 200)
        first_ids = [item["id"] for item in first.get_json()["config"]["codebook"]]
        self.assertEqual(len(first_ids), 2)
        self.assertEqual(len(set(first_ids)), 2)

        second = self.put_analysis(
            self.item_id,
            config=config,
            annotations={},
        )
        self.assertEqual(second.status_code, 200)
        second_ids = [item["id"] for item in second.get_json()["config"]["codebook"]]
        self.assertEqual(second_ids, first_ids)

    def test_nonfinite_and_large_timestamps_stay_finite_and_bounded(self):
        item_id = self.create_analysis_item(
            "nonfinite_timestamps",
            [
                {
                    "id": "nan_time",
                    "start": float("nan"),
                    "end": 10.0,
                    "speaker": "S1",
                    "text": "NaN時刻",
                },
                {
                    "id": "infinite_time",
                    "start": 0.0,
                    "end": float("inf"),
                    "speaker": "S1",
                    "text": "無限時刻",
                },
                {
                    "id": "too_large_time",
                    "start": 1e100,
                    "end": 1e100,
                    "speaker": "S2",
                    "text": "巨大時刻",
                },
                {
                    "id": "large_valid_time",
                    "start": 2_600_000.0,
                    "end": 2_600_001.0,
                    "speaker": "S2",
                    "text": "有効範囲内の大きな時刻",
                },
            ],
            speaker_names={"S1": "話者", "S2": "話者"},
        )

        response = self.client.get(f"/api/library/{item_id}/analysis")

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        json.dumps(data, ensure_ascii=False, allow_nan=False)
        self.assertEqual(
            data["automatic"]["data_quality"]["invalid_time_segments"],
            3,
        )
        self.assertLessEqual(len(data["automatic"]["time_bins"]), 5000)
        self.assertGreater(
            data["automatic"]["effective_time_bin_seconds"],
            data["automatic"]["requested_time_bin_seconds"],
        )
        self.assertEqual(data["automatic"]["overview"]["session_duration"], 2_600_001.0)
        for segment in data["segments"]:
            self.assertTrue(isinstance(segment["start"], (int, float)))
            self.assertTrue(isinstance(segment["end"], (int, float)))
            self.assertNotIn(str(segment["start"]), {"nan", "inf", "-inf"})
            self.assertNotIn(str(segment["end"]), {"nan", "inf", "-inf"})

        exported = self.client.get(
            f"/api/library/{item_id}/analysis/export.json"
        )
        self.assertEqual(exported.status_code, 200)
        json.dumps(
            json.loads(exported.data.decode("utf-8")),
            ensure_ascii=False,
            allow_nan=False,
        )

    def test_same_display_name_remains_separate_by_speaker_id(self):
        item_id = self.create_analysis_item(
            "same_display_name",
            [
                {
                    "id": "same_name_a",
                    "start": 0.0,
                    "end": 5.0,
                    "speaker": "SPEAKER_A",
                    "text": "共通品質改善",
                },
                {
                    "id": "same_name_b",
                    "start": 5.0,
                    "end": 10.0,
                    "speaker": "SPEAKER_B",
                    "text": "共通品質改善",
                },
            ],
            speaker_names={"SPEAKER_A": "同名", "SPEAKER_B": "同名"},
        )

        data = self.client.get(f"/api/library/{item_id}/analysis").get_json()

        bin_speakers = data["automatic"]["time_bins"][0]["speakers"]
        self.assertEqual(
            {item["speaker"] for item in bin_speakers},
            {"SPEAKER_A", "SPEAKER_B"},
        )
        self.assertEqual({item["speaker_name"] for item in bin_speakers}, {"同名"})
        keyword = next(
            item for item in data["automatic"]["keywords"]
            if item["term"] == "共通品質改善"
        )
        self.assertEqual(keyword["count"], 2)
        self.assertEqual(
            {item["speaker"] for item in keyword["by_speaker"]},
            {"SPEAKER_A", "SPEAKER_B"},
        )
        self.assertTrue(all(item["count"] == 1 for item in keyword["by_speaker"]))

    def test_empty_emotion_payload_is_not_counted_as_coverage(self):
        item_id = self.create_analysis_item(
            "emotion_coverage",
            [
                {
                    "id": "empty_emotion",
                    "start": 0.0,
                    "end": 2.0,
                    "speaker": "S1",
                    "text": "空の感情データ",
                    "emotions": {"aist": {}},
                },
                {
                    "id": "valid_emotion",
                    "start": 2.0,
                    "end": 4.0,
                    "speaker": "S1",
                    "text": "有効な感情データ",
                    "emotions": {
                        "aist": {
                            "model_name": "AIST emotion model",
                            "label": "neu",
                            "label_ja": "平常",
                        }
                    },
                },
            ],
            speaker_names={"S1": "参加者"},
        )

        data = self.client.get(f"/api/library/{item_id}/analysis").get_json()

        self.assertEqual(
            data["automatic"]["data_quality"]["emotion_coverage_percent"],
            50.0,
        )
        self.assertEqual(len(data["automatic"]["emotions"]), 1)
        self.assertEqual(data["automatic"]["emotions"][0]["model"], "aist")
        exported = self.client.get(
            f"/api/library/{item_id}/analysis/export.csv?dataset=emotions"
        )
        reader = csv.DictReader(io.StringIO(exported.data.decode("utf-8-sig")))
        rows = list(reader)
        self.assertIn("model", reader.fieldnames or [])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["model"], "aist")

    def test_zero_overlap_threshold_does_not_mark_touching_segments(self):
        item_id = self.create_analysis_item(
            "touching_segments",
            [
                {
                    "id": "touch_a",
                    "start": 0.0,
                    "end": 1.0,
                    "speaker": "S1",
                    "text": "先の発話",
                },
                {
                    "id": "touch_b",
                    "start": 1.0,
                    "end": 2.0,
                    "speaker": "S2",
                    "text": "直後の発話",
                },
            ],
            speaker_names={"S1": "参加者A", "S2": "参加者B"},
        )

        response = self.put_analysis(
            item_id,
            config={"overlap_seconds": 0.0},
            annotations={},
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["automatic"]["overlap_candidates"], [])
        self.assertEqual(len(data["automatic"]["transitions"]), 1)
        self.assertEqual(
            data["automatic"]["transitions"][0]["overlap_candidates"],
            0,
        )

    def test_excluded_segment_still_prevents_false_physical_silence(self):
        item_id = self.create_analysis_item(
            "excluded_physical_audio",
            [
                {
                    "id": "before_excluded",
                    "start": 0.0,
                    "end": 2.0,
                    "speaker": "S1",
                    "text": "前半",
                },
                {
                    "id": "excluded_middle",
                    "start": 2.0,
                    "end": 4.0,
                    "speaker": "S2",
                    "text": "分析対象外だが音声は存在する",
                },
                {
                    "id": "after_excluded",
                    "start": 4.0,
                    "end": 6.0,
                    "speaker": "S1",
                    "text": "後半",
                },
            ],
            speaker_names={"S1": "参加者A", "S2": "参加者B"},
        )

        response = self.put_analysis(
            item_id,
            config={"long_gap_seconds": 1.0},
            annotations={
                "excluded_middle": {
                    "excluded": True,
                    "memo": "分析対象からのみ除外",
                }
            },
        )

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["automatic"]["long_gaps"], [])
        self.assertEqual(data["automatic"]["overview"]["included_segment_count"], 2)
        self.assertEqual(data["automatic"]["data_quality"]["excluded_segments"], 1)
        middle = next(
            item for item in data["segments"] if item["id"] == "excluded_middle"
        )
        self.assertTrue(middle["excluded"])

    def test_source_and_analysis_revision_conflicts_return_409(self):
        current = self.client.get(
            f"/api/library/{self.item_id}/analysis"
        ).get_json()
        stale_payload = {
            "source_revision": current["item"]["revision_count"],
            "analysis_revision": current["item"]["analysis_revision"],
            "config": {"research_question": "競合テスト"},
            "annotations": {},
        }

        saved = self.client.put(
            f"/api/library/{self.item_id}/analysis",
            json=stale_payload,
        )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.get_json()["item"]["analysis_revision"], 1)

        analysis_conflict = self.client.put(
            f"/api/library/{self.item_id}/analysis",
            json=stale_payload,
        )
        self.assertEqual(analysis_conflict.status_code, 409)
        self.assertTrue(analysis_conflict.get_json()["conflict"])

        fresh = self.client.get(
            f"/api/library/{self.item_id}/analysis"
        ).get_json()
        source_stale_payload = {
            "source_revision": fresh["item"]["revision_count"],
            "analysis_revision": fresh["item"]["analysis_revision"],
            "config": fresh["config"],
            "annotations": fresh["annotations"],
        }
        with app.database_connection() as connection:
            connection.execute(
                "UPDATE library_items SET revision_count = revision_count + 1 WHERE id = ?",
                (self.item_id,),
            )

        source_conflict = self.client.put(
            f"/api/library/{self.item_id}/analysis",
            json=source_stale_payload,
        )
        self.assertEqual(source_conflict.status_code, 409)
        self.assertTrue(source_conflict.get_json()["conflict"])
        latest = self.client.get(
            f"/api/library/{self.item_id}/analysis"
        ).get_json()
        self.assertEqual(latest["item"]["analysis_revision"], 1)

    def test_orphaned_stored_annotations_are_reported_and_preserved(self):
        stored = {
            "p1_first": {
                "memo": "現行発話の注釈",
                "important": True,
            },
            "removed_segment": {
                "memo": "削除された発話に付いていた注釈",
                "important": True,
                "interaction_tags": ["agreement"],
            },
        }
        with app.database_connection() as connection:
            connection.execute(
                "UPDATE library_items SET analysis_annotations_json = ? WHERE id = ?",
                (json.dumps(stored, ensure_ascii=False), self.item_id),
            )

        loaded = self.client.get(
            f"/api/library/{self.item_id}/analysis"
        ).get_json()

        self.assertIn("p1_first", loaded["annotations"])
        self.assertNotIn("removed_segment", loaded["annotations"])
        self.assertEqual(loaded["manual"]["orphaned_annotation_count"], 1)
        self.assertEqual(
            loaded["manual"]["orphaned_annotations"],
            [{
                "segment_id": "removed_segment",
                "codes": [],
                "interaction_tags": ["agreement"],
                "memo": "削除された発話に付いていた注釈",
                "important": True,
                "excluded": False,
            }],
        )

        annotations = dict(loaded["annotations"])
        annotations["new_unknown_segment"] = {
            "memo": "新規PUTの未知IDは保存しない",
            "important": True,
        }
        saved = self.client.put(
            f"/api/library/{self.item_id}/analysis",
            json={
                "source_revision": loaded["item"]["revision_count"],
                "analysis_revision": loaded["item"]["analysis_revision"],
                "config": loaded["config"],
                "annotations": annotations,
            },
        )
        self.assertEqual(saved.status_code, 200)
        saved_data = saved.get_json()
        self.assertEqual(saved_data["manual"]["orphaned_annotation_count"], 1)
        self.assertEqual(
            saved_data["manual"]["orphaned_annotations"][0]["segment_id"],
            "removed_segment",
        )
        self.assertNotIn("new_unknown_segment", saved_data["annotations"])
        with app.database_connection() as connection:
            raw = connection.execute(
                "SELECT analysis_annotations_json FROM library_items WHERE id = ?",
                (self.item_id,),
            ).fetchone()[0]
        persisted = json.loads(raw)
        self.assertIn("removed_segment", persisted)
        self.assertNotIn("new_unknown_segment", persisted)

    def test_initialize_library_migrates_pre_analysis_database(self):
        legacy_database = Path(self.temporary.name) / "legacy.sqlite3"
        with closing(sqlite3.connect(legacy_database)) as connection:
            connection.execute(
                """
                CREATE TABLE library_items (
                    id TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    output_dir TEXT NOT NULL,
                    media_path TEXT,
                    language TEXT,
                    segments_json TEXT NOT NULL,
                    speaker_names_json TEXT NOT NULL,
                    outline_json TEXT,
                    emotion_analysis_json TEXT,
                    files_json TEXT NOT NULL,
                    write_srt INTEGER NOT NULL DEFAULT 1,
                    write_json INTEGER NOT NULL DEFAULT 1,
                    burn_subtitled_video INTEGER NOT NULL DEFAULT 0,
                    revision_count INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    session_profile_json TEXT NOT NULL DEFAULT '{}',
                    speaker_profiles_json TEXT NOT NULL DEFAULT '{}'
                )
                """
            )
            connection.execute(
                """
                INSERT INTO library_items (
                    id, source_name, output_dir, media_path, language,
                    segments_json, speaker_names_json, outline_json,
                    emotion_analysis_json, files_json, write_srt, write_json,
                    burn_subtitled_video, revision_count, created_at, updated_at,
                    session_profile_json, speaker_profiles_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "legacy_item", "legacy.wav", str(Path(self.temporary.name)),
                    None, "ja", "[]", "{}", None, None, "[]", 1, 1, 0, 0,
                    "2026-07-26T00:00:00+00:00",
                    "2026-07-26T00:00:00+00:00", "{}", "{}",
                ),
            )
            connection.commit()

        current_database = app.DATABASE_FILE
        try:
            app.DATABASE_FILE = legacy_database
            app.initialize_library()
            with closing(sqlite3.connect(legacy_database)) as connection:
                columns = {
                    row[1]
                    for row in connection.execute(
                        "PRAGMA table_info(library_items)"
                    ).fetchall()
                }
                self.assertIn("analysis_config_json", columns)
                self.assertIn("analysis_annotations_json", columns)
                self.assertIn("analysis_revision", columns)
                self.assertIn("analysis_updated_at", columns)
                migrated = connection.execute(
                    """
                    SELECT analysis_config_json, analysis_annotations_json,
                           analysis_revision, analysis_updated_at
                    FROM library_items WHERE id = 'legacy_item'
                    """
                ).fetchone()
                self.assertEqual(migrated, ("{}", "{}", 0, None))

            response = self.client.get("/api/library/legacy_item/analysis")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                response.get_json()["automatic"]["overview"]["segment_count"],
                0,
            )
        finally:
            app.DATABASE_FILE = current_database


if __name__ == "__main__":
    unittest.main()
