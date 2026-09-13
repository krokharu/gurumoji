import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


MEETING_SEGMENTS = [
    {
        "id": "m1",
        "start": 0.0,
        "end": 7.2,
        "speaker": "SPEAKER_00",
        "text": "田中さん、明日までに提案資料を作成してください。最優先でお願いします。",
    },
    {
        "id": "m2",
        "start": 7.2,
        "end": 12.5,
        "speaker": "SPEAKER_01",
        "text": "提案はこの方針で進めることに決まりました。",
    },
]
SPEAKER_NAMES = {"SPEAKER_00": "佐藤", "SPEAKER_01": "鈴木"}


class MeetingMinutesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="gurumoji-meeting-")
        self.root = Path(self.temporary.name)
        self.database_patch = patch.object(app, "DATABASE_FILE", self.root / "library.sqlite3")
        self.database_patch.start()
        self.addCleanup(self.database_patch.stop)
        self.addCleanup(self.temporary.cleanup)
        app.initialize_library()
        self.profile = {"session_type": "meeting", "session_date": "2026-09-14"}
        self.minutes = app.build_meeting_minutes(MEETING_SEGMENTS, SPEAKER_NAMES, self.profile)
        self.output = self.root / "output"
        app.upsert_library_item(
            item_id="meeting-1",
            source_name="定例会議.wav",
            output_dir=self.output,
            media_path=None,
            language="ja",
            segments=MEETING_SEGMENTS,
            speaker_names=SPEAKER_NAMES,
            files=[],
            outline=None,
            emotion_analysis=None,
            write_srt=False,
            write_json=True,
            session_profile=self.profile,
            meeting_minutes=self.minutes,
        )
        self.client = app.app.test_client()

    def test_extracts_reviewable_task_due_date_priority_and_decision(self):
        self.assertEqual(len(self.minutes["tasks"]), 1)
        task = self.minutes["tasks"][0]
        self.assertEqual(task["priority"], "high")
        self.assertEqual(task["due_date"], "2026-09-15")
        self.assertEqual(task["due_text"], "明日")
        self.assertEqual(task["evidence_segment_id"], "m1")
        self.assertEqual(task["confidence"], "candidate")
        self.assertEqual(self.minutes["analysis"]["priority_counts"]["high"], 1)
        self.assertEqual(self.minutes["analysis"]["decision_count"], 1)

    def test_persists_and_exports_markdown_csv_and_interoperable_json(self):
        saved = app.library_public(app.library_row("meeting-1"), full=True)
        self.assertEqual(saved["meeting_minutes"]["tasks"][0]["due_date"], "2026-09-15")

        json_response = self.client.get("/api/library/meeting-1/meeting.json")
        self.assertEqual(json_response.status_code, 200)
        external = json.loads(json_response.data.decode("utf-8"))
        self.assertEqual(external["schema"], "gurumoji.meeting.v1")
        self.assertEqual(external["meeting"]["id"], "meeting-1")
        self.assertEqual(external["tasks"][0]["priority"], "high")

        csv_response = self.client.get("/api/library/meeting-1/meeting-tasks.csv")
        self.assertEqual(csv_response.status_code, 200)
        rows = list(csv.DictReader(io.StringIO(csv_response.data.decode("utf-8-sig"))))
        self.assertEqual(rows[0]["due_date"], "2026-09-15")
        self.assertEqual(rows[0]["priority"], "high")

        markdown_response = self.client.get("/api/library/meeting-1/meeting-minutes.md")
        self.assertEqual(markdown_response.status_code, 200)
        self.assertIn("# 会議議事録", markdown_response.data.decode("utf-8"))
        self.assertIn("決定事項候補", markdown_response.data.decode("utf-8"))

    def test_output_bundle_contains_the_three_meeting_handoff_files(self):
        files = app.write_outputs(
            "定例会議.wav",
            self.output,
            MEETING_SEGMENTS,
            "ja",
            SPEAKER_NAMES,
            False,
            True,
            meeting_minutes=self.minutes,
        )
        names = {path.name for path in files}
        self.assertIn("定例会議_会議議事録.md", names)
        self.assertIn("定例会議_タスク.csv", names)
        self.assertIn("定例会議_meeting.json", names)

    def test_obsidian_route_saves_linked_minutes_and_preserves_versions(self):
        initial = self.client.get("/api/library/meeting-1/meeting-obsidian")
        self.assertEqual(initial.status_code, 200)
        self.assertEqual(initial.get_json()["status"], "unprepared")

        response = self.client.post("/api/library/meeting-1/meeting-obsidian")
        self.assertEqual(response.status_code, 200, response.get_json())
        published = response.get_json()
        self.assertEqual(published["status"], "completed")
        note_path = Path(published["path"])
        task_path = Path(published["tasks_path"])
        json_path = Path(published["json_path"])
        self.assertTrue(note_path.is_file())
        self.assertTrue(task_path.is_file())
        self.assertTrue(json_path.is_file())
        body = note_path.read_text(encoding="utf-8")
        self.assertIn("会議議事録", body)
        self.assertIn("アクションアイテム", body)
        self.assertIn("#^s-6d31", body)
        self.assertIn("タスクCSVを開く", body)
        self.assertEqual(json.loads(json_path.read_text(encoding="utf-8"))["schema"], "gurumoji.meeting.v1")
        self.assertEqual(list(csv.DictReader(io.StringIO(task_path.read_text(encoding="utf-8-sig"))))[0]["priority"], "high")

        manually_edited = body + "\n手動で追記したメモ\n"
        note_path.write_text(manually_edited, encoding="utf-8")
        repeated = self.client.post("/api/library/meeting-1/meeting-obsidian")
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(note_path.read_text(encoding="utf-8"), manually_edited)

        changed = json.loads(json.dumps(self.minutes, ensure_ascii=False))
        changed["tasks"][0]["title"] = "更新したタスク"
        with app.database_connection() as connection:
            connection.execute(
                "UPDATE library_items SET meeting_minutes_json=? WHERE id=?",
                (json.dumps(changed, ensure_ascii=False), "meeting-1"),
            )
        stale = self.client.get("/api/library/meeting-1/meeting-obsidian").get_json()
        self.assertEqual(stale["status"], "stale")
        updated = self.client.post("/api/library/meeting-1/meeting-obsidian").get_json()
        self.assertEqual(updated["status"], "completed")
        self.assertNotEqual(Path(updated["path"]), note_path)
        self.assertEqual(note_path.read_text(encoding="utf-8"), manually_edited)

        state = app.obsidian_workbench().load("meeting-1")
        hub = app.obsidian_workbench().layout.vault / app.obsidian_workbench().layout.register(
            "meeting-1", "定例会議.wav"
        )["hub"]
        self.assertIn("会議議事録・タスク", hub.read_text(encoding="utf-8"))
        self.assertEqual(state["meeting_minutes_note"], Path(updated["path"]).relative_to(app.obsidian_workbench().vault).as_posix())

    def test_normalization_ignores_malformed_persisted_numbers(self):
        normalized = app.normalize_meeting_minutes({
            "tasks": [{"title": "確認する", "evidence_start": "not-a-number"}],
            "decisions": [{"text": "決定", "evidence_end": "NaN"}],
            "analysis": {"speaker_activity": [{"speaker": "佐藤", "turns": "x", "seconds": "inf"}]},
        })
        self.assertEqual(normalized["tasks"][0]["evidence_start"], 0.0)
        self.assertEqual(normalized["decisions"][0]["evidence_end"], 0.0)
        self.assertEqual(normalized["analysis"]["speaker_activity"][0]["turns"], 0)
        self.assertEqual(normalized["analysis"]["speaker_activity"][0]["seconds"], 0.0)


if __name__ == "__main__":
    unittest.main()
