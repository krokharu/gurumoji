import io
import tempfile
import unittest
from pathlib import Path

import app


class SpeakerRegistryApiTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="gurumoji-speakers-")
        self.original_database = app.DATABASE_FILE
        app.DATABASE_FILE = Path(self.temporary.name) / "library.sqlite3"
        app.initialize_library()
        self.client = app.app.test_client()

    def tearDown(self):
        app.DATABASE_FILE = self.original_database
        self.temporary.cleanup()

    def test_saves_global_speaker_registry(self):
        response = self.client.put("/api/speakers", json={
            "speakers": [{
                "id": "speaker_test_001",
                "participant_code": "P-001",
                "display_name": "実名",
                "pseudonym": "参加者A",
                "default_role": "participant",
                "organization": "テスト株式会社",
                "job_title": "部長",
                "consent_status": "granted",
                "recording_consent": "granted",
                "confidentiality_status": "granted",
                "tags": ["顧客", "既存利用者"],
                "attributes": {"年齢層": "40代"},
                "notes": "連絡済み",
                "active": True,
            }],
            "delete_ids": [],
        })

        self.assertEqual(response.status_code, 200)
        record = response.get_json()["speakers"][0]
        self.assertEqual(record["participant_code"], "P-001")
        self.assertEqual(record["attributes"]["年齢層"], "40代")
        self.assertEqual(record["recording_consent"], "granted")

    def test_imports_google_forms_csv_and_preserves_unknown_questions(self):
        csv_body = (
            "\ufeffタイムスタンプ,参加者コード,氏名,仮名,役割,録音同意,年齢層,利用歴\n"
            "2026/07/26 10:00:00,P-002,山田花子,参加者B,参加者,同意,30代,3年\n"
        ).encode("utf-8")

        response = self.client.post(
            "/api/speakers/import",
            data={"csv_file": (io.BytesIO(csv_body), "forms.csv")},
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["imported_count"], 1)
        record = response.get_json()["speakers"][0]
        self.assertEqual(record["pseudonym"], "参加者B")
        self.assertEqual(record["recording_consent"], "granted")
        self.assertEqual(record["attributes"], {"年齢層": "30代", "利用歴": "3年"})

        exported = self.client.get("/api/speakers/export.csv")
        self.assertEqual(exported.status_code, 200)
        exported_text = exported.data.decode("utf-8-sig")
        self.assertIn("年齢層", exported_text)
        self.assertIn("参加者B", exported_text)

    def test_saves_conversation_profile_and_speaker_linkage(self):
        output_dir = Path(self.temporary.name) / "output"
        row = app.upsert_library_item(
            item_id="conversation_test",
            source_name="group_interview.wav",
            output_dir=output_dir,
            media_path=None,
            language="ja",
            segments=[
                {"start": 0.0, "end": 10.0, "speaker": "SPEAKER_00", "text": "質問です"},
                {"start": 10.0, "end": 30.0, "speaker": "SPEAKER_01", "text": "回答です"},
            ],
            speaker_names={"SPEAKER_00": "司会", "SPEAKER_01": "参加者A"},
            outline=None,
            emotion_analysis=None,
            files=[],
            write_srt=False,
            write_json=False,
        )
        self.assertIsNotNone(row)

        response = self.client.put("/api/library/conversation_test", json={
            "source_name": "group_interview.wav",
            "segments": app.row_segments(row),
            "speaker_names": {"SPEAKER_00": "司会", "SPEAKER_01": "参加者A"},
            "session_profile": {
                "session_type": "focus_group",
                "session_date": "2026-07-26",
                "location": "会議室A",
                "objective": "製品利用体験の確認",
                "moderator_guide": "導入、主要質問、締め",
                "group_conditions": "既存利用者",
                "confidentiality_notes": "録音同意済み",
                "field_notes": "参加者Aが積極的",
            },
            "speaker_profiles": {
                "SPEAKER_00": {
                    "display_name": "司会",
                    "session_role": "moderator",
                    "job_title": "リサーチャー",
                    "consent_status": "not_required",
                    "recording_consent": "granted",
                    "attendance_status": "attended",
                },
                "SPEAKER_01": {
                    "global_speaker_id": "speaker_test_001",
                    "display_name": "参加者A",
                    "session_role": "participant",
                    "job_title": "部長",
                    "consent_status": "granted",
                    "recording_consent": "granted",
                    "attendance_status": "attended",
                    "conditions": "既存利用3年以上",
                },
            },
        })

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["session_profile"]["session_type"], "focus_group")
        self.assertEqual(data["speaker_profiles"]["SPEAKER_00"]["session_role"], "moderator")
        self.assertEqual(data["speaker_profiles"]["SPEAKER_01"]["job_title"], "部長")

        exported = self.client.get("/api/library/conversation_test/speakers.csv")
        self.assertEqual(exported.status_code, 200)
        exported_text = exported.data.decode("utf-8-sig")
        self.assertIn("会話役割", exported_text)
        self.assertIn("moderator", exported_text)
        self.assertIn("既存利用3年以上", exported_text)


if __name__ == "__main__":
    unittest.main()
