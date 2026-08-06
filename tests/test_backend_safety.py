import base64
import csv
import io
import json
import math
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import app
from werkzeug.exceptions import RequestEntityTooLarge


class RequestSecurityTests(unittest.TestCase):
    def setUp(self):
        with app.jobs_lock:
            app.jobs.clear()
            app._job_admission_id = None
        self.client = app.app.test_client()

    def tearDown(self):
        with app.jobs_lock:
            app.jobs.clear()
            app._job_admission_id = None

    def test_rejects_untrusted_host_and_cross_site_api_requests(self):
        untrusted = self.client.get("/api/config", headers={"Host": "attacker.example"})
        self.assertEqual(untrusted.status_code, 400)

        cross_site = self.client.get(
            "/api/config",
            headers={"Sec-Fetch-Site": "cross-site"},
        )
        self.assertEqual(cross_site.status_code, 403)

        bad_origin = self.client.post(
            "/api/jobs/missing/cancel",
            headers={
                "Origin": "https://attacker.example",
                "Sec-Fetch-Site": "cross-site",
            },
        )
        self.assertEqual(bad_origin.status_code, 403)

    def test_same_origin_proxy_metadata_allows_rewritten_origin(self):
        response = self.client.post(
            "/api/jobs/missing/cancel",
            headers={
                "Origin": "https://random-tunnel.example",
                "Sec-Fetch-Site": "same-origin",
                "X-Gurumoji-Request": "1",
            },
        )
        self.assertEqual(response.status_code, 404)

    def test_remote_mode_requires_auth_and_csrf_header(self):
        token = "a-secure-remote-token-123456"
        credentials = base64.b64encode(f"user:{token}".encode()).decode()
        authorization = f"Basic {credentials}"
        with (
            patch.object(app, "REMOTE_ACCESS_ENABLED", True),
            patch.object(app, "REMOTE_ACCESS_TOKEN", token),
            patch.object(app, "REMOTE_LOCAL_PATHS_ENABLED", False),
        ):
            unauthenticated = self.client.get("/")
            self.assertEqual(unauthenticated.status_code, 401)
            self.assertIn("Basic", unauthenticated.headers["WWW-Authenticate"])

            authenticated = self.client.get("/", headers={"Authorization": authorization})
            self.assertEqual(authenticated.status_code, 200)

            missing_csrf = self.client.post(
                "/api/jobs/missing/cancel",
                headers={"Authorization": authorization},
            )
            self.assertEqual(missing_csrf.status_code, 403)
            self.assertIn("CSRF", missing_csrf.get_json()["error"])

            accepted = self.client.post(
                "/api/jobs/missing/cancel",
                headers={
                    "Authorization": authorization,
                    "X-Gurumoji-Request": "1",
                },
            )
            self.assertEqual(accepted.status_code, 404)

    def test_remote_local_paths_require_and_honor_the_explicit_opt_in(self):
        token = "a-secure-remote-token-123456"
        authorization = f"Bearer {token}"
        headers = {"Authorization": authorization, "Host": "localhost"}
        remote_address = {"REMOTE_ADDR": "192.0.2.10"}
        with (
            patch.object(app, "REMOTE_ACCESS_ENABLED", True),
            patch.object(app, "REMOTE_ACCESS_TOKEN", token),
            patch.object(app, "REMOTE_LOCAL_PATHS_ENABLED", False),
        ):
            disabled = self.client.get(
                "/api/config", headers=headers, environ_base=remote_address
            )
        with (
            patch.object(app, "REMOTE_ACCESS_ENABLED", True),
            patch.object(app, "REMOTE_ACCESS_TOKEN", token),
            patch.object(app, "REMOTE_LOCAL_PATHS_ENABLED", True),
        ):
            enabled = self.client.get(
                "/api/config", headers=headers, environ_base=remote_address
            )

        self.assertEqual(disabled.status_code, 200)
        self.assertEqual(disabled.get_json()["default_output_dir"], "")
        self.assertEqual(enabled.status_code, 200)
        self.assertTrue(enabled.get_json()["default_output_dir"])

    def test_remote_job_diagnostics_hide_absolute_paths_without_opt_in(self):
        token = "a-secure-remote-token-123456"
        job = app.JobRecord(
            id="f" * 32,
            source_name="sample.wav",
            output_dir=Path(r"C:\Users\alice\private-output"),
            write_srt=False,
            write_json=True,
            status="failed",
            message=r"Reading C:\Users\alice\secret.wav",
            logs=["safe status", "Failed at /home/alice/private/input.wav"],
            error=r"Cannot open \\server\private\secret.wav",
            output_warning="See file:///C:/Users/alice/private-output/result.json",
        )
        with app.jobs_lock:
            app.jobs[job.id] = job
        request_args = {
            "headers": {"Authorization": f"Bearer {token}", "Host": "localhost"},
            "environ_base": {"REMOTE_ADDR": "192.0.2.10"},
        }

        with (
            patch.object(app, "REMOTE_ACCESS_ENABLED", True),
            patch.object(app, "REMOTE_ACCESS_TOKEN", token),
            patch.object(app, "REMOTE_LOCAL_PATHS_ENABLED", False),
        ):
            hidden_response = self.client.get(f"/api/jobs/{job.id}", **request_args)
        hidden = hidden_response.get_json()
        self.assertEqual(hidden_response.status_code, 200)
        self.assertEqual(hidden["output_dir"], "")
        self.assertEqual(hidden["message"], app.HIDDEN_LOCAL_PATH_MESSAGE)
        self.assertEqual(hidden["logs"], ["safe status", app.HIDDEN_LOCAL_PATH_MESSAGE])
        self.assertEqual(hidden["error"], app.HIDDEN_LOCAL_PATH_MESSAGE)
        self.assertEqual(hidden["output_warning"], app.HIDDEN_LOCAL_PATH_MESSAGE)
        self.assertNotIn("alice", json.dumps(hidden))
        self.assertNotIn("server", json.dumps(hidden))

        with (
            patch.object(app, "REMOTE_ACCESS_ENABLED", True),
            patch.object(app, "REMOTE_ACCESS_TOKEN", token),
            patch.object(app, "REMOTE_LOCAL_PATHS_ENABLED", True),
        ):
            revealed_response = self.client.get(f"/api/jobs/{job.id}", **request_args)
        revealed = revealed_response.get_json()
        self.assertEqual(revealed_response.status_code, 200)
        self.assertIn("alice", revealed["message"])
        self.assertIn("server", revealed["error"])

    def test_remote_json_diagnostic_sanitizer_covers_nested_api_errors(self):
        payload = {
            "learning_warning": r"cache failed at C:\Users\alice\training.csv",
            "nested": {
                "restore_errors": ["rename failed:/home/alice/private.wav"],
                "safe_url": "/api/library/item/files/result.json",
            },
        }
        sanitized = app.sanitize_remote_json_payload(payload)
        self.assertEqual(sanitized["learning_warning"], app.HIDDEN_LOCAL_PATH_MESSAGE)
        self.assertEqual(
            sanitized["nested"]["restore_errors"],
            [app.HIDDEN_LOCAL_PATH_MESSAGE],
        )
        self.assertEqual(
            sanitized["nested"]["safe_url"],
            "/api/library/item/files/result.json",
        )

        token = "a-secure-remote-token-123456"
        machine = {"gpu": {"reason": "failed:/home/alice/private/model.bin"}}
        with (
            patch.object(app, "REMOTE_ACCESS_ENABLED", True),
            patch.object(app, "REMOTE_ACCESS_TOKEN", token),
            patch.object(app, "REMOTE_LOCAL_PATHS_ENABLED", False),
            patch.object(app, "get_machine_profile", return_value=machine),
            patch.object(app, "load_token_config", return_value=app.TokenConfig()),
        ):
            response = self.client.get(
                "/api/config",
                headers={"Authorization": f"Bearer {token}", "Host": "localhost"},
                environ_base={"REMOTE_ADDR": "192.0.2.10"},
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["machine"]["gpu"]["reason"],
            app.HIDDEN_LOCAL_PATH_MESSAGE,
        )

    def test_sensitive_responses_are_not_cached_and_have_security_headers(self):
        response = self.client.get("/api/config")
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertEqual(response.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertIn("frame-ancestors 'none'", response.headers["Content-Security-Policy"])

    def test_non_loopback_main_bind_requires_explicit_remote_opt_in(self):
        with (
            patch.dict("os.environ", {"MOJIOKOSI_HOST": "0.0.0.0"}, clear=False),
            patch.object(app, "REMOTE_ACCESS_ENABLED", False),
            patch.object(app, "initialize_application") as initialize,
            patch.object(app.app, "run") as run,
        ):
            self.assertEqual(app.main(), 2)
            initialize.assert_not_called()
            run.assert_not_called()


class InputAndExportSafetyTests(unittest.TestCase):
    def setUp(self):
        self.client = app.app.test_client()

    def test_stream_limits_reject_and_remove_partial_uploads(self):
        class Upload:
            def __init__(self, content: bytes):
                self.stream = io.BytesIO(content)

        with tempfile.TemporaryDirectory(prefix="gurumoji-upload-limit-") as temporary:
            target = Path(temporary) / "partial.wav"
            with self.assertRaises(RequestEntityTooLarge):
                app.save_upload_limited(Upload(b"12345"), target, 4)
            self.assertFalse(target.exists())
        with self.assertRaises(RequestEntityTooLarge):
            app.read_upload_limited(Upload(b"12345"), 4)

    def test_route_specific_csv_and_json_limits_return_413(self):
        with patch.object(app, "MAX_CSV_UPLOAD_BYTES", 4):
            csv_response = self.client.post(
                "/api/speakers/import",
                data={
                    "registry_revision": "0",
                    "csv_file": (io.BytesIO(b"12345"), "large.csv"),
                },
                content_type="multipart/form-data",
            )
        self.assertEqual(csv_response.status_code, 413)

        with patch.object(app, "MAX_JSON_REQUEST_BYTES", 8):
            json_response = self.client.put(
                "/api/jobs/missing/transcript",
                data=b'{"value":"too large"}',
                content_type="application/json",
            )
        self.assertEqual(json_response.status_code, 413)

    def test_nonfinite_transcript_times_and_form_numbers_are_rejected(self):
        for value in (float("nan"), float("inf"), float("-inf"), 10 ** 10000):
            with self.assertRaises(ValueError):
                app.normalize_edited_segments(
                    "finite-test",
                    [{"start": value, "end": 1.0, "speaker": "S1", "text": "x"}],
                )
        with app.app.test_request_context(
            "/api/jobs", method="POST", data={"vad_onset": "nan"}
        ):
            with self.assertRaises(ValueError):
                app.parse_optional_float("vad_onset", 0.35, 0.05, 0.95)

    def test_unc_paths_are_rejected_without_accessing_the_share(self):
        self.assertTrue(app.is_unc_path(r"\\server\share\meeting.wav"))
        with self.assertRaises(ValueError):
            app.resolve_local_media_path(r"\\server\share\meeting.wav")
        with self.assertRaises(ValueError):
            app.prepare_output_root(r"\\server\share\output")

    def test_speaker_csv_escapes_formulas_in_headers_and_values(self):
        record = {
            "participant_code": "=1+1",
            "display_name": "+name",
            "pseudonym": "@alias",
            "default_role": "participant",
            "organization": "-org",
            "department": "department",
            "job_title": "title",
            "consent_status": "unknown",
            "recording_consent": "unknown",
            "confidentiality_status": "unknown",
            "tags": ["=tag"],
            "notes": " @note",
            "active": True,
            "attributes": {"=custom header": "+custom value"},
        }
        rows = list(csv.reader(io.StringIO(
            app.speaker_registry_csv_bytes([record]).decode("utf-8-sig")
        )))
        flattened = [cell for row in rows for cell in row]
        for expected in ("'=1+1", "'+name", "'@alias", "'-org", "'=custom header", "'+custom value"):
            self.assertIn(expected, flattened)

    def test_source_thumbnail_requires_posted_json_path(self):
        client = app.app.test_client()
        self.assertEqual(client.get("/api/source-thumbnail?path=C:/secret.mp4").status_code, 405)
        self.assertEqual(client.post("/api/source-thumbnail", json={}).status_code, 400)

        with tempfile.TemporaryDirectory(prefix="gurumoji-thumbnail-") as temporary:
            root = Path(temporary)
            source = root / "source.mp4"
            thumbnail = root / "thumbnail.jpg"
            source.write_bytes(b"video")
            thumbnail.write_bytes(b"jpeg")
            with (
                patch.object(app, "resolve_local_media_path", return_value=source) as resolve,
                patch.object(app, "generate_video_thumbnail", return_value=thumbnail),
            ):
                response = client.post("/api/source-thumbnail", json={"path": str(source)})
            self.assertEqual(response.status_code, 200)
            resolve.assert_called_once_with(str(source))
            response.close()

    def test_remote_training_status_hides_urls_and_downloads_are_forbidden(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-training-") as temporary:
            root = Path(temporary)
            database = root / "library.sqlite3"
            jsonl = root / "corrections.jsonl"
            manifest = root / "manifest.csv"
            jsonl.write_text('{"ready_for_kushinada": true}\n', encoding="utf-8")
            manifest.write_text("audio_path,text\nC:/secret.wav,test\n", encoding="utf-8")
            with (
                patch.object(app, "REMOTE_ACCESS_ENABLED", True),
                patch.object(app, "remote_auth_valid", return_value=True),
                patch.object(app, "DATABASE_FILE", database),
                patch.object(app, "TRAINING_JSONL_FILE", jsonl),
                patch.object(app, "TRAINING_MANIFEST_FILE", manifest),
            ):
                app.initialize_library()
                event = {
                    "event_id": "f" * 32,
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "ready_for_kushinada": True,
                }
                with app.database_connection() as connection:
                    connection.execute(
                        "INSERT INTO training_events (event_id, payload_json, created_at) "
                        "VALUES (?, ?, ?)",
                        (event["event_id"], json.dumps(event), event["created_at"]),
                    )
                client = app.app.test_client()
                status = client.get("/api/training")
                raw_jsonl = client.get("/api/training/corrections.jsonl")
                raw_manifest = client.get("/api/training/manifest.csv")
            self.assertEqual(status.status_code, 200)
            self.assertIsNone(status.get_json()["jsonl_url"])
            self.assertIsNone(status.get_json()["manifest_url"])
            self.assertEqual(raw_jsonl.status_code, 403)
            self.assertEqual(raw_manifest.status_code, 403)


class AtomicAuxiliaryArtifactTests(unittest.TestCase):
    def test_output_promotion_restores_previous_file_on_process_interrupt(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-promotion-interrupt-") as temporary:
            root = Path(temporary)
            output = root / "output"
            staging = root / ".edit-staging-test"
            output.mkdir()
            staging.mkdir()
            target = output / "transcript.json"
            staged = staging / "transcript.json"
            target.write_bytes(b"old")
            staged.write_bytes(b"new")

            with self.assertRaises(KeyboardInterrupt):
                with app.promote_staged_files(staging, output, [staged]):
                    raise KeyboardInterrupt()

            self.assertEqual(target.read_bytes(), b"old")
            self.assertFalse(staging.exists())

    def test_output_promotion_retains_backup_when_rollback_restore_fails(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-promotion-recovery-") as temporary:
            root = Path(temporary)
            output = root / "output"
            staging = root / ".edit-staging-test"
            output.mkdir()
            staging.mkdir()
            target = output / "transcript.json"
            staged = staging / "transcript.json"
            target.write_bytes(b"old")
            staged.write_bytes(b"new")
            real_replace = os.replace

            def fail_backup_restore(source, destination):
                if ".previous" in str(source):
                    raise OSError("locked target")
                return real_replace(source, destination)

            with patch.object(app.os, "replace", side_effect=fail_backup_restore):
                with self.assertRaisesRegex(OSError, "recovery files were retained"):
                    with app.promote_staged_files(staging, output, [staged]):
                        raise KeyboardInterrupt()

            self.assertTrue((staging / ".previous" / "transcript.json").is_file())
            self.assertEqual(
                (staging / ".previous" / "transcript.json").read_bytes(),
                b"old",
            )

    def test_training_status_reports_canonical_database_failure(self):
        with patch.object(
            app,
            "training_events_from_connection",
            side_effect=OSError("corrupt canonical data"),
        ):
            response = app.app.test_client().get("/api/training")

        self.assertEqual(response.status_code, 500)
        self.assertIn("error", response.get_json())

    def test_thumbnail_timeout_does_not_leave_a_partial_cache(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-thumbnail-timeout-") as temporary:
            root = Path(temporary)
            source = root / "source.mp4"
            target = root / "cached.jpg"
            source.write_bytes(b"video")

            def timeout(command, **_kwargs):
                Path(command[-1]).write_bytes(b"partial")
                raise subprocess.TimeoutExpired(command, 60)

            with (
                patch.object(app.shutil, "which", return_value="ffmpeg"),
                patch.object(app, "thumbnail_cache_path", return_value=target),
                patch.object(app.subprocess, "run", side_effect=timeout),
            ):
                with self.assertRaises(RuntimeError):
                    app.generate_video_thumbnail(source)

            self.assertFalse(target.exists())
            self.assertEqual([path.name for path in root.iterdir()], [source.name])

    def test_training_clip_timeout_removes_partial_temporary_file(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-training-timeout-") as temporary:
            root = Path(temporary)
            media = root / "media.wav"
            audio_root = root / "audio"
            media.write_bytes(b"audio")

            def timeout(command, **_kwargs):
                Path(command[-1]).write_bytes(b"partial")
                raise subprocess.TimeoutExpired(command, 180)

            with (
                patch.object(app.shutil, "which", return_value="ffmpeg"),
                patch.object(app, "TRAINING_AUDIO_DIRECTORY", audio_root),
                patch.object(app.subprocess, "run", side_effect=timeout),
            ):
                with self.assertRaises(subprocess.TimeoutExpired):
                    app.extract_training_clip(
                        media,
                        "a" * 32,
                        "b" * 32,
                        {"start": 0, "end": 1},
                    )

            self.assertEqual(list(audio_root.rglob("*.*")), [])

    def test_training_append_failure_rolls_back_both_files_and_new_clips(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-training-atomic-") as temporary:
            root = Path(temporary)
            training = root / "training"
            audio_root = training / "audio"
            jsonl = training / "corrections.jsonl"
            manifest = training / "manifest.csv"
            database = root / "library.sqlite3"
            media = root / "media.wav"
            media.write_bytes(b"audio")
            row = {
                "id": "c" * 32,
                "source_name": "meeting.wav",
                "media_path": str(media),
            }
            before = [{"id": "segment-1", "start": 0, "end": 1, "speaker": "S1", "text": "old"}]
            after = [{"id": "segment-1", "start": 0, "end": 1, "speaker": "S1", "text": "new"}]

            def create_clip(_media, item_id, event_id, _segment):
                destination = audio_root / item_id / f"{event_id}.wav"
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(b"clip")
                return destination

            with (
                patch.object(app, "TRAINING_DIRECTORY", training),
                patch.object(app, "TRAINING_AUDIO_DIRECTORY", audio_root),
                patch.object(app, "TRAINING_JSONL_FILE", jsonl),
                patch.object(app, "TRAINING_MANIFEST_FILE", manifest),
                patch.object(app, "DATABASE_FILE", database),
                patch.object(app, "extract_training_clip", side_effect=create_clip),
                patch.object(app.csv.DictWriter, "writerow", side_effect=OSError("disk full")),
            ):
                app.initialize_library()
                with self.assertRaises(OSError):
                    app.record_training_corrections(row, before, after, {}, {})
                with app.database_connection() as connection:
                    event_count = connection.execute(
                        "SELECT COUNT(*) FROM training_events"
                    ).fetchone()[0]

            self.assertFalse(jsonl.exists())
            self.assertFalse(manifest.exists())
            self.assertEqual(list(audio_root.rglob("*.wav")), [])
            self.assertEqual(event_count, 0)

    def test_training_repair_migrates_legacy_once_and_rebuilds_derived_files(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-training-repair-") as temporary:
            root = Path(temporary)
            training = root / "training"
            audio_root = training / "audio"
            jsonl = training / "corrections.jsonl"
            manifest = training / "manifest.csv"
            database = root / "library.sqlite3"
            event_id = "d" * 32
            clip = audio_root / ("e" * 32) / f"{event_id}.wav"
            orphan = audio_root / ("e" * 32) / f"{'f' * 32}.wav"
            clip.parent.mkdir(parents=True)
            clip.write_bytes(b"referenced")
            orphan.write_bytes(b"orphan")
            event = {
                "schema_version": "1.0",
                "event_id": event_id,
                "created_at": "2026-01-01T00:00:00+00:00",
                "transcript_id": "e" * 32,
                "segment_id": "segment-1",
                "operation": "update",
                "source_name": "meeting.wav",
                "source_media": None,
                "audio_clip": str(clip),
                "before": {"text": "old"},
                "after": {"text": "new", "emotion": "neu"},
                "ready_for_kushinada": True,
            }
            training.mkdir(parents=True, exist_ok=True)
            jsonl.write_text(
                json.dumps(event, ensure_ascii=False) + "\n{partial",
                encoding="utf-8",
            )
            manifest.write_text("stale", encoding="utf-8")

            with (
                patch.object(app, "TRAINING_DIRECTORY", training),
                patch.object(app, "TRAINING_AUDIO_DIRECTORY", audio_root),
                patch.object(app, "TRAINING_JSONL_FILE", jsonl),
                patch.object(app, "TRAINING_MANIFEST_FILE", manifest),
                patch.object(app, "DATABASE_FILE", database),
            ):
                app.initialize_library()
                app.repair_training_artifacts()
                migrated_lines = jsonl.read_text(encoding="utf-8").splitlines()
                self.assertEqual([json.loads(line)["event_id"] for line in migrated_lines], [event_id])
                self.assertIn(event_id, manifest.read_text(encoding="utf-8-sig"))
                self.assertTrue(clip.is_file())
                self.assertFalse(orphan.exists())

                # A crash-era/stale derived record must not be re-imported after
                # the one-time migration marker has been committed.
                stale_event = {**event, "event_id": "a" * 32}
                jsonl.write_text(json.dumps(stale_event) + "\n", encoding="utf-8")
                manifest.write_text("broken", encoding="utf-8")
                app.repair_training_artifacts()
                repaired = [
                    json.loads(line)["event_id"]
                    for line in jsonl.read_text(encoding="utf-8").splitlines()
                ]
                with app.database_connection() as connection:
                    stored_count = connection.execute(
                        "SELECT COUNT(*) FROM training_events"
                    ).fetchone()[0]

            self.assertEqual(repaired, [event_id])
            self.assertEqual(stored_count, 1)

    def test_training_repair_commits_migration_when_derived_cache_is_locked(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-training-locked-") as temporary:
            root = Path(temporary)
            training = root / "training"
            jsonl = training / "corrections.jsonl"
            manifest = training / "manifest.csv"
            database = root / "library.sqlite3"
            event = {
                "event_id": "9" * 32,
                "created_at": "2026-01-01T00:00:00+00:00",
                "before": {"text": "old"},
                "after": {"text": "new"},
            }
            training.mkdir(parents=True)
            jsonl.write_text(json.dumps(event) + "\n", encoding="utf-8")

            with (
                patch.object(app, "DATABASE_FILE", database),
                patch.object(app, "TRAINING_DIRECTORY", training),
                patch.object(app, "TRAINING_AUDIO_DIRECTORY", training / "audio"),
                patch.object(app, "TRAINING_JSONL_FILE", jsonl),
                patch.object(app, "TRAINING_MANIFEST_FILE", manifest),
                patch.object(app, "write_training_exports", side_effect=OSError("locked")),
                patch.object(app.app.logger, "exception") as logged,
            ):
                app.initialize_library()
                app.repair_training_artifacts()
                with app.database_connection() as connection:
                    migrated = connection.execute(
                        "SELECT value FROM application_metadata "
                        "WHERE key = 'training_events_migrated'"
                    ).fetchone()[0]
                    event_count = connection.execute(
                        "SELECT COUNT(*) FROM training_events"
                    ).fetchone()[0]

            self.assertEqual(migrated, "1")
            self.assertEqual(event_count, 1)
            logged.assert_called_once()


class ExistingOutputImportSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="gurumoji-import-safety-")
        self.root = Path(self.temporary.name)
        self.output = self.root / "output"
        self.output.mkdir()
        self.originals = {
            "DATABASE_FILE": app.DATABASE_FILE,
            "DEFAULT_OUTPUT_DIRECTORY": app.DEFAULT_OUTPUT_DIRECTORY,
            "TRAINING_DIRECTORY": app.TRAINING_DIRECTORY,
            "TRAINING_AUDIO_DIRECTORY": app.TRAINING_AUDIO_DIRECTORY,
            "TRAINING_JSONL_FILE": app.TRAINING_JSONL_FILE,
            "TRAINING_MANIFEST_FILE": app.TRAINING_MANIFEST_FILE,
        }
        app.DATABASE_FILE = self.root / "library.sqlite3"
        app.DEFAULT_OUTPUT_DIRECTORY = self.output
        app.TRAINING_DIRECTORY = self.root / "training"
        app.TRAINING_AUDIO_DIRECTORY = app.TRAINING_DIRECTORY / "audio"
        app.TRAINING_JSONL_FILE = app.TRAINING_DIRECTORY / "corrections.jsonl"
        app.TRAINING_MANIFEST_FILE = app.TRAINING_DIRECTORY / "manifest.csv"
        app.initialize_library()
        self.client = app.app.test_client()

    def tearDown(self):
        for name, value in self.originals.items():
            setattr(app, name, value)
        with app.jobs_lock:
            app.jobs.clear()
            app._job_admission_id = None
        self.temporary.cleanup()

    @staticmethod
    def write_result(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({
                "source": f"{path.stem}.wav",
                "language": "ja",
                "speaker_names": {},
                "segments": [{
                    "id": "segment-1",
                    "start": 0.0,
                    "end": 1.0,
                    "speaker": "S1",
                    "text": text,
                }],
            }, ensure_ascii=False),
            encoding="utf-8",
        )

    def library_rows(self):
        with app.database_connection() as connection:
            return connection.execute("SELECT * FROM library_items ORDER BY id").fetchall()

    def test_legacy_single_row_provenance_schema_migrates_to_history(self):
        legacy_path = self.output / "legacy_話者分離.json"
        with app.database_connection() as connection:
            connection.execute("DROP TABLE output_import_provenance")
            connection.execute(
                """
                CREATE TABLE output_import_provenance (
                    item_id TEXT PRIMARY KEY,
                    canonical_path TEXT NOT NULL UNIQUE,
                    content_sha256 TEXT NOT NULL DEFAULT ''
                )
                """
            )
            connection.execute(
                "INSERT INTO output_import_provenance "
                "(item_id, canonical_path, content_sha256) VALUES (?, ?, ?)",
                (
                    "legacy-item",
                    app.canonical_output_import_path(legacy_path),
                    "legacy-hash",
                ),
            )

        app.initialize_library()

        second_path = self.output / "second_話者分離.json"
        with app.database_connection() as connection:
            connection.execute(
                "INSERT INTO output_import_provenance "
                "(item_id, canonical_path, content_sha256) VALUES (?, ?, ?)",
                (
                    "legacy-item",
                    app.canonical_output_import_path(second_path),
                    "second-hash",
                ),
            )
            rows = connection.execute(
                "SELECT canonical_path, content_sha256 "
                "FROM output_import_provenance WHERE item_id = ? "
                "ORDER BY canonical_path",
                ("legacy-item",),
            ).fetchall()
            primary_key = [
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(output_import_provenance)"
                ).fetchall()
                if row["pk"]
            ]

        self.assertEqual(primary_key, ["item_id", "canonical_path"])
        self.assertEqual(len(rows), 2)
        self.assertEqual(
            {row["content_sha256"] for row in rows},
            {"legacy-hash", "second-hash"},
        )

    def test_all_renamed_json_history_is_tombstoned_after_delete(self):
        original_json = self.output / "A_話者分離.json"
        self.write_result(original_json, "original")
        app.import_existing_outputs()
        imported = self.library_rows()[0]

        def rename_source(row, source_name):
            response = self.client.put(
                f"/api/library/{row['id']}",
                json={
                    "revision_count": int(row["revision_count"]),
                    "source_name": source_name,
                    "segments": app.row_segments(row),
                    "speaker_names": {},
                },
            )
            self.assertEqual(
                response.status_code, 200, response.get_data(as_text=True)
            )
            return app.library_row(row["id"])

        renamed_b = rename_source(imported, "B.wav")
        b_json = next(
            Path(value)
            for value in json.loads(renamed_b["files_json"])
            if str(value).endswith("_話者分離.json")
        )
        renamed_c = rename_source(renamed_b, "C.wav")
        c_json = next(
            Path(value)
            for value in json.loads(renamed_c["files_json"])
            if str(value).endswith("_話者分離.json")
        )

        expected_paths = {
            app.canonical_output_import_path(path)
            for path in (original_json, b_json, c_json)
        }
        with app.database_connection() as connection:
            provenance_paths = {
                row["canonical_path"]
                for row in connection.execute(
                    "SELECT canonical_path FROM output_import_provenance "
                    "WHERE item_id = ?",
                    (imported["id"],),
                ).fetchall()
            }
        self.assertEqual(provenance_paths, expected_paths)

        app.import_existing_outputs()
        self.assertEqual(len(self.library_rows()), 1)

        deleted = self.client.delete(f"/api/library/{imported['id']}")
        self.assertEqual(
            deleted.status_code, 200, deleted.get_data(as_text=True)
        )
        app.import_existing_outputs()

        self.assertEqual(self.library_rows(), [])
        with app.database_connection() as connection:
            tombstone_paths = {
                row["canonical_path"]
                for row in connection.execute(
                    "SELECT canonical_path FROM output_import_tombstones"
                ).fetchall()
            }
        self.assertTrue(expected_paths.issubset(tombstone_paths))

    def test_import_provenance_survives_edit_and_prevents_old_source_reappearing(self):
        original_json = self.output / "session_話者分離.json"
        self.write_result(original_json, "old")
        app.import_existing_outputs()
        imported = self.library_rows()[0]
        payload = {
            "revision_count": int(imported["revision_count"]),
            "source_name": imported["source_name"],
            "segments": app.row_segments(imported),
            "speaker_names": {},
        }
        payload["segments"][0]["text"] = "edited"
        updated = self.client.put(f"/api/library/{imported['id']}", json=payload)
        self.assertEqual(updated.status_code, 200)
        self.assertNotEqual(Path(updated.get_json()["output_dir"]), self.output)

        deleted = self.client.delete(f"/api/library/{imported['id']}")
        self.assertEqual(deleted.status_code, 200)
        app.import_existing_outputs()

        self.assertEqual(self.library_rows(), [])
        with app.database_connection() as connection:
            tombstoned = {
                row["canonical_path"]
                for row in connection.execute(
                    "SELECT canonical_path FROM output_import_tombstones"
                ).fetchall()
            }
        self.assertIn(app.canonical_output_import_path(original_json), tombstoned)

    def test_prefix_sibling_json_is_not_owned_or_tombstoned_by_first_result(self):
        first_json = self.output / "session_話者分離.json"
        sibling_json = self.output / "session_copy_話者分離.json"
        self.write_result(first_json, "first")
        sibling_json.write_text("{broken", encoding="utf-8")
        app.import_existing_outputs()
        first = self.library_rows()[0]
        self.assertNotIn(str(sibling_json), json.loads(first["files_json"]))

        self.write_result(sibling_json, "second")
        app.import_existing_outputs()
        rows = self.library_rows()
        self.assertEqual(len(rows), 2)
        first = next(row for row in rows if app.row_segments(row)[0]["text"] == "first")
        deleted = self.client.delete(f"/api/library/{first['id']}")
        self.assertEqual(deleted.status_code, 200)

        with app.database_connection() as connection:
            tombstoned = {
                row["canonical_path"]
                for row in connection.execute(
                    "SELECT canonical_path FROM output_import_tombstones"
                ).fetchall()
            }
        self.assertIn(app.canonical_output_import_path(first_json), tombstoned)
        self.assertNotIn(app.canonical_output_import_path(sibling_json), tombstoned)
        self.assertEqual(len(self.library_rows()), 1)

    def test_changed_content_at_a_tombstoned_path_can_be_imported_again(self):
        result_json = self.output / "replaceable_話者分離.json"
        self.write_result(result_json, "old")
        app.import_existing_outputs()
        imported = self.library_rows()[0]
        self.assertEqual(
            self.client.delete(f"/api/library/{imported['id']}").status_code,
            200,
        )

        self.write_result(result_json, "entirely new content")
        app.import_existing_outputs()
        rows = self.library_rows()
        self.assertEqual(len(rows), 1)
        self.assertEqual(app.row_segments(rows[0])[0]["text"], "entirely new content")

    def test_provenance_is_tombstoned_even_if_default_output_setting_changes(self):
        result_json = self.output / "moved-default_話者分離.json"
        self.write_result(result_json, "old")
        app.import_existing_outputs()
        imported = self.library_rows()[0]
        other_default = self.root / "other-output"
        other_default.mkdir()
        app.DEFAULT_OUTPUT_DIRECTORY = other_default
        self.assertEqual(
            self.client.delete(f"/api/library/{imported['id']}").status_code,
            200,
        )

        app.DEFAULT_OUTPUT_DIRECTORY = self.output
        app.import_existing_outputs()
        self.assertEqual(self.library_rows(), [])

    def test_legacy_path_id_and_broad_files_are_migrated_before_delete(self):
        first_json = self.output / "legacy_話者分離.json"
        sibling_json = self.output / "legacy_copy_話者分離.json"
        self.write_result(first_json, "legacy")
        self.write_result(sibling_json, "sibling")
        legacy_id = app.uuid.uuid5(
            app.uuid.NAMESPACE_URL,
            str(first_json.resolve()),
        ).hex
        app.upsert_library_item(
            item_id=legacy_id,
            source_name="legacy.wav",
            output_dir=self.output,
            media_path=None,
            language="ja",
            segments=[{
                "id": "segment-1", "start": 0.0, "end": 1.0,
                "speaker": "S1", "text": "legacy",
            }],
            speaker_names={},
            outline=None,
            emotion_analysis=None,
            files=[first_json, sibling_json],
            write_srt=False,
            write_json=True,
        )

        app.initialize_library()
        migrated = app.library_row(legacy_id)
        self.assertEqual(json.loads(migrated["files_json"]), [str(first_json)])
        with app.database_connection() as connection:
            provenance = connection.execute(
                "SELECT canonical_path FROM output_import_provenance WHERE item_id = ?",
                (legacy_id,),
            ).fetchone()
        self.assertEqual(
            provenance["canonical_path"],
            app.canonical_output_import_path(first_json),
        )

        self.assertEqual(self.client.delete(f"/api/library/{legacy_id}").status_code, 200)
        sibling_json.unlink()
        app.import_existing_outputs()
        self.assertEqual(self.library_rows(), [])

    def test_missing_provenance_file_at_delete_is_suppressed_when_it_returns(self):
        result_json = self.output / "temporarily-missing_話者分離.json"
        hidden_json = self.output / "temporarily-missing.backup"
        self.write_result(result_json, "old")
        app.import_existing_outputs()
        imported = self.library_rows()[0]
        os.replace(result_json, hidden_json)
        self.assertEqual(
            self.client.delete(f"/api/library/{imported['id']}").status_code,
            200,
        )
        os.replace(hidden_json, result_json)

        app.import_existing_outputs()
        self.assertEqual(self.library_rows(), [])


class JobLifecycleTests(unittest.TestCase):
    def setUp(self):
        with app.jobs_lock:
            app.jobs.clear()
            app._job_admission_id = None

    def tearDown(self):
        with app.jobs_lock:
            app.jobs.clear()
            app._job_admission_id = None

    def test_admission_is_visible_by_submission_id_and_active_lookup(self):
        submission_id = "a" * 32
        with app.jobs_lock:
            app._job_admission_id = submission_id

        client = app.app.test_client()
        exact = client.get(f"/api/jobs/{submission_id}")
        active = client.get("/api/jobs/active")
        duplicate = client.post(
            "/api/jobs",
            headers={"X-Gurumoji-Submission-Id": submission_id},
        )

        self.assertEqual(exact.status_code, 202)
        self.assertEqual(exact.get_json()["id"], submission_id)
        self.assertEqual(exact.get_json()["status"], "admitting")
        self.assertEqual(active.status_code, 200)
        self.assertEqual(active.get_json()["job"]["id"], submission_id)
        self.assertEqual(active.get_json()["job"]["status"], "admitting")
        self.assertEqual(duplicate.status_code, 202)
        self.assertEqual(duplicate.get_json()["id"], submission_id)
        self.assertEqual(duplicate.get_json()["status"], "admitting")

    @staticmethod
    def job(job_id: str, status: str = "queued") -> app.JobRecord:
        return app.JobRecord(
            id=job_id,
            source_name="sample.wav",
            output_dir=Path("output") / job_id,
            write_srt=False,
            write_json=True,
            status=status,
        )

    def test_active_route_and_terminal_eviction(self):
        active = self.job("active-job")
        with app.jobs_lock:
            app.jobs[active.id] = active
        response = app.app.test_client().get("/api/jobs/active")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["job"]["id"], active.id)

        finished = self.job("finished-job", "completed")
        finished.finished_at = 10.0
        with app.jobs_lock, patch.object(app, "JOB_TTL_SECONDS", 60):
            app.jobs.clear()
            app.jobs[finished.id] = finished
            app.prune_jobs_locked(now=71.0)
            self.assertNotIn(finished.id, app.jobs)

    def test_committing_job_is_active_but_cannot_be_cancelled(self):
        committing = self.job("committing-job", "committing")
        with app.jobs_lock:
            app.jobs[committing.id] = committing

        client = app.app.test_client()
        active = client.get("/api/jobs/active")
        self.assertEqual(active.status_code, 200)
        self.assertEqual(active.get_json()["job"]["id"], committing.id)

        cancel = client.post(f"/api/jobs/{committing.id}/cancel")
        self.assertEqual(cancel.status_code, 409)
        self.assertFalse(committing.cancel_event.is_set())

        competing = client.post("/api/jobs")
        self.assertEqual(competing.status_code, 409)

    def test_submission_id_is_validated_and_reuses_existing_job(self):
        client = app.app.test_client()
        invalid = client.post(
            "/api/jobs", headers={"X-Gurumoji-Submission-Id": "not-a-job-id"}
        )
        self.assertEqual(invalid.status_code, 400)

        submission_id = "d" * 32
        existing = self.job(submission_id, "queued")
        with app.jobs_lock:
            app.jobs[submission_id] = existing
        retried = client.post(
            "/api/jobs", headers={"X-Gurumoji-Submission-Id": submission_id}
        )
        self.assertEqual(retried.status_code, 202)
        self.assertEqual(retried.get_json()["id"], submission_id)

    def test_completed_job_files_use_library_download_route(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-job-files-") as temporary:
            output = Path(temporary)
            transcript = output / "transcript.json"
            transcript.write_text("{}", encoding="utf-8")
            job = self.job("e" * 32, "completed")
            job.output_dir = output
            job.files = [transcript]
            payload = job.public()
        self.assertEqual(
            payload["files"][0]["url"],
            f"/api/library/{job.id}/files/transcript.json",
        )

    def test_orphan_cleanup_preserves_recent_uuid_directory(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-orphans-") as temporary:
            upload_root = Path(temporary)
            recent = upload_root / ("a" * 32)
            old = upload_root / ("b" * 32)
            active_old = upload_root / ("c" * 32)
            recent.mkdir()
            old.mkdir()
            active_old.mkdir()
            now = time.time()
            os.utime(old, (now - 3600, now - 3600))
            os.utime(active_old, (now - 3600, now - 3600))
            with app.jobs_lock:
                app.jobs[active_old.name] = self.job(active_old.name, "committing")
            with (
                patch.object(app, "UPLOAD_DIRECTORY", upload_root),
                patch.object(app, "ORPHAN_UPLOAD_GRACE_SECONDS", 60),
                patch("app.time.time", return_value=now),
            ):
                app.cleanup_orphaned_uploads()
            self.assertTrue(recent.is_dir())
            self.assertFalse(old.exists())
            self.assertTrue(active_old.is_dir())

    def test_instance_lock_rejects_a_second_process(self):
        app.release_instance_lock()
        with tempfile.TemporaryDirectory(prefix="gurumoji-instance-lock-") as temporary:
            lock_path = Path(temporary) / "instance.lock"
            code = (
                "import sys; from pathlib import Path; import app; "
                "app.INSTANCE_LOCK_FILE=Path(sys.argv[1]); "
                "app.DATA_INSTANCE_LOCK_FILE=Path(sys.argv[1]); "
                "print(int(app.acquire_instance_lock()), flush=True); "
                "sys.stdin.readline(); app.release_instance_lock()"
            )
            child = subprocess.Popen(
                [sys.executable, "-c", code, str(lock_path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            try:
                self.assertEqual(child.stdout.readline().strip(), "1")
                with (
                    patch.object(app, "INSTANCE_LOCK_FILE", lock_path),
                    patch.object(app, "DATA_INSTANCE_LOCK_FILE", lock_path),
                ):
                    self.assertFalse(app.acquire_instance_lock())
            finally:
                if child.stdin:
                    child.stdin.write("\n")
                    child.stdin.flush()
                child.communicate(timeout=5)
                app.release_instance_lock()

    def test_worker_records_terminal_time_when_it_finishes(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-finished-at-") as temporary:
            root = Path(temporary)
            job = self.job("failed-worker")
            options = app.JobOptions(
                input_path=root / "input.wav",
                work_dir=root / "work",
                source_name="input.wav",
                output_dir=root / "output",
                model_name="tiny",
                language="ja",
                hf_token="hf_test",
                audio_preprocess="none",
                min_speakers=None,
                max_speakers=None,
                device="cpu",
                diarization_device="cpu",
                triple_pass=False,
                boost_quiet_speech=False,
                vad_onset=0.5,
                vad_offset=0.363,
                no_speech_threshold=0.6,
                write_srt=False,
                write_json=True,
                burn_subtitled_video=False,
                ai_provider="none",
                clean_transcript=False,
                detect_speaker_names=False,
                create_outline=False,
                emotion_analysis=False,
                emotion_model="kushinada",
            )
            started = time.time()
            with patch("app.shutil.which", return_value=None):
                app.run_transcription_job(job, options)
            self.assertEqual(job.status, "failed")
            self.assertIsNotNone(job.finished_at)
            self.assertGreaterEqual(job.finished_at, started)

    def test_failed_worker_removes_its_reserved_output_and_media(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-worker-rollback-") as temporary:
            root = Path(temporary)
            job_id = "f" * 32
            upload_root = root / "uploads"
            work_dir = upload_root / job_id
            output_dir = root / f"output_{job_id[:8]}"
            media_root = root / "media"
            media_dir = media_root / job_id
            work_dir.mkdir(parents=True)
            output_dir.mkdir()
            media_dir.mkdir(parents=True)
            (output_dir / "partial.json").write_text("partial", encoding="utf-8")
            (media_dir / "partial.wav").write_bytes(b"partial")
            input_path = work_dir / "input.wav"
            input_path.write_bytes(b"RIFF")
            job = self.job(job_id)
            job.output_dir = output_dir
            options = app.JobOptions(
                input_path=input_path,
                work_dir=work_dir,
                source_name="input.wav",
                output_dir=output_dir,
                model_name="tiny",
                language="ja",
                hf_token="hf_test",
                audio_preprocess="none",
                min_speakers=None,
                max_speakers=None,
                device="cpu",
                diarization_device="cpu",
                triple_pass=False,
                boost_quiet_speech=False,
                vad_onset=0.5,
                vad_offset=0.363,
                no_speech_threshold=0.6,
                write_srt=False,
                write_json=True,
                burn_subtitled_video=False,
                ai_provider="none",
                clean_transcript=False,
                detect_speaker_names=False,
                create_outline=False,
                emotion_analysis=False,
                emotion_model="kushinada",
                owns_output_dir=True,
            )
            with (
                patch.object(app, "UPLOAD_DIRECTORY", upload_root),
                patch.object(app, "MEDIA_DIRECTORY", media_root),
                patch.object(app, "library_row", return_value=None),
                patch("app.shutil.which", return_value=None),
            ):
                app.run_transcription_job(job, options)
            self.assertEqual(job.status, "failed")
            self.assertFalse(output_dir.exists())
            self.assertFalse(media_dir.exists())
            self.assertFalse(work_dir.exists())

    def test_job_admission_is_atomic_while_first_request_is_preparing(self):
        entered = threading.Event()
        release = threading.Event()
        responses = []
        original = app.app.view_functions["create_job"]

        def slow_create():
            entered.set()
            release.wait(3)
            return app.jsonify({"ok": True})

        app.app.view_functions["create_job"] = slow_create
        try:
            thread = threading.Thread(
                target=lambda: responses.append(app.app.test_client().post("/api/jobs"))
            )
            thread.start()
            self.assertTrue(entered.wait(2))
            competing = app.app.test_client().post("/api/jobs")
            self.assertEqual(competing.status_code, 409)
            release.set()
            thread.join(3)
            self.assertFalse(thread.is_alive())
            self.assertEqual(responses[0].status_code, 200)
            self.assertIsNone(app._job_admission_id)
        finally:
            release.set()
            app.app.view_functions["create_job"] = original

    def test_thread_start_failure_removes_job_and_upload_directory(self):
        with tempfile.TemporaryDirectory(prefix="gurumoji-job-start-") as temporary:
            root = Path(temporary)
            upload_root = root / "uploads"
            with (
                patch.object(app, "UPLOAD_DIRECTORY", upload_root),
                patch.object(app, "load_token_config", return_value=app.TokenConfig(huggingface_token="hf_test")),
                patch.object(app, "get_machine_profile", return_value={"gpu": {"cuda_available": False}}),
                patch.object(threading.Thread, "start", side_effect=RuntimeError("start failed")),
            ):
                response = app.app.test_client().post(
                    "/api/jobs",
                    data={
                        "input_file": (io.BytesIO(b"RIFFtest"), "meeting.wav"),
                        "output_dir": str(root / "output"),
                        "model_name": "tiny",
                        "language": "ja",
                        "device": "cpu",
                        "diarization_device": "cpu",
                        "audio_preprocess": "none",
                    },
                    content_type="multipart/form-data",
                )
            self.assertEqual(response.status_code, 500)
            self.assertEqual(app.jobs, {})
            self.assertEqual(list(upload_root.glob("*")), [])
            self.assertEqual(list((root / "output").glob("*")), [])


class TranscriptCasTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="gurumoji-cas-")
        self.root = Path(self.temporary.name)
        self.original_database = app.DATABASE_FILE
        app.DATABASE_FILE = self.root / "library.sqlite3"
        app.initialize_library()
        self.client = app.app.test_client()
        self.item_id = "cas-item"
        app.upsert_library_item(
            item_id=self.item_id,
            source_name="meeting.wav",
            output_dir=self.root / "output",
            media_path=None,
            language="ja",
            segments=[{"id": "s1", "start": 0.0, "end": 1.0, "speaker": "S1", "text": "hello"}],
            speaker_names={"S1": "Speaker"},
            outline=None,
            emotion_analysis=None,
            files=[],
            write_srt=False,
            write_json=True,
        )

    def tearDown(self):
        app.DATABASE_FILE = self.original_database
        with app.jobs_lock:
            app.jobs.clear()
        self.temporary.cleanup()

    def payload(self):
        row = app.library_row(self.item_id)
        return {
            "revision_count": int(row["revision_count"]),
            "source_name": "meeting.wav",
            "segments": app.row_segments(row),
            "speaker_names": {"S1": "Speaker"},
        }

    def test_stale_transcript_update_returns_409_without_overwriting(self):
        payload = self.payload()
        first = self.client.put(f"/api/library/{self.item_id}", json=payload)
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.get_json()["revision_count"], 1)

        stale = self.client.put(f"/api/library/{self.item_id}", json=payload)
        self.assertEqual(stale.status_code, 409)
        self.assertTrue(stale.get_json()["conflict"])
        self.assertEqual(stale.get_json()["current_revision"], 1)

        missing = dict(self.payload())
        missing.pop("revision_count")
        rejected = self.client.put(f"/api/library/{self.item_id}", json=missing)
        self.assertEqual(rejected.status_code, 400)

    def test_upsert_reads_back_inside_its_transaction(self):
        item_id = "transaction-readback"
        with patch.object(app, "library_row", side_effect=AssertionError("external readback")):
            row = app.upsert_library_item(
                item_id=item_id,
                source_name="atomic.wav",
                output_dir=self.root / "atomic-output",
                media_path=None,
                language="ja",
                segments=[
                    {"id": "s1", "start": 0.0, "end": 1.0, "speaker": "S1", "text": "ok"}
                ],
                speaker_names={"S1": "Speaker"},
                outline=None,
                emotion_analysis=None,
                files=[],
                write_srt=False,
                write_json=True,
            )
        self.assertEqual(row["id"], item_id)

    def test_database_failure_rolls_back_promoted_files_and_skips_training(self):
        first = self.client.put(f"/api/library/{self.item_id}", json=self.payload())
        self.assertEqual(first.status_code, 200)
        stored = app.library_row(self.item_id)
        final_files = [Path(value) for value in json.loads(stored["files_json"])]
        self.assertTrue(final_files)
        self.assertTrue(all(path.is_file() for path in final_files))
        self.assertTrue(all(".edit-staging-" not in str(path) for path in final_files))
        previous = {path: path.read_bytes() for path in final_files}

        changed = self.payload()
        changed["segments"][0]["text"] = "changed after staging"
        with (
            patch.object(app, "upsert_library_item", side_effect=sqlite3.OperationalError("db failed")),
            patch.object(app, "record_training_corrections") as training,
        ):
            failed = self.client.put(f"/api/library/{self.item_id}", json=changed)

        self.assertEqual(failed.status_code, 500)
        training.assert_not_called()
        self.assertEqual(int(app.library_row(self.item_id)["revision_count"]), 1)
        for path, content in previous.items():
            self.assertEqual(path.read_bytes(), content)
        output_dir = Path(stored["output_dir"])
        self.assertEqual(list(output_dir.glob(".edit-staging-*")), [])

    def test_training_insert_failure_rolls_back_transcript_and_retry_keeps_correction(self):
        first = self.client.put(f"/api/library/{self.item_id}", json=self.payload())
        self.assertEqual(first.status_code, 200)
        stored = app.library_row(self.item_id)
        final_files = [Path(value) for value in json.loads(stored["files_json"])]
        previous_files = {path: path.read_bytes() for path in final_files}
        changed = self.payload()
        changed["segments"][0]["text"] = "correction that must be learned"

        with patch.object(
            app,
            "insert_training_events",
            side_effect=sqlite3.OperationalError("training insert failed"),
        ):
            failed = self.client.put(f"/api/library/{self.item_id}", json=changed)

        self.assertEqual(failed.status_code, 500)
        rolled_back = app.library_row(self.item_id)
        self.assertEqual(int(rolled_back["revision_count"]), 1)
        self.assertEqual(app.row_segments(rolled_back)[0]["text"], "hello")
        for path, content in previous_files.items():
            self.assertEqual(path.read_bytes(), content)
        with app.database_connection() as connection:
            self.assertEqual(
                connection.execute("SELECT COUNT(*) FROM training_events").fetchone()[0],
                0,
            )

        training = self.root / "training"
        with (
            patch.object(app, "TRAINING_DIRECTORY", training),
            patch.object(app, "TRAINING_AUDIO_DIRECTORY", training / "audio"),
            patch.object(app, "TRAINING_JSONL_FILE", training / "corrections.jsonl"),
            patch.object(app, "TRAINING_MANIFEST_FILE", training / "manifest.csv"),
        ):
            retried = self.client.put(f"/api/library/{self.item_id}", json=changed)

        self.assertEqual(retried.status_code, 200)
        self.assertEqual(retried.get_json()["learning_events"], 1)
        committed = app.library_row(self.item_id)
        self.assertEqual(int(committed["revision_count"]), 2)
        self.assertEqual(
            app.row_segments(committed)[0]["text"],
            "correction that must be learned",
        )
        with app.database_connection() as connection:
            events = app.training_events_from_connection(connection)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["after"]["text"], "correction that must be learned")

    def test_training_export_failure_does_not_hide_committed_canonical_event(self):
        changed = self.payload()
        changed["segments"][0]["text"] = "saved in canonical database"
        training = self.root / "training-export-repair"
        with (
            patch.object(app, "TRAINING_DIRECTORY", training),
            patch.object(app, "TRAINING_AUDIO_DIRECTORY", training / "audio"),
            patch.object(app, "TRAINING_JSONL_FILE", training / "corrections.jsonl"),
            patch.object(app, "TRAINING_MANIFEST_FILE", training / "manifest.csv"),
        ):
            with patch.object(app, "write_training_exports", side_effect=OSError("disk full")):
                response = self.client.put(f"/api/library/{self.item_id}", json=changed)

            status = self.client.get("/api/training")
            jsonl_download = self.client.get("/api/training/corrections.jsonl")
            manifest_download = self.client.get("/api/training/manifest.csv")

        self.assertEqual(response.status_code, 200)
        self.assertIn("派生ファイル", response.get_json()["learning_warning"])
        self.assertEqual(status.status_code, 200)
        self.assertEqual(status.get_json()["jsonl_url"], "/api/training/corrections.jsonl")
        self.assertEqual(status.get_json()["manifest_url"], "/api/training/manifest.csv")
        self.assertEqual(jsonl_download.status_code, 200)
        self.assertEqual(manifest_download.status_code, 200)
        stored = app.library_row(self.item_id)
        self.assertEqual(int(stored["revision_count"]), 1)
        self.assertEqual(app.row_segments(stored)[0]["text"], "saved in canonical database")
        with app.database_connection() as connection:
            events = app.training_events_from_connection(connection)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["after"]["text"], "saved in canonical database")

    def test_source_name_control_characters_are_rejected(self):
        payload = self.payload()
        payload["source_name"] = "bad\nname.wav"
        response = self.client.put(f"/api/library/{self.item_id}", json=payload)
        self.assertEqual(response.status_code, 400)

    def test_delete_restores_media_and_thumbnail_when_database_delete_fails(self):
        media_root = self.root / "media"
        thumbnail_root = self.root / "thumbnails"
        media_dir = media_root / self.item_id
        media_dir.mkdir(parents=True)
        media_file = media_dir / "meeting.wav"
        media_file.write_bytes(b"media")
        thumbnail_root.mkdir(parents=True)
        thumbnail = thumbnail_root / f"word_cloud_{self.item_id}.svg"
        thumbnail.write_text("thumbnail", encoding="utf-8")
        row = app.library_row(self.item_id)

        @contextmanager
        def failing_connection():
            raise sqlite3.OperationalError("delete failed")
            yield

        with (
            patch.object(app, "MEDIA_DIRECTORY", media_root),
            patch.object(app, "THUMBNAIL_DIRECTORY", thumbnail_root),
            patch.object(app, "library_row", return_value=row),
            patch.object(app, "database_connection", failing_connection),
        ):
            response = self.client.delete(f"/api/library/{self.item_id}")

        self.assertEqual(response.status_code, 500)
        self.assertEqual(media_file.read_bytes(), b"media")
        self.assertEqual(thumbnail.read_text(encoding="utf-8"), "thumbnail")
        self.assertEqual(list(media_root.glob(".delete-staging-*")), [])
        self.assertEqual(list(thumbnail_root.glob(".delete-staging-*")), [])

    def test_delete_retains_quarantine_when_restore_fails(self):
        media_root = self.root / "media"
        thumbnail_root = self.root / "thumbnails"
        media_dir = media_root / self.item_id
        media_dir.mkdir(parents=True)
        media_file = media_dir / "meeting.wav"
        media_file.write_bytes(b"media")
        thumbnail_root.mkdir(parents=True)
        row = app.library_row(self.item_id)
        real_replace = os.replace

        @contextmanager
        def failing_connection():
            raise sqlite3.OperationalError("delete failed")
            yield

        def fail_restore(source, destination):
            if ".delete-staging-" in str(source):
                raise OSError("restore failed")
            return real_replace(source, destination)

        with (
            patch.object(app, "MEDIA_DIRECTORY", media_root),
            patch.object(app, "THUMBNAIL_DIRECTORY", thumbnail_root),
            patch.object(app, "library_row", return_value=row),
            patch.object(app, "database_connection", failing_connection),
            patch.object(app.os, "replace", side_effect=fail_restore),
        ):
            response = self.client.delete(f"/api/library/{self.item_id}")

        self.assertEqual(response.status_code, 500)
        payload = response.get_json()
        self.assertTrue(payload["restore_errors"])
        self.assertEqual(len(payload["recovery_paths"]), 1)
        recovery_root = Path(payload["recovery_paths"][0])
        self.assertTrue((recovery_root / self.item_id / "meeting.wav").is_file())
        self.assertIsNotNone(app.library_row(self.item_id))

    def test_delete_reports_quarantine_cleanup_failure_after_database_delete(self):
        media_root = self.root / "media"
        thumbnail_root = self.root / "thumbnails"
        media_dir = media_root / self.item_id
        media_dir.mkdir(parents=True)
        (media_dir / "meeting.wav").write_bytes(b"media")
        thumbnail_root.mkdir(parents=True)
        real_rmtree = shutil.rmtree

        def fail_quarantine_cleanup(path, *args, **kwargs):
            if ".delete-staging-" in str(path):
                raise OSError("file is locked")
            return real_rmtree(path, *args, **kwargs)

        with (
            patch.object(app, "MEDIA_DIRECTORY", media_root),
            patch.object(app, "THUMBNAIL_DIRECTORY", thumbnail_root),
            patch.object(app.shutil, "rmtree", side_effect=fail_quarantine_cleanup),
        ):
            response = self.client.delete(f"/api/library/{self.item_id}")

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["cleanup_warning"])
        self.assertEqual(len(payload["recovery_paths"]), 1)
        self.assertTrue(Path(payload["recovery_paths"][0]).is_dir())
        self.assertIsNone(app.library_row(self.item_id))

    def test_startup_recovers_delete_quarantine_when_database_row_remains(self):
        media_root = self.root / "media"
        thumbnail_root = self.root / "thumbnails"
        nonce = "a" * 32
        quarantined_media = media_root / f".delete-staging-{nonce}" / self.item_id
        quarantined_media.mkdir(parents=True)
        (quarantined_media / "meeting.wav").write_bytes(b"media")
        quarantined_thumbnail = (
            thumbnail_root
            / f".delete-staging-{nonce}"
            / f"word_cloud_{self.item_id}.svg"
        )
        quarantined_thumbnail.parent.mkdir(parents=True)
        quarantined_thumbnail.write_text("thumbnail", encoding="utf-8")

        with (
            patch.object(app, "MEDIA_DIRECTORY", media_root),
            patch.object(app, "THUMBNAIL_DIRECTORY", thumbnail_root),
        ):
            warnings = app.recover_delete_quarantines()

        self.assertEqual(warnings, [])
        self.assertEqual(
            (media_root / self.item_id / "meeting.wav").read_bytes(),
            b"media",
        )
        self.assertEqual(
            (thumbnail_root / f"word_cloud_{self.item_id}.svg").read_text(encoding="utf-8"),
            "thumbnail",
        )
        self.assertEqual(list(media_root.glob(".delete-staging-*")), [])
        self.assertEqual(list(thumbnail_root.glob(".delete-staging-*")), [])

    def test_startup_finishes_delete_quarantine_when_database_row_is_gone(self):
        media_root = self.root / "media"
        thumbnail_root = self.root / "thumbnails"
        quarantine = media_root / ".delete-staging-crash" / self.item_id
        quarantine.mkdir(parents=True)
        (quarantine / "meeting.wav").write_bytes(b"media")
        with app.database_connection() as connection:
            connection.execute("DELETE FROM library_items WHERE id = ?", (self.item_id,))

        with (
            patch.object(app, "MEDIA_DIRECTORY", media_root),
            patch.object(app, "THUMBNAIL_DIRECTORY", thumbnail_root),
        ):
            warnings = app.recover_delete_quarantines()

        self.assertEqual(warnings, [])
        self.assertFalse((media_root / self.item_id).exists())
        self.assertEqual(list(media_root.glob(".delete-staging-*")), [])

    def test_existing_output_import_skips_referenced_and_intentionally_deleted_results(self):
        first = self.client.put(f"/api/library/{self.item_id}", json=self.payload())
        self.assertEqual(first.status_code, 200)
        stored = app.library_row(self.item_id)
        machine_json = next(
            Path(value)
            for value in json.loads(stored["files_json"])
            if str(value).endswith("_話者分離.json")
        )
        self.assertTrue(machine_json.is_file())

        with patch.object(app, "DEFAULT_OUTPUT_DIRECTORY", self.root):
            app.import_existing_outputs()
            with app.database_connection() as connection:
                count_while_referenced = connection.execute(
                    "SELECT COUNT(*) FROM library_items"
                ).fetchone()[0]

            deleted = self.client.delete(f"/api/library/{self.item_id}")
            self.assertEqual(deleted.status_code, 200)
            self.assertTrue(machine_json.is_file())
            app.import_existing_outputs()
            with app.database_connection() as connection:
                count_after_restart_import = connection.execute(
                    "SELECT COUNT(*) FROM library_items"
                ).fetchone()[0]
                tombstone_count = connection.execute(
                    "SELECT COUNT(*) FROM output_import_tombstones"
                ).fetchone()[0]

        self.assertEqual(count_while_referenced, 1)
        self.assertEqual(count_after_restart_import, 0)
        self.assertEqual(tombstone_count, 1)


if __name__ == "__main__":
    unittest.main()
