import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app
from gurumoji.handlers.speaker_registry import (
    SpeakerIdentificationHandler,
    SpeakerRegistryHandler,
)


class TrackingLock:
    def __init__(self):
        self.active = False

    def __enter__(self):
        self.active = True

    def __exit__(self, *_args):
        self.active = False


class CompletedRunConnection:
    def __init__(self, item_ids):
        self.item_ids = item_ids
        self.statements = []

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def execute(self, statement):
        self.statements.append(statement)
        return self

    def fetchall(self):
        return [(item_id,) for item_id in self.item_ids]


class SpeakerRegistryHandlerTests(unittest.TestCase):
    def test_identification_handler_is_framework_independent(self):
        calls = []
        handler = SpeakerIdentificationHandler(
            lambda item_id, **options: calls.append((item_id, options)) or {
                "id": item_id,
                "speaker_identity": {"provider": options["provider"]},
            }
        )
        result = handler.run(
            "item-1", provider="openai", expected_revision=3
        )
        self.assertEqual(result["speaker_identity"]["provider"], "openai")
        self.assertEqual(calls, [(
            "item-1", {"provider": "openai", "expected_revision": 3}
        )])

    def test_save_and_archive_refresh_stay_under_shared_lock(self):
        lock = TrackingLock()
        connection = CompletedRunConnection(["item-1", "item-2"])
        saves = []
        refreshes = []

        def save_records(records, **options):
            self.assertTrue(lock.active)
            saves.append((records, options))
            return ([{"id": "speaker-1"}], 4)

        def refresh(item_id):
            self.assertTrue(lock.active)
            refreshes.append(item_id)

        handler = SpeakerRegistryHandler(
            snapshot=lambda **_options: ([{"id": "speaker-1"}], 3),
            save_records_locked=save_records,
            database_connection=lambda: connection,
            refresh_archive_index=refresh,
            write_lock=lock,
        )

        self.assertEqual(handler.list(), {
            "speakers": [{"id": "speaker-1"}],
            "total": 1,
            "registry_revision": 3,
        })
        self.assertEqual(
            handler.save(
                [{"id": "speaker-1"}],
                delete_ids=["speaker-old"],
                expected_revision=3,
            ),
            ([{"id": "speaker-1"}], 4),
        )
        self.assertEqual(refreshes, ["item-1", "item-2"])
        self.assertEqual(saves[0][1]["expected_revision"], 3)
        self.assertFalse(lock.active)


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
            "registry_revision": 0,
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
        self.assertEqual(response.get_json()["registry_revision"], 1)
        record = response.get_json()["speakers"][0]
        self.assertEqual(record["participant_code"], "P-001")
        self.assertEqual(record["attributes"]["年齢層"], "40代")
        self.assertEqual(record["recording_consent"], "granted")

    def test_registry_routes_are_registered_once_in_the_blueprint(self):
        rules = [
            rule for rule in app.app.url_map.iter_rules()
            if str(rule.rule) == "/api/speakers"
        ]
        self.assertEqual(sum("GET" in rule.methods for rule in rules), 1)
        self.assertEqual(sum("PUT" in rule.methods for rule in rules), 1)
        self.assertTrue(all(
            rule.endpoint.startswith("speaker_registry.") for rule in rules
        ))
        identification = [
            rule for rule in app.app.url_map.iter_rules()
            if str(rule.rule) == "/api/library/<item_id>/speaker-identification"
            and "POST" in rule.methods
        ]
        self.assertEqual(len(identification), 1)
        self.assertTrue(
            identification[0].endpoint.startswith("speaker_registry.")
        )

    def test_identified_speakers_link_only_to_a_unique_registered_name(self):
        profiles = app.normalize_conversation_speaker_profiles(
            None,
            {"SPEAKER_00", "SPEAKER_01", "SPEAKER_02"},
            {"SPEAKER_00": "田中 太郎", "SPEAKER_01": "佐藤", "SPEAKER_02": "山田"},
        )
        profiles, summary = app.link_detected_speakers_to_registry(profiles, {
            "SPEAKER_00": "田中 太郎",
            "SPEAKER_01": "佐藤",
            "SPEAKER_02": "山田",
        }, [
            {"id": "speaker_tanaka", "display_name": "田中太郎", "pseudonym": "田中", "active": True},
            {"id": "speaker_sato_a", "display_name": "佐藤", "active": True},
            {"id": "speaker_sato_b", "pseudonym": "佐藤", "active": True},
        ])

        self.assertEqual(profiles["SPEAKER_00"]["global_speaker_id"], "speaker_tanaka")
        self.assertEqual(profiles["SPEAKER_00"]["registration_status"], "registered")
        self.assertEqual(profiles["SPEAKER_01"]["global_speaker_id"], "")
        self.assertEqual(
            profiles["SPEAKER_01"]["registration_status"],
            "temporary_single_group",
        )
        self.assertEqual(
            profiles["SPEAKER_02"]["registration_status"],
            "temporary_single_group",
        )
        self.assertEqual(summary["linked"], {"SPEAKER_00": "speaker_tanaka"})
        self.assertEqual(summary["temporary"], {"SPEAKER_01": "佐藤", "SPEAKER_02": "山田"})
        self.assertEqual(summary["ambiguous"], {"SPEAKER_01": ["speaker_sato_a", "speaker_sato_b"]})

    def test_rerun_identification_links_registered_and_registers_new_name(self):
        app.save_speaker_registry_records([{
            "id": "speaker_tanaka",
            "display_name": "田中太郎",
        }], expected_revision=0)
        app.upsert_library_item(
            item_id="identity_link_test",
            source_name="group.wav",
            output_dir=Path(self.temporary.name) / "output",
            media_path=None,
            language="ja",
            segments=[
                {"start": 0.0, "end": 2.0, "speaker": "SPEAKER_00", "text": "田中太郎です"},
                {"start": 2.0, "end": 4.0, "speaker": "SPEAKER_01", "text": "山田です"},
            ],
            speaker_names={}, outline=None, emotion_analysis=None, files=[],
            write_srt=False, write_json=False,
        )
        revision = self.client.get("/api/library/identity_link_test").get_json()["revision_count"]
        with patch.object(app, "load_token_config", return_value=object()), \
             patch.object(app, "configured_ai_credentials", return_value=("secret", "test-model")), \
             patch.object(app, "detect_speaker_names_with_ai", return_value={
                 "SPEAKER_00": "田中 太郎", "SPEAKER_01": "山田",
             }), \
             patch.object(app, "refresh_archive_index"), \
             patch.object(app, "publish_input_vault"):
            response = self.client.post("/api/library/identity_link_test/speaker-identification", json={
                "provider": "openai", "revision_count": revision,
            })

        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["speaker_profiles"]["SPEAKER_00"]["global_speaker_id"], "speaker_tanaka")
        self.assertEqual(data["speaker_profiles"]["SPEAKER_00"]["registration_status"], "registered")
        new_speaker_id = data["speaker_profiles"]["SPEAKER_01"]["global_speaker_id"]
        self.assertTrue(new_speaker_id.startswith("speaker_auto_"))
        self.assertEqual(data["speaker_profiles"]["SPEAKER_01"]["registration_status"], "registered")
        self.assertEqual(
            data["speaker_identity"]["registration"]["created"],
            {"SPEAKER_01": new_speaker_id},
        )
        registry = self.client.get("/api/speakers").get_json()["speakers"]
        self.assertIn(
            (new_speaker_id, "山田"),
            {(record["id"], record["display_name"]) for record in registry},
        )

    def test_registers_an_unambiguous_detected_name_without_duplicate_records(self):
        profiles = app.normalize_conversation_speaker_profiles(
            None, {"SPEAKER_00"}, {"SPEAKER_00": "鈴木"}
        )

        profiles, summary = app.register_detected_speakers(
            profiles, {"SPEAKER_00": "鈴木"}
        )

        speaker_id = summary["created"]["SPEAKER_00"]
        self.assertTrue(speaker_id.startswith("speaker_auto_"))
        self.assertEqual(profiles["SPEAKER_00"]["global_speaker_id"], speaker_id)
        self.assertEqual(profiles["SPEAKER_00"]["registration_status"], "registered")
        registry = self.client.get("/api/speakers").get_json()
        self.assertEqual(registry["registry_revision"], 1)
        self.assertEqual(len(registry["speakers"]), 1)
        self.assertEqual(registry["speakers"][0]["display_name"], "鈴木")

    def test_does_not_register_a_name_when_active_records_are_ambiguous(self):
        app.save_speaker_registry_records([
            {"id": "speaker_sato_a", "display_name": "佐藤"},
            {"id": "speaker_sato_b", "pseudonym": "佐藤"},
        ], expected_revision=0)
        profiles = app.normalize_conversation_speaker_profiles(
            None, {"SPEAKER_00"}, {"SPEAKER_00": "佐藤"}
        )

        profiles, summary = app.register_detected_speakers(
            profiles, {"SPEAKER_00": "佐藤"}
        )

        self.assertEqual(summary["created"], {})
        self.assertEqual(summary["ambiguous"], {"SPEAKER_00": ["speaker_sato_a", "speaker_sato_b"]})
        self.assertEqual(profiles["SPEAKER_00"]["registration_status"], "temporary_single_group")
        self.assertEqual(len(self.client.get("/api/speakers").get_json()["speakers"]), 2)

    def test_imports_google_forms_csv_and_preserves_unknown_questions(self):
        csv_body = (
            "\ufeffタイムスタンプ,参加者コード,氏名,仮名,役割,録音同意,年齢層,利用歴\n"
            "2026/07/26 10:00:00,P-002,山田花子,参加者B,参加者,同意,30代,3年\n"
        ).encode("utf-8")

        response = self.client.post(
            "/api/speakers/import",
            data={
                "registry_revision": "0",
                "csv_file": (io.BytesIO(csv_body), "forms.csv"),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["imported_count"], 1)
        self.assertEqual(response.get_json()["registry_revision"], 1)
        record = response.get_json()["speakers"][0]
        self.assertEqual(record["pseudonym"], "参加者B")
        self.assertEqual(record["recording_consent"], "granted")
        self.assertEqual(record["attributes"], {"年齢層": "30代", "利用歴": "3年"})

        exported = self.client.get("/api/speakers/export.csv")
        self.assertEqual(exported.status_code, 200)
        exported_text = exported.data.decode("utf-8-sig")
        self.assertIn("年齢層", exported_text)
        self.assertIn("参加者B", exported_text)
        self.assertNotIn("研究同意", exported_text.splitlines()[0])
        self.assertNotIn("録音同意", exported_text.splitlines()[0])

    def test_registry_revision_prevents_lost_updates_between_tabs(self):
        initial = self.client.get("/api/speakers").get_json()
        self.assertEqual(initial["registry_revision"], 0)
        payload = {
            "registry_revision": initial["registry_revision"],
            "speakers": [{
                "id": "speaker_revision_001",
                "participant_code": "P-REV",
                "display_name": "First tab",
            }],
            "delete_ids": [],
        }
        first = self.client.put("/api/speakers", json=payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.get_json()["registry_revision"], 1)

        stale = self.client.put("/api/speakers", json={
            **payload,
            "speakers": [{
                "id": "speaker_revision_001",
                "participant_code": "P-REV",
                "display_name": "Stale second tab",
            }],
        })
        self.assertEqual(stale.status_code, 409)
        self.assertTrue(stale.get_json()["conflict"])
        self.assertEqual(stale.get_json()["current_revision"], 1)

        current = self.client.get("/api/speakers").get_json()
        self.assertEqual(current["registry_revision"], 1)
        self.assertEqual(current["speakers"][0]["display_name"], "First tab")

        missing = self.client.put("/api/speakers", json={"speakers": [], "delete_ids": []})
        self.assertEqual(missing.status_code, 400)

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

        current_response = self.client.get("/api/library/conversation_test")
        self.assertEqual(current_response.status_code, 200)
        current_revision = current_response.get_json()["revision_count"]

        response = self.client.put("/api/library/conversation_test", json={
            "revision_count": current_revision,
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
        self.assertEqual(data["speaker_profiles"]["SPEAKER_01"]["registration_status"], "registered")

        exported = self.client.get("/api/library/conversation_test/speakers.csv")
        self.assertEqual(exported.status_code, 200)
        exported_text = exported.data.decode("utf-8-sig")
        self.assertIn("会話役割", exported_text)
        self.assertIn("話者登録状態", exported_text)
        self.assertIn("moderator", exported_text)
        self.assertIn("既存利用3年以上", exported_text)
        self.assertNotIn("研究同意", exported_text.splitlines()[0])
        self.assertNotIn("録音同意", exported_text.splitlines()[0])


if __name__ == "__main__":
    unittest.main()
