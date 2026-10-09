"""Isolated synthetic SQLite/Flask tests; no app runtime or researcher data."""

import copy
import io
import json
import sqlite3
import hashlib
import shutil
import subprocess
import sys
import tempfile
import time
import threading
import urllib.request
import unittest
import zipfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from werkzeug.serving import make_server

from gurumoji import transcript_preparation as preparation
from gurumoji.services.library_rows import row_segments, row_session_profile, row_speaker_profiles
from gurumoji.services.durable_files import path_is_within
from gurumoji.services.ai_data_export import (
    ExportError, ai_export_payload, preparation_export_snapshot, validate_export_request,
)
from gurumoji.services.ai_data_export_bundle import validate_ai_bundle_zip
from gurumoji.services.ai_data_export_frames import extract_frames, permitted_media
from gurumoji.web.export_routes import register_export_routes


class AIDataExportAPITests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.db = self.root / "synthetic.sqlite"
        self.on_segments = None
        with self.connection() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("""CREATE TABLE library_items (
                id TEXT PRIMARY KEY, source_name TEXT, language TEXT, segments_json TEXT,
                original_segments_json TEXT, original_segments_status TEXT,
                speaker_names_json TEXT, speaker_profiles_json TEXT, session_profile_json TEXT,
                analysis_annotations_json TEXT, media_path TEXT, outline_json TEXT,
                revision_count INTEGER, analysis_revision INTEGER)""")
            c.execute("CREATE TABLE analysis_runs (id TEXT, item_id TEXT, stale INTEGER)")
            c.execute("CREATE TABLE analysis_run_members (run_id TEXT, item_id TEXT)")
            preparation.initialize(c)
            segments = [
                {"id": "zero", "start": 0, "end": 1, "text": "  原文、こんにちは\n世界  ", "speaker": "S1"},
                {"id": "unknown", "text": "時刻不明", "speaker": "S2"},
            ]
            c.execute("INSERT INTO library_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                "sample", "合成.mp4", "ja", json.dumps(segments), json.dumps(segments),
                "initial_import", json.dumps({"S1": "名前一", "S2": "名前二"}),
                json.dumps({"S1": {"organization": "許可組織", "notes": "秘密メモ"}}),
                "{}", "{}", None, "null", 1, 0))
            row = c.execute("SELECT * FROM library_items").fetchone()
            preparation.capture(c, row, "synthetic")
        self.app = Flask(__name__)
        self.app.testing = True
        register_export_routes(
            self.app, database_connection=self.connection, library_row=lambda _: None,
            group_analysis_for_row=lambda *a, **k: {}, list_speaker_registry=lambda: [],
            meeting_minutes_export_row=lambda _: None, row_segments=self.segments,
            row_session_profile=row_session_profile, row_speaker_profiles=row_speaker_profiles,
            media_directory=lambda: self.root / "media", path_is_within=path_is_within,
        )
        self.client = self.app.test_client()

    def segments(self, row):
        if self.on_segments:
            self.on_segments()
        return row_segments(row)

    @contextmanager
    def connection(self):
        c = sqlite3.connect(self.db)
        c.row_factory = sqlite3.Row
        try:
            yield c
            c.commit()
        finally:
            c.close()

    def test_preparation_get_readonly_preserves_zero_null_and_full_versions(self):
        before = self.db.read_bytes()
        with patch.object(preparation, "capture", side_effect=AssertionError("must not capture")), \
                patch.object(preparation, "write_state", side_effect=AssertionError("must not save")):
            response = self.client.get("/api/library/sample/preparation/export.json")
        self.assertEqual(response.status_code, 200)
        value = response.get_json()
        self.assertEqual(value["rows"][0]["start"], 0)
        self.assertIsNone(value["rows"][1]["start"])
        self.assertEqual(value["rows"][0]["text"], "  原文、こんにちは\n世界  ")
        self.assertEqual(value["versions"][0]["source"]["segments"][0]["start"], 0)
        self.assertEqual(value["manifest"]["rows_sha256"], preparation.digest(value["rows"]))
        self.assertEqual(before, self.db.read_bytes())

    def test_legacy_get_does_not_initialize_missing_version(self):
        with self.connection() as c:
            c.execute("DELETE FROM transcript_versions")
        before = self.db.read_bytes()
        value = self.client.get("/api/library/sample/preparation/export.json").get_json()
        self.assertIsNone(value["input_version"])
        self.assertEqual(value["versions"], [])
        self.assertEqual(before, self.db.read_bytes())

    def test_preparation_get_uses_one_snapshot_during_concurrent_update(self):
        def edit():
            with self.connection() as c:
                c.execute("UPDATE library_items SET segments_json='[]' WHERE id='sample'")
                row = c.execute("SELECT * FROM library_items WHERE id='sample'").fetchone()
                preparation.capture(c, row, "concurrent")
                preparation.write_state(c, "sample", 1, {"source_hash": preparation.digest(preparation.source(row))})
        self.on_segments = edit
        value = self.client.get("/api/library/sample/preparation/export.json").get_json()
        self.assertEqual(len(value["rows"]), 2)
        self.assertEqual(value["input_version"], 1)
        self.assertEqual(len(value["versions"]), 1)
        self.assertEqual(value["review_history"], [])
        self.assertEqual(value["revision"], 0)

    def post(self, payload=None, item="sample"):
        return self.client.post(f"/api/library/{item}/ai-export.zip", json={} if payload is None else payload)

    def archive(self, response):
        self.assertEqual(response.status_code, 200, response.data[:500])
        self.assertEqual(response.mimetype, "application/zip")
        self.assertIn("attachment", response.headers["Content-Disposition"])
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        validate_ai_bundle_zip(response.data)
        archive = zipfile.ZipFile(io.BytesIO(response.data))
        manifest = json.loads(archive.read("manifest.json"))
        for record in manifest["files"]:
            data = archive.read(record["path"])
            self.assertEqual(hashlib.sha256(data).hexdigest(), record["sha256"])
            self.assertEqual(len(data), record["size"])
        return archive

    def test_normal_zip_names_excluded_one_attribute_zero_null_readonly(self):
        before = self.db.read_bytes()
        with patch("gurumoji.web.export_routes.extract_frames", side_effect=AssertionError("disabled must not read media")):
            response = self.post({"speaker_attributes": ["organization"]})
        archive = self.archive(response)
        conversation = json.loads(archive.read("conversation.json"))
        prepared = conversation["preparation"]
        self.assertEqual([r["start"] for r in prepared["rows"]], [0, None])
        self.assertEqual(prepared["input_version"], 1)
        self.assertEqual(prepared["manifest"]["rows_sha256"], preparation.digest([
            {k: r[k] for k in preparation.FIELDS} for r in prepared["rows"]]))
        self.assertNotIn("speaker_names", prepared["versions"][0]["source"])
        self.assertNotIn("秘密メモ", archive.read("conversation.json").decode("utf-8"))
        profile = prepared["versions"][0]["source"]["speaker_profiles"]["S1"]
        self.assertEqual(profile, {"speaker_label": "S1", "organization": "許可組織"})
        speakers = json.loads(archive.read("speakers.json"))
        self.assertEqual(speakers[0]["display_name"], None)
        self.assertEqual(speakers[0]["attributes"], {"organization": "許可組織"})
        self.assertEqual(json.loads(archive.read("outline.json"))["outline"], None)
        self.assertEqual(before, self.db.read_bytes())
        self.assertEqual(response.data, self.post({"speaker_attributes": ["organization"]}).data)

    def test_normal_zip_unicode_edited_lineage_and_saved_outline(self):
        with self.connection() as c:
            segments = [{"id": "edited", "speaker": "S1", "start": 0, "end": 1,
                         "text": "  修正済み 🌸\n逐語録  ", "private_path": "C:/secret"},
                        {"id": "unknown", "speaker": "UNKNOWN", "text": "欠測"}]
            c.execute("UPDATE library_items SET segments_json=?, outline_json=? WHERE id='sample'",
                      (json.dumps(segments), json.dumps({"summary": "保存済み概要", "provenance": "未認定"})))
            row = c.execute("SELECT * FROM library_items").fetchone()
            preparation.capture(c, row, "synthetic_edit")
            preparation.write_state(c, "sample", 1, {"source_hash": preparation.digest(preparation.source(row)),
                "records": {"edited": {"source_segment_ids": ["zero"], "source_locator": "合成:行一",
                    "text_status": "transcript_checked", "boundary_verified": True}}, "confirmed": False})
        response = self.post({"include_names": True})
        archive = self.archive(response)
        prepared = json.loads(archive.read("conversation.json"))["preparation"]
        self.assertEqual(prepared["rows"][0]["text"], "  修正済み 🌸\n逐語録  ")
        self.assertEqual(prepared["rows"][0]["source_segment_ids"], ["zero"])
        self.assertIsNone(prepared["rows"][0]["original_text"])
        self.assertEqual(prepared["original_segments"][0]["text"], "  原文、こんにちは\n世界  ")
        self.assertEqual(prepared["input_version"], 2)
        self.assertEqual(len(prepared["versions"]), 2)
        self.assertNotIn("private_path", prepared["versions"][1]["source"]["segments"][0])
        self.assertEqual(prepared["rows"][1]["raw_speaker_label"], "UNKNOWN")
        self.assertIsNone(prepared["rows"][1]["speaker_id"])
        self.assertIsInstance(prepared["rows"][1]["speaker_no"], int)
        self.assertEqual(json.loads(archive.read("outline.json"))["provenance"]["kind"], "saved")

    def test_bad_requests_rejected_before_snapshot_or_media(self):
        cases = [[], {"path": "C:/secret.mp4"}, {"url": "https://example.invalid"},
                 {"include_names": 1}, {"speaker_attributes": ["notes"]},
                 {"speaker_attributes": ["organization", "organization"]}, {"expected_revision": True},
                 {"frames": {"enabled": False, "start": 0}}, {"frames": {"enabled": True}},
                 {"frames": {"enabled": True, "start": 0, "end": 24, "interval": 1}},
                 {"frames": {"enabled": True, "start": 0, "end": 601, "interval": 100}},
                 {"frames": {"enabled": True, "start": 0, "end": 1, "interval": .5}},
                 {"frames": {"enabled": True, "start": 0, "end": 1, "interval": 1, "max_dimension": 1281}},
                 {"frames": {"enabled": True, "start": float("nan"), "end": 1, "interval": 1}},
                 {"frames": {"enabled": True, "start": 0, "end": 1, "interval": True}}]
        with patch("gurumoji.web.export_routes.preparation_export_snapshot", side_effect=AssertionError("no snapshot")), \
                patch("gurumoji.web.export_routes.extract_frames", side_effect=AssertionError("no media")):
            for value in cases:
                with self.subTest(value=value):
                    self.assertEqual(self.post(value).status_code, 400)

    def test_missing_item_and_optimistic_conflicts(self):
        self.assertEqual(self.post(item="missing").status_code, 404)
        self.assertEqual(self.post({"expected_source_hash": "old"}).status_code, 409)
        self.assertEqual(self.post({"expected_revision": 8}).status_code, 409)

    def video(self):
        if not shutil.which("ffmpeg"):
            self.skipTest("ffmpeg unavailable")
        directory = self.root / "media" / "sample"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "synthetic.mp4"
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-f", "lavfi", "-i", "testsrc2=size=1600x900:rate=5", "-t", "3", "-c:v", "mpeg4", str(path)],
            check=True, timeout=15, capture_output=True)
        with self.connection() as c:
            c.execute("UPDATE library_items SET media_path=?", (str(path),))
        return path

    def frame_options(self):
        return {"frames": {"enabled": True, "start": 0, "end": 1, "interval": 1, "max_dimension": 320}}

    def test_actual_synthetic_video_jpegs_pts_and_source_unchanged(self):
        from PIL import Image
        path = self.video()
        before = (self.db.read_bytes(), path.read_bytes(), path.stat())
        archive = self.archive(self.post(self.frame_options()))
        entries = [json.loads(line) for line in archive.read("frames/index.jsonl").splitlines()]
        self.assertEqual(len(entries), 2)
        for entry in entries:
            with Image.open(io.BytesIO(archive.read(entry["path"]))) as image:
                image.load()
                self.assertEqual(image.format, "JPEG")
                self.assertLessEqual(max(image.size), 320)
            self.assertIsNotNone(entry["actual_time"])
            self.assertEqual(entry["method"], "ffmpeg_showinfo_pts")
        self.assertEqual(entries[0]["actual_time"], 0)
        self.assertEqual(entries[0]["utterance_ids"], ["zero"])
        self.assertEqual(before[0], self.db.read_bytes())
        self.assertEqual(before[1], path.read_bytes())
        self.assertEqual(before[2].st_mtime_ns, path.stat().st_mtime_ns)

    def test_frames_missing_audio_outside_path_and_no_ffmpeg(self):
        request = self.frame_options()
        self.assertEqual(self.post(request).get_json()["frames"]["reason"], "missing_media")
        outside = self.root / "outside.mp4"
        outside.write_bytes(b"synthetic")
        with self.connection() as c:
            c.execute("UPDATE library_items SET media_path=?", (str(outside),))
        self.assertEqual(self.post(request).get_json()["frames"]["reason"], "media_not_permitted")
        audio = self.root / "media" / "sample" / "synthetic.wav"
        audio.parent.mkdir(parents=True)
        audio.write_bytes(b"synthetic")
        with self.connection() as c:
            c.execute("UPDATE library_items SET media_path=?", (str(audio),))
        self.assertEqual(self.post(request).get_json()["frames"]["reason"], "audio_only")
        path = audio.with_suffix(".mp4")
        path.write_bytes(b"synthetic")
        with self.connection() as c:
            c.execute("UPDATE library_items SET media_path=?", (str(path),))
        with patch("gurumoji.services.ai_data_export_frames.shutil.which", return_value=None):
            response = self.post(request)
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["frames"]["reason"], "ffmpeg_unavailable")

    def test_frames_failure_timeout_and_cancel_are_explicit(self):
        self.video()
        with patch("gurumoji.services.ai_data_export_frames._run_bounded", return_value=(1, b"", b"")):
            response = self.post(self.frame_options())
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["frames"]["reason"], "frame_extraction_failed")
        with patch("gurumoji.services.ai_data_export_frames._run_bounded",
                   side_effect=ExportError("frame_timeout", 408, frame_status="failed")):
            self.assertEqual(self.post(self.frame_options()).status_code, 408)
        with self.connection() as c:
            row = c.execute("SELECT * FROM library_items").fetchone()
        with self.assertRaises(ExportError) as caught:
            extract_frames(row, [], validate_export_request(self.frame_options())["frames"],
                           media_directory=lambda: self.root / "media", path_is_within=path_is_within,
                           check_cancelled=lambda: (_ for _ in ()).throw(InterruptedError()))
        self.assertEqual(caught.exception.reason, "frame_cancelled")

    def test_media_root_cannot_be_widened_by_item_identifier(self):
        for item_id in ("..", ".", "../sample", "sample/..", "sample\\..", "C:", "/sample"):
            with self.subTest(item_id=item_id), self.assertRaises(ExportError) as caught:
                permitted_media({"id": item_id, "media_path": str(self.root / "synthetic.mp4")},
                    lambda: self.root / "media", path_is_within)
            self.assertEqual(caught.exception.reason, "media_not_permitted")

    def test_adapter_real_decode_before_serializer_integration(self):
        path = self.video()
        before = path.read_bytes()
        with self.connection() as c:
            row = c.execute("SELECT * FROM library_items").fetchone()
        result = extract_frames(row, [{"segment_id": "zero", "start": 0, "end": 1}],
            validate_export_request(self.frame_options())["frames"],
            media_directory=lambda: self.root / "media", path_is_within=path_is_within)
        self.assertEqual(result["status"], "complete")
        self.assertEqual([f["actual_time"] for f in result["items"]], [0, 1])
        self.assertEqual(before, path.read_bytes())

    def test_media_substitution_during_decode_returns_conflict(self):
        from gurumoji.services import ai_data_export_frames as frames
        path = self.video()
        original = frames._run_bounded
        def substitute(*args):
            result = original(*args)
            path.write_bytes(b"substituted synthetic video")
            return result
        with patch.object(frames, "_run_bounded", side_effect=substitute):
            response = self.post(self.frame_options())
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["frames"]["reason"], "media_changed")

    def test_source_changed_while_building_zip_returns_conflict(self):
        from gurumoji.services import ai_data_export_bundle as bundle
        original = bundle.build_ai_bundle
        def edit(payload):
            with self.connection() as c:
                c.execute("UPDATE library_items SET segments_json='[]'")
            return original(payload)
        with patch.object(bundle, "build_ai_bundle", side_effect=edit):
            self.assertEqual(self.post().status_code, 409)

    def test_media_changed_while_building_zip_returns_conflict(self):
        from gurumoji.services import ai_data_export_bundle as bundle
        path = self.video()
        original = bundle.build_ai_bundle
        def edit(payload):
            path.unlink()
            return original(payload)
        with patch.object(bundle, "build_ai_bundle", side_effect=edit):
            response = self.post(self.frame_options())
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["frames"]["reason"], "media_changed")

    def test_subprocess_pipe_limit_and_shared_deadline_are_enforced(self):
        from gurumoji.services.ai_data_export_frames import _run_bounded
        with self.assertRaises(ExportError) as overflow:
            _run_bounded([sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'x' * (2*1024*1024+1))"],
                         time.monotonic() + 5, None)
        self.assertEqual(overflow.exception.reason, "frame_output_limit")
        started = time.monotonic()
        with self.assertRaises(ExportError) as timeout:
            _run_bounded([sys.executable, "-c", "import time; time.sleep(5)"], started + .1, None)
        self.assertEqual(timeout.exception.status, 408)
        self.assertLess(time.monotonic() - started, 2)

    def test_actual_loopback_http_download(self):
        server = make_server("127.0.0.1", 0, self.app)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            request = urllib.request.Request(
                f"http://127.0.0.1:{server.server_port}/api/library/sample/ai-export.zip",
                data=b"{}", headers={"Content-Type": "application/json", "X-Gurumoji-Request": "1"}, method="POST")
            with urllib.request.urlopen(request, timeout=10) as response:
                self.assertEqual(response.status, 200)
                self.assertEqual(response.headers.get_content_type(), "application/zip")
                self.assertIn("attachment", response.headers["Content-Disposition"])
                data = response.read()
            validate_ai_bundle_zip(data)
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                self.assertEqual(json.loads(archive.read("manifest.json"))["item_id"], "sample")
        finally:
            server.shutdown()
            server.server_close()
            worker.join(timeout=2)

    def test_decoded_dimensions_and_aggregate_jpeg_limit(self):
        from PIL import Image
        self.video()
        with self.connection() as c:
            row = c.execute("SELECT * FROM library_items").fetchone()
        image_data = io.BytesIO()
        Image.new("RGB", (321, 1)).save(image_data, format="JPEG")
        with patch("gurumoji.services.ai_data_export_frames._run_bounded", return_value=(0, image_data.getvalue(), b"")):
            response = self.post(self.frame_options())
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["frames"]["reason"], "frame_dimensions")
        image_data = io.BytesIO()
        Image.new("RGB", (16, 16)).save(image_data, format="JPEG")
        jpeg = image_data.getvalue()
        jpeg += b"\x00" * (2 * 1024 * 1024 - len(jpeg) - 2) + b"\xff\xd9"
        with patch("gurumoji.services.ai_data_export_frames._run_bounded", return_value=(0, jpeg, b"")):
            with self.assertRaises(ExportError) as caught:
                extract_frames(row, [], {"times": list(range(24)), "max_dimension": 1280},
                               media_directory=lambda: self.root / "media", path_is_within=path_is_within)
        self.assertEqual(caught.exception.reason, "frame_total_limit")


    def test_projection_does_not_mutate_preparation_or_selection(self):
        with self.connection() as c:
            row = c.execute("SELECT * FROM library_items").fetchone()
            segments = row_segments(row)
            prepared = preparation_export_snapshot(c, row, segments)
        options = validate_export_request({"speaker_attributes": ["organization"]})
        before = copy.deepcopy((prepared, segments, options))
        payload = ai_export_payload(row, segments, prepared, options)
        self.assertEqual((prepared, segments, options), before)
        payload["selection"]["speaker_attributes"].clear()
        self.assertEqual(options["speaker_attributes"], ["organization"])
        self.assertNotIn("speaker_no", prepared["rows"][0])
        with self.assertRaises(ValueError):
            ai_export_payload(row, segments[:1], prepared, options)

    def test_all_saved_label_sources_selected_profiles_and_narrative_preserved(self):
        with self.connection() as c:
            original = [{"id": "original_only", "speaker": "Original", "text": "原保存", "path": "/private"}]
            segments = [{"id": "now", "speaker": "Current", "text": "名前は本文に残る", "start": 0, "end": 1},
                        {"id": "none", "text": "話者なし"}]
            profiles = {"Current": {"display_name": "", "organization": "", "department": "除外部門",
                                    "session_role_source": "manual", "global_speaker_id": "never-export", "notes": "private-note"},
                        "ProfileOnly": {"organization": "保存組織"}}
            c.execute("UPDATE library_items SET segments_json=?, original_segments_json=?, speaker_profiles_json=?, "
                      "speaker_names_json=?, session_profile_json=?", (json.dumps(segments), json.dumps(original), json.dumps(profiles),
                      json.dumps({"Current": "fallback-name"}), json.dumps({"note": "ユーザー本文の名前"})))
            row = c.execute("SELECT * FROM library_items").fetchone()
            preparation.capture(c, row, "synthetic_current")
        archive = self.archive(self.post({"speaker_attributes": ["organization"]}))
        speakers = json.loads(archive.read("speakers.json"))
        self.assertEqual([s["raw_label"] for s in speakers], ["Current", "Original", "ProfileOnly", "S1", "S2"])
        prepared = json.loads(archive.read("conversation.json"))["preparation"]
        self.assertIsNone(prepared["rows"][1]["speaker_no"])
        self.assertEqual(speakers[0]["attributes"], {"organization": ""})
        self.assertNotIn("path", prepared["original_segments"][0])
        text = archive.read("conversation.json").decode()
        for secret in ("fallback-name", "private-note", "never-export", "除外部門"):
            self.assertNotIn(secret, text)
        self.assertIn("ユーザー本文の名前", text)
        self.assertIn("名前は本文に残る", text)
        named = self.archive(self.post({"include_names": True, "speaker_attributes": ["session_role_source"]}))
        saved = json.loads(named.read("speakers.json"))[0]
        self.assertEqual(saved["display_name"], "")
        self.assertEqual(saved["attributes"], {"session_role_source": "manual"})

    def test_migrated_and_unavailable_original_status_remain_explicit(self):
        for status in ("migrated_current_snapshot", None):
            with self.connection() as c:
                c.execute("UPDATE library_items SET original_segments_status=?", (status,))
            value = json.loads(self.archive(self.post()).read("conversation.json"))["preparation"]
            self.assertEqual(value["original_status"], status or "unavailable")
            self.assertEqual(value["rows"][0]["original_status"], status or "unavailable")

    def test_frames_unknown_pts_never_substitutes_requested_time(self):
        from PIL import Image
        self.video()
        data = io.BytesIO()
        Image.new("RGB", (16, 16)).save(data, format="JPEG")
        with patch("gurumoji.services.ai_data_export_frames._run_bounded", return_value=(0, data.getvalue(), b"unrelated pts_time:0")):
            archive = self.archive(self.post(self.frame_options()))
        entries = [json.loads(line) for line in archive.read("frames/index.jsonl").splitlines()]
        self.assertEqual([f["requested_time"] for f in entries], [0, 1])
        self.assertTrue(all(f["actual_time"] is None and not f["utterance_ids"] and
                            f["method"] == "ffmpeg_pts_unavailable" for f in entries))

    def test_partial_extraction_is_422_and_never_downloads_a_zip(self):
        from PIL import Image
        self.video()
        data = io.BytesIO()
        Image.new("RGB", (16, 16)).save(data, format="JPEG")
        outputs = [(0, data.getvalue(), b"[Parsed_showinfo_1 @ x] n: 0 pts_time:0"), (1, b"", b"error")]
        with patch("gurumoji.services.ai_data_export_frames._run_bounded", side_effect=outputs):
            response = self.post(self.frame_options())
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["frames"]["status"], "partial")
        self.assertEqual(response.mimetype, "application/json")
        self.assertNotIn("Content-Disposition", response.headers)

    def test_subprocess_timeout_after_one_frame_is_408_without_zip(self):
        from PIL import Image
        self.video()
        data = io.BytesIO()
        Image.new("RGB", (16, 16)).save(data, format="JPEG")
        outputs = [(0, data.getvalue(), b""), ExportError("frame_timeout", 408, frame_status="failed")]
        with patch("gurumoji.services.ai_data_export_frames._run_bounded", side_effect=outputs):
            response = self.post(self.frame_options())
        self.assertEqual(response.status_code, 408)
        self.assertEqual(response.get_json()["frames"]["reason"], "frame_timeout")
        self.assertNotIn("Content-Disposition", response.headers)

    def test_expired_subprocess_budget_does_not_spawn(self):
        from gurumoji.services.ai_data_export_frames import _run_bounded
        with patch("gurumoji.services.ai_data_export_frames.subprocess.Popen", side_effect=AssertionError("must not spawn")):
            with self.assertRaises(ExportError) as caught:
                _run_bounded(["unused"], time.monotonic() - 1, None)
        self.assertEqual(caught.exception.status, 408)

    def test_symlink_cannot_escape_saved_item_media_root(self):
        outside = self.root / "outside.mp4"
        outside.write_bytes(b"synthetic")
        directory = self.root / "media" / "sample"
        directory.mkdir(parents=True)
        link = directory / "linked.mp4"
        try:
            link.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("symlink unavailable")
        with self.connection() as c:
            c.execute("UPDATE library_items SET media_path=?", (str(link),))
        response = self.post(self.frame_options())
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["frames"]["reason"], "media_not_permitted")

    def test_playlist_disguised_as_video_is_not_decoded(self):
        path = self.video()
        playlist = path.with_name("playlist.mp4")
        playlist.write_text("ffconcat version 1.0\nfile 'synthetic.mp4'\n", encoding="utf-8")
        with self.connection() as c:
            c.execute("UPDATE library_items SET media_path=?", (str(playlist),))
        response = self.post(self.frame_options())
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["frames"]["reason"], "frame_extraction_failed")
        self.assertNotIn("Content-Disposition", response.headers)

    def test_decimal_frame_grid_includes_endpoint_and_rejects_overflow(self):
        cases = [
            (0.1, 4.1, 1, [0.1, 1.1, 2.1, 3.1, 4.1]),
            (0.1, 3.4, 1.1, [0.1, 1.2, 2.3, 3.4]),
            (0.1, 3.3999999999999995, 1.1, [0.1, 1.2, 2.3]),
        ]
        for start, end, interval, expected in cases:
            request = {"frames": {"enabled": True, "start": start, "end": end, "interval": interval,
                                  "max_frames": len(expected)}}
            with self.subTest(start=start, end=end, interval=interval):
                self.assertEqual(validate_export_request(request)["frames"]["times"], expected)
                request["frames"]["max_frames"] -= 1
                with self.assertRaises(ExportError) as caught:
                    validate_export_request(request)
                self.assertEqual(caught.exception.reason, "frame_count")
                with patch("gurumoji.web.export_routes.preparation_export_snapshot", side_effect=AssertionError("no snapshot")), \
                        patch("gurumoji.web.export_routes.extract_frames", side_effect=AssertionError("no media")):
                    self.assertEqual(self.post(request).status_code, 400)
        # Decimal arithmetic does not relax the frozen >=1 second interval.
        with self.assertRaises(ExportError) as caught:
            validate_export_request({"frames": {"enabled": True, "start": 0.1, "end": 0.3, "interval": 0.1}})
        self.assertEqual(caught.exception.reason, "frame_bounds")

    def test_request_maximum_bounds_and_nonfinite_saved_data(self):
        valid = {"frames": {"enabled": True, "start": 0.1, "end": 23.1, "interval": 1, "max_frames": 24, "max_dimension": 16}}
        self.assertEqual(len(validate_export_request(valid)["frames"]["times"]), 24)
        for key, value in (("max_frames", True), ("max_frames", 25), ("max_dimension", 15), ("start", 10 ** 400), ("end", float("inf"))):
            request = copy.deepcopy(valid)
            request["frames"][key] = value
            with self.subTest(key=key), self.assertRaises(ExportError):
                validate_export_request(request)
        with self.connection() as c:
            c.execute("UPDATE library_items SET outline_json=?", ('{"invalid": NaN}',))
        response = self.post()
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["error"], "invalid_saved_export_data")


if __name__ == "__main__":
    unittest.main()
