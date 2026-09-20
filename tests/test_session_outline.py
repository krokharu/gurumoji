import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import analysis_insights as subject
import app


def transformer_result():
    return {
        "parameters": {"mode": "manual", "time_bin_seconds": 60},
        "topics": [
            {"topic_id": "T01", "label": "価格について", "origin": "manual",
             "segment_count": 2, "speaker_count": 2, "speaking_seconds": 6.0,
             "representative_segment_ids": ["s1", "s2"]},
            {"topic_id": "T02", "label": "操作について", "origin": "manual",
             "segment_count": 0, "speaker_count": 0, "speaking_seconds": 0.0,
             "representative_segment_ids": []},
        ],
        "assignments": [
            {"segment_id": "s1", "topic_id": "T01", "topic_label": "価格について", "start": 0.0},
            {"segment_id": "s2", "topic_id": "T01", "topic_label": "価格について", "start": 30.0},
            {"segment_id": "s9", "topic_id": "T02", "topic_label": "操作について", "start": 300.0},
        ],
        "timeline": [
            {"bin_index": 0, "start": 0, "end": 60, "topic_id": "T01",
             "topic_label": "価格について", "segment_count": 2},
            {"bin_index": 5, "start": 300, "end": 360, "topic_id": "T02",
             "topic_label": "操作について", "segment_count": 1},
        ],
    }


class SessionOutlineTests(unittest.TestCase):
    def test_plan_items_strip_numbering_and_bullets(self):
        profile = {"moderator_guide": "1. 価格について\n・操作について\n\n   \nQ3: 導入の体制"}
        self.assertEqual([item["text"] for item in subject.plan_items(profile)],
                         ["価格について", "操作について", "導入の体制"])
        self.assertEqual(subject.plan_items({}), [])

    def test_plan_status_uses_only_themes_the_researcher_defined(self):
        outline = subject.build_session_outline(
            outline=None, transformer=transformer_result(),
            session_profile={"moderator_guide": "価格について\n操作について\n価格以外の要望"},
        )
        plan = outline["plan"]
        self.assertTrue(plan["available"])
        self.assertEqual(plan["match"], "manual_topics")
        self.assertEqual([row["status"] for row in plan["items"]],
                         ["discussed", "not_discussed", "unmatched"])
        self.assertEqual(plan["items"][0]["segment_count"], 2)
        self.assertEqual(plan["discussed_count"], 1)

    def test_auto_topics_never_count_as_a_matched_plan(self):
        result = transformer_result()
        for topic in result["topics"]:
            topic["origin"] = "kmeans"
        plan = subject.build_session_outline(
            outline=None, transformer=result,
            session_profile={"moderator_guide": "価格について"},
        )["plan"]
        self.assertEqual(plan["match"], "none")
        self.assertEqual(plan["items"][0]["status"], "unmatched")

    def test_titles_come_from_the_agenda_and_themes_fill_the_gaps(self):
        outline = {"sections": [{"title": "価格の議題", "start": 0, "end": 60,
                                 "bullets": ["高いという声"], "segment_ids": ["s1", "s2"]}]}
        rows = subject.build_session_outline(
            outline=outline, transformer=transformer_result(), session_profile=None,
        )["result"]["rows"]
        self.assertEqual([row["title"] for row in rows], ["価格の議題", "操作について"])
        self.assertEqual([row["title_source"] for row in rows], ["outline", "transformer"])
        self.assertEqual(rows[0]["topics"][0], {"topic_id": "T01", "label": "価格について", "segment_count": 2})
        self.assertEqual(rows[0]["topic_evidence"], "segment_ids")
        self.assertLess(rows[0]["start"], rows[1]["start"])

    def test_sections_without_evidence_ids_fall_back_to_the_time_range(self):
        outline = {"sections": [{"title": "旧形式の議題", "start": 0, "end": 60, "bullets": []}]}
        row = subject.build_session_outline(
            outline=outline, transformer=transformer_result(), session_profile=None,
        )["result"]["rows"][0]
        self.assertEqual(row["topic_evidence"], "time_range")
        self.assertEqual(row["segment_count"], 2)

    def test_empty_inputs_report_nothing_instead_of_zero_results(self):
        empty = subject.build_session_outline(outline=None, transformer=None, session_profile=None)
        self.assertFalse(empty["plan"]["available"])
        self.assertFalse(empty["result"]["available"])
        self.assertFalse(empty["result"]["outline_available"])
        self.assertFalse(empty["result"]["transformer_available"])
        self.assertEqual(empty["result"]["rows"], [])

class SessionOutlineApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gurumoji-session-outline-")
        self.addCleanup(self.temp.cleanup)
        patcher = patch.object(app, "DATABASE_FILE", Path(self.temp.name) / "library.sqlite3")
        patcher.start()
        self.addCleanup(patcher.stop)
        app.initialize_library()
        self.client = app.app.test_client()
        segments = [
            {"id": "s1", "speaker": "A", "text": "価格が高いと感じました", "start": 0, "end": 3},
            {"id": "s2", "speaker": "B", "text": "料金が予算に合いません", "start": 30, "end": 34},
            {"id": "s9", "speaker": "A", "text": "画面の操作が分かりにくい", "start": 300, "end": 304},
        ]
        app.upsert_library_item(
            item_id="session", source_name="group.wav",
            output_dir=Path(self.temp.name) / "output", media_path=None, language="ja",
            segments=segments, speaker_names={"A": "参加者A", "B": "参加者B"}, files=[],
            outline={"title": "議題", "sections": [
                {"title": "価格の議題", "start": 0, "end": 60, "bullets": ["高いという声"],
                 "segment_ids": ["s1", "s2"]},
            ]},
            emotion_analysis=None, write_srt=False, write_json=True,
            session_profile={"moderator_guide": "1. 価格について\n2. 操作について"},
        )
        with app.database_connection() as connection:
            connection.execute(
                "UPDATE library_items SET transformer_analysis_json=? WHERE id='session'",
                (json.dumps({**transformer_result(), "source_revision": 0, "analysis_revision": 0},
                            ensure_ascii=False),),
            )

    def test_item_payload_pairs_the_plan_with_the_time_ordered_result(self):
        payload = self.client.get("/api/library/session").get_json()
        outline = payload["session_outline"]
        self.assertEqual([row["text"] for row in outline["plan"]["items"]],
                         ["価格について", "操作について"])
        self.assertEqual([row["status"] for row in outline["plan"]["items"]],
                         ["discussed", "not_discussed"])
        self.assertEqual([row["title"] for row in outline["result"]["rows"]],
                         ["価格の議題", "操作について"])
        self.assertEqual([row["title_source"] for row in outline["result"]["rows"]],
                         ["outline", "transformer"])
        self.assertFalse(outline["result"]["transformer_stale"])

    def test_edited_transcript_marks_the_saved_themes_as_older(self):
        row = app.library_row("session")
        app.upsert_library_item(
            item_id="session", source_name="group.wav",
            output_dir=Path(self.temp.name) / "output", media_path=None, language="ja",
            segments=[{**segment, "text": segment["text"] + "。"} for segment in app.row_segments(row)],
            speaker_names={"A": "参加者A", "B": "参加者B"}, files=[], outline=None,
            emotion_analysis=None, write_srt=False, write_json=True, increment_revision=True,
        )
        outline = self.client.get("/api/library/session").get_json()["session_outline"]
        self.assertTrue(outline["result"]["transformer_stale"])

    def test_the_plan_list_is_absent_when_no_guide_is_registered(self):
        app.upsert_library_item(
            item_id="plain", source_name="plain.wav",
            output_dir=Path(self.temp.name) / "output", media_path=None, language="ja",
            segments=[{"id": "p1", "speaker": "A", "text": "はじめます", "start": 0, "end": 2}],
            speaker_names={}, files=[], outline=None, emotion_analysis=None,
            write_srt=False, write_json=True,
        )
        outline = self.client.get("/api/library/plain").get_json()["session_outline"]
        self.assertFalse(outline["plan"]["available"])
        self.assertFalse(outline["result"]["available"])


if __name__ == "__main__":
    unittest.main()
