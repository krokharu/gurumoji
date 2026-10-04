"""Regression tests for trash recovery and lossless, failure-isolated imports."""

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from gurumoji.handlers.application_lifecycle import ApplicationLifecycle
from gurumoji.services import edit_transactions, library_trash
from gurumoji.services.durable_files import durable_move
from gurumoji.services.library_rows import (
    normalize_conversation_speaker_profiles, normalize_session_profile,
    row_segments, row_session_profile,
)
from gurumoji.services.library_schema import make_library_schema
from gurumoji.services.library_store import make_library_store
from gurumoji.services.output_import import make_output_import
from gurumoji.services.outputs import write_outputs


def connection_factory(path):
    def connect():
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        return connection
    return connect


def move(source, target):
    durable_move(source, target, replace_existing=False)


def locked(source, target):
    raise PermissionError("simulated temporary file lock")


class TrashRecoveryIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gurumoji-trash-integrity-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.media = self.root / "media"
        self.quarantine = self.media / ".delete-staging-test" / "conversation"
        self.quarantine.mkdir(parents=True)
        (self.quarantine / "unique.wav").write_bytes(b"original recording")
        self.connect = connection_factory(self.root / "library.sqlite3")
        with self.connect() as connection:
            connection.execute("CREATE TABLE library_items(id TEXT PRIMARY KEY)")
            connection.execute("INSERT INTO library_items VALUES('conversation')")
            rows = library_trash.snapshot_rows(connection, "conversation")
            connection.execute("DELETE FROM library_items WHERE id='conversation'")
        self.trash = self.root / "trash"
        self.entry = library_trash.begin(
            self.trash, item_id="conversation", source_name="unique.wav", rows=rows,
            tombstones_added=[], tombstones_replaced=[],
            assets=[("media", self.quarantine, self.media / "conversation")],
        )

    def recover(self, mover=move):
        warnings = library_trash.recover_pending(
            self.trash, row_exists=lambda _: False, move=mover,
        )
        warnings += edit_transactions.recover_delete_quarantines(
            connect=self.connect, media_directory=self.media,
            thumbnail_directory=self.root / "thumbnails",
        )
        return warnings

    def test_locked_media_survives_repeated_startup_and_later_restores(self):
        self.assertTrue(library_trash.finish(self.entry, locked))
        journal = json.loads((self.entry / library_trash.PENDING).read_text())
        self.assertEqual(journal["assets"][0]["quarantine"], str(self.quarantine))
        self.assertTrue(self.recover(locked))
        self.assertEqual((self.quarantine / "unique.wav").read_bytes(), b"original recording")
        self.assertTrue((self.entry / library_trash.PENDING).is_file())
        self.assertEqual(self.recover(), [])
        self.assertFalse((self.entry / library_trash.PENDING).exists())
        self.assertEqual((self.entry / "media/conversation/unique.wav").read_bytes(), b"original recording")
        restored = library_trash.restore(
            self.trash, self.entry.name, connect=self.connect,
            targets={"media": self.media, "thumbnail": self.root / "thumbnails"}, move=move,
        )
        self.assertEqual(restored, "conversation")
        self.assertEqual((self.media / "conversation/unique.wav").read_bytes(), b"original recording")
        with self.connect() as connection:
            self.assertIsNotNone(connection.execute("SELECT * FROM library_items").fetchone())

    def test_pending_entry_cannot_expire_or_restore_without_media(self):
        library_trash.finish(self.entry, locked)
        later = datetime.now(timezone.utc) + timedelta(days=365)
        self.assertEqual(library_trash.purge_expired(self.trash, 30, later), [])
        with self.assertRaises(library_trash.TrashError):
            library_trash.purge(self.trash, self.entry.name)
        with self.assertRaises(library_trash.TrashError):
            library_trash.restore(
                self.trash, self.entry.name, connect=self.connect,
                targets={"media": self.media}, move=locked,
            )
        self.assertTrue(self.quarantine.is_dir())
        self.assertTrue((self.entry / library_trash.PENDING).is_file())

    def test_partial_move_is_retryable_without_replacing_already_moved_asset(self):
        thumbnail = self.root / "thumbnails/.delete-staging-test/word_cloud_conversation.svg"
        thumbnail.parent.mkdir(parents=True)
        thumbnail.write_bytes(b"thumbnail")
        pending = self.entry / library_trash.PENDING
        manifest = json.loads(pending.read_text())
        manifest["assets"].append({"kind": "thumbnail", "name": thumbnail.name,
                                   "quarantine": str(thumbnail)})
        pending.write_text(json.dumps(manifest))
        def partial(source, target):
            if source == thumbnail:
                return locked(source, target)
            return move(source, target)
        self.assertTrue(library_trash.finish(self.entry, partial))
        self.assertFalse(self.quarantine.exists())
        self.assertTrue(thumbnail.exists())
        self.assertEqual(self.recover(), [])
        self.assertEqual((self.entry / "media/conversation/unique.wav").read_bytes(), b"original recording")
        self.assertEqual((self.entry / "thumbnails" / thumbnail.name).read_bytes(), b"thumbnail")

    def test_unreadable_pending_manifest_retains_quarantine(self):
        (self.entry / library_trash.PENDING).write_text("{broken")
        self.assertTrue(self.recover())
        self.assertTrue(self.quarantine.is_dir())
        later = datetime.now(timezone.utc) + timedelta(days=365)
        self.assertEqual(library_trash.purge_expired(self.trash, 30, later), [])
        with self.assertRaises(library_trash.TrashError):
            library_trash.purge(self.trash, self.entry.name)

    def test_legacy_failed_manifest_still_protects_quarantine(self):
        pending = self.entry / library_trash.PENDING
        manifest = json.loads(pending.read_text())
        manifest["assets"][0].pop("quarantine")
        manifest["assets"][0]["in_trash"] = False
        (self.entry / library_trash.MANIFEST).write_text(json.dumps(manifest))
        pending.unlink()
        self.assertTrue(self.recover())
        self.assertTrue(self.quarantine.is_dir())
        later = datetime.now(timezone.utc) + timedelta(days=365)
        self.assertEqual(library_trash.purge_expired(self.trash, 30, later), [])
        with self.assertRaises(library_trash.TrashError):
            library_trash.purge(self.trash, self.entry.name)

    def test_unknown_asset_kind_never_allows_recording_cleanup(self):
        pending = self.entry / library_trash.PENDING
        manifest = json.loads(pending.read_text())
        manifest["assets"][0]["kind"] = "unexpected_kind"
        pending.write_text(json.dumps(manifest))
        self.assertIsNone(library_trash.protected_quarantine_assets(self.trash))
        self.assertTrue(self.recover())
        self.assertTrue(pending.is_file())
        self.assertEqual((self.quarantine / "unique.wav").read_bytes(), b"original recording")

    def test_malformed_asset_structure_or_identity_protects_all_quarantines(self):
        pending = self.entry / library_trash.PENDING
        original = json.loads(pending.read_text())
        invalid_assets = [{}, "invalid", [None], [{"kind": "media", "name": "another-item"}],
                          [{"kind": "media", "name": None}], [{"kind": [], "name": "conversation"}],
                          [{"kind": "media", "name": "conversation", "quarantine": None}],
                          [{"kind": "media", "name": "conversation", "quarantine": "/wrong/identity"}]]
        for assets in invalid_assets:
            with self.subTest(assets=assets):
                pending.write_text(json.dumps({**original, "assets": assets}))
                self.assertIsNone(library_trash.protected_quarantine_assets(self.trash))
                warnings = self.recover()
                self.assertTrue(warnings)
                self.assertTrue(pending.exists())
                self.assertEqual((self.quarantine / "unique.wav").read_bytes(), b"original recording")

    def test_corrupt_final_manifest_cannot_expire_purge_or_restore(self):
        pending = self.entry / library_trash.PENDING
        original = json.loads(pending.read_text())
        pending.unlink()
        final = self.entry / library_trash.MANIFEST
        for assets in ([None], ["invalid"], [{"kind": "unknown", "name": "conversation"}]):
            with self.subTest(assets=assets):
                final.write_text(json.dumps({**original, "assets": assets}))
                self.assertTrue(self.recover())
                later = datetime.now(timezone.utc) + timedelta(days=365)
                self.assertEqual(library_trash.purge_expired(self.trash, 30, later), [])
                with self.assertRaises(library_trash.TrashError):
                    library_trash.purge(self.trash, self.entry.name)
                with self.assertRaises(library_trash.TrashError):
                    library_trash.restore(self.trash, self.entry.name, connect=self.connect,
                                          targets={"media": self.media}, move=move)
                self.assertTrue(final.exists())
                self.assertEqual((self.quarantine / "unique.wav").read_bytes(), b"original recording")


class OutputImportIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gurumoji-import-integrity-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / "output"
        self.output.mkdir()
        self.connect = connection_factory(self.root / "library.sqlite3")
        make_library_schema(
            data_directory=lambda: self.root, media_directory=lambda: self.root / "media",
            thumbnail_directory=lambda: self.root / "thumbnails",
            training_audio_directory=lambda: self.root / "training",
            database_connection=self.connect, repair_output_import_provenance=lambda c: None,
        )[-1]()
        row, _, _, upsert = make_library_store(
            media_directory=lambda: self.root / "media", database_connection=self.connect,
            local_path_access_allowed=lambda: True, media_kind=lambda p: "audio",
            normalize_ai_usage=lambda value: value or {}, row_segments=row_segments,
            row_session_profile=row_session_profile, row_speaker_profiles=lambda *args: {},
        )
        self.import_outputs = make_output_import(
            default_output_directory=lambda: self.output, database_connection=self.connect,
            library_row=row, publish_input_vault=lambda *args, **kwargs: None,
            upsert_library_item=upsert,
        )[-1]

    def write_result(self, *, session_profile=None):
        names = {"SPEAKER_00": "Host"}
        profiles = normalize_conversation_speaker_profiles({"SPEAKER_00": {
            "display_name": "Host", "session_role": "moderator",
            "consent_status": "declined", "recording_consent": "declined",
            "theme_color": "#FF0000", "global_speaker_id": "registry-person-1",
            "conditions": "No sharing", "notes": "Researcher note",
        }}, {"SPEAKER_00"}, names)
        write_outputs(
            "meeting.wav", self.output,
            [{"id": "s1", "start": 0, "end": 1, "speaker": "SPEAKER_00", "text": "hello"}],
            "ja", names, False, True, speaker_profiles=profiles,
            meeting_minutes={"summary": ["Important summary"], "tasks": [], "decisions": []},
            session_profile=session_profile,
            write_word_cloud=lambda *args: None, emotion_csv_text=lambda *args: "",
        )
        return json.loads((self.output / "meeting_話者分離.json").read_text())

    def rows(self):
        with self.connect() as connection:
            return connection.execute("SELECT * FROM library_items").fetchall()

    def test_writer_importer_roundtrip_preserves_complete_metadata(self):
        profile = normalize_session_profile({"session_type": "meeting", "session_date": "2026-10-02",
                                            "objective": "Planning", "field_notes": "Meeting notes"})
        payload = self.write_result(session_profile=profile)
        self.import_outputs()
        [row] = self.rows()
        for source, column in (("speaker_profiles", "speaker_profiles_json"),
                               ("meeting_minutes", "meeting_minutes_json"),
                               ("session_profile", "session_profile_json"),
                               ("speaker_names", "speaker_names_json"),
                               ("segments", "segments_json")):
            self.assertEqual(json.loads(row[column]), payload[source], source)
        self.assertEqual(row["language"], payload["language"])
        self.import_outputs()
        self.assertEqual(len(self.rows()), 1)

    def test_legacy_json_keeps_minutes_without_inventing_session_type(self):
        payload = self.write_result()
        self.assertNotIn("session_profile", payload)
        self.import_outputs()
        [row] = self.rows()
        self.assertEqual(json.loads(row["meeting_minutes_json"]), payload["meeting_minutes"])
        self.assertEqual(json.loads(row["session_profile_json"]), normalize_session_profile(None))

    def test_bad_files_warn_and_do_not_abort_startup_or_other_imports(self):
        invalid = [[], None, "secret body", 42, {"segments": {}}, {"segments": [None]}]
        invalid.extend({"segments": [], "language": value} for value in ([], {}, 42, True))
        invalid.extend({"segments": [], "source": value} for value in ([], {}, 42, True))
        for index, value in enumerate(invalid):
            (self.output / f"bad-{index}_話者分離.json").write_text(json.dumps(value))
        (self.output / "bad-syntax_話者分離.json").write_text("{unfinished")
        self.write_result()
        released = []
        lifecycle = ApplicationLifecycle(
            acquire_instance_lock=lambda: True, release_instance_lock=lambda: released.append(True),
            initialize_library=lambda: None, recover_edits=lambda: [], repair_provenance=lambda: None,
            recover_deletes=lambda: [], repair_training=lambda: None, cleanup_uploads=lambda: None,
            import_outputs=self.import_outputs, report_edit_warning=lambda _: None,
            report_delete_warning=lambda _: None, spawn_watcher=lambda: None,
        )
        with self.assertLogs("gurumoji.services.output_import", level="WARNING") as logs:
            lifecycle.initialize()
        self.assertEqual(len(logs.output), len(invalid) + 1)
        self.assertNotIn("secret body", "\n".join(logs.output))
        self.assertEqual(released, [])
        self.assertEqual(len(self.rows()), 1)

    def test_import_database_failure_is_not_misreported_as_invalid_json(self):
        self.write_result()
        def fail_save(**kwargs):
            raise sqlite3.OperationalError("simulated database failure")
        importer = make_output_import(
            default_output_directory=lambda: self.output, database_connection=self.connect,
            library_row=lambda _: None, publish_input_vault=lambda *args, **kwargs: None,
            upsert_library_item=fail_save,
        )[-1]
        with self.assertRaisesRegex(sqlite3.OperationalError, "simulated database failure"):
            importer()
        self.assertEqual(self.rows(), [])


if __name__ == "__main__":
    unittest.main()
