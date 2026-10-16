"""Stage 1A: source preservation, transaction boundaries and missing media facts."""

import io
import json
import sqlite3
import tempfile
import threading
import shutil
import wave
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import app
from support import use_temporary_library
from gurumoji.services import conversation_projection as projection, media_assets, library_trash


class ProjectionSqlTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.addCleanup(self.db.close)
        self.db.execute("CREATE TABLE library_items(id TEXT PRIMARY KEY, speaker_profiles_json TEXT, segments_json TEXT)")
        self.db.execute("CREATE TABLE application_metadata(key TEXT PRIMARY KEY, value TEXT)")

    def insert(self, segments, profiles=None):
        self.db.execute("INSERT INTO library_items VALUES ('c', ?, ?)",
                        (json.dumps(profiles or {"S1": {"display_name": "架空話者", "global_speaker_id": "g1"}}), json.dumps(segments)))

    def test_initial_backfill_preserves_source_and_only_runs_once(self):
        self.insert([{"id": "a", "speaker": "S1", "start": 0, "end": 3, "text": "架空発話"}])
        before = self.db.execute("SELECT * FROM library_items").fetchall()
        projection.initialize(self.db)
        self.assertEqual(self.db.execute("SELECT * FROM conversation_segments").fetchall(), [("c", "a", 0, "S1", 0.0, 3.0, 4)])
        self.assertTrue(projection.check(self.db)["ok"])
        self.db.execute("UPDATE conversation_segments SET char_count=99")
        projection.initialize(self.db)
        self.assertEqual(self.db.execute("SELECT char_count FROM conversation_segments").fetchone()[0], 99)
        self.assertEqual(before, self.db.execute("SELECT * FROM library_items").fetchall())
        self.assertEqual(projection.check(self.db)["issues"][0]["reason"], "projection_mismatch")

    def test_invalid_json_and_wrong_shapes_never_block_source_save(self):
        projection.initialize(self.db)
        self.insert([{"id": "a", "text": "x"}])
        for source in ("{", "null", '"plain"', "42", "true", "{}"):
            with self.subTest(source=source):
                self.db.execute("UPDATE library_items SET segments_json=?, speaker_profiles_json=?", (source, source))
                self.assertEqual(self.db.execute("SELECT segments_json FROM library_items").fetchone()[0], source)
                self.assertEqual(self.db.execute("SELECT COUNT(*) FROM conversation_segments").fetchone()[0], 0)
        self.db.execute("UPDATE library_items SET speaker_profiles_json=?", ('{"S1":"plain","S2":null,"S3":{}}',))
        self.assertEqual(self.db.execute("SELECT speaker_label FROM conversation_speakers").fetchall(), [("S3",)])
        self.assertFalse(projection.check(self.db)["ok"])

    def test_id_validation_first_duplicate_wins_and_ordinal_is_original(self):
        projection.initialize(self.db)
        segments = [None, "text", 1, [], {}, {"id": 2}, {"id": ""}, {"id": "bad id"}, {"id": "あ"},
                    {"id": "z" * 81}, {"id": "ok-_1", "text": "先行", "start": 0, "end": None},
                    {"id": "ok-_1", "text": "重複"}, {"id": "b", "text": "後続", "start": "?", "end": 10}]
        self.insert(segments)
        self.assertEqual(self.db.execute("SELECT segment_id, ordinal, start, end, char_count FROM conversation_segments ORDER BY ordinal").fetchall(),
                         [("ok-_1", 10, 0.0, None, 2), ("b", 12, None, 10.0, 2)])
        issues = projection.check(self.db)["issues"]
        self.assertEqual(sum(value["reason"] == "invalid_segment_id" for value in issues), 10)
        self.assertEqual(sum(value["reason"] == "duplicate_segment_id" for value in issues), 1)
        self.assertNotIn("projection_mismatch", [value["reason"] for value in issues])

    def test_updates_deletes_and_rollback_are_atomic(self):
        projection.initialize(self.db)
        self.insert([{"id": "a", "text": "x"}])
        self.db.commit()
        self.db.execute("UPDATE library_items SET segments_json='[]', speaker_profiles_json='{}'")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM conversation_segments").fetchone()[0], 0)
        self.db.rollback()
        self.assertTrue(projection.check(self.db)["ok"])
        self.db.execute("UPDATE library_items SET id='renamed'")
        self.assertEqual(self.db.execute("SELECT item_id FROM conversation_segments").fetchone()[0], "renamed")
        self.db.execute("DELETE FROM library_items")
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM conversation_speakers").fetchone()[0], 0)
        self.db.rollback()
        self.assertTrue(projection.check(self.db)["ok"])

    def test_disposable_delete_tolerates_absent_future_tables_and_rolls_back(self):
        projection.initialize(self.db)
        self.insert([{"id": "a", "text": "x"}])
        for table in library_trash.DISPOSABLE_ITEM_TABLES[2:]:
            if table == "media_assets":
                continue
            self.db.execute(f"CREATE TABLE {table}(item_id TEXT)")
            self.db.executemany(f"INSERT INTO {table} VALUES (?)", [("c",), ("other",)])
        self.db.commit()
        library_trash.delete_disposable_rows(self.db, "c")
        self.assertEqual(self.db.execute("SELECT item_id FROM segment_labels").fetchall(), [("other",)])
        self.db.rollback()
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM segment_labels").fetchone()[0], 2)


class MediaFactsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "synthetic.mp4"
        self.path.write_bytes(b"synthetic media")

    def test_missing_files_tools_and_invalid_results_are_null_with_reasons(self):
        for path, tool, reason in ((self.path.parent / "missing", "ffprobe", "file_not_found"),
                                  (None, "ffprobe", "no_media_path"), (self.path, None, "ffprobe_unavailable")):
            with self.subTest(reason=reason), patch("gurumoji.services.outputs.shutil.which", return_value=tool):
                runner = unittest.mock.Mock()
                facts = media_assets.inspect(path, imported_at="2026-01-01", run_subprocess=runner)
                self.assertIsNone(facts["duration_seconds"])
                self.assertEqual(json.loads(facts["unknown_reasons_json"])["duration_seconds"], reason)
                runner.assert_not_called()
        with patch("gurumoji.services.outputs.shutil.which", return_value="ffprobe"):
            for result in (SimpleNamespace(returncode=1, stdout=""), SimpleNamespace(returncode=0, stdout="bad"),
                           SimpleNamespace(returncode=0, stdout='{"format":{"duration":"NaN"}}')):
                facts = media_assets.inspect(self.path, imported_at="2026-01-01", run_subprocess=lambda *a, **k: result)
                self.assertIsNone(facts["duration_seconds"])
                self.assertTrue(json.loads(facts["unknown_reasons_json"])["duration_seconds"])

    def test_probe_preserves_zero_and_distinguishes_three_dates(self):
        payload = {"format": {"duration": "0", "format_name": "mp4", "tags": {"creation_time": "2020-01-01T01:02:03Z"}},
                   "streams": [{"codec_type": "video", "codec_name": "h264", "width": 1280, "height": 720,
                                "avg_frame_rate": "30000/1001"}, {"codec_type": "audio", "codec_name": "aac",
                                                                "sample_rate": "48000", "channels": 2}],
                   "program_version": {"version": "synthetic-version"}}
        calls = []
        def run(command, **options):
            calls.append((command, options))
            return SimpleNamespace(returncode=0, stdout=json.dumps(payload))
        with patch("gurumoji.services.outputs.shutil.which", return_value="ffprobe"):
            facts = media_assets.inspect(self.path, imported_at="2026-01-01", run_subprocess=run)
        self.assertEqual(facts["duration_seconds"], 0)
        self.assertEqual(facts["media_created_at"], "2020-01-01T01:02:03Z")
        self.assertEqual(facts["imported_at"], "2026-01-01")
        self.assertNotEqual(facts["file_modified_at"], facts["imported_at"])
        self.assertAlmostEqual(facts["fps"], 29.97002997)
        self.assertEqual(json.loads(facts["unknown_reasons_json"]), {})
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][1]["timeout"], 30)

    @unittest.skipUnless(shutil.which("ffprobe"), "ffprobe is unavailable")
    def test_real_ffprobe_reads_only_synthetic_wave(self):
        path = self.path.with_suffix(".wav")
        with wave.open(str(path), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(8000)
            audio.writeframes(b"\0\0" * 2000)
        before = path.read_bytes()
        facts = media_assets.inspect(path, imported_at="2026-01-01")
        self.assertAlmostEqual(facts["duration_seconds"], 0.25)
        self.assertEqual(facts["sample_rate"], 8000)
        self.assertEqual(facts["channels"], 1)
        self.assertIsNone(facts["media_created_at"])
        self.assertIsNone(facts["width"])
        self.assertTrue(facts["probe_tool_version"])
        self.assertEqual(before, path.read_bytes())


class ProjectionWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gurumoji-1a-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for name, folder in (("DATA_DIRECTORY", "data"), ("MEDIA_DIRECTORY", "media"),
                             ("THUMBNAIL_DIRECTORY", "thumbnails"), ("TRAINING_AUDIO_DIRECTORY", "training")):
            patcher = patch.object(app, name, self.root / folder)
            patcher.start()
            self.addCleanup(patcher.stop)
        use_temporary_library(self, self.root, output=self.root / "output")
        self.client = app.app.test_client()
        self.create()

    def create(self, identity="c", media_path=None):
        return app.upsert_library_item(item_id=identity, source_name="架空会話.wav", output_dir=self.root / identity,
            media_path=media_path, language="ja", segments=[{"id": "a", "speaker": "S1", "start": 0, "end": 9, "text": "架空の回答"}],
            speaker_names={"S1": "架空話者"}, outline=None, emotion_analysis=None, files=[], write_srt=False, write_json=True)

    def assert_consistent(self):
        with app.database_connection() as db:
            self.assertTrue(projection.check(db)["ok"], projection.check(db))

    def test_import_edit_identification_and_registry_csv_keep_projection_consistent(self):
        self.assert_consistent()
        row = app.library_row("c")
        with patch.object(app, "publish_input_vault"), patch.object(app, "refresh_archive_index"):
            edited = self.client.put("/api/library/c", json={"revision_count": 0, "source_name": "架空会話.wav",
                "segments": app.row_segments(row), "speaker_names": {"S1": "編集名"},
                "speaker_profiles": {"S1": {"display_name": "編集名", "global_speaker_id": "g1"}}})
            self.assertEqual(edited.status_code, 200, edited.get_json())
        self.assert_consistent()
        with patch.object(app, "load_token_config", return_value=object()), \
             patch.object(app, "configured_ai_credentials", return_value=("synthetic", "synthetic-model")), \
             patch.object(app, "detect_speaker_names_with_ai", return_value={"S1": "識別名"}), \
             patch.object(app, "publish_input_vault"), patch.object(app, "refresh_archive_index"):
            identified = self.client.post("/api/library/c/speaker-identification", json={"provider": "openai", "revision_count": edited.get_json()["revision_count"]})
            self.assertEqual(identified.status_code, 200, identified.get_json())
        self.assert_consistent()
        revision = self.client.get("/api/speakers").get_json()["registry_revision"]
        with patch.object(app, "refresh_archive_index"):
            imported = self.client.post("/api/speakers/import", data={"registry_revision": str(revision),
                "csv_file": (io.BytesIO("参加者コード,氏名,自由属性\nP1,架空話者,架空値\n".encode("utf-8")), "synthetic.csv")}, content_type="multipart/form-data")
        self.assertEqual(imported.status_code, 200, imported.get_json())
        self.assert_consistent()

    def test_delete_restore_rebuilds_only_json_projections(self):
        with app.database_connection() as db:
            rows = library_trash.snapshot_rows(db, "c")
        self.assertNotIn("media_assets", rows)
        with patch.object(app, "retire_input_vault"):
            deleted = self.client.delete("/api/library/c")
        self.assertEqual(deleted.status_code, 200, deleted.get_json())
        with app.database_connection() as db:
            for table in ("conversation_speakers", "conversation_segments", "media_assets"):
                self.assertEqual(db.execute(f"SELECT COUNT(*) FROM {table} WHERE item_id='c'").fetchone()[0], 0)
        entries = self.client.get("/api/library/trash").get_json()
        self.assertTrue(entries)
        # Use the existing manifest restoration path without involving actual media.
        entry = next(app.trash_directory().glob("*/manifest.json")).parent
        restored = library_trash.restore(app.trash_directory(), entry.name, connect=app.database_connection,
                                        targets={"media": self.root / "media", "thumbnail": self.root / "thumbnails"},
                                        move=lambda source, target: None)
        self.assertEqual(restored, "c")
        self.assert_consistent()
        with app.database_connection() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM media_assets").fetchone()[0], 0)

    def test_media_summary_filters_sort_and_readonly_details(self):
        self.create("b")
        with app.database_connection() as db:
            for identity, duration, recording in (("c", 0, "2026-02-01T00:00:00Z"), ("b", 20, "2026-01-01")):
                facts = media_assets.inspect(None, imported_at="2026-03-01")
                facts.update(duration_seconds=duration, media_created_at=recording)
                media_assets.save(db, identity, "stored", facts)
        listing = self.client.get("/api/library?sort=media_duration_desc").get_json()["items"]
        self.assertEqual([value["id"] for value in listing], ["b", "c"])
        self.assertEqual(listing[1]["media_duration_seconds"], 0)
        self.assertEqual(listing[1]["duration"], 9)
        filtered = self.client.get("/api/library?recorded_from=2026-02-01&media_duration_max=0").get_json()["items"]
        self.assertEqual([value["id"] for value in filtered], ["c"])
        for query in ("media_duration_min=nan", "media_duration_min=-1", "recorded_from=bad", "media_duration_min=5&media_duration_max=2"):
            self.assertEqual(self.client.get("/api/library?" + query).status_code, 400)
        with app.database_connection() as db:
            before = list(db.iterdump())
        details = self.client.get("/api/library/c").get_json()
        self.assertEqual(details["media_assets"][0]["path_status"], "no_media_path")
        with patch.object(app, "system_activity_snapshot", return_value={}):
            diagnostics = self.client.get("/api/system/activity?library_check=1").get_json()
        self.assertTrue(diagnostics["library_projection"]["ok"])
        with app.database_connection() as db:
            self.assertEqual(list(db.iterdump()), before)

    def test_backfill_is_deferred_idempotent_and_does_not_resurrect_deleted_rows(self):
        with app.database_connection() as db:
            db.execute("DELETE FROM media_assets")
        with patch.object(media_assets, "inspect", wraps=media_assets.inspect) as inspect:
            app.initialize_library()
            inspect.assert_not_called()
            backfill = media_assets.Backfill(app.database_connection, app.library_write_lock)
            backfill.run(threading.Event())
            self.assertEqual(backfill.snapshot()["status"], "completed")
            self.assertEqual(inspect.call_count, 1)
            backfill.run(threading.Event())
            self.assertEqual(inspect.call_count, 1)
        with app.database_connection() as db:
            db.execute("DELETE FROM library_items WHERE id='c'")
            media_assets.save(db, "c", "stored", media_assets.inspect(None, imported_at="2026-01-01"))
            self.assertEqual(db.execute("SELECT COUNT(*) FROM media_assets").fetchone()[0], 0)

    def test_backfill_cancellation_prevents_post_shutdown_write_and_probe_errors_are_visible(self):
        with app.database_connection() as db:
            db.execute("DELETE FROM media_assets")
        stop = threading.Event()
        facts = media_assets.inspect(None, imported_at="2026-01-01")
        def cancel(*args, **options):
            stop.set()
            return facts
        worker = media_assets.Backfill(app.database_connection, app.library_write_lock)
        with patch.object(media_assets, "inspect", side_effect=cancel):
            worker.run(stop)
        self.assertEqual(worker.snapshot()["status"], "cancelled")
        with app.database_connection() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM media_assets").fetchone()[0], 0)
        facts["unknown_reasons_json"] = '{"duration_seconds":"ffprobe_failed"}'
        worker = media_assets.Backfill(app.database_connection, app.library_write_lock)
        with patch.object(media_assets, "inspect", return_value=facts):
            worker.run(threading.Event())
        self.assertEqual(worker.snapshot()["status"], "completed_with_errors")
        self.assertEqual(worker.snapshot()["failed"], 1)
        self.assertEqual(worker.snapshot()["reasons"], {"ffprobe_failed": 1})

    def test_display_checks_missing_paths_and_hides_raw_probe_tags_without_writing(self):
        path = self.root / "vanished.wav"
        path.write_bytes(b"synthetic")
        facts = media_assets.inspect(path, imported_at="2026-01-01", run_subprocess=lambda *a, **k: SimpleNamespace(returncode=1, stdout=""))
        facts["probe_json"] = '{"format":{"tags":{"private":"synthetic private tag"}}}'
        with app.database_connection() as db:
            media_assets.save(db, "c", "original", facts)
        path.unlink()
        with app.database_connection() as db:
            before = list(db.iterdump())
            displayed = next(value for value in media_assets.public(db, "c", reveal_paths=False) if value["role"] == "original")
            self.assertEqual(displayed["path_status"], "file_not_found")
            self.assertFalse(displayed["path_exists"])
            self.assertIsNone(displayed["path"])
            self.assertIsNone(displayed["original_filename"])
            self.assertNotIn("probe_json", displayed)
            self.assertEqual(before, list(db.iterdump()))


if __name__ == "__main__":
    unittest.main()
